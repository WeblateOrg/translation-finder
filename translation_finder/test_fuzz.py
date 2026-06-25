# Copyright © Michal Čihař <michal@weblate.org>
#
# SPDX-License-Identifier: GPL-3.0-or-later
"""Fuzz tests for discovery behavior."""

from __future__ import annotations

import json
import tempfile
import warnings
from pathlib import Path, PurePath
from typing import TYPE_CHECKING
from unittest import TestCase

from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from .api import discover
from .discovery.base import BaseDiscovery
from .discovery.result import DiscoveryResult
from .finder import Finder

if TYPE_CHECKING:
    from collections.abc import Iterable

FUZZ_SETTINGS = settings(
    deadline=None,
    derandomize=True,
    max_examples=40,
    suppress_health_check=[HealthCheck.too_slow],
)

LANGUAGE_CODES = st.sampled_from(
    ("en", "cs", "de", "es", "fr", "pt_BR", "pt-BR", "zh_Hans", "sr_Latn"),
)
EXTENSIONS = st.sampled_from(
    (
        "arb",
        "catkeys",
        "csv",
        "dtd",
        "ftl",
        "html",
        "json",
        "lang",
        "md",
        "php",
        "po",
        "pot",
        "properties",
        "rc",
        "resx",
        "strings",
        "toml",
        "ts",
        "txt",
        "xlf",
        "xliff",
        "xml",
        "yaml",
        "yml",
    ),
)
NAME_TOKEN = st.text(
    alphabet="abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_-",
    min_size=1,
    max_size=12,
)
CONTENT_VALUE = st.text(
    alphabet="abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789 _-{}[]<>/=:,.;\n\t|@",
    max_size=80,
)
DIRECTORY = st.one_of(
    st.sampled_from(("app", "i18n", "locale", "locales", "po", "resources", "src")),
    NAME_TOKEN,
)
STRING_RESULT_FIELDS = (
    "file_format",
    "filemask",
    "intermediate",
    "language_regex",
    "name",
    "new_base",
    "template",
)
FileContent = str | bytes
FileSet = dict[str, FileContent]


@st.composite
def path_name(draw: st.DrawFn) -> str:
    """Generate a valid relative translation-like path."""
    language = draw(LANGUAGE_CODES)
    extension = draw(EXTENSIONS)
    name = draw(NAME_TOKEN)
    dirs = draw(st.lists(DIRECTORY, max_size=3))
    pattern = draw(
        st.sampled_from(
            (
                "android",
                "dot",
                "language_dir",
                "language_file",
                "prefixed_dash",
                "prefixed_underscore",
            ),
        ),
    )

    if pattern == "android":
        parts = [*dirs, f"values-{language}", "strings.xml"]
    elif pattern == "dot":
        parts = [*dirs, f"{name}.{language}.{extension}"]
    elif pattern == "language_dir":
        parts = [*dirs, language, f"{name}.{extension}"]
    elif pattern == "language_file":
        parts = [*dirs, f"{language}.{extension}"]
    elif pattern == "prefixed_dash":
        parts = [*dirs, f"{name}-{language}.{extension}"]
    else:
        parts = [*dirs, f"{name}_{language}.{extension}"]

    return "/".join(parts)


PATH_NAMES = st.lists(path_name(), min_size=1, max_size=16, unique=True)


def language_pair(directory: str, extension: str, content: FileContent) -> FileSet:
    """Build source and target files for template-based discovery."""
    return {
        f"{directory}/en.{extension}": content,
        f"{directory}/cs.{extension}": content,
    }


def json_files(draw: st.DrawFn) -> FileSet:
    """Generate JSON files with valid or invalid translation-like content."""
    key = draw(NAME_TOKEN)
    value = draw(CONTENT_VALUE)
    variant = draw(st.sampled_from(("flat", "go", "invalid", "nested", "webext")))

    if variant == "flat":
        content: FileContent = json.dumps({key: value})
    elif variant == "go":
        content = json.dumps([{"id": key, "translation": value}])
    elif variant == "nested":
        content = json.dumps({key: {"message": value}})
    elif variant == "webext":
        content = json.dumps({key: {"description": value, "message": value}})
    else:
        content = value

    if draw(st.booleans()):
        content = b"\xef\xbb\xbf" + str(content).encode()
    return language_pair("json", "json", content)


def yaml_files(draw: st.DrawFn) -> FileSet:
    """Generate YAML files with valid or malformed content."""
    key = draw(NAME_TOKEN)
    value = draw(CONTENT_VALUE)
    content = draw(
        st.sampled_from(
            (
                f"en:\n  {key}: {value!r}\n",
                f"{key}: {value!r}\n",
                f"en: {value!r}\ncs: {value!r}\n",
                "[broken\n",
            ),
        ),
    )
    return language_pair("yaml", "yml", content)


