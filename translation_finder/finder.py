# Copyright © Michal Čihař <michal@weblate.org>
#
# SPDX-License-Identifier: GPL-3.0-or-later

"""Filesystem finder for translations."""

from __future__ import annotations

import operator
import re
from fnmatch import fnmatch, translate
from os import scandir
from pathlib import Path, PurePath
from typing import TYPE_CHECKING, overload

if TYPE_CHECKING:
    from collections.abc import Generator, Iterable
    from io import FileIO, TextIOWrapper

    from _typeshed import OpenBinaryMode, OpenTextMode

EXCLUDES = {
    ".git",
    ".hg",
    ".eggs",
    "*.egg-info",
    "*.swp",
    "__pycache__",
    "__MACOSX",
    ".DS_Store",
    ".deps",
    ".venv",
    ".env",
    ".github",
    "build",
    "dist",
    "node_modules",
    ".*_cache",
}


def lc_convert(relative_path: str, relative: PurePath) -> tuple[str, str, PurePath]:
    """Convert path to lower case and extract directory and filename from it."""
    lower = relative_path.lower()
    try:
        directory, filename = lower.rsplit("/", 1)
    except ValueError:
        directory, filename = "", lower
    return directory, filename, relative


PathListItem = tuple[PurePath, PurePath, str]
PathListType = list[PathListItem]
PathMockType = tuple[PathListType, PathListType]
LowerPathListItem = tuple[str, str, PurePath]
FileMatchItem = tuple[str, PurePath]


