# -*- coding: utf-8 -*-
#
# Copyright © 2018 Michal Čihař <michal@cihar.com>
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
# along with this program.  If not, see <http://www.gnu.org/licenses/>.
#
"""Highlevel API for translation-finder."""
from __future__ import unicode_literals, absolute_import, print_function

from argparse import ArgumentParser
import sys

from .finder import Finder
from .discovery import (
    GettextDiscovery,
    QtDiscovery,
    AndroidDiscovery,
    OSXDiscovery,
    JavaDiscovery,
    RESXDiscovery,
)

BACKENDS = [
    GettextDiscovery,
    QtDiscovery,
    AndroidDiscovery,
    OSXDiscovery,
    JavaDiscovery,
    RESXDiscovery,
]


def discover(root, files=None, source_language="en"):
    """High level discovery interface."""
    finder = Finder(root, files)
    results = []
    for backend in BACKENDS:
        instance = backend(finder, source_language)
        results.extend(instance.discover())
    return results


def cli(stdout=None, args=None):
    """Execution entry point."""
    stdout = stdout if stdout is not None else sys.stdout

    parser = ArgumentParser(
        description="Weblate translation discovery utility.",
        epilog="This utility is developed at <{0}>.".format(
            "https://github.com/WeblateOrg/translation-finder"
        ),
    )
    parser.add_argument("directory", help="Directory where to perform discovery")

    params = parser.parse_args(args)

    for pos, match in enumerate(discover(params.directory)):
        print("== Match {} ==".format(pos + 1), file=stdout)
        for key, value in sorted(match.items()):
            print("{:15}: {}".format(key, value), file=stdout)
        print("", file=stdout)
