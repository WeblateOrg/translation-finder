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
"""Individual discovery rules for translation formats."""
from __future__ import unicode_literals, absolute_import


class BaseDiscovery(object):
    """Abstract base class for discovery."""
    def __init__(self, finder):
        self.finder = finder

    @staticmethod
    def is_language_code(code):
        """Analysis whether passed parameter looks like language code."""
        if len(code) <= 2:
            return True

    def discover(self):
        raise NotImplementedError()


class GettextDiscovery(BaseDiscovery):
    """Gettext PO files discovery."""
    def discover(self):
        masks = set()
        for path in self.finder.filter_files("*.po"):
            parts = list(path.parts)
            for pos, part in enumerate(parts):
                if self.is_language_code(part):
                    mask = parts[:]
                    mask[pos] = "*"
                    masks.add("/".join(mask))

        return [{"filemask": mask, "format": "po"} for mask in masks]
