# Copyright © Michal Čihař <michal@weblate.org>
#
# SPDX-License-Identifier: GPL-3.0-or-later
"""Fuzz tests for discovery behavior."""

from __future__ import annotations

from pathlib import PurePath
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
