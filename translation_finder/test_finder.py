# Copyright © Michal Čihař <michal@weblate.org>
#
# SPDX-License-Identifier: GPL-3.0-or-later
"""File finder tests."""

import pathlib
import tempfile
from fnmatch import translate
from unittest import TestCase
from unittest.mock import patch

from .finder import Finder


class FinderTest(TestCase):
    @staticmethod
    def get_finder(paths: list[str]) -> Finder:
        return Finder(
            pathlib.PurePath(),
            mock=(
                [
                    (
                        pathlib.PurePath(path),
                        pathlib.PurePath(path),
                        path,
                    )
                    for path in paths
                ],
                [],
            ),
        )

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

    def test_filter_masks_exact_name(self) -> None:
        finder = self.get_finder(
            [
                "locale/cs/messages.json",
                "locale/en/messages.json",
                "locale/en/other.json",
                "locale/en/messages.po",
            ],
        )

        self.assertEqual(
            list(finder.filter_masks("messages.json")),
            [
                pathlib.PurePath("locale/cs/messages.json"),
                pathlib.PurePath("locale/en/messages.json"),
            ],
        )

    def test_filter_masks_suffix(self) -> None:
        finder = self.get_finder(
            [
                "locale/en/messages.po",
                "locale/cs/messages.po",
                "locale/en/messages.json",
            ],
        )

        self.assertEqual(
            list(finder.filter_masks("*.po")),
            [
                pathlib.PurePath("locale/cs/messages.po"),
                pathlib.PurePath("locale/en/messages.po"),
            ],
        )

    def test_filter_masks_empty(self) -> None:
        finder = self.get_finder(["locale/en/messages.po"])

        self.assertEqual(list(finder.filter_masks(())), [])

    def test_glob_suffix_candidate_without_glob_magic(self) -> None:
        self.assertEqual(Finder.glob_suffix_candidate("messages.po"), ".po")

    def test_filter_files_candidate_hints_match_full_scan(self) -> None:
        finder = self.get_finder(
            [
                "locale/en/app.resx",
                "locale/cs/app.resx",
                "locale/de/app.resw",
                "locale/de/app.po",
            ],
        )

        expected = list(finder.filter_files(r".*\.res[xw]"))
        actual = list(
            finder.filter_files(
                r".*\.res[xw]",
                candidate_suffixes=(".resx", ".resw"),
            ),
        )

        self.assertEqual(actual, expected)

    def test_filter_masks_fallback_matches_filter_files(self) -> None:
        finder = self.get_finder(
            [
                "locale/en/resources.resx",
                "locale/en/resources.resw",
                "locale/en/resources.resz",
            ],
        )

        self.assertEqual(
            list(finder.filter_masks("resources.res[xw]")),
            list(finder.filter_files(translate("resources.res[xw]"))),
        )

    def test_mask_matches_uses_literal_question_and_bracket(self) -> None:
        finder = self.get_finder(
            [
                "locale/en?.json",
                "locale/en[1].json",
                "locale/enx.json",
            ],
        )

        self.assertEqual(
            list(finder.mask_matches("locale/en?.json")),
            [pathlib.PurePath("locale/en?.json")],
        )
        self.assertEqual(
            list(finder.mask_matches("locale/en[1].json")),
            [pathlib.PurePath("locale/en[1].json")],
        )

    def test_mask_matches_falls_back_for_suffixless_wildcard(self) -> None:
        finder = self.get_finder(
            [
                "locale/messages",
                "locale/messages.po",
                "other/messages",
            ],
        )

        self.assertEqual(
            list(finder.mask_matches("locale/*")),
            [
                pathlib.PurePath("locale/messages"),
                pathlib.PurePath("locale/messages.po"),
            ],
        )

    def test_unreadable_directories_are_skipped(self) -> None:
        class FakeEntry:
            def __init__(self, path: pathlib.Path) -> None:
                self.path = path

            @staticmethod
            def is_symlink() -> bool:
                return False

            @staticmethod
            def is_dir() -> bool:
                return True

        class FakeScandir:
            def __init__(self, entries: list[FakeEntry]) -> None:
                self.entries = entries

            def __enter__(self) -> list[FakeEntry]:
                return self.entries

            def __exit__(
                self,
                exc_type: object,
                exc_value: object,
                traceback: object,
            ) -> None:
                return None

        with tempfile.TemporaryDirectory() as tmpdir:
            root = pathlib.Path(tmpdir)
            blocked = root / "blocked"

            def fake_scandir(path: pathlib.Path) -> FakeScandir:
                if path == root:
                    return FakeScandir([FakeEntry(blocked)])
                raise OSError

            with patch("translation_finder.finder.scandir", side_effect=fake_scandir):
                finder = Finder(root)

        self.assertEqual(finder.files, [])
        self.assertEqual(finder.dirnames, {"blocked"})

    def test_open_mock_file_rejects_non_real_path(self) -> None:
        finder = Finder(
            pathlib.PurePath(),
            mock=(
                [
                    (
                        pathlib.PurePath("mock.txt"),
                        pathlib.PurePath("mock.txt"),
                        "mock.txt",
                    ),
                ],
                [],
            ),
        )
        with self.assertRaisesRegex(TypeError, "Not a real file"):
            finder.open(pathlib.PurePath("mock.txt"))

    def test_generated_directories_are_skipped(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = pathlib.Path(tmpdir)
            for dirname in ("build", "dist", "node_modules", "package.egg-info"):
                directory = root / dirname
                directory.mkdir()
                (directory / "messages.po").write_text("", encoding="utf-8")

            finder = Finder(root)

        self.assertEqual(finder.files, [])
