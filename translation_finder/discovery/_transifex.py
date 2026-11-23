# Copyright © Michal Čihař <michal@weblate.org>
#
# SPDX-License-Identifier: GPL-3.0-or-later

"""
Compact reader for the INI dialect used by the Transifex client.

The client uses go-ini with its default load options. Keep plain dictionaries
instead of ConfigParser section proxies, including for sections without useful
discovery options. Comments and serialization metadata are not retained.
"""

from __future__ import annotations

import re
from bisect import bisect_right
from io import StringIO
from operator import itemgetter
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Iterator

    from .base import DiscoveryBudget

MAX_SUBSTITUTIONS = 99
RESOURCE_KEYS = ("file_filter", "source_file", "type")


class InterpolationLimitError(Exception):
    """The run has insufficient work left to resolve another resource."""


class InterpolationBudget:
    """Share option resolution work across Transifex configuration files."""

    def __init__(self, remaining: int = 8 * 1024 * 1024) -> None:
        self.remaining = remaining

    def charge(self, work: int) -> None:
        if work > self.remaining:
            raise InterpolationLimitError
        self.remaining -= work


def _find_reference(value: str) -> str | None:
    """Return the first reference, scanning each span between closing delimiters once."""
    start = 0
    while (start := value.find("%(", start)) >= 0:
        end = value.find(")", start + 2)
        if end < 0:
            break
        if end > start + 2 and value.startswith("s", end + 1):
            return value[start : end + 2]
        start = end + 1
    return None


def _read_assignment(line: str) -> tuple[str, str]:
    """Split an assignment, allowing the client's quoted key names."""
    quote = next((value for value in ('"""', '"', "`") if line.startswith(value)), "")
    if quote:
        end = line.find(quote, len(quote))
        if end < 0:
            raise ValueError
        name = line[len(quote) : end].strip()
        rest = line[end + len(quote) :]
    else:
        name = ""
        rest = line
    match = re.search(r"[=:]", rest)
    if match is None:
        raise ValueError
    if not quote:
        name = rest[: match.start()].strip()
    if not name:
        raise ValueError
    return name, rest[match.end() :]


def _read_value(value: str, lines: Iterator[str]) -> str:
    """Read quoting and continuations using go-ini's default options."""
    value = value.lstrip()
    quote = next((item for item in ('"""', "`") if value.startswith(item)), "")
    if quote:
        value = value[len(quote) :]
        end = value.rfind(quote)
        if end >= 0:
            return value[:end]
        parts = [value]
        for line in lines:
            end = line.rfind(quote)
            if end >= 0:
                return "".join((*parts, line[:end]))
            parts.append(line)
        raise ValueError

    value = value.strip()
    if value.endswith("\\"):
        parts = [value[:-1]]
        for line in lines:
            following = line.strip()
            if not following:
                break
            if not following.endswith("\\"):
                parts.append(following)
                break
            parts.append(following[:-1])
        return "".join(parts)

    value = re.split(r"[#;]", value, maxsplit=1)[0].strip()
    if (
        len(value) > 1
        and value[0] in "\"'"
        and value.find(value[0], 1) == len(value) - 1
    ):
        return value[1:-1]
    return value


