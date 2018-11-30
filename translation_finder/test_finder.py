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
# along with this program.  If not, see <https://www.gnu.org/licenses/>.
#
from __future__ import unicode_literals, absolute_import

from unittest import TestCase
import os.path

from .finder import Finder


class FinderTest(TestCase):
    def test_init(self):
        finder = Finder(os.path.dirname(__file__))
        self.assertNotEqual(finder.files, {})

    def test_find(self):
        finder = Finder(os.path.dirname(__file__))
        result = list(finder.filter_files("test_finder.py"))
        self.assertEqual(len(result), 1)
