# Copyright © Michal Čihař <michal@weblate.org>
#
# SPDX-License-Identifier: GPL-3.0-or-later

"""Discovery result class."""

from __future__ import annotations

from collections import UserDict
from typing import TypedDict, cast


class ResultMeta(TypedDict, total=False):
    priority: int
    file_format: str
    discovery: str
    origin: str | None


class ResultDict(TypedDict, total=False):
    name: str
    filemask: str
    template: str
    file_format: str
    intermediate: str
    new_base: str


class DiscoveryResult(UserDict):
    """
    Discovery result class.

    Subclass of a dict with meta dict containing additional information.
    """

    data: ResultDict  # type: ignore[assignment]

    def __init__(self, data: ResultDict) -> None:
        super().__init__(data)
        self.meta: ResultMeta = {}

    @property
    def _sort_key(self) -> tuple[int, str]:
        return (self.meta["priority"], self["file_format"])

    @property
    def match(self) -> ResultDict:
        return cast(ResultDict, dict(self.data))

    def __lt__(self, other: DiscoveryResult) -> bool:
        """Only method needed for sort."""
        return self._sort_key < other._sort_key

    def __eq__(self, other: object) -> bool:
        return super().__eq__(other) and (
            self.meta == other.meta if isinstance(other, DiscoveryResult) else True
        )

    def __ne__(self, other: object) -> bool:
        return not self.__eq__(other)

    def __repr__(self) -> str:
        return f"{self.match!r} [meta:{self.meta!r}]"

    def copy(self) -> DiscoveryResult:
        result = DiscoveryResult(self.data.copy())
        result.meta = self.meta.copy()
        return result