class Finder:
    """Finder for files which might be considered translations."""

    def __init__(
        self,
        root: PurePath | str,
        mock: PathMockType | None = None,
    ) -> None:
        if not isinstance(root, PurePath):
            root = Path(root)
        self.root = root
        if mock is None:
            files: PathListType = []
            dirs: PathListType = []
            self.list_files(root, files, dirs)
        else:
            files, dirs = mock
        # For the has_file/has_dir
        self.filenames = {relative_path for absolute, relative, relative_path in files}
        self.dirnames = {relative_path for absolute, relative, relative_path in dirs}
        # Needed for filter_files
        self.lc_files = [
            lc_convert(relative_path, relative)
            for absolute, relative, relative_path in files
        ]
        self.lc_files.sort(key=operator.itemgetter(slice(2)))
        self.lc_files_by_name: dict[str, list[LowerPathListItem]] = {}
        self.lc_files_by_suffix: dict[str, list[LowerPathListItem]] = {}
        for lc_item in self.lc_files:
            filename = lc_item[1]
            self.lc_files_by_name.setdefault(filename, []).append(lc_item)
            if suffix := self.get_suffix(filename):
                self.lc_files_by_suffix.setdefault(suffix, []).append(lc_item)
        # Needed for open
        self.absolutes = {
            relative_path: absolute for absolute, relative, relative_path in files
        }
        # Needed for mask_matches
        self.files = [
            (relative_path, relative) for absolute, relative, relative_path in files
        ]
        self.files.sort(key=operator.itemgetter(0))
        self.files_by_path = dict(self.files)
        self.files_by_name: dict[str, list[FileMatchItem]] = {}
        self.files_by_suffix: dict[str, list[FileMatchItem]] = {}
        for file_item in self.files:
            relative_path = file_item[0]
            filename = relative_path.rsplit("/", 1)[-1]
            self.files_by_name.setdefault(filename, []).append(file_item)
            if suffix := self.get_suffix(filename.lower()):
                self.files_by_suffix.setdefault(suffix, []).append(file_item)

    @staticmethod
    def get_suffix(filename: str) -> str | None:
        """Return the final file suffix usable for candidate narrowing."""
        dot_position = filename.rfind(".")
        if dot_position == -1 or dot_position == len(filename) - 1:
            return None
        return filename[dot_position:]

    @staticmethod
    def has_glob_magic(pattern: str, magic: str = "*?[") -> bool:
        """Check whether pattern contains glob wildcards."""
        return any(char in pattern for char in magic)

    @classmethod
    def glob_suffix_candidate(cls, pattern: str, magic: str = "*?[") -> str | None:
        """Return a safe suffix candidate for a glob pattern."""
        last_magic = max((pattern.rfind(char) for char in magic), default=-1)
        if last_magic == -1:
            return cls.get_suffix(pattern.lower())
        tail = pattern[last_magic + 1 :]
        return cls.get_suffix(tail.lower())

    @classmethod
    def mask_candidates(
        cls, masks: tuple[str, ...]
    ) -> tuple[set[str], set[str]] | None:
        """Return indexed filename candidates for fnmatch-style masks."""
        names: set[str] = set()
        suffixes: set[str] = set()
        for mask in masks:
            filename = mask.rsplit("/", 1)[-1]
            if not cls.has_glob_magic(filename):
                names.add(filename.lower())
                continue
            if suffix := cls.glob_suffix_candidate(filename):
                suffixes.add(suffix)
                continue
            return None

        return names, suffixes

    def process_path(self, path: PurePath) -> tuple[PurePath, PurePath, str]:
        """Convert path to relative path."""
        relative = path.relative_to(self.root)
        return (path, relative, relative.as_posix())

    def list_files(
        self, root: PurePath, files: PathListType, dirs: PathListType
    ) -> None:
        """
        Recursively list files and dirs in a path.

        It skips excluded files.
        """
        with scandir(root) as matches:
            for match in matches:
                if match.is_symlink():
                    continue
                is_dir = match.is_dir()
                path = Path(match.path)
                if any(path.match(exclude) for exclude in EXCLUDES):
                    continue
                if is_dir:
                    dirs.append(self.process_path(path))
                    try:
                        self.list_files(path, files, dirs)
                    except OSError:
                        continue
                else:
                    files.append(self.process_path(path))

    def has_file(self, name: str) -> bool:
        """Check whether file exists."""
        return name in self.filenames

    def has_dir(self, name: str) -> bool:
        """Check whether dir exists."""
        return name in self.dirnames

    def mask_matches(self, mask: str) -> Generator[PurePath]:
        """Return all mask matches."""
        candidates: tuple[FileMatchItem, ...] | list[FileMatchItem]
        if "*" not in mask:
            match = self.files_by_path.get(mask)
            candidates = ((mask, match),) if match is not None else ()
        else:
            filename = mask.rsplit("/", 1)[-1]
            if "*" not in filename:
                candidates = self.files_by_name.get(filename, [])
            elif suffix := self.glob_suffix_candidate(filename, magic="*"):
                candidates = self.files_by_suffix.get(suffix, [])
            else:
                candidates = self.files

        # Avoid dealing [ as a special char
        mask = mask.replace("[", "[[]").replace("?", "[?]")
        for name, path in candidates:
            if fnmatch(name, mask):
                yield path

    def get_lc_candidates(
        self,
        candidate_names: Iterable[str] | None,
        candidate_suffixes: Iterable[str] | None,
    ) -> list[LowerPathListItem]:
        """Return lowercase file candidates narrowed by filename hints."""
        if candidate_names is None and candidate_suffixes is None:
            return self.lc_files

        candidates: dict[PurePath, LowerPathListItem] = {}
        if candidate_names is not None:
            for name in candidate_names:
                for item in self.lc_files_by_name.get(name.lower(), ()):
                    candidates[item[2]] = item
        if candidate_suffixes is not None:
            for suffix in candidate_suffixes:
                for item in self.lc_files_by_suffix.get(suffix.lower(), ()):
                    candidates[item[2]] = item

        result = list(candidates.values())
        result.sort(key=operator.itemgetter(slice(2)))
        return result

    def filter_masks(
        self,
        masks: str | Iterable[str],
        dirglob: str | None = None,
    ) -> Generator[PurePath]:
        """Filter lowercase file names against fnmatch-style masks."""
        masks = (masks,) if isinstance(masks, str) else tuple(masks)
        if not masks:
            return

        candidates = self.mask_candidates(masks)
        if candidates is None:
            candidate_names = candidate_suffixes = None
        else:
            candidate_names, candidate_suffixes = candidates

        yield from self.filter_files(
            "|".join(translate(mask) for mask in masks),
            dirglob,
            candidate_names=candidate_names,
            candidate_suffixes=candidate_suffixes,
        )

    def filter_files(
        self,
        fileglob: str,
        dirglob: str | None = None,
        *,
        candidate_names: Iterable[str] | None = None,
        candidate_suffixes: Iterable[str] | None = None,
    ) -> Generator[PurePath]:
        """Filter lowercase file names against glob."""
        fileglob_re = re.compile(fileglob)
        dirglob_re = re.compile(dirglob) if dirglob else None
        for directory, filename, path in self.get_lc_candidates(
            candidate_names,
            candidate_suffixes,
        ):
            if dirglob_re and not dirglob_re.fullmatch(directory):
                continue

            if fileglob_re.fullmatch(filename):
                yield path

    @overload
    def open(self, path: PurePath, mode: OpenTextMode = "r") -> TextIOWrapper: ...
    @overload
    def open(self, path: PurePath, mode: OpenBinaryMode) -> FileIO: ...
    def open(self, path, mode="r"):
        """Open file from the finder."""
        path_obj = self.absolutes[path.as_posix()]
        if not isinstance(path_obj, Path):
            msg = "Not a real file"
            raise TypeError(msg)
        return path_obj.open(mode=mode)
