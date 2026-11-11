# Copyright © Michal Čihař <michal@weblate.org>
#
# SPDX-License-Identifier: GPL-3.0-or-later

"""Compact path references used inside discovery."""

from __future__ import annotations

import ntpath
from dataclasses import dataclass, field
from pathlib import Path, PurePath, PureWindowsPath


@dataclass(frozen=True, slots=True)
class DirectoryRecord:
    """Directory paths shared by all files collected from that directory."""

    absolute: PurePath
    relative: PurePath
    text: str
    lower_text: str = field(init=False)

    def __post_init__(self) -> None:
        """Normalize directory text once, rather than once per file."""
        object.__setattr__(self, "lower_text", self.text.lower())


@dataclass(frozen=True, slots=True, eq=False)
class FileRecord:
    """An indexed file without a retained, parsed per-file Path object."""

    directory: DirectoryRecord
    name: str
    text: str
    normalized_text: str = field(init=False)

    def __post_init__(self) -> None:
        """Share the normalized text with the wildcard prefix index."""
        object.__setattr__(
            self,
            "normalized_text",
            ntpath.normcase(self.text)
            if isinstance(self.directory.relative, PureWindowsPath)
            else self.text,
        )

    @property
    def parts(self) -> tuple[str, ...]:
        """Components sharing the directory's existing strings."""
        return (*self.directory.relative.parts, self.name)

    @property
    def parent(self) -> PurePath:
        """The shared relative parent directory."""
        return self.directory.relative

    def as_posix(self) -> str:
        """Return the canonical indexed relative path text."""
        return self.text


DiscoveryPath = FileRecord | PurePath
PathKey = tuple[bool, str]


def path_key(path: DiscoveryPath) -> PathKey:
    """Preserve POSIX and Windows path equality, independently of the host."""
    if isinstance(path, FileRecord):
        return isinstance(
            path.directory.relative, PureWindowsPath
        ), path.normalized_text
    if isinstance(path, PureWindowsPath):
        return True, ntpath.normcase(path.as_posix())
    return False, path.as_posix()


def path_sort_key(path: DiscoveryPath) -> tuple[str, ...]:
    """Compare path components using the reference's native case rules."""
    if (
        isinstance(path, FileRecord)
        and isinstance(path.directory.relative, PureWindowsPath)
    ) or isinstance(path, PureWindowsPath):
        return tuple(part.lower() for part in path.parts)
    return path.parts


def relative_path(path: DiscoveryPath) -> PurePath:
    """Materialize filesystem paths only at public Finder boundaries."""
    if isinstance(path, FileRecord):
        return Path(path.directory.relative, path.name)
    return path


def absolute_path(path: DiscoveryPath) -> PurePath:
    """Materialize an absolute file path when opening an indexed file."""
    if isinstance(path, FileRecord):
        return Path(path.directory.absolute, path.name)
    return path


def is_real_path(path: DiscoveryPath) -> bool:
    """Allow content sampling for collected files and concrete mock paths."""
    return isinstance(path, (FileRecord, Path))
