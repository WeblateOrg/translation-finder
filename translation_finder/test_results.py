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

from pickle import dumps, loads  # nosec
from unittest import TestCase

from .discovery.result import DiscoveryResult


class ResultTest(TestCase):
    def test_lt(self):
        r1 = DiscoveryResult({"file_format": "a"})
        r1.meta["priority"] = 10
        r2 = DiscoveryResult({"file_format": "b"})
        r2.meta["priority"] = 20
        self.assertLess(r1, r2)
        r2.meta["priority"] = 10
        self.assertLess(r1, r2)

    def test_repr(self):
        r1 = DiscoveryResult({"file_format": "a"})
        r1.meta["priority"] = 10
        self.assertEqual(f"{r1!r}", "{'file_format': 'a'} [meta:{'priority': 10}]")

    def test_pickle(self):
        r1 = DiscoveryResult({"file_format": "a"})
        r1.meta["priority"] = 10
        r2 = loads(dumps(r1))
        self.assertIsInstance(r2, DiscoveryResult)
        self.assertEqual(r2, r1)
        r2.meta["x"] = "y"
        self.assertNotEqual(r2, r1)
