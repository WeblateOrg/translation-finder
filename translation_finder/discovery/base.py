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
# along with this program.  If not, see <https://www.gnu.org/licenses/>.
#
"""Base discovery code."""
from __future__ import unicode_literals, absolute_import

from itertools import chain
import re

from chardet.universaldetector import UniversalDetector

from ..languages import LANGUAGES

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
            skip = set()
            for pos, part in enumerate(parts):
                if pos in skip:
                    continue
                wildcard = self.get_wildcard(part)
                if wildcard:
                    mask = parts[:]
                    while part in mask:
                        index = mask.index(part)
                        skip.add(index)
                        mask[index] = wildcard
                    mask[pos] = wildcard
                    yield {"filemask": "/".join(mask)}


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
