# Copyright © Michal Čihař <michal@weblate.org>
#
# SPDX-License-Identifier: GPL-3.0-or-later

"""Highlevel API for translation-finder."""

from __future__ import annotations

import sys
from argparse import ArgumentParser, ArgumentTypeError
from dataclasses import fields
from os import scandir
from pathlib import Path
from typing import TYPE_CHECKING, TextIO, TypeVar

from translation_finder.discovery.base import (
    DISCOVERY_TRUNCATED_MESSAGE,
    BaseDiscovery,
    DiscoveryBudget,
    DiscoveryLimits,
    SniffBudget,
)
from translation_finder.discovery.result import DiscoveryLimit, DiscoveryResults

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


def discover(  # ruff: ignore[too-many-arguments]
    root: PurePath | str,
    *,
    mock: PathMockType | None = None,
    source_language: str = "en",
    eager: bool = False,
    hint: str | None = None,
    limits: DiscoveryLimits | None = None,
) -> DiscoveryResults:
    """
    High level discovery interface.

    It detects all files which seem translatable (either follow conventions for
    given file format or contain source language in a file path or name).

    The eager mode detects all files in known format regardless their naming.
    Use this in case you want to list all files which can be handled by
    localization tools such as Weblate.

    Discovery is bounded to avoid excessive work on crafted repositories.
    Inspect truncated and limit_reasons on the returned results for limit status.
    """
    limits = limits if limits is not None else DiscoveryLimits()
    if limits.max_results == 0:
        if mock is None:
            with scandir(root):
                pass
        return DiscoveryResults(limit_reasons=[DiscoveryLimit.RESULTS])
    finder = Finder(
        root,
        mock=mock,
        max_files=limits.max_files,
        max_dirs=limits.max_dirs,
        max_depth=limits.max_depth,
        max_entries=limits.max_entries,
        max_match_checks=limits.max_match_checks,
    )
    discovery_budget = DiscoveryBudget(
        limits.max_candidates, limits.max_new_base_checks, limits.max_masks_per_path
    )
    sniff_budget = SniffBudget(limits.sniff_max_bytes, limits.sniff_max_files)
    results: list[DiscoveryResult] = []
    for backend in BACKENDS:
        if DiscoveryLimit.CANDIDATES in discovery_budget.limit_reasons:
            break
        instance = backend(finder, source_language)
        instance._set_run_discovery_budget(  # ruff: ignore[private-member-access]
            discovery_budget
        )
        instance._set_run_sniff_budget(  # ruff: ignore[private-member-access]
            sniff_budget
        )
        result_iterator = instance.discover(eager=eager, hint=hint)
        while limits.max_results is None or len(results) < limits.max_results:
            try:
                result = next(result_iterator)
            except StopIteration:
                break
            results.append(result)
        if limits.max_results is not None and len(results) >= limits.max_results:
            try:
                next(result_iterator)
            except StopIteration:
                continue
            discovery_budget.reach_limit(DiscoveryLimit.RESULTS)
            if hasattr(result_iterator, "close"):
                result_iterator.close()
            break
    discovery_results = DiscoveryResults(
        results,
        limit_reasons=discovery_budget.limit_reasons | finder.limit_reasons,
    )
    discovery_results.sort()
    return discovery_results


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


def nonnegative_integer(value: str) -> int:
    """Validate a CLI resource limit."""
    try:
        number = int(value)
    except ValueError as error:
        msg = "limit must be a nonnegative integer"
        raise ArgumentTypeError(msg) from error
    if number < 0:
        msg = "limit must be a nonnegative integer"
        raise ArgumentTypeError(msg)
    return number


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

    defaults = DiscoveryLimits()
    for field in fields(defaults):
        unit = "bytes" if field.name == "sniff_max_bytes" else "count"
        parser.add_argument(
            "--" + field.name.replace("_", "-"),
            type=nonnegative_integer,
            default=None,
            help=f"Discovery {field.name.replace('_', ' ')} ({unit}; default: "
            f"{getattr(defaults, field.name)}; zero permits no work)",
        )
    parser.add_argument(
        "--unlimited",
        action="store_true",
        help="Disable discovery budgets (internal parser and sampling limits remain)",
    )

    params = parser.parse_args(args)

    overrides = {
        field.name: getattr(params, field.name)
        for field in fields(defaults)
        if getattr(params, field.name) is not None
    }
    if params.unlimited and overrides:
        parser.error("--unlimited cannot be combined with explicit discovery limits")
    limits = (
        DiscoveryLimits.unlimited()
        if params.unlimited
        else DiscoveryLimits(**overrides)
    )
    results = discover(
        params.directory,
        source_language=params.source_language,
        eager=params.eager,
        hint=params.hint,
        limits=limits,
    )
    for pos, match in enumerate(results):
        origin = (
            f" ({_escape_terminal(match.meta['origin'])})"
            if match.meta["origin"]
            else ""
        )
        print(f"== Match {pos + 1}{origin} ==", file=stdout)
        for key, value in sorted(match.items()):
            print(f"{_escape_terminal(key):15}: {_escape_terminal(value)}", file=stdout)
        print(file=stdout)
    if results.truncated:
        reasons = ", ".join(sorted(results.limit_reasons))
        print(  # ruff: ignore[print]
            f"warning: {DISCOVERY_TRUNCATED_MESSAGE} (limits: {reasons})",
            file=sys.stderr,
        )
        return 3
    return 0
