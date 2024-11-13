# Copyright © Michal Čihař <michal@weblate.org>
#
# SPDX-License-Identifier: GPL-3.0-or-later

import os.path
from unittest import TestCase

from .finder import Finder


class FinderTest(TestCase):
    def test_init(self) -> None:
        finder = Finder(os.path.dirname(__file__))
        self.assertNotEqual(finder.files, {})

    def test_find(self) -> None:
        finder = Finder(os.path.dirname(__file__))
        result = list(finder.filter_files("test_finder.py"))
        self.assertEqual(len(result), 1)
