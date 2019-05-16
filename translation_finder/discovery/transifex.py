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
"""Transifex configuration discovery."""
from __future__ import absolute_import, unicode_literals

from six.moves.configparser import RawConfigParser

from .base import BaseDiscovery


class TransifexDiscovery(BaseDiscovery):
    """Transifex configuration discovery."""

    origin = "Transifex"
    priority = 500

    typemap = {
        "ANDROID": "aresource",
        "STRINGS": "strings",
        "CHROME": "webextension",
        "PO": "po",
        "PROPERTIES": "properties",
        "UNICODEPROPERTIES": "properties-utf8",
        "INI": "joomla",
        "KEYVALUEJSON": "json-nested",
        "MAGENTO": "csv",
        "DTD": "dtd",
        "PHP_ARRAY": "php",
        "QT": "ts",
        "RESX": "resx",
        "XLIFF": "xliff",
        "XLSX": "xlsx",
        "YAML_GENERIC": "yaml",
        "YML": "ruby-yaml",
    }

    extension_map = (
        (".po", "po"),
        ("strings.xml", "aresource"),
        (".ini", "joomla"),
        (".csv", "csv"),
        (".json", "json-nested"),
        (".dtd", "dtd"),
        (".php", "php"),
        (".xlf", "xliff"),
        (".xliff", "xliff"),
        (".ts", "ts"),
        (".resx", "resx"),
        (".resw", "resx"),
        (".xlsx", "xlsx"),
        (".yml", "yaml"),
        (".yaml", "yaml"),
        (".properties", "properties"),
        (".strings", "strings"),
    )

    def extract_format(self, transifex):
        transifex = transifex.upper()
        try:
            return self.typemap[transifex]
        except KeyError:
            return ""

    def detect_format(self, filemask):
        filemask = filemask.lower()
        for end, result in self.extension_map:
            if filemask.endswith(end):
                return result
        return ""

    def extract_section(self, config, section):
        if section == "main" or not config.has_option(section, "file_filter"):
            return None
        result = {
            "name": section,
            "filemask": config.get(section, "file_filter").replace("<lang>", "*"),
            "file_format": "",
        }

        if config.has_option(section, "type"):
            result["file_format"] = self.extract_format(config.get(section, "type"))

        if not result["file_format"]:
            result["file_format"] = self.detect_format(result["filemask"])
        if not result["file_format"]:
            return None

        if config.has_option(section, "source_file"):
            template = config.get(section, "source_file")
            if template.lower().endswith(".pot"):
                result["new_base"] = template
            else:
                result["template"] = template

        return result

    def get_masks(self):
        """Retuns matches from transifex files."""
        for path in self.finder.filter_files("config", ".tx"):
            config = RawConfigParser()
            with self.finder.open(path) as handle:
                config.readfp(handle)
            for section in config.sections():
                result = self.extract_section(config, section)
                if result:
                    yield result
