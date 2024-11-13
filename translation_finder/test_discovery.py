# Copyright © Michal Čihař <michal@weblate.org>
#
# SPDX-License-Identifier: GPL-3.0-or-later

from __future__ import annotations

from operator import itemgetter
from pathlib import Path, PurePath
from typing import TYPE_CHECKING
from unittest import TestCase

from .discovery.base import DiscoveryResult, ResultDict
from .discovery.files import (
    AndroidDiscovery,
    AppStoreDiscovery,
    ARBDiscovery,
    CSVDiscovery,
    FluentDiscovery,
    FormatJSDiscovery,
    GettextDiscovery,
    HTMLDiscovery,
    JavaDiscovery,
    JoomlaDiscovery,
    JSONDiscovery,
    MOKODiscovery,
    OSXDiscovery,
    PHPDiscovery,
    QtDiscovery,
    RCDiscovery,
    ResourceDictionaryDiscovery,
    RESXDiscovery,
    StringsdictDiscovery,
    TOMLDiscovery,
    TXTDiscovery,
    WebExtensionDiscovery,
    XliffDiscovery,
    YAMLDiscovery,
)
from .discovery.transifex import TransifexDiscovery
from .finder import Finder

if TYPE_CHECKING:
    from collections.abc import Iterable

TEST_DATA = Path(__file__).parent / "test_data"


class DiscoveryTestCase(TestCase):
    maxDiff = None

    @staticmethod
    def get_finder(paths, dirs=None):
        if dirs is None:
            dirs = []
        return Finder(
            PurePath("."),
            mock=(
                [(PurePath(path), PurePath(path), path) for path in paths],
                [(PurePath(path), PurePath(path), path) for path in dirs],
            ),
        )

    @staticmethod
    def get_real_finder():
        return Finder(TEST_DATA)

    def assert_discovery(
        self, actual: Iterable[DiscoveryResult], expected: list[ResultDict]
    ) -> None:
        actual_list = sorted(actual, key=itemgetter("filemask"))
        expected_list = sorted(expected, key=itemgetter("filemask"))
        self.assertEqual(
            len(actual_list), len(expected_list), "Mismatched count of results"
        )
        for i, value in enumerate(actual_list):
            self.assertIsInstance(value, DiscoveryResult)
            self.assertEqual(value.data, expected_list[i])


