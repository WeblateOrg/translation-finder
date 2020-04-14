#
# Copyright © 2012 - 2020 Michal Čihař <michal@cihar.com>
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
from unittest import TestCase

from .discovery.base import DiscoveryResult
from .discovery.files import (
    AndroidDiscovery,
    AppStoreDiscovery,
    FluentDiscovery,
    GettextDiscovery,
    JavaDiscovery,
    JoomlaDiscovery,
    JSONDiscovery,
    OSXDiscovery,
    QtDiscovery,
    RESXDiscovery,
    WebExtensionDiscovery,
    XliffDiscovery,
    YAMLDiscovery,
)
from .discovery.transifex import TransifexDiscovery
from .finder import Finder, PurePath

TEST_DATA = os.path.join(os.path.dirname(__file__), "test_data")


class DiscoveryTestCase(TestCase):
    maxDiff = None

    def get_finder(self, paths, dirs=None):
        if dirs is None:
            dirs = []
        return Finder(
            PurePath("."),
            mock=(
                [(PurePath(path), PurePath(path), path) for path in paths],
                [(PurePath(path), PurePath(path), path) for path in dirs],
            ),
        )

    def get_real_finder(self):
        return Finder(TEST_DATA)

    def assert_discovery(self, first, second):
        def sort_key(item):
            return item["filemask"]

        self.assertEqual(sorted(first, key=sort_key), sorted(second, key=sort_key))
        for value in first:
            self.assertIsInstance(value, DiscoveryResult)


