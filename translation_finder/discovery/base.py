# Copyright © Michal Čihař <michal@weblate.org>
#
# SPDX-License-Identifier: GPL-3.0-or-later

"""Base discovery code."""

from __future__ import annotations

import fnmatch
import re
from itertools import chain
from pathlib import Path
from typing import TYPE_CHECKING, ClassVar

from charset_normalizer import from_fp
from weblate_language_data.country_codes import COUNTRIES
from weblate_language_data.language_codes import LANGUAGES

from translation_finder.data import LANGUAGES_BLACKLIST

from .result import DiscoveryResult

if TYPE_CHECKING:
    from collections.abc import Generator
    from pathlib import PurePath

    from translation_finder.finder import Finder

    from .result import FileFormatParams, ResultDict

TOKEN_SPLIT = re.compile(r"([_.-])")

LOCALES = {"latn", "cyrl", "hant", "hans"}

EXTENSION_MAP = (
    (".po", "po"),
    ("strings.xml", "aresource"),
    (".stringsdict", "stringsdict"),
    (".ini", "joomla"),
    (".islu", "islu"),
    (".csv", "csv"),
    (".ftl", "fluent"),
    (".json", "json-nested"),
    (".arb", "arb"),
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
    (".srt", "srt"),
    (".sub", "sub"),
    (".ass", "ass"),
    (".ssa", "ssa"),
    (".txt", "txt"),
    (".html", "html"),
    (".htm", "html"),
    (".idml", "idml"),
    (".idms", "idml"),
    (".rc", "rc"),
    (".catkeys", "catkeys"),
    (".lang", "mi18n-lang"),
    (".toml", "toml"),
    (".tbx", "tbx"),
    (".md", "markdown"),
    (".markdown", "markdown"),
    (".dw", "dokuwiki"),
    (".mw", "mediawiki"),
    (".ad", "asciidoc"),
    (".adoc", "asciidoc"),
    (".asciidoc", "asciidoc"),
    (".wxl", "wxl"),
    (".xml", "flatxml"),
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

    file_format: ClassVar[str] = ""
    file_format_params: ClassVar[FileFormatParams | None] = None
    mask: ClassVar[str | tuple[str, ...]] = "*.*"
    new_base_mask: ClassVar[str | None] = None
    origin: ClassVar[str | None] = None
    priority: ClassVar[int] = 1000
    uses_template: ClassVar[bool] = False

    def __init__(self, finder: Finder, source_language: str = "en") -> None:
        self.finder: Finder = finder
        self.source_language: str = source_language

    @staticmethod
    def is_country_code(code: str) -> bool:
        """Check whether string looks like a country code."""
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
        """Detect format based on the file mask."""
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
        """Extend the result for new_base and intermediate parameters."""
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

    def get_language_aliases(self, language: str) -> list[str]:  # noqa: PLR6301
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
        """Extend the result with template name."""
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
        """Extend the result with class default file format if not present."""
        if "file_format" not in result:
            result["file_format"] = self.file_format

    def fill_in_file_format_params(self, result: ResultDict) -> None:
        """Extend the result with class default file format parameters."""
        if self.file_format_params is not None and "file_format_params" not in result:
            result["file_format_params"] = self.file_format_params.copy()

    def adjust_format(self, result: ResultDict) -> None:  # noqa: PLR6301
        """Override detected format, based on the file content."""
        return

    def discover(
        self, *, eager: bool = False, hint: str | None = None
    ) -> Generator[DiscoveryResult]:
        """Yield translation configurations matching this discovery."""
        discovered = set()
        for result in self.get_masks(eager=eager, hint=hint):
            if result["filemask"] in discovered:
                continue
            self.fill_in_template(result)
            self.adjust_format(result)
            self.fill_in_new_base(result)
            self.fill_in_file_format(result)
            self.fill_in_file_format_params(result)
            discovered.add(result["filemask"])
            discovery_result = DiscoveryResult(result)
            discovery_result.meta["discovery"] = self.__class__.__name__
            discovery_result.meta["origin"] = self.origin
            discovery_result.meta["priority"] = self.priority
            yield discovery_result

    @property
    def masks_list(self) -> tuple[str, ...]:
        """Normalized access for mask property."""
        if isinstance(self.mask, str):
            if not self.mask:
                return ()
            return (self.mask,)
        return self.mask

    def filter_files(self) -> Generator[PurePath]:
        """Filter possible file matches."""
        return self.finder.filter_files(
            "|".join(fnmatch.translate(mask) for mask in self.masks_list),
        )

    def get_masks(
        self, *, eager: bool = False, hint: str | None = None
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

    def fill_in_new_base(self, result: ResultDict) -> None:  # noqa: PLR6301
        """Extend the result for new_base and intermediate parameters."""
        if "new_base" not in result and "template" in result:
            result["new_base"] = result["template"]


class EncodingDiscovery(BaseDiscovery):
    """Base class for formats needing encoding detection."""

    encoding_parameter: ClassVar[str] = ""
    encoding_parameters_by_format: ClassVar[dict[str, str]] = {}
    encoding_map: ClassVar[dict[str, str]] = {}

    def get_encoding_parameter(self, result: ResultDict) -> str:
        """Return the encoding parameter for the result format."""
        file_format = result.get("file_format") or self.file_format
        if self.encoding_parameters_by_format:
            return self.encoding_parameters_by_format.get(file_format, "")
        if file_format == self.file_format:
            return self.encoding_parameter
        return ""

    def get_managed_encoding_parameters(self) -> tuple[str, ...]:
        """Return file format parameter names managed by this discovery."""
        parameters = list(self.encoding_parameters_by_format.values())
        if self.encoding_parameter:
            parameters.append(self.encoding_parameter)
        return tuple(dict.fromkeys(parameters))

    def normalize_encoding_parameters(self, result: ResultDict) -> None:
        """Keep only the encoding parameter supported by the result format."""
        params = result.get("file_format_params")
        if params is None:
            return

        parameter = self.get_encoding_parameter(result)
        value = params.get(parameter) if parameter else None
        for managed_parameter in self.get_managed_encoding_parameters():
            if value is None and managed_parameter in params:
                value = params[managed_parameter]
            if managed_parameter != parameter:
                params.pop(managed_parameter, None)

        if parameter and value is not None:
            params[parameter] = value
        if not params:
            result.pop("file_format_params", None)

    def set_encoding_parameter(self, result: ResultDict, encoding: str) -> None:
        """Set detected encoding in the parameter for the result format."""
        parameter = self.get_encoding_parameter(result)
        self.normalize_encoding_parameters(result)
        if not parameter:
            return

        params = result.get("file_format_params")
        if params is None:
            params = {}
            result["file_format_params"] = params
        params[parameter] = encoding

    def detect_encoding(self, result: ResultDict) -> str | None:
        """Detect file encoding and translate it to a Weblate parameter value."""
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
            return self.encoding_map.get(encoding)
        return None

    def adjust_encoding(self, result: ResultDict) -> str | None:
        """Detect and set encoding parameter."""
        encoding = self.detect_encoding(result)
        if encoding is None:
            self.normalize_encoding_parameters(result)
        else:
            self.set_encoding_parameter(result, encoding)
        return encoding

    def adjust_format(self, result: ResultDict) -> None:
        """Override detected format, based on the file content."""
        self.adjust_encoding(result)


class EnglishVariantsDiscovery(BaseDiscovery):
    """Discovery supporting widely used English variants."""

    def get_language_aliases(self, language: str) -> list[str]:
        """Language code aliases."""
        result = super().get_language_aliases(language)
        if language == "en":
            result.extend(["en-US", "en-GB", "en-AU"])
        return result
