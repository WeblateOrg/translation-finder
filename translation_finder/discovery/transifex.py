# Copyright © Michal Čihař <michal@weblate.org>
#
# SPDX-License-Identifier: GPL-3.0-or-later

"""Transifex configuration discovery."""

from configparser import RawConfigParser
from typing import Optional

from translation_finder.api import register_discovery

from .base import BaseDiscovery


@register_discovery
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

    def extract_format(self, transifex: str):
        transifex = transifex.upper()
        try:
            return self.typemap[transifex]
        except KeyError:
            return ""

    def extract_section(self, config, section: str):
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

    def get_masks(self, eager: bool = False, hint: Optional[str] = None):
        """Retuns matches from transifex files."""
        for path in self.finder.filter_files("config", ".tx"):
            config = RawConfigParser()
            with self.finder.open(path) as handle:
                config.read_file(handle)
            for section in config.sections():
                result = self.extract_section(config, section)
                if result:
                    yield result
