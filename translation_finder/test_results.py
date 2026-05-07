# Copyright © Michal Čihař <michal@weblate.org>
#
# SPDX-License-Identifier: GPL-3.0-or-later
# ruff: noqa: S403,S301
"""Discovery result tests including pickling."""

import operator
from pickle import dumps, loads  # nosec
from typing import Any
from unittest import TestCase

from .discovery.result import DiscoveryResult


class ResultTest(TestCase):
    def test_lt(self) -> None:
        r1 = DiscoveryResult({"file_format": "a"})
        r1.meta["priority"] = 10
        second_result = DiscoveryResult({"file_format": "b"})
        second_result.meta["priority"] = 20
        self.assertLess(r1, second_result)
        second_result.meta["priority"] = 10
        self.assertLess(r1, second_result)

    def test_lt_unknown_type(self) -> None:
        result = DiscoveryResult({"file_format": "a"})
        other: Any = {}
        with self.assertRaises(TypeError):
            operator.lt(result, other)

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
