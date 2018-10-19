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

from itertools import chain
import re

from .languages import LANGUAGES

BLACKLIST = frozenset(("po", "ts"))

TOKEN_SPLIT = re.compile(r"([_-])")


class BaseDiscovery(object):
    """Abstract base class for discovery."""

    file_format = "auto"
    mask = "*.*"

    def __init__(self, finder, source_language="en"):
        self.finder = finder
        self.source_language = source_language

    @staticmethod
    def is_language_code(code):
        """Analysis whether passed parameter looks like language code."""
        if code.lower() in BLACKLIST:
            return False

        return code.lower().replace("-", "_") in LANGUAGES

    def get_wildcard(self, part):
        """Generate language wilcard for a path part.

        Retruns None if not possible."""
        if self.is_language_code(part):
            return "*"
        if "." in part:
            base, ext = part.rsplit(".", 1)
            # Handle <language>.extension
            if self.is_language_code(base):
                return "*.{}".format(ext)
            # Handle prefix-<language>.extension or prefix_<language>.extension
            tokens = TOKEN_SPLIT.split(base)
            for pos, token in enumerate(tokens):
                if token in ("-", "_"):
                    continue
                if self.is_language_code(token):
                    return "{}*.{}".format("".join(tokens[:pos]), ext)
        return None

    def discover(self):
        """Retun list of translation configurations matching this discovery."""
        discovered = set()
        for result in self.get_masks():
            if result["filemask"] in discovered:
                continue
            if "template" in result and not self.finder.has_file(result["template"]):
                continue
            if "template" not in result:
                template = result["filemask"].replace("*", self.source_language)
                if self.finder.has_file(template):
                    result["template"] = template
            discovered.add(result["filemask"])
            result["file_format"] = self.file_format
            yield result

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
                    yield {"filemask": "/".join(mask)}


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

            yield {"filemask": "/".join(mask), "template": path.as_posix()}


class OSXDiscovery(BaseDiscovery):
    """OSX string properties files discovery.

    TODO: Detect encoding
    """

    file_format = "strings"

    def get_masks(self):
        """Return all file masks found in the directory.

        It is expected to contain duplicates."""
        for path in chain(
            self.finder.filter_files("*.strings", "*/base.lproj"),
            self.finder.filter_files("*.strings", "*/en.lproj"),
        ):
            mask = list(path.parts)
            mask[-2] = "*.lproj"

            yield {"filemask": "/".join(mask), "template": path.as_posix()}


class JavaDiscovery(BaseDiscovery):
    """Java string properties files discovery.

    TODO: Detect encoding
    """

    file_format = "properties"

    def get_masks(self):
        """Return all file masks found in the directory.

        It is expected to contain duplicates."""
        for path in self.finder.filter_files("*_*.properties"):
            mask = list(path.parts)
            template = mask[:]
            base, code = mask[-1].rsplit(".")[0].split("_", 1)
            if not self.is_language_code(code):
                continue
            mask[-1] = "{0}_*.properties".format(base)
            template[-1] = "{0}.properties".format(base)

            yield {"filemask": "/".join(mask), "template": "/".join(template)}


class RESXDiscovery(BaseDiscovery):
    """RESX files discovery.
    """

    file_format = "resx"
    mask = "resources.res[xw]"

    def get_masks(self):
        """Return all file masks found in the directory.

        It is expected to contain duplicates."""
        for path in self.finder.filter_files("*.*.res[xw]"):
            mask = list(path.parts)
            template = mask[:]
            base, code, ext = mask[-1].rsplit(".", 2)
            if not self.is_language_code(code):
                continue
            mask[-1] = "{0}.*.{1}".format(base, ext)
            template[-1] = "{0}.{1}".format(base, ext)

            yield {"filemask": "/".join(mask), "template": "/".join(template)}
        for match in super(RESXDiscovery, self).get_masks():
            match["template"] = match["filemask"].replace("*", self.source_language)
            yield match
