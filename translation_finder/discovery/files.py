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
from __future__ import absolute_import, unicode_literals

import json
from itertools import chain

import six
from ruamel.yaml import YAML, YAMLError

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

    def fill_in_new_base(self, result):
        super(GettextDiscovery, self).fill_in_new_base(result)
        if "new_base" not in result:
            pot_names = [
                result["filemask"].replace("po/*/", "pot/") + "t",
                result["filemask"].replace(".*", ""),
            ]
            for pot_name in pot_names:
                if self.finder.has_file(pot_name):
                    result["new_base"] = pot_name
                    break


class QtDiscovery(BaseDiscovery):
    """Qt Linguist files discovery."""

    file_format = "ts"
    mask = "*.ts"
    new_base_mask = "*.ts"


class XliffDiscovery(BaseDiscovery):
    """XLIFF files discovery."""

    file_format = "xliff"
    mask = "*.xliff"

    def filter_files(self):
        """Filters possible file matches."""
        return chain(
            self.finder.filter_files(self.mask), self.finder.filter_files("*.xlf")
        )


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
    mask = "*_*.properties"

    def possible_templates(self, language, mask):
        yield mask.replace("_*", "")
        for result in super(JavaDiscovery, self).possible_templates(language, mask):
            yield result


class RESXDiscovery(BaseDiscovery):
    """RESX files discovery.
    """

    file_format = "resx"
    mask = "resources.res[xw]"

    def possible_templates(self, language, mask):
        yield mask.replace(".*", "")
        for result in super(RESXDiscovery, self).possible_templates(language, mask):
            yield result

    def get_masks(self):
        """Return all file masks found in the directory.

        It is expected to contain duplicates."""
        for path in self.finder.filter_files("*.*.res[xw]"):
            mask = list(path.parts)
            base, code, ext = mask[-1].rsplit(".", 2)
            if not self.is_language_code(code):
                continue
            mask[-1] = "{0}.*.{1}".format(base, ext)
            yield {"filemask": "/".join(mask)}
        for match in super(RESXDiscovery, self).get_masks():
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

    def get_language_aliases(self, language):
        """Language code aliases"""
        if language == "en":
            return ["en", "en-US", "en-GB", "en-AU"]
        return [language]


class JSONDiscovery(BaseDiscovery):
    """JSON files discovery."""

    file_format = "json-nested"
    mask = "*.json"

    def adjust_format(self, result):
        if "template" not in result:
            return

        path = list(self.finder.mask_matches(result["template"]))[0]

        if not hasattr(path, "open"):
            return

        with self.finder.open(path, "r") as handle:
            try:
                data = json.load(handle)
            except ValueError:
                return
            if not isinstance(data, dict):
                return
            all_strings = True
            i18next = False
            for key, value in data.items():
                if (
                    isinstance(value, dict)
                    and "message" in value
                    and "description" in value
                ):
                    result["file_format"] = "webextension"
                    return
                if not isinstance(key, six.string_types) or not isinstance(
                    value, six.string_types
                ):
                    all_strings = False
                    break
                elif key.endswith("_plural") or "{{" in value:
                    i18next = True

            if all_strings:
                if i18next:
                    result["file_format"] = "i18next"
                else:
                    result["file_format"] = "json"


class FluentDiscovery(BaseDiscovery):
    """Fluent files discovery."""

    file_format = "fluent"
    mask = "*.ftl"

    def get_language_aliases(self, language):
        """Language code aliases"""
        if language == "en":
            return ["en", "en-US"]
        return [language]


class YAMLDiscovery(BaseDiscovery):
    """YAML files discovery."""

    file_format = "yaml"
    mask = "*.yml"

    def filter_files(self):
        """Filters possible file matches."""
        return chain(
            self.finder.filter_files(self.mask), self.finder.filter_files("*.yaml")
        )

    def adjust_format(self, result):
        if "template" not in result:
            return

        path = list(self.finder.mask_matches(result["template"]))[0]

        if not hasattr(path, "open"):
            return

        with self.finder.open(path, "rb") as handle:
            yaml = YAML()
            try:
                data = yaml.load(handle)
            except YAMLError:
                return
            if isinstance(data, dict) and len(data) == 1:
                key = list(data.keys())[0]
                if "filemask" in result:
                    if result["filemask"].replace("*", key) == result["template"]:
                        result["file_format"] = "ruby-yaml"
                elif key in result["template"]:
                    result["file_format"] = "ruby-yaml"


class SRTDiscovery(BaseDiscovery):
    """SRT subtitle files discovery."""

    file_format = "srt"
    mask = "*.srt"


class SUBDiscovery(BaseDiscovery):
    """SUB subtitle files discovery."""

    file_format = "sub"
    mask = "*.sub"


class ASSDiscovery(BaseDiscovery):
    """ASS subtitle files discovery."""

    file_format = "ass"
    mask = "*.ass"


class SSADiscovery(BaseDiscovery):
    """SSA subtitle files discovery."""

    file_format = "ssa"
    mask = "*.ssa"


class PHPDiscovery(BaseDiscovery):
    """PHP files discovery."""

    file_format = "php"
    mask = "*.php"
