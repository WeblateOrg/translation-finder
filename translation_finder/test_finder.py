# Copyright © Michal Čihař <michal@weblate.org>
#
# SPDX-License-Identifier: GPL-3.0-or-later
"""File finder tests."""

import os
import pathlib
import socket
import subprocess  # ruff: ignore[suspicious-subprocess-import]
import sys
import tempfile
from fnmatch import translate
from unittest import TestCase, skipUnless
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
            def is_dir(*, follow_symlinks: bool = True) -> bool:
                return not follow_symlinks

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

    def test_deep_directories_are_scanned_iteratively(self) -> None:
        class FakeEntry:
            def __init__(self, path: pathlib.Path, *, is_dir: bool) -> None:
                self.path = path
                self._is_dir = is_dir

            @staticmethod
            def is_symlink() -> bool:
                return False

            def is_dir(self, *, follow_symlinks: bool = True) -> bool:
                return self._is_dir

            def is_file(self, *, follow_symlinks: bool = True) -> bool:
                return not self._is_dir

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

        root = pathlib.Path("root")
        depth = sys.getrecursionlimit() + 10

        def fake_scandir(path: pathlib.Path) -> FakeScandir:
            current_depth = len(path.parts) - len(root.parts)
            if current_depth < depth:
                return FakeScandir([FakeEntry(path / "d", is_dir=True)])
            return FakeScandir([FakeEntry(path / "messages.po", is_dir=False)])

        with patch("translation_finder.finder.scandir", side_effect=fake_scandir):
            finder = Finder(root)

        deep_file = pathlib.Path(*(["d"] * depth), "messages.po").as_posix()
        self.assertEqual(len(finder.dirnames), depth)
        self.assertTrue(finder.has_file(deep_file))

    def test_unreadable_root_is_reported(self) -> None:
        root = pathlib.Path("root")
        with (
            patch("translation_finder.finder.scandir", side_effect=OSError),
            self.assertRaises(OSError),
        ):
            Finder(root)

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
            for dirname in (
                "build",
                "dist",
                "node_modules",
                "package.egg-info",
                ".ruff_cache",
                ".mypy_cache",
            ):
                directory = root / dirname
                directory.mkdir()
                (directory / "messages.po").write_text("", encoding="utf-8")

            finder = Finder(root)

        self.assertEqual(finder.files, [])
        self.assertEqual(finder.dirnames, set())


class FinderOpenTest(TestCase):
    def test_open_regular_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = pathlib.Path(tmpdir)
            (root / "en.json").write_bytes(b'{"hello": "world"}')
            finder = Finder(root)
            for nofollow in (getattr(os, "O_NOFOLLOW", 0), 0):
                with (
                    self.subTest(nofollow=nofollow),
                    patch.object(os, "O_NOFOLLOW", nofollow, create=True),
                ):
                    with finder.open(pathlib.Path("en.json")) as handle:
                        self.assertEqual(handle.read(), '{"hello": "world"}')
                    with finder.open(pathlib.Path("en.json"), "rb") as handle:
                        self.assertEqual(handle.read(), b'{"hello": "world"}')

    def test_open_fstat_failure_closes_descriptor(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = pathlib.Path(tmpdir)
            (root / "en.json").touch()
            finder = Finder(root)
            with (
                patch.object(os, "fstat", side_effect=OSError("stat failed")),
                patch.object(os, "close", wraps=os.close) as close,
                self.assertRaisesRegex(OSError, "stat failed"),
            ):
                finder.open(pathlib.Path("en.json"))
            close.assert_called_once()
            with self.assertRaises(OSError):
                os.fstat(close.call_args.args[0])

    def test_open_replaced_directory_without_nofollow(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = pathlib.Path(tmpdir)
            path = root / "en.json"
            path.touch()
            finder = Finder(root)
            path.unlink()
            path.mkdir()
            with (
                patch.object(os, "O_NOFOLLOW", 0, create=True),
                self.assertRaisesRegex(OSError, "Not a regular file"),
            ):
                finder.open(pathlib.Path("en.json"))

    # Coverage includes tests; platform-specific bodies cannot run on Windows.
    @skipUnless(sys.platform != "win32", "Requires symlink support")  # pragma: no cover
    def test_open_replaced_symlink(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = pathlib.Path(tmpdir)
            path = root / "en.json"
            path.touch()
            (root / "target.json").write_text("{}")
            finder = Finder(root)
            path.unlink()
            path.symlink_to(root / "target.json")
            for nofollow in (getattr(os, "O_NOFOLLOW", 0), 0):
                with (
                    self.subTest(nofollow=nofollow),
                    patch.object(os, "O_NOFOLLOW", nofollow, create=True),
                    self.assertRaises(OSError),
                ):
                    finder.open(pathlib.Path("en.json"))

    @skipUnless(hasattr(os, "mkfifo"), "Requires FIFOs")  # pragma: no cover
    def test_fifo_discovery_and_replacement_do_not_block(self) -> None:
        # Keep potentially blocking operations in a child that can be killed.
        script = """
import os
import sys
from pathlib import Path
from unittest import TestCase
from unittest.mock import patch
from translation_finder import discover
from translation_finder.finder import Finder

check = TestCase()
root = Path(sys.argv[1])
path = root / "en.json"
os.mkfifo(path)
finder = Finder(root)
check.assertFalse(finder.has_file("en.json"))
check.assertEqual(list(finder.mask_matches("*.json")), [])
check.assertEqual(list(finder.filter_masks("*.json")), [])
check.assertEqual(discover(root), [])
check.assertEqual(discover(root, eager=True), [])
path.unlink()
path.write_text('{}')
check.assertTrue(discover(root))
finder = Finder(root)
path.unlink()
os.mkfifo(path)
with patch.object(os, "close", wraps=os.close) as close:
    with check.assertRaises(OSError):
        finder.open(Path("en.json"), "rb")
    close.assert_called_once()
    with check.assertRaises(OSError):
        os.fstat(close.call_args.args[0])
"""
        with tempfile.TemporaryDirectory() as tmpdir:
            result = subprocess.run(  # ruff: ignore[subprocess-without-shell-equals-true]
                [sys.executable, "-c", script, tmpdir],
                check=True,
                capture_output=True,
                timeout=10,
            )
            self.assertEqual(result.stdout, b"")

    @skipUnless(sys.platform != "win32", "Requires Unix sockets")  # pragma: no cover
    def test_socket_is_not_indexed(self) -> None:
        with (
            tempfile.TemporaryDirectory() as tmpdir,
            socket.socket(socket.AF_UNIX) as server,
        ):
            root = pathlib.Path(tmpdir)
            server.bind(str(root / "en.json"))
            (root / "cs.json").write_text("{}")
            finder = Finder(root)
            self.assertEqual(finder.filenames, {"cs.json"})
            self.assertEqual(
                list(finder.filter_masks("*.json")), [pathlib.Path("cs.json")]
            )

    def test_open_nonregular_descriptor_is_closed(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = pathlib.Path(tmpdir)
            (root / "en.json").touch()
            finder = Finder(root)
            with (
                patch.object(os, "fstat", return_value=os.stat_result((0,) * 10)),
                patch.object(os, "close", wraps=os.close) as close,
                self.assertRaisesRegex(OSError, "Not a regular file"),
            ):
                finder.open(pathlib.Path("en.json"))
            close.assert_called_once()
            with self.assertRaises(OSError):
                os.fstat(close.call_args.args[0])
