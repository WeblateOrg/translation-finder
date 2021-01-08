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

from unittest import TestCase

from .chardet import detect_charset

TEXT = "zkouška sirén"
SHORT = "zkouška"
EMOJI = "🦬 🦣 🦫 🐻 🦤 🪶 🦭 🪲 🪳 🪰 "


class ChardetTest(TestCase):
    def test_plain(self):
        self.assertEqual(detect_charset(TEXT.encode("iso-8859-2")), None)
        self.assertEqual(detect_charset(SHORT.encode("iso-8859-2")), None)

    def test_unicode(self, charset: str = "utf-8", expected: str = "utf-8"):
        self.assertEqual(detect_charset(TEXT.encode(charset)), expected)
        self.assertEqual(detect_charset(SHORT.encode(charset)), expected)
        self.assertEqual(detect_charset(EMOJI.encode(charset)), expected)

    def test_utf_8_bom(self):
        self.test_unicode("utf-8-sig")

    def test_utf_16(self):
        self.test_unicode("utf-16", "utf-16")
