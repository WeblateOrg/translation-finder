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
from io import StringIO
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Iterator

    from .base import DiscoveryBudget

REFERENCE = re.compile(r"%\(([^)]+)\)s")
MAX_SUBSTITUTIONS = 99
RESOURCE_KEYS = ("file_filter", "source_file", "type")


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

    def _lookup(self, section: str, key: str) -> tuple[str, str] | None:
        """Look up a key, including dotted parent sections."""
        while True:
            if section in self.sections:
                if section in self.invalid:
                    return None
                values = self.sections[section]
                if key in values:
                    return section, values[key]
            parent, separator, _ = section.rpartition(".")
            if not separator:
                return None
            section = parent

    def _resolve(self, section: str, key: str, max_bytes: int) -> str | None:
        """Resolve references without allowing expanded values to grow unbounded."""
        found = self._lookup(section, key)
        if found is None:
            return None
        owner, value = found
        for _ in range(MAX_SUBSTITUTIONS):
            if len(value.encode("utf-8")) > max_bytes:
                raise ValueError
            match = REFERENCE.search(value)
            if match is None:
                return value
            reference = match[1]
            replacement = self._lookup(owner, reference)
            if replacement is None or (replacement[0], reference) == (owner, key):
                replacement = self._lookup("DEFAULT", reference)
            if replacement is None:
                return value
            marker = match[0]
            count = value.count(marker)
            replacement_bytes = len(replacement[1].encode("utf-8"))
            expanded_bytes = len(value.encode("utf-8")) + count * (
                replacement_bytes - len(marker.encode("utf-8"))
            )
            if expanded_bytes > max_bytes:
                raise ValueError
            value = value.replace(marker, replacement[1])
        return value

    def resources(self, max_bytes: int) -> Iterator[tuple[str, dict[str, str]]]:
        """Yield resolved options used by discovery for each valid resource."""
        for section in self.sections:
            if section in {"main", "DEFAULT"} or section in self.invalid:
                continue
            values: dict[str, str] = {}
            try:
                for key in RESOURCE_KEYS:
                    value = self._resolve(section, key, max_bytes)
                    if value is not None:
                        values[key] = value
            except ValueError:
                continue
            yield section, values
