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
"""Individual discovery rules for translation formats."""
from __future__ import unicode_literals, absolute_import

from itertools import chain

from .base import BaseDiscovery, EncodingDiscovery


class GettextDiscovery(BaseDiscovery):
    """Gettext PO files discovery."""

    file_format = "po"
    mask = "*.po"
    new_base_mask = "*.pot"

    def discover(self):
        for result in super(GettextDiscovery, self).discover():
            if "template" not in result:
                yield result
                continue
            bi = result.copy()
            del bi["template"]
            yield bi
            mono = result.copy()
            mono["file_format"] = "po-mono"
            yield mono


class QtDiscovery(BaseDiscovery):
    """Qt Linguist files discovery."""

    file_format = "ts"
    mask = "*.ts"
    new_base_mask = "*.ts"


class XliffDiscovery(BaseDiscovery):
    """XLIFF files discovery."""

    file_format = "xliff"
    mask = "*.xliff"


class XliffDiscovery2(BaseDiscovery):
    """XLIFF files discovery."""

    file_format = "xliff"
    mask = "*.xlf"


class JoomlaDiscovery(BaseDiscovery):
    """Joomla files discovery."""

    file_format = "joomla"
    mask = "*.ini"


class WebExtensionDiscovery(BaseDiscovery):
    """web extension files discovery."""

    file_format = "webextension"
    mask = "messages.json"


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


class OSXDiscovery(EncodingDiscovery):
    """OSX string properties files discovery."""

    file_format = "strings"
    encoding_map = {"utf-8": "strings-utf8"}

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


class JavaDiscovery(EncodingDiscovery):
    """Java string properties files discovery."""

    file_format = "properties"
    encoding_map = {"utf-8": "properties-utf8", "utf-16": "properties-utf16"}

    def get_masks(self):
        """Return all file masks found in the directory.

        It is expected to contain duplicates."""
        for path in self.finder.filter_files("*_*.properties"):
            mask = list(path.parts)
            template = mask[:]
            base, code = mask[-1].rsplit(".")[0].split("_", 1)
            if not self.is_language_code(code):
                base, code = mask[-1].rsplit(".")[0].rsplit("_", 1)
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


class AppStoreDiscovery(BaseDiscovery):
    """App store metadata.
    """

    file_format = "appstore"

    def filter_files(self):
        """Filters possible file matches."""
        for path in chain(
            self.finder.filter_files("short_description.txt"),
            self.finder.filter_files("full_description.txt"),
            self.finder.filter_files("title.txt"),
        ):
            yield path.parent
        for path in self.finder.filter_files("*.txt", "*/changelogs"):
            yield path.parent.parent

    def has_storage(self, name):
        """Check whether finder has a storage."""
        return self.finder.has_dir(name)

    def fill_in_template(self, result, source_language=None):
        super(AppStoreDiscovery, self).fill_in_template(result, source_language)
        if "template" not in result and source_language is None:
            for lang in ("en-US", "en-GB", "en-AU"):
                super(AppStoreDiscovery, self).fill_in_template(result, lang)
                if "template" in result:
                    break


class JSONDiscovery(BaseDiscovery):
    """JSON files discovery."""

    file_format = "json"
    mask = "*.json"
