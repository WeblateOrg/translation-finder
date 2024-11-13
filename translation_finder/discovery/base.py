# Copyright © Michal Čihař <michal@weblate.org>
#
# SPDX-License-Identifier: GPL-3.0-or-later

"""Base discovery code."""

from __future__ import annotations

import fnmatch
import re
from itertools import chain
from pathlib import Path, PurePath
from typing import TYPE_CHECKING

from charset_normalizer import from_fp
from weblate_language_data.country_codes import COUNTRIES
from weblate_language_data.language_codes import LANGUAGES

from translation_finder.data import LANGUAGES_BLACKLIST

from .result import DiscoveryResult, ResultDict

if TYPE_CHECKING:
    from collections.abc import Generator

    from translation_finder.finder import Finder

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
    (".xaml", "resourcedictionary"),
    (".txt", "txt"),
    (".html", "html"),
    (".idml", "idml"),
    (".rc", "rc"),
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
    mask: str | tuple[str, ...] = "*.*"
    new_base_mask: str | None = None
    origin: str | None = None
    priority = 1000
    uses_template = False

    def __init__(self, finder: Finder, source_language: str = "en") -> None:
        self.finder: Finder = finder
        self.source_language: str = source_language

    @staticmethod
    def is_country_code(code: str) -> bool:
        code = code.lower()
        return code in COUNTRIES or code in LOCALES

    @classmethod
    def is_language_code(cls, code: str) -> bool:
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
    def detect_format(filemask: str) -> str:
        filemask = filemask.lower()
        for end, result in EXTENSION_MAP:
            if filemask.endswith(end):
                return result
        return ""

    def get_wildcard(self, part: str) -> str | None:
        """
        Generate language wilcard for a path part.

        Retruns None if not possible.
        """
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
                if token in {"-", "_", "."}:
                    continue
                if self.is_language_code(token):
                    end = pos + 1
                    if pos + 3 <= len(tokens) and self.is_language_code(
                        "".join(tokens[pos : pos + 3]),
                    ):
                        end = pos + 3
                    # Skip possible language codes in middle of string
                    if pos != 0 and end != len(tokens) and tokens[end] != ".":
                        continue
                    return "{}*{}.{}".format(
                        "".join(tokens[:pos]),
                        "".join(tokens[end:]),
                        ext,
                    )
        return None

    def fill_in_new_base(self, result: ResultDict) -> None:
        if self.new_base_mask is None:
            return
        path = result["filemask"]
        basename = path.rsplit("/", 1)[-1].rsplit(".", 1)[0]
        if "*" in basename:
            for replacement_match, replacement in TEMPLATE_REPLACEMENTS:
                basename = basename.replace(replacement_match, replacement)
        new_name = self.new_base_mask.replace("*", basename).lower()

        new_regex = f"{re.escape(new_name)}|{fnmatch.translate(self.new_base_mask)}"

        best_result = None

        while "/" in path:
            path = path.rsplit("/", 1)[0]
            path_wild = path.replace("*", "")
            for match in self.finder.filter_files(
                new_regex,
                f"{re.escape(path)}|{re.escape(path_wild)}",
            ):
                if new_name == match.parts[-1].lower():
                    result["new_base"] = "/".join(match.parts)
                    return
                if not best_result:
                    best_result = "/".join(match.parts)

        if best_result is not None:
            result["new_base"] = best_result

    def has_storage(self, name: str) -> bool:
        """Check whether finder has a storage."""
        return self.finder.has_file(name)

    def get_language_aliases(self, language: str) -> list[str]:
        """Language code aliases."""
        return [language]

    def possible_templates(self, language: str, mask: str) -> Generator[str]:
        """Yield possible template filenames."""
        for alias in self.get_language_aliases(language):
            yield mask.replace("*", alias)
        for match, replacement in TEMPLATE_REPLACEMENTS:
            if match in mask:
                yield mask.replace(match, replacement)

    def fill_in_template(
        self,
        result: ResultDict,
        source_language: str | None = None,
    ) -> None:
        if "template" not in result:
            if source_language is None:
                source_language = self.source_language
            for template in self.possible_templates(
                source_language,
                result["filemask"],
            ):
                if self.has_storage(template):
                    result["template"] = template
                    break

    def fill_in_file_format(self, result: ResultDict) -> None:
        if "file_format" not in result:
            result["file_format"] = self.file_format

    def adjust_format(self, result: ResultDict) -> None:
        return

    def discover(
        self, eager: bool = False, hint: str | None = None
    ) -> Generator[DiscoveryResult]:
        """Retun list of translation configurations matching this discovery."""
        discovered = set()
        for result in self.get_masks(eager=eager, hint=hint):
            if result["filemask"] in discovered:
                continue
            self.fill_in_template(result)
            self.adjust_format(result)
            self.fill_in_new_base(result)
            self.fill_in_file_format(result)
            discovered.add(result["filemask"])
            discovery_result = DiscoveryResult(result)
            discovery_result.meta["discovery"] = self.__class__.__name__
            discovery_result.meta["origin"] = self.origin
            discovery_result.meta["priority"] = self.priority
            yield discovery_result

    @property
    def masks_list(self) -> tuple[str, ...]:
        if isinstance(self.mask, str):
            return (self.mask,)
        return self.mask

    def filter_files(self) -> Generator[PurePath]:
        """Filters possible file matches."""
        return self.finder.filter_files(
            "|".join(fnmatch.translate(mask) for mask in self.masks_list),
        )

    def get_masks(
        self, eager: bool = False, hint: str | None = None
    ) -> Generator[ResultDict]:
        """
        Return all file masks found in the directory.

        It is expected to contain duplicates.
        """
        if hint:
            for mask in self.masks_list:
                if fnmatch.fnmatch(hint, mask):
                    yield {"filemask": hint}
        for path in self.filter_files():
            parts = list(path.parts)
            if eager:
                parts[-1] = "*.{}".format(parts[-1].rsplit(".", 1)[1])
                result: ResultDict = {"filemask": "/".join(parts)}
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
                    mask_parts = parts.copy()
                    match = re.compile(f"(^|[._-]){re.escape(part)}($|[._-])")
                    for i, current in enumerate(mask_parts):
                        if match.findall(current):
                            skip.add(i)
                            mask_parts[i] = match.sub(
                                f"\\g<1>{wildcard}\\g<2>", current
                            )
                    mask_parts[pos] = wildcard
                    yield {"filemask": "/".join(mask_parts)}


