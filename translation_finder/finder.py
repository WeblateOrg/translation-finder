# -*- coding: utf-8 -*-
#
# Copyright © 2018 Michal Čihař <michal@cihar.com>
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
# along with this program.  If not, see <http://www.gnu.org/licenses/>.
#
from __future__ import unicode_literals, absolute_import

try:
    from pathlib import Path
except ImportError:
    from pathlib2 import Path

EXCLUDES = frozenset((".git", ".hg", ".eggs", "*.swp", "__pycache__"))


class Finder(object):
    def __init__(self, path):
        self.path = Path(path)
        self.files = list(self.list_files())
        self.lowercase_files = [path.as_posix().lower() for path in self.files]

    def list_files(self, root=None):
        if root is None:
            root = self.path
        for path in root.iterdir():
            if any((path.match(exclude) for exclude in EXCLUDES)):
                continue
            if path.is_dir():
                for ret in self.list_files(path):
                    yield ret
            else:
                yield path
