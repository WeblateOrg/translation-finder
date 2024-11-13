# Copyright © Michal Čihař <michal@weblate.org>
#
# SPDX-License-Identifier: GPL-3.0-or-later

"""Filesystem finder for translations."""

from __future__ import annotations

import operator
import re
from fnmatch import fnmatch
from os import scandir
from pathlib import Path, PurePath
from typing import TYPE_CHECKING, overload

if TYPE_CHECKING:
    from collections.abc import Generator
    from io import FileIO, TextIOWrapper

    from _typeshed import OpenBinaryMode, OpenTextMode

EXCLUDES = {
    ".git",
    ".hg",
    ".eggs",
    "*.swp",
    "__pycache__",
    "__MACOSX",
    ".deps",
    ".venv",
    ".env",
    ".github",
}


def lc_convert(relative_path: str, relative: PurePath) -> tuple[str, str, PurePath]:
    lower = relative_path.lower()
    try:
        directory, filename = lower.rsplit("/", 1)
    except ValueError:
        directory, filename = "", lower
    return directory, filename, relative


PathListItem = tuple[PurePath, PurePath, str]
PathListType = list[PathListItem]
PathMockType = tuple[PathListType, PathListType]


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
        # Needed for open
        self.absolutes = {
            relative_path: absolute for absolute, relative, relative_path in files
        }
        # Needed for mask_matches
        self.files = [
            (relative_path, relative) for absolute, relative, relative_path in files
        ]
        self.files.sort(key=operator.itemgetter(0))

    def process_path(self, path: PurePath) -> tuple[PurePath, PurePath, str]:
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
        # Avoid dealing [ as a special char
        mask = mask.replace("[", "[[]").replace("?", "[?]")
        for name, path in self.files:
            if fnmatch(name, mask):
                yield path

    def filter_files(
        self, fileglob: str, dirglob: str | None = None
    ) -> Generator[PurePath]:
        """Filter lowercase file names against glob."""
        fileglob_re = re.compile(fileglob)
        dirglob_re = re.compile(dirglob) if dirglob else None
        for directory, filename, path in self.lc_files:
            if dirglob_re and not dirglob_re.fullmatch(directory):
                continue

            if fileglob_re.fullmatch(filename):
                yield path

    @overload
    def open(self, path: PurePath, mode: OpenTextMode = "r") -> TextIOWrapper: ...
    @overload
    def open(self, path: PurePath, mode: OpenBinaryMode) -> FileIO: ...
    def open(self, path, mode="r"):
        path_obj = self.absolutes[path.as_posix()]
        if not isinstance(path_obj, Path):
            msg = "Not a real file"
            raise TypeError(msg)
        return path_obj.open(mode=mode)
