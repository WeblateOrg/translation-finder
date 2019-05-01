# -*- coding: utf-8 -*-
#
# Copyright © 2018 - 2019 Michal Čihař <michal@cihar.com>
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
from __future__ import unicode_literals


class DiscoveryResult(dict):
    def __init__(self, *args, **kwargs):
        super(DiscoveryResult, self).__init__(*args, **kwargs)
        self.meta = {}

    @property
    def _sort_key(self):
        return (self.meta["priority"], self["file_format"])

    @property
    def match(self):
        return dict(self)

    def __lt__(self, other):
        """This is only method needed for sort."""
        return self._sort_key < other._sort_key

    def __eq__(self, other):
        return super(DiscoveryResult, self).__eq__(other) and (
            self.meta == other.meta if isinstance(other, DiscoveryResult) else True
        )

    def __ne__(self, other):
        return not self.__eq__(other)

    def __repr__(self):
        return "{!r} [meta:{!r}]".format(self.match, self.meta)

    def copy(self):
        result = DiscoveryResult(super(DiscoveryResult, self).copy())
        result.meta = self.meta.copy()
        return result