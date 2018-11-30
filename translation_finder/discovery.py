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

from chardet.universaldetector import UniversalDetector

from six.moves.configparser import RawConfigParser, NoOptionError

from .languages import LANGUAGES

BLACKLIST = frozenset(("po", "ts"))

TOKEN_SPLIT = re.compile(r"([_-])")


class BaseDiscovery(object):
    """Abstract base class for discovery."""

    file_format = "auto"
    file_format_mono = None
    mask = "*.*"
    new_base_mask = None

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

    def fill_in_new_base(self, result):
        if not self.new_base_mask:
            return
        path = result["filemask"]
        basename = path.rsplit("/", 1)[1].rsplit(".", 1)[0]
        new_name = self.new_base_mask.replace("*", basename)

        while "/" in path:
            path = path.rsplit("/", 1)[0]
            for match in chain(
                self.finder.filter_files(new_name, path),
                self.finder.filter_files(self.new_base_mask, path),
            ):
                result["new_base"] = "/".join(match.parts)
                return

    def fill_in_template(self, result):
        if "template" not in result:
            template = result["filemask"].replace("*", self.source_language)
            if self.finder.has_file(template):
                result["template"] = template

    def fill_in_file_format(self, result):
        if "file_format" in result:
            return
        if "template" in result and self.file_format_mono:
            result["file_format"] = self.file_format_mono
        else:
            result["file_format"] = self.file_format

    def adjust_encoding(self, result):
        return

    def discover(self):
        """Retun list of translation configurations matching this discovery."""
        discovered = set()
        for result in self.get_masks():
            if result["filemask"] in discovered:
                continue
            if "template" in result and not self.finder.has_file(result["template"]):
                continue
            self.adjust_encoding(result)
            self.fill_in_template(result)
            self.fill_in_new_base(result)
            self.fill_in_file_format(result)
            discovered.add(result["filemask"])
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
    file_format_mono = "po-mono"
    mask = "*.po"
    new_base_mask = "*.pot"


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


class EncodingDiscovery(BaseDiscovery):
    encoding_map = {}

    def adjust_encoding(self, result):
        detector = UniversalDetector()

        for path in chain(
            self.finder.mask_matches(result["filemask"]),
            self.finder.mask_matches(result["template"]),
        ):
            if not hasattr(path, "open"):
                continue
            with self.finder.open(path, "rb") as handle:
                detector.feed(handle.read())
                if detector.done:
                    break
        detector.close()

        if detector.result["encoding"]:
            encoding = detector.result["encoding"].lower()
            if encoding in self.encoding_map:
                result["file_format"] = self.encoding_map[encoding]


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


class TransifexDiscovery(BaseDiscovery):
    """Transifex configuration discovery."""

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

    def extract_format(self, transifex):
        transifex = transifex.upper()
        try:
            return self.typemap[transifex]
        except KeyError:
            return "auto"

    def extract_section(self, config, section):
        if not config.has_option(section, "file_filter"):
            return None
        result = {
            "name": section,
            "filemask": config.get(section, "file_filter").replace("<lang>", "*"),
        }

        if config.has_option(section, "type"):
            result["file_format"] = self.extract_format(config.get(section, "type"))

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
