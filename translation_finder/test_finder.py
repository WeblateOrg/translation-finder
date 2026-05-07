# Copyright © Michal Čihař <michal@weblate.org>
#
# SPDX-License-Identifier: GPL-3.0-or-later
"""File finder tests."""

import pathlib
import tempfile
from unittest import TestCase
from unittest.mock import patch

from .finder import Finder


class FinderTest(TestCase):
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