class GetttetTest(DiscoveryTestCase):
    maxDiff = None

    def test_basic(self) -> None:
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
                    "de/LC_MESSAGES/pot_not_honored.po",
                    "pot_not_honored.pot",
                ],
            ),
        )
        self.assert_discovery(
            discovery.discover(),
            [
                {
                    "file_format": "po",
                    "filemask": "*/LC_MESSAGES/pot_not_honored.po",
                    "new_base": "pot_not_honored.pot",
                },
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

    def test_duplicate_code(self) -> None:
        discovery = GettextDiscovery(
            self.get_finder(
                [
                    "locales/messages.pot",
                    "locales/cs/other/cs/messages.po",
                    "locales/de/other/de/messages.po",
                    "help/ar/ar.po",
                    "po/cs/docs.po",
                ],
            ),
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

    def test_double(self) -> None:
        discovery = GettextDiscovery(
            self.get_finder(
                [
                    "locale/bag_de-DE.po",
                    "locale/baz-de-DE.po",
                    "locale/foo-de_DE.po",
                    "locale/foa_de_DE.po",
                ],
            ),
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

    def test_uppercase(self) -> None:
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
                ],
            ),
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

    def test_mono(self) -> None:
        discovery = GettextDiscovery(
            self.get_finder(["locale/en/strings.po", "locale/de/strings.po"]),
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

    def test_mono_language(self) -> None:
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

    def test_filename(self) -> None:
        discovery = GettextDiscovery(
            self.get_finder(["locales/cs.po", "locales/de.po"]),
        )
        self.assert_discovery(
            discovery.discover(),
            [{"filemask": "locales/*.po", "file_format": "po"}],
        )

    def test_root(self) -> None:
        discovery = GettextDiscovery(self.get_finder(["en.po", "de.po"]))
        self.assert_discovery(
            discovery.discover(),
            [
                {"filemask": "*.po", "file_format": "po"},
                {"filemask": "*.po", "file_format": "po-mono", "template": "en.po"},
            ],
        )

    def test_new_base(self) -> None:
        discovery = GettextDiscovery(self.get_finder(["foo.fr.po", "foo.po"]))
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

    def test_po_pot(self) -> None:
        discovery = GettextDiscovery(self.get_finder(["po/jasp_nl.po", "po/jasp.po"]))
        self.assert_discovery(
            discovery.discover(),
            [
                {
                    "filemask": "po/jasp_*.po",
                    "file_format": "po",
                    "new_base": "po/jasp.po",
                },
            ],
        )

    def test_po_many(self) -> None:
        test_file = TEST_DATA / "calibre.txt"
        filenames = test_file.read_text(encoding="utf-8").splitlines()
        discovery = GettextDiscovery(self.get_finder(filenames))
        self.assert_discovery(
            discovery.discover(),
            [
                {
                    "file_format": "po",
                    "filemask": "translations/manual/*/catalogs.po",
                    "new_base": "translations/manual/catalogs.pot",
                },
                {
                    "file_format": "po",
                    "filemask": "translations/manual/*/conversion.po",
                    "new_base": "translations/manual/conversion.pot",
                },
                {
                    "file_format": "po",
                    "filemask": "translations/manual/*/creating_plugins.po",
                    "new_base": "translations/manual/creating_plugins.pot",
                },
                {
                    "file_format": "po",
                    "filemask": "translations/manual/*/customize.po",
                    "new_base": "translations/manual/customize.pot",
                },
                {
                    "file_format": "po",
                    "filemask": "translations/manual/*/db_api.po",
                    "new_base": "translations/manual/db_api.pot",
                },
                {
                    "file_format": "po",
                    "filemask": "translations/manual/*/develop.po",
                    "new_base": "translations/manual/develop.pot",
                },
                {
                    "file_format": "po",
                    "filemask": "translations/manual/*/diff.po",
                    "new_base": "translations/manual/diff.pot",
                },
                {
                    "file_format": "po",
                    "filemask": "translations/manual/*/drm.po",
                    "new_base": "translations/manual/drm.pot",
                },
                {
                    "file_format": "po",
                    "filemask": "translations/manual/*/edit.po",
                    "new_base": "translations/manual/edit.pot",
                },
                {
                    "file_format": "po",
                    "filemask": "translations/manual/*/faq.po",
                    "new_base": "translations/manual/faq.pot",
                },
                {
                    "file_format": "po",
                    "filemask": "translations/manual/*/function_mode.po",
                    "new_base": "translations/manual/function_mode.pot",
                },
                {
                    "file_format": "po",
                    "filemask": "translations/manual/*/glossary.po",
                    "new_base": "translations/manual/glossary.pot",
                },
                {
                    "file_format": "po",
                    "filemask": "translations/manual/*/gui.po",
                    "new_base": "translations/manual/gui.pot",
                },
                {
                    "file_format": "po",
                    "filemask": "translations/manual/*/index.po",
                    "new_base": "translations/manual/index.pot",
                },
                {
                    "file_format": "po",
                    "filemask": "translations/manual/*/metadata.po",
                    "new_base": "translations/manual/metadata.pot",
                },
                {
                    "file_format": "po",
                    "filemask": "translations/manual/*/news.po",
                    "new_base": "translations/manual/news.pot",
                },
                {
                    "file_format": "po",
                    "filemask": "translations/manual/*/news_recipe.po",
                    "new_base": "translations/manual/news_recipe.pot",
                },
                {
                    "file_format": "po",
                    "filemask": "translations/manual/*/plugins.po",
                    "new_base": "translations/manual/plugins.pot",
                },
                {
                    "file_format": "po",
                    "filemask": "translations/manual/*/polish.po",
                    "new_base": "translations/manual/polish.pot",
                },
                {
                    "file_format": "po",
                    "filemask": "translations/manual/*/regexp.po",
                    "new_base": "translations/manual/regexp.pot",
                },
                {
                    "file_format": "po",
                    "filemask": "translations/manual/*/regexp_quick_reference.po",
                    "new_base": "translations/manual/regexp_quick_reference.pot",
                },
                {
                    "file_format": "po",
                    "filemask": "translations/manual/*/server.po",
                    "new_base": "translations/manual/server.pot",
                },
                {
                    "file_format": "po",
                    "filemask": "translations/manual/*/simple_index.po",
                    "new_base": "translations/manual/simple_index.pot",
                },
                {
                    "file_format": "po",
                    "filemask": "translations/manual/*/snippets.po",
                    "new_base": "translations/manual/snippets.pot",
                },
                {
                    "file_format": "po",
                    "filemask": "translations/manual/*/sphinx.po",
                    "new_base": "translations/manual/sphinx.pot",
                },
                {
                    "file_format": "po",
                    "filemask": "translations/manual/*/sub_groups.po",
                    "new_base": "translations/manual/sub_groups.pot",
                },
                {
                    "file_format": "po",
                    "filemask": "translations/manual/*/template_lang.po",
                    "new_base": "translations/manual/template_lang.pot",
                },
                {
                    "file_format": "po",
                    "filemask": "translations/manual/*/tutorials.po",
                    "new_base": "translations/manual/tutorials.pot",
                },
                {
                    "file_format": "po",
                    "filemask": "translations/manual/*/typesetting_math.po",
                    "new_base": "translations/manual/typesetting_math.pot",
                },
                {
                    "file_format": "po",
                    "filemask": "translations/manual/*/viewer.po",
                    "new_base": "translations/manual/viewer.pot",
                },
                {
                    "file_format": "po",
                    "filemask": "translations/manual/*/virtual_libraries.po",
                    "new_base": "translations/manual/virtual_libraries.pot",
                },
                {
                    "file_format": "po",
                    "filemask": "translations/manual/*/xpath.po",
                    "new_base": "translations/manual/xpath.pot",
                },
            ],
        )


class QtTest(DiscoveryTestCase):
    def test_basic(self) -> None:
        discovery = QtDiscovery(
            self.get_finder(
                [
                    "ts/cs.ts",
                    "ts/zh_CN.ts",
                    "lrc/translations/lrc_de.ts",
                    "lrc/translations/lrc_id.ts",
                    "quickevent/app/quickevent/quickevent.cs_CZ.ts",
                    "libqf/libqfqmlwidgets/libqfqmlwidgets.pl_PL.ts",
                ],
            ),
        )
        self.assert_discovery(
            discovery.discover(),
            [
                {"filemask": "ts/*.ts", "file_format": "ts", "new_base": "ts/cs.ts"},
                {
                    "filemask": "lrc/translations/lrc_*.ts",
                    "file_format": "ts",
                    "new_base": "lrc/translations/lrc_de.ts",
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
            ],
        )

    def test_po_mono_template(self) -> None:
        discovery = GettextDiscovery(
            self.get_finder(
                [
                    "PoFiles/templates",
                    "PoFiles/templates/MdeMeta.pot",
                    "PoFiles/en/MdeMeta.po",
                    "PoFiles/de/MdeMeta.po",
                ],
            ),
        )
        self.assert_discovery(
            discovery.discover(),
            [
                {
                    "file_format": "po",
                    "filemask": "PoFiles/*/MdeMeta.po",
                    "new_base": "PoFiles/templates/MdeMeta.pot",
                },
                {
                    "file_format": "po-mono",
                    "filemask": "PoFiles/*/MdeMeta.po",
                    "new_base": "PoFiles/templates/MdeMeta.pot",
                    "template": "PoFiles/en/MdeMeta.po",
                },
            ],
        )


class AndroidTest(DiscoveryTestCase):
    def test_basic(self) -> None:
        discovery = AndroidDiscovery(
            self.get_finder(
                [
                    "app/src/res/main/values/strings.xml",
                    "app/src/res/main/values-it/strings.xml",
                    "app/src/res/main/values-it/strings-other.xml",
                ],
            ),
        )
        self.assert_discovery(
            discovery.discover(),
            [
                {
                    "filemask": "app/src/res/main/values-*/strings.xml",
                    "file_format": "aresource",
                    "template": "app/src/res/main/values/strings.xml",
                },
            ],
        )


class MOKOTest(DiscoveryTestCase):
    def test_basic(self) -> None:
        discovery = MOKODiscovery(
            self.get_finder(
                [
                    "app/src/res/main/values/strings.xml",
                    "app/src/res/main/values-it/strings.xml",
                    "app/src/res/main/values-it/strings-other.xml",
                    "src/commonMain/resources/MR/base/strings.xml",
                    "src/commonMain/resources/MR/base/plurals.xml",
                ],
            ),
        )
        self.assert_discovery(
            discovery.discover(),
            [
                {
                    "filemask": "src/commonMain/resources/MR/*/plurals.xml",
                    "template": "src/commonMain/resources/MR/base/plurals.xml",
                    "file_format": "moko-resource",
                },
                {
                    "filemask": "src/commonMain/resources/MR/*/strings.xml",
                    "template": "src/commonMain/resources/MR/base/strings.xml",
                    "file_format": "moko-resource",
                },
            ],
        )


class OSXTest(DiscoveryTestCase):
    def test_basic(self) -> None:
        discovery = OSXDiscovery(
            self.get_finder(
                [
                    "App/Resources/en.lproj/Localizable.strings",
                    "App/Resources/Base.lproj/Other.strings",
                    "App/Resources/ru.lproj/Third.strings",
                ],
            ),
        )
        self.assert_discovery(
            discovery.discover(),
            [
                {
                    "filemask": "App/Resources/*.lproj/Localizable.strings",
                    "file_format": "strings-utf8",
                    "template": "App/Resources/en.lproj/Localizable.strings",
                },
                {
                    "filemask": "App/Resources/*.lproj/Other.strings",
                    "file_format": "strings-utf8",
                    "template": "App/Resources/Base.lproj/Other.strings",
                },
            ],
        )

    def test_pappl(self) -> None:
        discovery = OSXDiscovery(
            self.get_finder(
                [
                    "pappl/strings/de.strings",
                    "pappl/strings/en.strings",
                    "pappl/strings/ja.strings",
                    "pappl/strings/base.strings",
                    "pappl/strings/es.strings",
                    "pappl/strings/fr.strings",
                    "pappl/strings/it.strings",
                    "pappl/strings/ipp.strings",
                ],
            ),
        )
        self.assert_discovery(
            discovery.discover(),
            [
                {
                    "filemask": "pappl/strings/*.strings",
                    "file_format": "strings-utf8",
                    "template": "pappl/strings/base.strings",
                },
            ],
        )


class StringsdictTest(DiscoveryTestCase):
    def test_basic(self) -> None:
        discovery = StringsdictDiscovery(
            self.get_finder(
                [
                    "App/Resources/en.lproj/Localizable.stringsdict",
                    "App/Resources/Base.lproj/Other.stringsdict",
                    "App/Resources/ru.lproj/Third.stringsdict",
                ],
            ),
        )
        self.assert_discovery(
            discovery.discover(),
            [
                {
                    "filemask": "App/Resources/*.lproj/Localizable.stringsdict",
                    "file_format": "stringsdict",
                    "template": "App/Resources/en.lproj/Localizable.stringsdict",
                },
                {
                    "filemask": "App/Resources/*.lproj/Other.stringsdict",
                    "file_format": "stringsdict",
                    "template": "App/Resources/Base.lproj/Other.stringsdict",
                },
            ],
        )


class JavaTest(DiscoveryTestCase):
    def test_basic(self) -> None:
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
                    "foo_en.properties",
                    "foo_de.properties",
                ],
            ),
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
                {
                    "file_format": "properties",
                    "filemask": "foo_*.properties",
                    "template": "foo_en.properties",
                },
            ],
        )


