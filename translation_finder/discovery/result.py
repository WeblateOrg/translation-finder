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


class DiscoverResult(dict):
    def __init__(self, *args, **kwargs):
        super(DiscoverResult, self).__init__(*args, **kwargs)
        self.meta = {}

    @property
    def _sort_key(self):
        return (self.meta["priority"], self["file_format"])

    def __lt__(self, other):
        """This is only method needed for sort."""
        return self._sort_key < other._sort_key

    def copy(self):
        result = DiscoverResult(super(DiscoverResult, self).copy())
        result.meta = self.meta.copy()
        return result