class TransifexConfig:
    """Read resource sections under a shared processing allowance."""

    def __init__(self, content: str, budget: DiscoveryBudget) -> None:
        self.sections: dict[str, dict[str, str]] = {"DEFAULT": {}}
        self.invalid: set[str] = set()
        section: str | None = "DEFAULT"
        automatic_key = 0
        lines = iter(StringIO(content, newline=""))
        for line in lines:
            stripped = line.lstrip()
            if not stripped.strip() or stripped.startswith(("#", ";")):
                continue
            if stripped.startswith("["):
                end = stripped.rfind("]")
                if end <= 1:
                    # A broken header starts a new block, not an error in the
                    # preceding resource. Ignore its body until a valid header.
                    section = None
                    continue
                section = stripped[1:end]
                if (
                    section not in {"main", "DEFAULT"}
                    and not budget.consume_candidate()
                ):
                    break
                self.sections.setdefault(section, {})
                automatic_key = 0
                continue
            if section is None:
                continue
            try:
                key, value = _read_assignment(stripped)
                value = _read_value(value, lines)
            except ValueError:
                self.invalid.add(section)
                continue
            if key == "-":
                automatic_key += 1
                key = f"#{automatic_key}"
            self.sections[section][key] = value
        self._position: dict[str, int] = {}
        self._inherited: dict[tuple[str | None, str], list[tuple[int, str | None]]] = {}
        self._scope: dict[str, str | None] = {}
        self._index_inheritance()

    def _index_inheritance(self) -> None:
        """Record changes in inherited options while visiting dotted subtrees."""
        # Only sections with descendants contribute inherited options. Sorting
        # the dotted prefixes separately handles names such as "a", "a!", "a.b".
        entries = [(section, True, section) for section in self.sections]
        entries.extend((f"{section}.", False, section) for section in self.sections)
        entries.sort()
        prefixes: list[tuple[str, str, dict[str, str | None]]] = []
        for position, (name, is_section, section) in enumerate(entries):
            while prefixes and not name.startswith(prefixes[-1][0]):
                _, parent, previous = prefixes.pop()
                for key, owner in previous.items():
                    binding = (self._scope[parent], key)
                    self._inherited[binding].append((position, owner))
            if is_section:
                self._position[section] = position
                self._scope[section] = (
                    self._scope[prefixes[-1][1]] if prefixes else None
                )
                if section in self.invalid:
                    self._scope[section] = section
            elif position + 1 < len(entries) and entries[position + 1][0].startswith(
                name
            ):
                previous = {}
                prefixes.append((name, section, previous))
                if section in self.invalid:
                    continue
                for key in self.sections[section]:
                    binding = (self._scope[section], key)
                    history = self._inherited.setdefault(binding, [])
                    previous[key] = history[-1][1] if history else None
                    history.append((position, section))

    def _lookup(self, section: str, key: str) -> tuple[str, str] | None:
        """Find the applicable definition without walking the parent chain."""
        if section in self.invalid:
            return None
        if key in self.sections[section]:
            return section, self.sections[section][key]
        history = self._inherited.get((self._scope[section], key))
        if history:
            index = bisect_right(history, self._position[section], key=itemgetter(0))
            if index and (owner := history[index - 1][1]) is not None:
                return owner, self.sections[owner][key]
        return None

    def _resolve(
        self, section: str, key: str, max_bytes: int, budget: InterpolationBudget
    ) -> str | None:
        """Resolve references without allowing expanded values to grow unbounded."""
        found = self._lookup(section, key)
        if found is None:
            return None
        owner, value = found
        for _ in range(MAX_SUBSTITUTIONS):
            # Account for lookup overhead even when scanning short values.
            budget.charge(64 + len(value))
            value_bytes = len(value.encode("utf-8"))
            if value_bytes > max_bytes:
                raise ValueError
            marker = _find_reference(value)
            if marker is None:
                return value
            reference = marker[2:-2]
            replacement = self._lookup(owner, reference)
            if replacement is None or (replacement[0], reference) == (owner, key):
                replacement = self._lookup("DEFAULT", reference)
            if replacement is None:
                return value
            budget.charge(len(replacement[1]))
            if replacement[1] == marker:
                return value
            count = value.count(marker)
            replacement_bytes = len(replacement[1].encode("utf-8"))
            expanded_bytes = value_bytes + count * (
                replacement_bytes - len(marker.encode("utf-8"))
            )
            if expanded_bytes > max_bytes:
                raise ValueError
            budget.charge(len(value) + count * (len(replacement[1]) - len(marker)))
            value = value.replace(marker, replacement[1])
        return value

    def resources(
        self, max_bytes: int, budget: InterpolationBudget
    ) -> Iterator[tuple[str, dict[str, str]]]:
        """Yield resolved options used by discovery for each valid resource."""
        for section in self.sections:
            if section in {"main", "DEFAULT"} or section in self.invalid:
                continue
            values: dict[str, str] = {}
            try:
                for key in RESOURCE_KEYS:
                    value = self._resolve(section, key, max_bytes, budget)
                    if value is not None:
                        values[key] = value
            except ValueError:
                continue
            yield section, values
