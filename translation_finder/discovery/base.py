#
# Copyright © 2012 - 2021 Michal Čihař <michal@cihar.com>
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

import re
from itertools import chain
from typing import Dict, Optional

from weblate_language_data.country_codes import COUNTRIES
from weblate_language_data.language_codes import LANGUAGES

from ..chardet import detect_charset
from ..data import LANGUAGES_BLACKLIST
from .result import DiscoveryResult

TOKEN_SPLIT = re.compile(r"([_.-])")

LOCALES = {"latn", "cyrl", "hant", "hans"}

EXTENSION_MAP = (
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

TEMPLATE_REPLACEMENTS = (
    ("/*/", "/"),
    ("-*", ""),
    (".*", ""),
    ("*", ""),
    ("*", "templates"),
)


class BaseDiscovery:
    """Abstract base class for discovery."""

    file_format = ""
    mask = "*.*"
    new_base_mask = None
    origin = None
    priority = 1000
    uses_template = False

    def __init__(self, finder, source_language="en"):
        self.finder = finder
        self.source_language = source_language

    @staticmethod
    def is_country_code(code):
        code = code.lower()
        return code in COUNTRIES or code in LOCALES

    @classmethod
    def is_language_code(cls, code: str):
        """Analysis whether passed parameter looks like language code."""
        code = code.lower().replace("-", "_")
        if code in LANGUAGES and code not in LANGUAGES_BLACKLIST:
            return True

        if "_" in code:
            lang, country = code.split("_", 1)
            if (
                lang in LANGUAGES
                and lang not in LANGUAGES_BLACKLIST
                and cls.is_country_code(country)
            ):
                return True

        return False

    @staticmethod
    def detect_format(filemask: str):
        filemask = filemask.lower()
        for end, result in EXTENSION_MAP:
            if filemask.endswith(end):
                return result
        return ""

    def get_wildcard(self, part: str):
        """Generate language wilcard for a path part.

        Retruns None if not possible."""
        if self.is_language_code(part):
            return "*"
        if "." in part:
            base, ext = part.rsplit(".", 1)
            # Handle <language>.extension
            if self.is_language_code(base):
                return f"*.{ext}"
            # Handle prefix.<language>.extension
            if "." in base:
                prefix, token = base.split(".", 1)
                if self.is_language_code(token):
                    return f"{prefix}.*.{ext}"
            # Handle prefix-<language>.extension or prefix_<language>.extension
            tokens = TOKEN_SPLIT.split(base)
            for pos, token in enumerate(tokens):
                if token in ("-", "_", "."):
                    continue
                if self.is_language_code(token):
                    end = pos + 1
                    if pos + 3 <= len(tokens):
                        if self.is_language_code("".join(tokens[pos : pos + 3])):
                            end = pos + 3
                    # Skip possible language codes in middle of string
                    if pos != 0 and end != len(tokens) and tokens[end] != ".":
                        continue
                    return "{}*{}.{}".format(
                        "".join(tokens[:pos]), "".join(tokens[end:]), ext
                    )
        return None

    def fill_in_new_base(self, result: Dict[str, str]):
        if not self.new_base_mask:
            return
        path = result["filemask"]
        basename = path.rsplit("/", 1)[-1].rsplit(".", 1)[0]
        if "*" in basename:
            for match, replacement in TEMPLATE_REPLACEMENTS:
                basename = basename.replace(match, replacement)
        new_name = self.new_base_mask.replace("*", basename).lower()

        while "/" in path:
            path = path.rsplit("/", 1)[0]
            path_wild = path.replace("*", "")
            for match in chain(
                self.finder.filter_files(new_name, path),
                self.finder.filter_files(new_name, path_wild),
                self.finder.filter_files(self.new_base_mask, path),
                self.finder.filter_files(self.new_base_mask, path_wild),
            ):
                result["new_base"] = "/".join(match.parts)
                return

    def has_storage(self, name: str):
        """Check whether finder has a storage."""
        return self.finder.has_file(name)

    @staticmethod
    def get_language_aliases(language: str):
        """Language code aliases."""
        return [language]

    def possible_templates(self, language: str, mask: str):
        """Yield possible template filenames."""
        for alias in self.get_language_aliases(language):
            yield mask.replace("*", alias)
        for match, replacement in TEMPLATE_REPLACEMENTS:
            if match in mask:
                yield mask.replace(match, replacement)

    def fill_in_template(
        self, result: Dict[str, str], source_language: Optional[str] = None
    ):
        if "template" not in result:
            if source_language is None:
                source_language = self.source_language
            for template in self.possible_templates(
                source_language, result["filemask"]
            ):
                if self.has_storage(template):
                    result["template"] = template
                    break

    def fill_in_file_format(self, result: Dict[str, str]):
        if "file_format" not in result:
            result["file_format"] = self.file_format

    @staticmethod
    def adjust_format(result: Dict[str, str]):
        return

    def discover(self, eager: bool = False):
        """Retun list of translation configurations matching this discovery."""
        discovered = set()
        for result in self.get_masks(eager=eager):
            if result["filemask"] in discovered:
                continue
            self.fill_in_template(result)
            self.adjust_format(result)
            self.fill_in_new_base(result)
            self.fill_in_file_format(result)
            discovered.add(result["filemask"])
            result = DiscoveryResult(result)
            result.meta["discovery"] = self.__class__.__name__
            result.meta["origin"] = self.origin
            result.meta["priority"] = self.priority
            yield result

    def filter_files(self):
        """Filters possible file matches."""
        if isinstance(self.mask, str):
            masks = [self.mask]
        else:
            masks = self.mask
        return chain.from_iterable(self.finder.filter_files(mask) for mask in masks)

    def get_masks(self, eager: bool = False):
        """Return all file masks found in the directory.

        It is expected to contain duplicates."""
        for path in self.filter_files():
            parts = list(path.parts)
            if eager:
                parts[-1] = "*.{}".format(parts[-1].rsplit(".", 1)[1])
                result = {"filemask": "/".join(parts)}
                if self.uses_template:
                    result["new_base"] = result["template"] = "/".join(path.parts)
                yield result
                continue
            skip = set()
            for pos, part in enumerate(parts):
                if pos in skip:
                    continue
                wildcard = self.get_wildcard(part)
                if wildcard:
                    mask = parts[:]
                    match = re.compile(f"(^|[._-]){re.escape(part)}($|[._-])")
                    for i, current in enumerate(mask):
                        if match.findall(current):
                            skip.add(i)
                            mask[i] = match.sub(f"\\g<1>{wildcard}\\g<2>", current)
                    mask[pos] = wildcard
                    yield {"filemask": "/".join(mask)}


class MonoTemplateDiscovery(BaseDiscovery):
    """Base class for monolingual template based files."""

    uses_template = True

    def fill_in_new_base(self, result: Dict[str, str]):
        if "new_base" not in result and "template" in result:
            result["new_base"] = result["template"]


class EncodingDiscovery(BaseDiscovery):
    """Base class for formats needing encoding detection."""

    encoding_map = {}

    def adjust_format(self, result: Dict[str, str]):
        encoding = None
        matches = [self.finder.mask_matches(result["filemask"])]
        if "template" in result:
            matches.append(self.finder.mask_matches(result["template"]))

        for path in chain(*matches):
            if not hasattr(path, "open"):
                continue
            with self.finder.open(path, "rb") as handle:
                encoding = detect_charset(handle.read())
                if encoding in self.encoding_map:
                    result["file_format"] = self.encoding_map[encoding]
                return
