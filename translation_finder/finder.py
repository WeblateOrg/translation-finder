# Copyright © Michal Čihař <michal@weblate.org>
#
# SPDX-License-Identifier: GPL-3.0-or-later

"""Filesystem finder for translations."""

import re
from fnmatch import fnmatch
from os import scandir
from pathlib import Path, PurePath
from typing import Optional

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


def lc_convert(relative_path, relative):
    lower = relative_path.lower()
    try:
        directory, filename = lower.rsplit("/", 1)
    except ValueError:
        directory, filename = "", lower
    return directory, filename, relative


class Finder:
    """Finder for files which might be considered translations."""

    def __init__(self, root, mock=None):
        if not isinstance(root, PurePath):
            root = Path(root)
        self.root = root
        if mock is None:
            files = []
            dirs = []
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
        self.lc_files.sort(key=lambda x: x[:2])
        # Needed for open
        self.absolutes = {
            relative_path: absolute for absolute, relative, relative_path in files
        }
        # Needed for mask_matches
        self.files = [
            (relative_path, relative) for absolute, relative, relative_path in files
        ]
        self.files.sort(key=lambda x: x[0])

    def process_path(self, path):
        relative = path.relative_to(self.root)
        return (path, relative, relative.as_posix())

    def list_files(self, root, files, dirs):
        """Recursively list files and dirs in a path.

        It skips excluded files."""

        with scandir(root) as matches:
            for path in matches:
                if path.is_symlink():
                    continue
                is_dir = path.is_dir()
                path = Path(path.path)
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

    def has_file(self, name: str):
        """Check whether file exists."""
        return name in self.filenames

    def has_dir(self, name: str):
        """Check whether dir exists."""
        return name in self.dirnames

    def mask_matches(self, mask: str):
        """Return all mask matches."""
        for name, path in self.files:
            if fnmatch(name, mask):
                yield path

    def filter_files(self, fileglob: str, dirglob: Optional[str] = None):
        """Filter lowercase file names against glob."""
        fileglob = re.compile(fileglob)
        if dirglob:
            dirglob = re.compile(dirglob)
        for directory, filename, path in self.lc_files:
            if dirglob and not dirglob.fullmatch(directory):
                continue

            if fileglob.fullmatch(filename):
                yield path

    def open(self, path, *args, **kwargs):  # noqa: A003
        return self.absolutes[path.as_posix()].open(*args, **kwargs)
