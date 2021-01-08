#
# Copyright © 2012 - 2021 Michal Čihař <michal@cihar.com>
#
# This file is part of Weblate translation-finder
# <https://github.com/WeblateOrg/translation-finder>
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.
#
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