def toml_files(draw: st.DrawFn) -> FileSet:
    """Generate TOML files with valid or malformed content."""
    key = draw(NAME_TOKEN)
    value = draw(CONTENT_VALUE)
    content = draw(
        st.sampled_from(
            (
                f"{key} = {json.dumps(value)}\n",
                f'[[messages]]\nid = "{key}"\nmessage = {json.dumps(value)}\n',
                "[broken\n",
            ),
        ),
    )
    return language_pair("toml", "toml", content)


def csv_files(draw: st.DrawFn) -> FileSet:
    """Generate CSV files with simple and multivalue shapes."""
    key = draw(NAME_TOKEN)
    value = draw(CONTENT_VALUE)
    content = draw(
        st.sampled_from(
            (
                f"{key},{value}\n",
                f"context,source,target\n{key},{value},{value}\n",
                f"context,source,target\n{key},{value},{value}\n{key},{value},other\n",
                value,
            ),
        ),
    )
    return language_pair("csv", "csv", content)


def php_files(draw: st.DrawFn) -> FileSet:
    """Generate PHP translation files."""
    key = draw(NAME_TOKEN)
    value = draw(CONTENT_VALUE)
    content = draw(
        st.sampled_from(
            (
                f"<?php\nreturn ['{key}' => '{value}|other'];\n",
                f"<?php\nreturn [{key!r} => {value!r}];\n",
                value,
            ),
        ),
    )
    return language_pair("php", "php", content)


def properties_files(draw: st.DrawFn) -> FileSet:
    """Generate Java properties files."""
    key = draw(NAME_TOKEN)
    value = draw(CONTENT_VALUE)
    content = draw(
        st.sampled_from(
            (
                f"{key}={value}\n",
                f"{key}[one]=one\n{key}[other]=other\n",
                f"# XWiki\n{key}={value}\n",
                value,
            ),
        ),
    )
    return {
        "java/messages.properties": content,
        "java/messages_cs.properties": content,
    }


def xliff_files(draw: st.DrawFn) -> FileSet:
    """Generate XLIFF-like files."""
    value = draw(CONTENT_VALUE)
    content = draw(
        st.sampled_from(
            (
                f'<xliff version="2.0"><file><unit><segment>{value}</segment></unit></file></xliff>',
                '<xliff version="2.1"><pc>wrapped</pc></xliff>',
                '<xliff><file original="Localizable.strings"></file></xliff>',
                f"<xliff>{value}</xliff>",
            ),
        ),
    )
    return language_pair("xliff", "xliff", content)


def android_files(draw: st.DrawFn) -> FileSet:
    """Generate Android resource files."""
    key = draw(NAME_TOKEN)
    value = draw(CONTENT_VALUE)
    content = draw(
        st.sampled_from(
            (
                f'<resources><string name="{key}">{value}</string></resources>',
                '<resources><plural name="count"><item quantity="one">One</item></plural></resources>',
                value,
            ),
        ),
    )
    return {
        "app/src/main/res/values/strings.xml": content,
        "app/src/main/res/values-cs/strings.xml": content,
    }


def flat_xml_files(draw: st.DrawFn) -> FileSet:
    """Generate flat XML files."""
    value = draw(CONTENT_VALUE)
    content = draw(
        st.sampled_from(
            (
                "<xwikidoc><syntaxId>plain/1.0</syntaxId></xwikidoc>",
                "<xwikidoc><syntaxId>xwiki/2.1</syntaxId></xwikidoc>",
                f"<root>{value}</root>",
            ),
        ),
    )
    return language_pair("xml", "xml", content)


def transifex_files(draw: st.DrawFn) -> FileSet:
    """Generate Transifex configuration files."""
    key = draw(NAME_TOKEN)
    content = draw(
        st.sampled_from(
            (
                f"[o:{key}:p]\nfile_filter = locale/<lang>.json\nsource_file = locale/en.json\ntype = KEYVALUEJSON\n",
                "[main\nbroken\n",
                "",
            ),
        ),
    )
    return {
        ".tx/config": content,
        "locale/en.json": json.dumps({"hello": "world"}),
        "locale/cs.json": json.dumps({"hello": "svet"}),
    }


CONTENT_FILE_BUILDERS = (
    android_files,
    csv_files,
    flat_xml_files,
    json_files,
    php_files,
    properties_files,
    toml_files,
    transifex_files,
    xliff_files,
    yaml_files,
)


@st.composite
def content_file_set(draw: st.DrawFn) -> FileSet:
    """Generate real file trees whose content is inspected by discovery."""
    builder = draw(st.sampled_from(CONTENT_FILE_BUILDERS))
    return builder(draw)


