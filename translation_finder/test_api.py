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

import os.path
from io import StringIO

from .api import cli, discover
from .finder import PurePath
from .test_discovery import DiscoveryTestCase

TEST_DATA = os.path.join(os.path.dirname(__file__), "test_data")


class APITest(DiscoveryTestCase):
    maxDiff = None

    def test_discover(self):
        paths = ["locales/cs/messages.po", "locales/de/messages.po"]
        self.assert_discovery(
            discover(
                PurePath("."),
                mock=([(PurePath(path), PurePath(path), path) for path in paths], []),
            ),
            [{"filemask": "locales/*/messages.po", "file_format": "po"}],
        )

    def test_discover_files(self):
        self.assert_discovery(
            discover(TEST_DATA),
            [
                {
                    "file_format": "po",
                    "filemask": "locales/*.po",
                    "new_base": "locales/messages.pot",
                    "name": "translation",
                },
                {
                    "file_format": "po",
                    "filemask": "test/*.po",
                    "new_base": "test/messages.pot",
                },
                {
                    "file_format": "po",
                    "filemask": "other/locales/*.po",
                    "new_base": "other/locales/messages.pot",
                    "name": "auto",
                },
                {
                    "file_format": "aresource",
                    "filemask": "app/src/res/main/values-*/strings.xml",
                    "name": "android",
                    "template": "app/src/res/main/values/strings.xml",
                },
                {"file_format": "json-nested", "filemask": "json/bi-*.json"},
                {
                    "file_format": "json-nested",
                    "filemask": "json/bom-*.json",
                    "template": "json/bom-en.json",
                },
                {
                    "file_format": "i18next",
                    "filemask": "json/i18next-*.json",
                    "template": "json/i18next-en.json",
                },
                {
                    "file_format": "json-nested",
                    "filemask": "json/nested-*.json",
                    "template": "json/nested-en.json",
                },
                {
                    "file_format": "go-i18n-json",
                    "filemask": "json/go-*.json",
                    "template": "json/go-en.json",
                },
                {
                    "file_format": "webextension",
                    "filemask": "json/webext-*.json",
                    "template": "json/webext-en.json",
                },
                {
                    "file_format": "json",
                    "filemask": "json/flat-*.json",
                    "template": "json/flat-en.json",
                },
                {
                    "filemask": "locales/*.po",
                    "new_base": "locales/messages.pot",
                    "file_format": "po",
                },
                {"file_format": "po", "filemask": "monopo/*.po"},
                {
                    "file_format": "po-mono",
                    "filemask": "monopo/*.po",
                    "template": "monopo/en.po",
                },
                {
                    "filemask": "app/src/res/main/values-*/strings.xml",
                    "file_format": "aresource",
                    "template": "app/src/res/main/values/strings.xml",
                },
                {
                    "filemask": "java/utf-8_*.properties",
                    "template": "java/utf-8.properties",
                    "file_format": "properties-utf8",
                },
                {
                    "filemask": "java/utf-16_*.properties",
                    "template": "java/utf-16.properties",
                    "file_format": "properties-utf16",
                },
                {
                    "filemask": "java/iso_*.properties",
                    "template": "java/iso.properties",
                    "file_format": "properties",
                },
                {
                    "filemask": "po/*.po",
                    "file_format": "po",
                    "new_base": "po/messages.pot",
                    "name": "implicit",
                },
                {
                    "filemask": "yaml/*/*.yml",
                    "file_format": "yaml",
                    "template": "yaml/en/en.yml",
                },
                {
                    "filemask": "yaml/*.yml",
                    "file_format": "ruby-yaml",
                    "template": "yaml/en.yml",
                },
                {
                    "filemask": "yaml/*/nomatch.yml",
                    "template": "yaml/en/nomatch.yml",
                    "file_format": "yaml",
                },
                {
                    "filemask": "yaml/*/corrupt.yml",
                    "template": "yaml/en/corrupt.yml",
                    "file_format": "yaml",
                },
                {
                    "file_format": "php",
                    "filemask": "php/*.php",
                    "new_base": "php/en.php",
                    "template": "php/en.php",
                },
                {
                    "file_format": "laravel",
                    "filemask": "laravel/*.php",
                    "new_base": "laravel/en.php",
                    "template": "laravel/en.php",
                },
            ],
        )

    def test_cli(self):
        output = StringIO()
        cli(args=[TEST_DATA], stdout=output)
        self.assertIn("Match 2", output.getvalue())

    def test_no_match(self):
        paths = ["files/document.odt"]
        self.assert_discovery(
            discover(
                PurePath("."),
                mock=([(PurePath(path), PurePath(path), path) for path in paths], []),
                eager=True,
            ),
            [
                {
                    "filemask": "files/*.odt",
                    "new_base": "files/document.odt",
                    "template": "files/document.odt",
                    "file_format": "odf",
                }
            ],
        )