class GetttetTest(DiscoveryTestCase):
    maxDiff = None

    def test_basic(self):
        discovery = GettextDiscovery(
            self.get_finder(
                [
                    "locales/cs/messages.po",
                    "locales/de/messages.po",
                    "locales/messages.pot",
                    "locales/cs/other.po",
                    "locales/de/other.po",
                    "locales/en/other.po",
                    "locales/other.pot",
                    "locale/pl_PL/LC_MESSAGES/emote_collector.po",
                    "locale/es_ES/LC_MESSAGES/emote_collector.po",
                    "locale/hu_HU/LC_MESSAGES/emote_collector.po",
                    "help/pt_BR/pt_BR.po",
                    "help/nl/nl.po",
                    "help/de/de.po",
                    "Source/WebCore/platform/gtk/po/ar.po",
                    "Source/WebCore/platform/gtk/po/pt.po",
                    "Source/WebCore/platform/gtk/po/sv.po",
                    "desktop-docs/gpl/sr/sr.po",
                    "desktop-docs/gpl/sr@latin/sr@latin.po",
                    "po/jp/rawhide/pages/welcome/Welcome.po",
                    "pot/rawhide/pages/welcome/Welcome.pot",
                ]
            )
        )
        self.assert_discovery(
            discovery.discover(),
            [
                {
                    "filemask": "locales/*/messages.po",
                    "file_format": "po",
                    "new_base": "locales/messages.pot",
                },
                {
                    "filemask": "locales/*/other.po",
                    "file_format": "po",
                    "new_base": "locales/other.pot",
                },
                {
                    "filemask": "locales/*/other.po",
                    "file_format": "po-mono",
                    "new_base": "locales/other.pot",
                    "template": "locales/en/other.po",
                },
                {
                    "filemask": "locale/*/LC_MESSAGES/emote_collector.po",
                    "file_format": "po",
                },
                {"filemask": "help/*/*.po", "file_format": "po"},
                {"file_format": "po", "filemask": "desktop-docs/gpl/*/*.po"},
                {
                    "filemask": "Source/WebCore/platform/gtk/po/*.po",
                    "file_format": "po",
                },
                {
                    "file_format": "po",
                    "filemask": "po/*/rawhide/pages/welcome/Welcome.po",
                    "new_base": "pot/rawhide/pages/welcome/Welcome.pot",
                },
            ],
        )

    def test_duplicate_code(self):
        discovery = GettextDiscovery(
            self.get_finder(
                [
                    "locales/messages.pot",
                    "locales/cs/other/cs/messages.po",
                    "locales/de/other/de/messages.po",
                    "help/ar/ar.po",
                    "po/cs/docs.po",
                ]
            )
        )
        self.assert_discovery(
            discovery.discover(),
            [
                {"filemask": "po/*/docs.po", "file_format": "po"},
                {
                    "filemask": "locales/*/other/*/messages.po",
                    "file_format": "po",
                    "new_base": "locales/messages.pot",
                },
                {"filemask": "help/*/*.po", "file_format": "po"},
            ],
        )

    def test_double(self):
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

    def test_uppercase(self):
        discovery = GettextDiscovery(
            self.get_finder(
                [
                    "sources/localization/Xenko.Core.Presentation.pot",
                    "sources/localization/ja/Xenko.Core.Assets.Editor.ja.po",
                    "sources/localization/ja/Xenko.GameStudio.ja.po",
                    "sources/localization/ja/Xenko.Assets.Presentation.ja.po",
                    "sources/localization/ja/Xenko.Core.Presentation.ja.po",
                    "sources/localization/Xenko.Core.Assets.Editor.pot",
                    "sources/localization/fr/Xenko.Core.Presentation.fr.po",
                    "sources/localization/fr/Xenko.Assets.Presentation.fr.po",
                    "sources/localization/fr/Xenko.GameStudio.fr.po",
                    "sources/localization/fr/Xenko.Core.Assets.Editor.fr.po",
                    "sources/localization/Xenko.GameStudio.pot",
                    "sources/localization/Xenko.Assets.Presentation.pot",
                ]
            )
        )
        self.assert_discovery(
            discovery.discover(),
            [
                {
                    "filemask": "sources/localization/*/Xenko.Core.Assets.Editor.*.po",
                    "file_format": "po",
                    "new_base": "sources/localization/Xenko.Core.Assets.Editor.pot",
                },
                {
                    "filemask": "sources/localization/*/Xenko.Assets.Presentation.*.po",
                    "file_format": "po",
                    "new_base": "sources/localization/Xenko.Assets.Presentation.pot",
                },
                {
                    "filemask": "sources/localization/*/Xenko.Core.Presentation.*.po",
                    "file_format": "po",
                    "new_base": "sources/localization/Xenko.Core.Presentation.pot",
                },
                {
                    "filemask": "sources/localization/*/Xenko.GameStudio.*.po",
                    "file_format": "po",
                    "new_base": "sources/localization/Xenko.GameStudio.pot",
                },
            ],
        )

    def test_mono(self):
        discovery = GettextDiscovery(
            self.get_finder(["locale/en/strings.po", "locale/de/strings.po"])
        )
        self.assert_discovery(
            discovery.discover(),
            [
                {"filemask": "locale/*/strings.po", "file_format": "po"},
                {
                    "filemask": "locale/*/strings.po",
                    "file_format": "po-mono",
                    "template": "locale/en/strings.po",
                },
            ],
        )

    def test_mono_language(self):
        discovery = GettextDiscovery(
            self.get_finder(["locale/cs_CZ/strings.po", "locale/de/strings.po"]),
            "cs_CZ",
        )
        self.assert_discovery(
            discovery.discover(),
            [
                {"filemask": "locale/*/strings.po", "file_format": "po"},
                {
                    "filemask": "locale/*/strings.po",
                    "file_format": "po-mono",
                    "template": "locale/cs_CZ/strings.po",
                },
            ],
        )

    def test_filename(self):
        discovery = GettextDiscovery(
            self.get_finder(["locales/cs.po", "locales/de.po"])
        )
        self.assert_discovery(
            discovery.discover(), [{"filemask": "locales/*.po", "file_format": "po"}]
        )

    def test_root(self):
        discovery = GettextDiscovery(self.get_finder(["en.po", "de.po"]))
        self.assert_discovery(
            discovery.discover(),
            [
                {"filemask": "*.po", "file_format": "po"},
                {"filemask": "*.po", "file_format": "po-mono", "template": "en.po"},
            ],
        )

    def test_new_base(self):
        discovery = GettextDiscovery(self.get_finder(["foo.fr.po", "foo.po"]))
        print(list(discovery.discover()))
        self.assert_discovery(
            discovery.discover(),
            [
                {"filemask": "foo.*.po", "new_base": "foo.po", "file_format": "po"},
                {
                    "filemask": "foo.*.po",
                    "template": "foo.po",
                    "new_base": "foo.po",
                    "file_format": "po-mono",
                },
            ],
        )


