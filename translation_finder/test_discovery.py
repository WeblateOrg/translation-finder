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
from __future__ import unicode_literals, absolute_import

from unittest import TestCase

from .finder import Finder, PurePath
from .discovery import (
    GettextDiscovery,
    QtDiscovery,
    AndroidDiscovery,
    OSXDiscovery,
    JavaDiscovery,
    RESXDiscovery,
)


class DiscoveryTestCase(TestCase):
    def get_finder(self, paths):
        return Finder(PurePath("."), [PurePath(path) for path in paths])

    def assert_discovery(self, first, second):
        def sort_key(item):
            return item["filemask"]

        self.assertEqual(sorted(first, key=sort_key), sorted(second, key=sort_key))


class GetttetTest(DiscoveryTestCase):
    def test_basic(self):
        discovery = GettextDiscovery(
            self.get_finder(
                ["locales/cs/messages.po", "locales/de/messages.po", "test/cs.po"]
            )
        )
        self.assert_discovery(
            discovery.discover(),
            [{"filemask": "locales/*/messages.po", "file_format": "po"}],
        )

    def test_double(self):
        self.maxDiff = None
        discovery = GettextDiscovery(
            self.get_finder(
                [
                    "locale/bag_de-DE.po",
                    "locale/baz-de-DE.po",
                    "locale/foo-de_DE.po",
                    "locale/foa_de_DE.po",
                ]
            )
        )
        self.assert_discovery(
            discovery.discover(),
            [
                {"filemask": "locale/foa_*.po", "file_format": "po"},
                {"filemask": "locale/foo-*.po", "file_format": "po"},
                {"filemask": "locale/bag_*.po", "file_format": "po"},
                {"filemask": "locale/baz-*.po", "file_format": "po"},
            ],
        )

    def test_mono(self):
        self.maxDiff = None
        discovery = GettextDiscovery(
            self.get_finder(["locale/en/strings.po", "locale/de/strings.po"])
        )
        self.assert_discovery(
            discovery.discover(),
            [
                {
                    "filemask": "locale/*/strings.po",
                    "file_format": "po",
                    "template": "locale/en/strings.po",
                }
            ],
        )

    def test_mono_language(self):
        self.maxDiff = None
        discovery = GettextDiscovery(
            self.get_finder(["locale/cs_CZ/strings.po", "locale/de/strings.po"]),
            "cs_CZ",
        )
        self.assert_discovery(
            discovery.discover(),
            [
                {
                    "filemask": "locale/*/strings.po",
                    "file_format": "po",
                    "template": "locale/cs_CZ/strings.po",
                }
            ],
        )

    def test_filename(self):
        discovery = GettextDiscovery(
            self.get_finder(["locales/cs.po", "locales/de.po"])
        )
        self.assert_discovery(
            discovery.discover(), [{"filemask": "locales/*.po", "file_format": "po"}]
        )


class QtTest(DiscoveryTestCase):
    def test_basic(self):
        discovery = QtDiscovery(
            self.get_finder(["ts/cs.ts", "ts/zh_CN.ts", "lrc/translations/lrc_id.ts"])
        )
        self.assert_discovery(
            discovery.discover(),
            [
                {"filemask": "ts/*.ts", "file_format": "ts"},
                {"filemask": "lrc/translations/lrc_*.ts", "file_format": "ts"},
            ],
        )


class AndroidTest(DiscoveryTestCase):
    def test_basic(self):
        discovery = AndroidDiscovery(
            self.get_finder(
                [
                    "app/src/res/main/values/strings.xml",
                    "app/src/res/main/values-it/strings.xml",
                    "app/src/res/main/values-it/strings-other.xml",
                ]
            )
        )
        self.assert_discovery(
            discovery.discover(),
            [
                {
                    "filemask": "app/src/res/main/values-*/strings.xml",
                    "file_format": "aresource",
                    "template": "app/src/res/main/values/strings.xml",
                }
            ],
        )


class OSXTest(DiscoveryTestCase):
    def test_basic(self):
        discovery = OSXDiscovery(
            self.get_finder(
                [
                    "App/Resources/en.lproj/Localizable.strings",
                    "App/Resources/Base.lproj/Other.strings",
                    "App/Resources/ru.lproj/Third.strings",
                ]
            )
        )
        self.assert_discovery(
            discovery.discover(),
            [
                {
                    "filemask": "App/Resources/*.lproj/Localizable.strings",
                    "file_format": "strings",
                    "template": "App/Resources/en.lproj/Localizable.strings",
                },
                {
                    "filemask": "App/Resources/*.lproj/Other.strings",
                    "file_format": "strings",
                    "template": "App/Resources/Base.lproj/Other.strings",
                },
            ],
        )


class JavaTest(DiscoveryTestCase):
    def test_basic(self):
        discovery = JavaDiscovery(
            self.get_finder(
                [
                    "bundle/UIMessages_de.properties",
                    "bundle/UIMessages_fr.properties",
                    "bundle/UIMessages_ja.properties",
                    "bundle/UIMessages_nb_NO.properties",
                    "bundle/UIMessages.properties",
                    "bundle/UIMessages_ru.properties",
                    "bundle/UIMessages_zh.properties",
                    "bundle/FixedMessages.properties",
                    "bundle/Other_Messages.properties",
                ]
            )
        )
        self.assert_discovery(
            discovery.discover(),
            [
                {
                    "filemask": "bundle/UIMessages_*.properties",
                    "file_format": "properties",
                    "template": "bundle/UIMessages.properties",
                }
            ],
        )


class RESXTest(DiscoveryTestCase):
    def test_basic(self):
        discovery = RESXDiscovery(
            self.get_finder(
                [
                    "App/Localization/AboutStrings.ar.resx",
                    "App/Localization/AboutStrings.resx",
                    "App/Localization/MainStrings.ar.resw",
                    "App/Localization/MainStrings.resw",
                    "App/Localization/OtherStrings.resx",
                    "App/Localization/Other.Strings.resx",
                    "App/Localization/SettingsStrings.fr.resx",
                    "App/Localization/ar/Resources.resw",
                    "App/Localization/en/Resources.resw",
                ]
            )
        )
        self.assert_discovery(
            discovery.discover(),
            [
                {
                    "filemask": "App/Localization/AboutStrings.*.resx",
                    "file_format": "resx",
                    "template": "App/Localization/AboutStrings.resx",
                },
                {
                    "filemask": "App/Localization/MainStrings.*.resw",
                    "file_format": "resx",
                    "template": "App/Localization/MainStrings.resw",
                },
                {
                    "filemask": "App/Localization/*/Resources.resw",
                    "file_format": "resx",
                    "template": "App/Localization/en/Resources.resw",
                },
            ],
        )
