# Copyright © Michal Čihař <michal@weblate.org>
#
# SPDX-License-Identifier: GPL-3.0-or-later
# ruff: noqa: S403,S301
"""Discovery result tests including piclking."""

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
        original_result = DiscoveryResult({"file_format": "a"})
        original_result.meta["priority"] = 10
        unpickled_result = loads(dumps(original_result))
        self.assertIsInstance(unpickled_result, DiscoveryResult)
        self.assertEqual(unpickled_result, original_result)
        self.assertEqual(unpickled_result.meta, original_result.meta)
        unpickled_result.meta["x"] = "y"
        self.assertNotEqual(unpickled_result, original_result)