class JoomlaTest(DiscoveryTestCase):
    def test_basic(self) -> None:
        discovery = JoomlaDiscovery(
            self.get_finder(
                [
                    "public/lang/cs.ini",
                    "public/lang/ru.ini",
                    "public/lang/nl.ini",
                    "public/lang/rm.ini",
                    "public/lang/ca.ini",
                    "public/lang/en.ini",
                ],
            ),
        )
        self.assert_discovery(
            discovery.discover(),
            [
                {
                    "filemask": "public/lang/*.ini",
                    "file_format": "joomla",
                    "template": "public/lang/en.ini",
                },
            ],
        )


class RESXTest(DiscoveryTestCase):
    def test_basic(self) -> None:
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
                ],
            ),
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


class ResourceDictionaryTest(DiscoveryTestCase):
    def test_basic(self) -> None:
        discovery = ResourceDictionaryDiscovery(
            self.get_finder(
                [
                    "Languages/de.xaml",
                    "Languages/en.xaml",
                    "Languages/pl.xaml",
                    "Languages/sk.xaml",
                    "Languages/tr.xaml",
                    "Languages/zh-cn.xaml",
                    "Languages/zh-tw.xaml",
                ],
            ),
        )
        self.assert_discovery(
            discovery.discover(),
            [
                {
                    "filemask": "Languages/*.xaml",
                    "file_format": "resourcedictionary",
                    "template": "Languages/en.xaml",
                },
            ],
        )


