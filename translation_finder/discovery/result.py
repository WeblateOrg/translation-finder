# Copyright © Michal Čihař <michal@weblate.org>
#
# SPDX-License-Identifier: GPL-3.0-or-later

"""Discovery result class."""


class DiscoveryResult(dict):
    """
    Discovery result class.

    This is essentially a dict with meta dict containing additional
    information.
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.meta = {}

    @property
    def _sort_key(self):
        return (self.meta["priority"], self["file_format"])

    @property
    def match(self):
        return dict(self)

    def __lt__(self, other):
        """This is only method needed for sort."""
        return self._sort_key < other._sort_key  # noqa:SF01,SLF001

    def __eq__(self, other):
        return super().__eq__(other) and (
            self.meta == other.meta if isinstance(other, DiscoveryResult) else True
        )

    def __ne__(self, other):
        return not self.__eq__(other)

    def __repr__(self):
        return f"{self.match!r} [meta:{self.meta!r}]"

    def copy(self):
        result = DiscoveryResult(super().copy())
        result.meta = self.meta.copy()
        return result
