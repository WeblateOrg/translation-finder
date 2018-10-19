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

BLACKLIST = frozenset(("po", "ts"))


class BaseDiscovery(object):
    """Abstract base class for discovery."""

    file_format = "auto"
    mask = "*.*"

    def __init__(self, finder):
        self.finder = finder

    @staticmethod
    def is_language_code(code):
        """Analysis whether passed parameter looks like language code."""
        if len(code) <= 2:
            if code in BLACKLIST:
                return False
            return True
        return False

    def get_wildcard(self, part):
        """Generate language wilcard for a path part.

        Retruns None if not possible."""
        if self.is_language_code(part):
            return "*"
        if "." in part:
            base, ext = part.rsplit(".", 1)
            if self.is_language_code(base):
                return "*.{}".format(ext)
        return None

    def discover(self):
        """Retun list of translation configurations matching this discovery."""
        return [
            {"filemask": mask, "file_format": self.file_format, "template": template}
            for mask, template in set(self.get_masks())
        ]

    def get_masks(self):
        """Return all file masks found in the directory.

        It is expected to contain duplicates."""
        for path in self.finder.filter_files(self.mask):
            parts = list(path.parts)
            for pos, part in enumerate(parts):
                wildcard = self.get_wildcard(part)
                if wildcard:
                    mask = parts[:]
                    mask[pos] = wildcard
                    yield "/".join(mask), None


class GettextDiscovery(BaseDiscovery):
    """Gettext PO files discovery."""

    file_format = "po"
    mask = "*.po"


class QtDiscovery(BaseDiscovery):
    """Qt Linguist files discovery."""

    file_format = "ts"
    mask = "*.ts"


class AndroidDiscovery(BaseDiscovery):
    """Android string files discovery."""

    file_format = "aresource"

    def get_masks(self):
        """Return all file masks found in the directory.

        It is expected to contain duplicates."""
        for path in self.finder.filter_files("strings*.xml", "*/values"):
            mask = list(path.parts)
            mask[-2] = "values-*"

            yield "/".join(mask), path.as_posix()


class OSXDiscovery(BaseDiscovery):
    """OSX string properties files discovery."""

    file_format = "strings"

    def get_masks(self):
        """Return all file masks found in the directory.

        It is expected to contain duplicates."""
        for path in self.finder.filter_files("*.strings", "*/en.lproj"):
            mask = list(path.parts)
            mask[-2] = "*.lproj"

            yield "/".join(mask), path.as_posix()
