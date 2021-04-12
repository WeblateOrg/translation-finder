#
# Copyright © 2012 - 2021 Michal Čihař <michal@cihar.com>
#
# This file is part of Weblate translation-finder
# <https://github.com/WeblateOrg/translation-finder>
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.
#
"""Highlevel API for translation-finder."""

import sys
from argparse import ArgumentParser

from .finder import Finder

BACKENDS = []


def register_discovery(cls):
    """Registers a discovery class."""
    BACKENDS.append(cls)
    return cls


def discover(root, mock=None, source_language: str = "en", eager: bool = False):
    """
    High level discovery interface.

    It detects all files which seem translatable (either follow conventions for
    given file format or contain source langauge in a file path or name).

    The eager mode detects all files in known format regardless their naming.
    Use this in case you want to list all files which can be handled by
    localization tools such as Weblate.
    """
    finder = Finder(root, mock=mock)
    results = []
    for backend in BACKENDS:
        instance = backend(finder, source_language)
        results.extend(instance.discover(eager=eager))
    results.sort()
    return results


def cli(stdout=None, args=None):
    """Execution entry point."""
    stdout = stdout if stdout is not None else sys.stdout

    parser = ArgumentParser(
        description="Weblate translation discovery utility.",
        epilog="This utility is developed at <{}>.".format(
            "https://github.com/WeblateOrg/translation-finder"
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
            params.directory, source_language=params.source_language, eager=params.eager
        )
    ):
        origin = " ({})".format(match.meta["origin"]) if match.meta["origin"] else ""
        print(f"== Match {pos + 1}{origin} ==", file=stdout)
        for key, value in sorted(match.items()):
            print(f"{key:15}: {value}", file=stdout)
        print("", file=stdout)
    return 0