@st.composite
def wildcard_part(draw: st.DrawFn) -> str:
    """Generate one path part that might contain a language code."""
    language = draw(LANGUAGE_CODES)
    extension = draw(EXTENSIONS)
    name = draw(NAME_TOKEN)
    pattern = draw(
        st.sampled_from(
            (
                "directory_language",
                "dot",
                "language_file",
                "prefixed_dash",
                "prefixed_underscore",
                "plain",
            ),
        ),
    )

    if pattern == "directory_language":
        return language
    if pattern == "dot":
        return f"{name}.{language}.{extension}"
    if pattern == "language_file":
        return f"{language}.{extension}"
    if pattern == "prefixed_dash":
        return f"{name}-{language}.{extension}"
    if pattern == "prefixed_underscore":
        return f"{name}_{language}.{extension}"
    return f"{name}.{extension}"


def make_path_items(paths: Iterable[str]) -> list[tuple[PurePath, PurePath, str]]:
    """Build finder mock entries from relative path names."""
    return [(PurePath(path), PurePath(path), path) for path in sorted(paths)]


def make_dir_items(paths: Iterable[str]) -> list[tuple[PurePath, PurePath, str]]:
    """Build finder mock directory entries from relative path names."""
    directories: set[str] = set()
    for path in paths:
        parts = PurePath(path).parts[:-1]
        directories.update("/".join(parts[:pos]) for pos in range(1, len(parts) + 1))
    return make_path_items(directories)


def write_files(root: Path, files: FileSet) -> None:
    """Write generated file content under a temporary root."""
    for filename, content in files.items():
        path = root / filename
        path.parent.mkdir(parents=True, exist_ok=True)
        if isinstance(content, bytes):
            path.write_bytes(content)
        else:
            path.write_text(content, encoding="utf-8")


def discover_real_files(files: FileSet) -> list[DiscoveryResult]:
    """Run discovery on generated real files, ignoring expected parser warnings."""
    with tempfile.TemporaryDirectory() as tmpdir:
        root = Path(tmpdir)
        write_files(root, files)
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            return discover(root)


class FuzzTest(TestCase):
    @FUZZ_SETTINGS
    @given(paths=PATH_NAMES)
    def test_finder_accepts_generated_mock_paths(self, paths: list[str]) -> None:
        finder = Finder(
            PurePath(),
            mock=(make_path_items(paths), make_dir_items(paths)),
        )

        self.assertEqual(finder.filenames, set(paths))
        for path in paths:
            self.assertEqual(list(finder.mask_matches(path)), [PurePath(path)])

    @FUZZ_SETTINGS
    @given(part=wildcard_part())
    def test_wildcard_generation_returns_valid_path_part(self, part: str) -> None:
        discovery = BaseDiscovery(Finder(PurePath(), mock=([], [])))

        wildcard = discovery.get_wildcard(part)

        if wildcard is not None:
            self.assertIn("*", wildcard)
            self.assertNotIn("/", wildcard)
            self.assertEqual(wildcard.strip(), wildcard)

    @FUZZ_SETTINGS
    @given(eager=st.booleans(), paths=PATH_NAMES, source_language=LANGUAGE_CODES)
    def test_discovery_accepts_generated_mock_paths(
        self,
        eager: bool,  # noqa: FBT001
        paths: list[str],
        source_language: str,
    ) -> None:
        results = discover(
            PurePath(),
            eager=eager,
            mock=(make_path_items(paths), make_dir_items(paths)),
            source_language=source_language,
        )

        self.assertEqual(sorted(results), results)
        for result in results:
            self.assertIsInstance(result, DiscoveryResult)
            self.assert_valid_result(result)

    @FUZZ_SETTINGS
    @given(files=content_file_set())
    def test_discovery_accepts_generated_file_contents(self, files: FileSet) -> None:
        results = discover_real_files(files)

        self.assertEqual(sorted(results), results)
        for result in results:
            self.assertIsInstance(result, DiscoveryResult)
            self.assert_valid_result(result)

    def assert_valid_result(self, result: DiscoveryResult) -> None:
        self.assertIn("filemask", result)
        self.assertIn("file_format", result)
        self.assertIsInstance(result.meta["discovery"], str)
        self.assertIsInstance(result.meta["priority"], int)
        self.assertIsInstance(result.meta["origin"], str | None)

        for field in STRING_RESULT_FIELDS:
            if field in result:
                self.assertIsInstance(result[field], str)

        if "file_format_params" in result:
            params = result["file_format_params"]
            self.assertIsInstance(params, dict)
            for key, value in params.items():
                self.assertIsInstance(key, str)
                self.assertIsInstance(value, str | int | bool)