class QtTest(DiscoveryTestCase):
    def test_basic(self):
        discovery = QtDiscovery(
            self.get_finder(
                [
                    "ts/cs.ts",
                    "ts/zh_CN.ts",
                    "lrc/translations/lrc_id.ts",
                    "quickevent/app/quickevent/quickevent.cs_CZ.ts",
                    "libqf/libqfqmlwidgets/libqfqmlwidgets.pl_PL.ts",
                    "6-migrate-archived-model-to-revision.ts",
                ]
            )
        )
        self.assert_discovery(
            discovery.discover(),
            [
                {"filemask": "ts/*.ts", "file_format": "ts", "new_base": "ts/cs.ts"},
                {
                    "filemask": "lrc/translations/lrc_*.ts",
                    "file_format": "ts",
                    "new_base": "lrc/translations/lrc_id.ts",
                },
                {
                    "filemask": "quickevent/app/quickevent/quickevent.*.ts",
                    "file_format": "ts",
                    "new_base": "quickevent/app/quickevent/quickevent.cs_CZ.ts",
                },
                {
                    "filemask": "libqf/libqfqmlwidgets/libqfqmlwidgets.*.ts",
                    "file_format": "ts",
                    "new_base": "libqf/libqfqmlwidgets/libqfqmlwidgets.pl_PL.ts",
                },
                {
                    "filemask": "6-migrate-archived-model-*-revision.ts",
                    "file_format": "ts",
                },
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
                    "length_1.properties",
                    "length_1_de.properties",
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
                },
                {
                    "filemask": "length_1_*.properties",
                    "file_format": "properties",
                    "template": "length_1.properties",
                },
            ],
        )


