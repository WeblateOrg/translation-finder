# Copyright © Michal Čihař <michal@weblate.org>
#
# SPDX-License-Identifier: GPL-3.0-or-later

from pickle import dumps, loads  # nosec
from unittest import TestCase

from .discovery.result import DiscoveryResult


class ResultTest(TestCase):
    def test_lt(self) -> None:
        r1 = DiscoveryResult({"file_format": "a"})
        r1.meta["priority"] = 10
        r2 = DiscoveryResult({"file_format": "b"})
        r2.meta["priority"] = 20
        self.assertLess(r1, r2)
        r2.meta["priority"] = 10
        self.assertLess(r1, r2)

    def test_repr(self) -> None:
        r1 = DiscoveryResult({"file_format": "a"})
        r1.meta["priority"] = 10
        self.assertEqual(f"{r1!r}", "{'file_format': 'a'} [meta:{'priority': 10}]")

    def test_pickle(self) -> None:
        r1 = DiscoveryResult({"file_format": "a"})
        r1.meta["priority"] = 10
        r2 = loads(dumps(r1))
        self.assertIsInstance(r2, DiscoveryResult)
        self.assertEqual(r2, r1)
        r2.meta["x"] = "y"
        self.assertNotEqual(r2, r1)