class XliffTest(DiscoveryTestCase):
    def test_basic(self) -> None:
        discovery = XliffDiscovery(
            self.get_finder(["locales/cs.xliff", "locales/en.xliff"]),
        )
        self.assert_discovery(
            discovery.discover(),
            [
                {
                    "filemask": "locales/*.xliff",
                    "file_format": "xliff",
                    "template": "locales/en.xliff",
                },
            ],
        )

    def test_short(self) -> None:
        discovery = XliffDiscovery(
            self.get_finder(
                [
                    "locales/cs.xlf",
                    "locales/en.xlf",
                    "otherlocales/cs/main.xlf",
                    "otherlocales/cs/help.xlf",
                    "length_1.properties.xlf",
                    "length_1_de.properties.xlf",
                ],
            ),
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
    def test_basic(self) -> None:
        discovery = WebExtensionDiscovery(
            self.get_finder(["_locales/cs/messages.json", "_locales/en/messages.json"]),
        )
        self.assert_discovery(
            discovery.discover(),
            [
                {
                    "filemask": "_locales/*/messages.json",
                    "file_format": "webextension",
                    "template": "_locales/en/messages.json",
                },
            ],
        )


class JSONDiscoveryTest(DiscoveryTestCase):
    def test_basic(self) -> None:
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
                ],
            ),
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

    def test_shell_chars(self) -> None:
        discovery = JSONDiscovery(
            self.get_finder(
                [
                    "src/app/[locale]/_translations/en.json",
                    "src/app/[locale]/_translations/de.json",
                    "src/app/[locale]/_translations/cs.json",
                ],
            ),
        )
        self.assert_discovery(
            discovery.discover(),
            [
                {
                    "filemask": "src/app/[locale]/_translations/*.json",
                    "file_format": "json-nested",
                    "template": "src/app/[locale]/_translations/en.json",
                },
            ],
        )

    def test_json_data(self) -> None:
        """
        Test discovery on huge list of JSON files.

        Based on Cataclysm-DDA, see
        https://github.com/WeblateOrg/translation-finder/issues/54
        """
        test_file = TEST_DATA / "catalysm.txt"
        filenames = test_file.read_text(encoding="utf-8").splitlines()
        discovery = JSONDiscovery(self.get_finder(filenames))
        # This has many false positives, but most of them come from
        # filename starting with language code what is something we generally want
        # to detect
        self.assert_discovery(
            discovery.discover(),
            [
                {
                    "file_format": "json-nested",
                    "filemask": "data/json/mapgen/*_car_dealership.json",
                },
                {
                    "file_format": "json-nested",
                    "filemask": "data/json/mapgen/*_car_showroom.json",
                },
                {
                    "file_format": "json-nested",
                    "filemask": "data/json/mapgen/*_city_dump_small.json",
                },
                {
                    "file_format": "json-nested",
                    "filemask": "data/json/mapgen/*_gardening_allotment.json",
                },
                {
                    "file_format": "json-nested",
                    "filemask": "data/json/mapgen/*_internet_cafe.json",
                },
                {
                    "file_format": "json-nested",
                    "filemask": "data/json/mapgen/*_market_small.json",
                },
                {
                    "file_format": "json-nested",
                    "filemask": "data/json/mapgen/*_open_sewer_small.json",
                },
                {
                    "file_format": "json-nested",
                    "filemask": "data/json/mapgen/*_private_park.json",
                },
                {
                    "file_format": "json-nested",
                    "filemask": "data/json/mapgen/*_public_art_piece.json",
                },
                {
                    "file_format": "json-nested",
                    "filemask": "data/json/mapgen/*_public_space.json",
                },
                {
                    "file_format": "json-nested",
                    "filemask": "data/json/mapgen/*_sex_shop.json",
                },
                {
                    "file_format": "json-nested",
                    "filemask": "data/json/mapgen/*_tire_shop.json",
                },
                {
                    "file_format": "json-nested",
                    "filemask": "data/json/mapgen/house/house05_*.json",
                },
                {
                    "file_format": "json-nested",
                    "filemask": "data/json/mapgen/mi-go/*-go_encampment.json",
                },
                {
                    "file_format": "json-nested",
                    "filemask": "data/json/mapgen/mi-go/*-go_nested.json",
                },
                {
                    "file_format": "json-nested",
                    "filemask": "data/json/mapgen/mi-go/*-go_scout_tower.json",
                },
                {
                    "file_format": "json-nested",
                    "filemask": "data/json/mapgen/refugee_center/rc_grounds_*.json",
                },
                {
                    "file_format": "json-nested",
                    "filemask": "data/json/mapgen_palettes/*-go_palette.json",
                },
                {
                    "file_format": "json-nested",
                    "filemask": "data/json/monstergroups/*-go.json",
                },
                {
                    "file_format": "json-nested",
                    "filemask": "data/json/monsters/*-go.json",
                },
                {
                    "file_format": "json-nested",
                    "filemask": "data/json/npcs/*_trait_groups.json",
                },
                {
                    "file_format": "json-nested",
                    "filemask": "data/json/npcs/*_traits.json",
                },
                {
                    "file_format": "json-nested",
                    "filemask": "data/json/npcs/holdouts/*_Lapin.json",
                },
                {
                    "file_format": "json-nested",
                    "filemask": "data/json/npcs/prisoners/*-go_prisoners.json",
                },
                {
                    "file_format": "json-nested",
                    "filemask": "data/mods/more_classes_scenarios/*_classes.json",
                },
                {
                    "file_format": "json-nested",
                    "filemask": "data/mods/more_classes_scenarios/*_scenarios.json",
                },
                {
                    "file_format": "json-nested",
                    "filemask": "data/mods/more_classes_scenarios/*_locations.json",
                },
                {
                    "file_format": "json-nested",
                    "filemask": "data/names/*.json",
                    "template": "data/names/en.json",
                },
            ],
        )


