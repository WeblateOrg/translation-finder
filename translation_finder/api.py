# Copyright © Michal Čihař <michal@weblate.org>
#
# SPDX-License-Identifier: GPL-3.0-or-later

"""Highlevel API for translation-finder."""

from __future__ import annotations

import sys
from argparse import ArgumentParser
from io import TextIOWrapper
from typing import TYPE_CHECKING, cast

from .finder import Finder, PathMockType

if TYPE_CHECKING:
    from pathlib import PurePath

    from translation_finder.discovery.base import BaseDiscovery
    from translation_finder.discovery.result import DiscoveryResult

BACKENDS = []


def register_discovery(cls: type[BaseDiscovery]) -> type[BaseDiscovery]:
    """Registers a discovery class."""
    BACKENDS.append(cls)
    return cls


def discover(
    root: PurePath | str,
    mock: PathMockType | None = None,
    source_language: str = "en",
    eager: bool = False,
    hint: str | None = None,
) -> list[DiscoveryResult]:
    """
    High level discovery interface.

    It detects all files which seem translatable (either follow conventions for
    given file format or contain source langauge in a file path or name).

    The eager mode detects all files in known format regardless their naming.
    Use this in case you want to list all files which can be handled by
    localization tools such as Weblate.
    """
    finder = Finder(root, mock=mock)
    results: list[DiscoveryResult] = []
    for backend in BACKENDS:
        instance = backend(finder, source_language)
        results.extend(instance.discover(eager=eager, hint=hint))
    results.sort()
    return results


def cli(stdout: TextIOWrapper | None = None, args: list[str] | None = None) -> int:
    """Execution entry point."""
    stdout = stdout if stdout is not None else cast(TextIOWrapper, sys.stdout)

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
    parser.add_argument("directory", help="Directory where to perform discovery")

    params = parser.parse_args(args)

    for pos, match in enumerate(
        discover(
            params.directory,
            source_language=params.source_language,
            eager=params.eager,
        ),
    ):
        origin = " ({})".format(match.meta["origin"]) if match.meta["origin"] else ""
        print(f"== Match {pos + 1}{origin} ==", file=stdout)
        for key, value in sorted(match.items()):
            print(f"{key:15}: {value}", file=stdout)
        print(file=stdout)
    return 0