class MonoTemplateDiscovery(BaseDiscovery):
    """Base class for monolingual template based files."""

    uses_template = True

    def fill_in_new_base(self, result: ResultDict) -> None:
        if "new_base" not in result and "template" in result:
            result["new_base"] = result["template"]


class EncodingDiscovery(BaseDiscovery):
    """Base class for formats needing encoding detection."""

    encoding_map: dict[str, str] = {}

    def adjust_format(self, result: ResultDict) -> None:
        encoding: str | None = None
        matches = [self.finder.mask_matches(result["filemask"])]
        if "template" in result:
            matches.append(self.finder.mask_matches(result["template"]))

        for path in chain(*matches):
            if not isinstance(path, Path):
                # PurePath only
                continue
            with self.finder.open(path, "rb") as handle:
                detection_result = from_fp(handle).best()
            if detection_result is None:
                continue

            encoding = detection_result.encoding.lower()
            if encoding in self.encoding_map:
                result["file_format"] = self.encoding_map[encoding]
            return


class EnglishVariantsDiscovery(BaseDiscovery):
    def get_language_aliases(self, language: str) -> list[str]:
        """Language code aliases."""
        result = super().get_language_aliases(language)
        if language == "en":
            result.extend(["en-US", "en-GB", "en-AU"])
        return result