class TransifexTest(DiscoveryTestCase):
    def test_basic(self) -> None:
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
    def test_basic(self) -> None:
        discovery = AppStoreDiscovery(
            self.get_finder(
                [
                    "metadata/en-AU/short_description.txt",
                    "metadata/en-US/short_description.txt",
                    "private/metadata/en-AU/changelogs/10000.txt",
                    "short_description.txt",
                ],
                ["metadata/en-AU", "metadata/en-US", "private/metadata/en-AU"],
            ),
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
    def test_basic(self) -> None:
        discovery = FluentDiscovery(
            self.get_finder(
                [
                    "browser/locales/en-US/browser/component/file.ftl",
                    "browser/locales/cs-CS/browser/component/file.ftl",
                ],
            ),
        )
        self.assert_discovery(
            discovery.discover(),
            [
                {
                    "filemask": "browser/locales/*/browser/component/file.ftl",
                    "file_format": "fluent",
                    "template": "browser/locales/en-US/browser/component/file.ftl",
                },
            ],
        )


class YAMLDiscoveryTest(DiscoveryTestCase):
    def test_basic(self) -> None:
        discovery = YAMLDiscovery(
            self.get_finder(
                ["translations/en/messages.en.yml", "translations/de/messages.de.yml"],
            ),
        )
        self.assert_discovery(
            discovery.discover(),
            [
                {
                    "filemask": "translations/*/messages.*.yml",
                    "file_format": "yaml",
                    "template": "translations/en/messages.en.yml",
                },
            ],
        )

    def test_workflows(self) -> None:
        discovery = YAMLDiscovery(
            self.get_finder(
                [
                    ".github/workflows/json.yml",
                    ".github/workflows/pr-validator.yml",
                    ".github/workflows/ccpp.yml",
                ],
            ),
        )
        self.assert_discovery(discovery.discover(), [])


class TOMLDiscoveryTest(DiscoveryTestCase):
    def test_basic(self) -> None:
        discovery = TOMLDiscovery(
            self.get_finder(
                [
                    "translations/en/messages.en.toml",
                    "translations/de/messages.de.toml",
                ],
            ),
        )
        self.assert_discovery(
            discovery.discover(),
            [
                {
                    "filemask": "translations/*/messages.*.toml",
                    "file_format": "toml",
                    "template": "translations/en/messages.en.toml",
                },
            ],
        )


class ARBDiscoveryTest(DiscoveryTestCase):
    def test_basic(self) -> None:
        discovery = ARBDiscovery(
            self.get_finder(
                [
                    "lib/l10n/intl_en.arb",
                    "lib/l10n/intl_messages.arb",
                    "lib/l10n/intl_cs.arb",
                    "res/values/strings_en.arb",
                ],
            ),
        )
        self.assert_discovery(
            discovery.discover(),
            [
                {
                    "filemask": "lib/l10n/intl_*.arb",
                    "file_format": "arb",
                    "template": "lib/l10n/intl_en.arb",
                    "intermediate": "lib/l10n/intl_messages.arb",
                },
                {
                    "filemask": "res/values/strings_*.arb",
                    "file_format": "arb",
                    "template": "res/values/strings_en.arb",
                },
            ],
        )


class HTMLDiscoveryTest(DiscoveryTestCase):
    def test_basic(self) -> None:
        discovery = HTMLDiscovery(self.get_finder(["docs/en.html", "docs/cs.html"]))
        self.assert_discovery(
            discovery.discover(),
            [
                {
                    "filemask": "docs/*.html",
                    "file_format": "html",
                    "template": "docs/en.html",
                    "new_base": "docs/en.html",
                },
            ],
        )


class CSVDiscoveryTest(DiscoveryTestCase):
    def test_basic(self) -> None:
        discovery = CSVDiscovery(self.get_finder(["csv/en.csv", "csv/cs.csv"]))
        self.assert_discovery(
            discovery.discover(),
            [
                {
                    "filemask": "csv/*.csv",
                    "file_format": "csv",
                    "new_base": "csv/en.csv",
                },
                {
                    "filemask": "csv/*.csv",
                    "file_format": "csv",
                    "template": "csv/en.csv",
                    "new_base": "csv/en.csv",
                },
            ],
        )


class PHPDiscoveryTest(DiscoveryTestCase):
    def test_basic(self) -> None:
        discovery = PHPDiscovery(self.get_finder(["test/en.php"]))
        self.assert_discovery(
            discovery.discover(),
            [
                {
                    "filemask": "test/*.php",
                    "file_format": "php",
                    "template": "test/en.php",
                    "new_base": "test/en.php",
                },
            ],
        )


class RCDiscoveryTest(DiscoveryTestCase):
    def test_basic(self) -> None:
        discovery = RCDiscovery(self.get_finder(["test_enu.rc", "other_ENU.rc"]))
        self.assert_discovery(
            discovery.discover(),
            [
                {
                    "filemask": "test_*.rc",
                    "file_format": "rc",
                    "template": "test_enu.rc",
                    "new_base": "test_enu.rc",
                },
                {
                    "filemask": "other_*.rc",
                    "file_format": "rc",
                    "template": "other_ENU.rc",
                    "new_base": "other_ENU.rc",
                },
            ],
        )


class TXTDiscoveryTest(DiscoveryTestCase):
    def test_basic(self) -> None:
        discovery = TXTDiscovery(
            self.get_finder(
                [
                    "foo/en.txt",
                    "bar/cs.txt",
                    "baz/other.txt",
                ],
            ),
        )
        self.assert_discovery(
            discovery.discover(),
            [
                {
                    "filemask": "bar/*.txt",
                    "file_format": "txt",
                },
                {
                    "filemask": "foo/*.txt",
                    "template": "foo/en.txt",
                    "new_base": "foo/en.txt",
                    "file_format": "txt",
                },
            ],
        )

    def test_hint(self) -> None:
        discovery = TXTDiscovery(
            self.get_finder(
                [
                    "baz/other.txt",
                ],
            ),
        )
        self.assert_discovery(
            discovery.discover(hint="baz/*.txt"),
            [
                {
                    "filemask": "baz/*.txt",
                    "file_format": "txt",
                },
            ],
        )


class FormatJSDiscoveryTest(DiscoveryTestCase):
    def test_basic(self) -> None:
        discovery = FormatJSDiscovery(
            self.get_finder(
                [
                    "src/lang/cs.json",
                    "src/extracted/en.json",
                ],
            ),
        )
        self.assert_discovery(
            discovery.discover(),
            [
                {
                    "filemask": "src/lang/*.json",
                    "template": "src/extracted/en.json",
                    "file_format": "formatjs",
                },
            ],
        )

    def test_nontranslated(self) -> None:
        discovery = FormatJSDiscovery(
            self.get_finder(
                [
                    "src/extracted/en.json",
                ],
            ),
        )
        self.assert_discovery(
            discovery.discover(),
            [
                {
                    "filemask": "src/lang/*.json",
                    "template": "src/extracted/en.json",
                    "file_format": "formatjs",
                },
            ],
        )