class JoomlaTest(DiscoveryTestCase):
    def test_basic(self):
        discovery = JoomlaDiscovery(
            self.get_finder(
                [
                    "public/lang/cs.ini",
                    "public/lang/ru.ini",
                    "public/lang/nl.ini",
                    "public/lang/rm.ini",
                    "public/lang/ca.ini",
                    "public/lang/en.ini",
                ]
            )
        )
        self.assert_discovery(
            discovery.discover(),
            [
                {
                    "filemask": "public/lang/*.ini",
                    "file_format": "joomla",
                    "template": "public/lang/en.ini",
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
                {
                    "file_format": "resx",
                    "filemask": "App/Localization/SettingsStrings.*.resx",
                },
            ],
        )


class XliffTest(DiscoveryTestCase):
    def test_basic(self):
        discovery = XliffDiscovery(
            self.get_finder(["locales/cs.xliff", "locales/en.xliff"])
        )
        self.assert_discovery(
            discovery.discover(),
            [
                {
                    "filemask": "locales/*.xliff",
                    "file_format": "xliff",
                    "template": "locales/en.xliff",
                }
            ],
        )

    def test_short(self):
        discovery = XliffDiscovery(
            self.get_finder(
                [
                    "locales/cs.xlf",
                    "locales/en.xlf",
                    "otherlocales/cs/main.xlf",
                    "otherlocales/cs/help.xlf",
                    "length_1.properties.xlf",
                    "length_1_de.properties.xlf",
                ]
            )
        )
        self.assert_discovery(
            discovery.discover(),
            [
                {
                    "filemask": "locales/*.xlf",
                    "file_format": "xliff",
                    "template": "locales/en.xlf",
                },
                {"filemask": "otherlocales/*/main.xlf", "file_format": "xliff"},
                {"filemask": "otherlocales/*/help.xlf", "file_format": "xliff"},
                {"filemask": "length_1_*.properties.xlf", "file_format": "xliff"},
            ],
        )


class WebExtensionTest(DiscoveryTestCase):
    def test_basic(self):
        discovery = WebExtensionDiscovery(
            self.get_finder(["_locales/cs/messages.json", "_locales/en/messages.json"])
        )
        self.assert_discovery(
            discovery.discover(),
            [
                {
                    "filemask": "_locales/*/messages.json",
                    "file_format": "webextension",
                    "template": "_locales/en/messages.json",
                }
            ],
        )


class JSONDiscoveryTest(DiscoveryTestCase):
    def test_basic(self):
        discovery = JSONDiscovery(
            self.get_finder(
                [
                    "tr/wizard-nl_BE.json",
                    "tr/wizard-fr.json",
                    "tr/wizard-en.json",
                    "tr/register-en.json",
                    "tr/register-sk.json",
                    "tr/recordings-en.json",
                    "sa/profiles/Generic/snmp_metrics/interface_errors_in.json",
                    "Source/JavaScriptCore/inspector/protocol/Canvas.json",
                    "Source/JavaScriptCore/inspector/protocol/Target.json",
                    "Source/JavaScriptCore/inspector/protocol/Console.json",
                    "data/cs/strings.json",
                    "data/strings.json",
                ]
            )
        )
        self.assert_discovery(
            discovery.discover(),
            [
                {
                    "filemask": "tr/wizard-*.json",
                    "file_format": "json-nested",
                    "template": "tr/wizard-en.json",
                },
                {
                    "filemask": "tr/register-*.json",
                    "file_format": "json-nested",
                    "template": "tr/register-en.json",
                },
                {
                    "filemask": "tr/recordings-*.json",
                    "file_format": "json-nested",
                    "template": "tr/recordings-en.json",
                },
                {
                    "filemask": "data/*/strings.json",
                    "file_format": "json-nested",
                    "template": "data/strings.json",
                },
            ],
        )


class TransifexTest(DiscoveryTestCase):
    def test_basic(self):
        discovery = TransifexDiscovery(self.get_real_finder())
        results = list(discovery.discover())
        self.assert_discovery(
            results,
            [
                {
                    "filemask": "locales/*.po",
                    "file_format": "po",
                    "new_base": "locales/messages.pot",
                    "name": "translation",
                },
                {
                    "file_format": "aresource",
                    "filemask": "app/src/res/main/values-*/strings.xml",
                    "name": "android",
                    "template": "app/src/res/main/values/strings.xml",
                },
                {
                    "filemask": "po/*.po",
                    "file_format": "po",
                    "new_base": "po/messages.pot",
                    "name": "implicit",
                },
                {
                    "file_format": "po",
                    "filemask": "other/locales/*.po",
                    "new_base": "other/locales/messages.pot",
                    "name": "auto",
                },
            ],
        )
        self.assertEqual(results[0].meta["discovery"], "TransifexDiscovery")
        self.assertEqual(results[0].meta["origin"], "Transifex")


class AppStoreDiscoveryTest(DiscoveryTestCase):
    def test_basic(self):
        discovery = AppStoreDiscovery(
            self.get_finder(
                [
                    "metadata/en-AU/short_description.txt",
                    "metadata/en-US/short_description.txt",
                    "private/metadata/en-AU/changelogs/10000.txt",
                    "short_description.txt",
                ],
                ["metadata/en-AU", "metadata/en-US", "private/metadata/en-AU"],
            )
        )
        self.assert_discovery(
            discovery.discover(),
            [
                {
                    "filemask": "metadata/*",
                    "file_format": "appstore",
                    "template": "metadata/en-US",
                },
                {
                    "filemask": "private/metadata/*",
                    "file_format": "appstore",
                    "template": "private/metadata/en-AU",
                },
            ],
        )


class FluentDiscoveryTest(DiscoveryTestCase):
    def test_basic(self):
        discovery = FluentDiscovery(
            self.get_finder(
                [
                    "browser/locales/en-US/browser/component/file.ftl",
                    "browser/locales/cs-CS/browser/component/file.ftl",
                ]
            )
        )
        self.assert_discovery(
            discovery.discover(),
            [
                {
                    "filemask": "browser/locales/*/browser/component/file.ftl",
                    "file_format": "fluent",
                    "template": "browser/locales/en-US/browser/component/file.ftl",
                }
            ],
        )


class YAMLDiscoveryTest(DiscoveryTestCase):
    def test_basic(self):
        discovery = YAMLDiscovery(
            self.get_finder(
                ["translations/en/messages.en.yml", "translations/de/messages.de.yml"]
            )
        )
        self.assert_discovery(
            discovery.discover(),
            [
                {
                    "filemask": "translations/*/messages.*.yml",
                    "file_format": "yaml",
                    "template": "translations/en/messages.en.yml",
                }
            ],
        )
