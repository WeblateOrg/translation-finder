# Copyright © Michal Čihař <michal@weblate.org>
#
# SPDX-License-Identifier: GPL-3.0-or-later
# ruff: file-ignore[private-member-access]

"""Regression tests for compact discovery references and path boundaries."""

from __future__ import annotations

import tempfile
from pathlib import Path, PurePosixPath, PureWindowsPath
from typing import cast
from unittest import TestCase

from translation_finder._paths import (
    DirectoryRecord,
    DiscoveryPath,
    FileRecord,
    absolute_path,
    is_real_path,
    path_key,
    path_sort_key,
    relative_path,
)
from translation_finder.discovery.files import GettextDiscovery
from translation_finder.discovery.result import DiscoveryCandidate
from translation_finder.finder import Finder


class PathRecordTest(TestCase):
    def test_shared_components_and_materialization(self) -> None:
        parent = DirectoryRecord(
            Path("repository/catalogs"), Path("catalogs"), "catalogs"
        )
        first = FileRecord(parent, "cs.po", "catalogs/cs.po")
        second = FileRecord(parent, "en.po", "catalogs/en.po")
        self.assertIs(first.parent, parent.relative)
        self.assertIs(first.parts[0], second.parts[0])
        self.assertIs(first.as_posix(), first.text)
        self.assertEqual(relative_path(first), Path("catalogs/cs.po"))
        self.assertEqual(absolute_path(first), Path("repository/catalogs/cs.po"))
        self.assertEqual(parent.lower_text, "catalogs")
        self.assertTrue(is_real_path(first))
        self.assertTrue(is_real_path(Path("mock.po")))
        pure = PurePosixPath("mock.po")
        self.assertIs(relative_path(pure), pure)
        self.assertIs(absolute_path(pure), pure)
        self.assertFalse(is_real_path(pure))

    def test_path_identity_and_ordering(self) -> None:
        for path_class in (PurePosixPath, PureWindowsPath):
            with self.subTest(path_class=path_class):
                parent = DirectoryRecord(
                    path_class("repository/Folder"), path_class("Folder"), "Folder"
                )
                record = FileRecord(parent, "a.po", "Folder/a.po")
                original = path_class("Folder/a.po")
                self.assertEqual(path_key(record), path_key(original))
                self.assertEqual(path_sort_key(record), path_sort_key(original))
                self.assertEqual(
                    path_key(record) == path_key(path_class("folder/A.po")),
                    path_class is PureWindowsPath,
                )
                values = [
                    path_class(value)
                    for value in ("a/b.po", "a-b.po", "A/c.po", "a/B.po")
                ]
                self.assertEqual(sorted(values, key=path_sort_key), sorted(values))
                self.assertEqual(
                    path_sort_key(record) < path_sort_key(path_class("Folder/z.po")),
                    original < path_class("Folder/z.po"),
                )
        self.assertNotEqual(
            path_key(PurePosixPath("a.po")), path_key(PureWindowsPath("a.po"))
        )

    def test_candidate_merges_records_and_paths(self) -> None:
        parent = DirectoryRecord(Path("repository"), Path(), "")
        record = FileRecord(parent, "en.po", "en.po")
        original = Path("en.po")
        references: list[DiscoveryPath] = [record, original]
        additional: list[DiscoveryPath] = [original, Path("cs.po"), record]
        candidate = DiscoveryCandidate({"filemask": "*.po"}, iter(references))
        candidate.merge_paths(iter(additional))
        self.assertEqual(candidate.paths, [record, Path("cs.po")])
        reverse = DiscoveryCandidate({"filemask": "*.po"}, [original, record])
        self.assertEqual(reverse.paths, [original])

    def test_public_paths_and_internal_record_caches(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            (root / "catalogs").mkdir()
            for name in ("cs.po", "en.po"):
                (root / "catalogs" / name).touch()
            finder = Finder(root)
            records = list(finder._mask_records("catalogs/*.po"))
            self.assertTrue(all(isinstance(record, FileRecord) for record in records))
            self.assertIsInstance(records[0], FileRecord)
            first = cast("FileRecord", records[0])
            second = cast("FileRecord", records[1])
            self.assertIs(first.directory, second.directory)
            for paths in (
                finder.mask_matches("catalogs/*.po"),
                finder.filter_masks("*.po"),
                finder.filter_files(r".*\.po"),
                (entry[2] for entry in finder.get_lc_candidates(None, None)),
            ):
                collected = list(paths)
                self.assertEqual(
                    collected, [Path("catalogs/cs.po"), Path("catalogs/en.po")]
                )
                self.assertTrue(all(isinstance(path, Path) for path in collected))
            self.assertEqual(
                finder._mask_matches_cache["catalogs/*.po"], tuple(records)
            )
            candidates = list(GettextDiscovery(finder).get_masks())
            self.assertTrue(candidates)
            self.assertTrue(
                all(
                    isinstance(path, FileRecord)
                    for candidate in candidates
                    for path in candidate.paths
                )
            )
            self.assertFalse(hasattr(first, "open"))

    def test_open_binds_record_to_current_finder(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            first_root = Path(tmpdir) / "first"
            second_root = Path(tmpdir) / "second"
            first_root.mkdir()
            second_root.mkdir()
            (first_root / "en.po").write_text("first", encoding="utf-8")
            (second_root / "en.po").write_text("second", encoding="utf-8")
            first = Finder(first_root)
            second = Finder(second_root)
            record = next(second._mask_records("en.po"))
            with first.open(record) as handle:
                self.assertEqual(handle.read(), "first")
