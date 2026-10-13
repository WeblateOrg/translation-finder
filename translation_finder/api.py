# Copyright © Michal Čihař <michal@weblate.org>
#
# SPDX-License-Identifier: GPL-3.0-or-later

"""Highlevel API for translation-finder."""

from __future__ import annotations

import sys
import warnings
from argparse import ArgumentParser, ArgumentTypeError
from pathlib import Path
from typing import TYPE_CHECKING, TextIO, TypeVar

from translation_finder.discovery.base import (
    DISCOVERY_MAX_CANDIDATES,
    DISCOVERY_MAX_RESULTS,
    DISCOVERY_SNIFF_MAX_BYTES,
    DISCOVERY_SNIFF_MAX_FILES,
    DISCOVERY_TRUNCATED_MESSAGE,
    BaseDiscovery,
    DiscoveryBudget,
    SniffBudget,
)
from translation_finder.discovery.result import DiscoveryLimit

from .finder import Finder

if TYPE_CHECKING:
    from pathlib import PurePath

    from translation_finder.discovery.result import DiscoveryResult

    from .finder import PathMockType

BACKENDS: list[type[BaseDiscovery]] = []


DiscoveryT = TypeVar("DiscoveryT", bound=type[BaseDiscovery])


def register_discovery(cls: DiscoveryT) -> DiscoveryT:
    """Register a discovery class."""
    BACKENDS.append(cls)
    return cls


def discover(
    root: PurePath | str,
    *,
    mock: PathMockType | None = None,
    source_language: str = "en",
    eager: bool = False,
    hint: str | None = None,
) -> list[DiscoveryResult]:
    """
    High level discovery interface.

    It detects all files which seem translatable (either follow conventions for
    given file format or contain source language in a file path or name).

    The eager mode detects all files in known format regardless their naming.
    Use this in case you want to list all files which can be handled by
    localization tools such as Weblate.

    Discovery is bounded to avoid excessive work on crafted repositories. A
    RuntimeWarning is emitted when the returned results might be incomplete.
    """
    finder = Finder(root, mock=mock)
    discovery_budget = DiscoveryBudget(DISCOVERY_MAX_CANDIDATES)
    sniff_budget = SniffBudget(
        DISCOVERY_SNIFF_MAX_BYTES,
        DISCOVERY_SNIFF_MAX_FILES,
    )
    results: list[DiscoveryResult] = []
    result_limit_reached = False
    for backend in BACKENDS:
        if discovery_budget.exhausted:
            break
        instance = backend(finder, source_language)
        instance._set_run_discovery_budget(  # ruff: ignore[private-member-access]
            discovery_budget
        )
        instance._set_run_sniff_budget(  # ruff: ignore[private-member-access]
            sniff_budget
        )
        result_iterator = instance.discover(eager=eager, hint=hint)
        while len(results) < DISCOVERY_MAX_RESULTS:
            try:
                result = next(result_iterator)
            except StopIteration:
                break
            results.append(result)
        if len(results) >= DISCOVERY_MAX_RESULTS:
            discovery_budget.reach_limit(DiscoveryLimit.RESULTS)
            result_limit_reached = True
        if result_limit_reached:
            if hasattr(result_iterator, "close"):
                result_iterator.close()
            break
    if discovery_budget.truncated:
        warnings.warn(
            DISCOVERY_TRUNCATED_MESSAGE,
            RuntimeWarning,
            stacklevel=2,
        )
    results.sort()
    return results


def _escape_terminal(value: object) -> str:
    """Render non-printable characters as visible escapes for terminal output."""
    return "".join(
        char if char.isprintable() else char.encode("unicode_escape").decode("ascii")
        for char in str(value)
    )


def existing_directory(value: str) -> str:
    """Validate that a path argument points to an existing directory."""
    if not Path(value).is_dir():
        msg = f"no such directory: {_escape_terminal(value)}"
        raise ArgumentTypeError(msg)
    return value


def cli(stdout: TextIO | None = None, args: list[str] | None = None) -> int:
    """Command line execution entry point."""
    stdout = stdout if stdout is not None else sys.stdout

    parser = ArgumentParser(
        description="Weblate translation discovery utility.",
        epilog="This utility is developed at <{}>.".format(
            "https://github.com/WeblateOrg/translation-finder",
        ),
    )
    parser.add_argument("--source-language", help="Source language code", default="en")
    parser.add_argument(
        "--eager",
        help="Enable eager discovery mode",
        default=False,
        action="store_true",
    )
    parser.add_argument("--hint", help="File mask hint for the discovery", default=None)
    parser.add_argument(
        "directory",
        help="Directory where to perform discovery",
        type=existing_directory,
    )

    params = parser.parse_args(args)

    for pos, match in enumerate(
        discover(
            params.directory,
            source_language=params.source_language,
            eager=params.eager,
            hint=params.hint,
        ),
    ):
        origin = (
            f" ({_escape_terminal(match.meta['origin'])})"
            if match.meta["origin"]
            else ""
        )
        print(f"== Match {pos + 1}{origin} ==", file=stdout)
        for key, value in sorted(match.items()):
            print(f"{_escape_terminal(key):15}: {_escape_terminal(value)}", file=stdout)
        print(file=stdout)
    return 0
