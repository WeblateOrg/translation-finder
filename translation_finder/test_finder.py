# Copyright © Michal Čihař <michal@weblate.org>
#
# SPDX-License-Identifier: GPL-3.0-or-later
"""File finder tests."""

import pathlib
from unittest import TestCase

from .finder import Finder


class FinderTest(TestCase):
    def test_init(self) -> None:
        finder = Finder(pathlib.Path(__file__).parent)
        self.assertNotEqual(finder.files, {})

    def test_find(self) -> None:
        finder = Finder(pathlib.Path(__file__).parent)
        result = list(finder.filter_files("test_finder.py"))
        self.assertEqual(len(result), 1)
        # Verify that the returned file is the expected test file
        self.assertIsInstance(result[0], pathlib.Path)
        expected_path = pathlib.Path("test_finder.py")
        self.assertEqual(result[0], expected_path)
