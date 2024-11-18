# Copyright © Michal Čihař <michal@weblate.org>
#
# SPDX-License-Identifier: GPL-3.0-or-later

"""Individual discovery rules for translation formats."""

from __future__ import annotations

import json
import re
import warnings
from typing import TYPE_CHECKING

from ruamel.yaml import YAML
from ruamel.yaml.error import YAMLError, YAMLFutureWarning

from translation_finder.api import register_discovery

from .base import (
    BaseDiscovery,
    EncodingDiscovery,
    EnglishVariantsDiscovery,
    MonoTemplateDiscovery,
)

if TYPE_CHECKING:
    from collections.abc import Generator
    from pathlib import PurePath

    from .result import DiscoveryResult, ResultDict

LARAVEL_RE = re.compile(r"=>.*\|")


@register_discovery
class GettextDiscovery(BaseDiscovery):
    """Gettext PO files discovery."""

    file_format = "po"
    mask = "*.po"
    new_base_mask = "*.pot"

    def discover(
        self, eager: bool = False, hint: str | None = None
    ) -> Generator[DiscoveryResult]:
        for result in super().discover(eager=eager, hint=hint):
            if "template" not in result:
                yield result
                continue
            bi = result.copy()
            del bi["template"]
            yield bi
            mono = result.copy()
            mono["file_format"] = "po-mono"
            yield mono

    def fill_in_new_base(self, result: ResultDict) -> None:
        super().fill_in_new_base(result)
        if "new_base" not in result:
            pot_names = [
                result["filemask"].replace("po/*/", "pot/") + "t",
                result["filemask"].replace("*", "templates") + "t",
                result["filemask"].replace(".*", ""),
                result["filemask"].replace("_*", ""),
                result["filemask"].replace("-*", ""),
            ]
            for pot_name in pot_names:
                if self.finder.has_file(pot_name):
                    result["new_base"] = pot_name
                    break


@register_discovery
class QtDiscovery(BaseDiscovery):
    """Qt Linguist files discovery."""

    file_format = "ts"
    mask = "*.ts"
    new_base_mask = "*.ts"


@register_discovery
class XliffDiscovery(BaseDiscovery):
    """XLIFF files discovery."""

    file_format = "xliff"
    mask = ("*.xliff", "*.xlf", "*.sdlxliff", "*.mxliff", "*.poxliff")

    def adjust_format(self, result: ResultDict) -> None:
        base = result["template"] if "template" in result else result["filemask"]

        path = next(iter(self.finder.mask_matches(base)))

        if not hasattr(path, "open"):
            return

        with self.finder.open(path, "r") as handle:
            content = handle.read()
            if 'restype="x-gettext' in content:
                result["file_format"] = "poxliff"
            elif "<x " not in content and "<g " not in content:
                result["file_format"] = "plainxliff"


@register_discovery
class JoomlaDiscovery(BaseDiscovery):
    """Joomla files discovery."""

    file_format = "joomla"
    mask = "*.ini"


@register_discovery
class CSVDiscovery(MonoTemplateDiscovery):
    """CSV files discovery."""

    file_format = "csv"
    mask = "*.csv"

    def discover(
        self, eager: bool = False, hint: str | None = None
    ) -> Generator[DiscoveryResult]:
        for result in super().discover(eager=eager, hint=hint):
            if "template" not in result:
                yield result
                continue
            bilingual = result.copy()
            del bilingual["template"]
            yield bilingual
            yield result


@register_discovery
class WebExtensionDiscovery(BaseDiscovery):
    """web extension files discovery."""

    file_format = "webextension"
    mask = "messages.json"


@register_discovery
class AndroidDiscovery(BaseDiscovery):
    """Android string files discovery."""

    file_format = "aresource"

    def get_masks(
        self, eager: bool = False, hint: str | None = None
    ) -> Generator[ResultDict]:
        """
        Return all file masks found in the directory.

        It is expected to contain duplicates.
        """
        for path in self.finder.filter_files(r"strings.*\.xml", ".*/values"):
            mask = list(path.parts)
            mask[-2] = "values-*"

            yield {"filemask": "/".join(mask), "template": path.as_posix()}


@register_discovery
class MOKODiscovery(BaseDiscovery):
    """Mobile Kotlin resources discovery."""

    file_format = "moko-resource"

    def get_masks(
        self, eager: bool = False, hint: str | None = None
    ) -> Generator[ResultDict]:
        """
        Return all file masks found in the directory.

        It is expected to contain duplicates.
        """
        for path in self.finder.filter_files(
            r"(strings|plurals)\.xml",
            ".*/resources/mr/base",
        ):
            mask = list(path.parts)
            mask[-2] = "*"

            yield {"filemask": "/".join(mask), "template": path.as_posix()}


@register_discovery
class OSXDiscovery(EncodingDiscovery):
    """OSX string properties files discovery."""

    file_format = "strings-utf8"
    encoding_map = {
        "utf_16": "strings",
    }

    def possible_templates(self, language: str, mask: str) -> Generator[str]:
        yield mask.replace("*", "Base")
        yield from super().possible_templates(language, mask)

    def get_masks(
        self, eager: bool = False, hint: str | None = None
    ) -> Generator[ResultDict]:
        """
        Return all file masks found in the directory.

        It is expected to contain duplicates.
        """
        for path in self.finder.filter_files(
            r".*\.strings",
            r".*/(base|en(-[a-z]{2})?)\.lproj",
        ):
            mask = list(path.parts)
            mask[-2] = "*.lproj"

            yield {"filemask": "/".join(mask), "template": path.as_posix()}

        for path in self.finder.filter_files(r"base\.strings"):
            mask = list(path.parts)
            mask[-1] = "*.strings"

            yield {"filemask": "/".join(mask), "template": path.as_posix()}


@register_discovery
class StringsdictDiscovery(BaseDiscovery):
    """Stringsdoct files discovery."""

    file_format = "stringsdict"

    def get_masks(
        self, eager: bool = False, hint: str | None = None
    ) -> Generator[ResultDict]:
        """
        Return all file masks found in the directory.

        It is expected to contain duplicates.
        """
        for path in self.finder.filter_files(
            r".*\.stringsdict",
            r".*/(base|en)\.lproj",
        ):
            mask = list(path.parts)
            mask[-2] = "*.lproj"

            yield {"filemask": "/".join(mask), "template": path.as_posix()}


@register_discovery
class JavaDiscovery(EncodingDiscovery):
    """Java string properties files discovery."""

    file_format = "properties"
    encoding_map = {
        "utf_8": "properties-utf8",
        "utf_16": "properties-utf16",
    }
    mask = ("*_*.properties", "*.properties")

    def possible_templates(self, language: str, mask: str) -> Generator[str]:
        yield mask.replace("_*", "")
        yield from super().possible_templates(language, mask)


@register_discovery
class RESXDiscovery(BaseDiscovery):
    """RESX files discovery."""

    file_format = "resx"
    mask = "resources.res[xw]"

    def possible_templates(self, language: str, mask: str) -> Generator[str]:
        yield mask.replace(".*", "")
        yield from super().possible_templates(language, mask)

    def get_masks(
        self, eager: bool = False, hint: str | None = None
    ) -> Generator[ResultDict]:
        """
        Return all file masks found in the directory.

        It is expected to contain duplicates.
        """
        for path in self.finder.filter_files(r".*\..*\.res[xw]"):
            mask = list(path.parts)
            base, code, ext = mask[-1].rsplit(".", 2)
            if not self.is_language_code(code):
                continue
            mask[-1] = f"{base}.*.{ext}"
            yield {"filemask": "/".join(mask)}
        yield from super().get_masks(eager=eager, hint=hint)


@register_discovery
class ResourceDictionaryDiscovery(BaseDiscovery):
    """ResourceDictionary files discovery."""

    file_format = "resourcedictionary"
    mask = "*.xaml"
    new_base_mask = "*.xaml"


@register_discovery
class AppStoreDiscovery(EnglishVariantsDiscovery):
    """App store metadata."""

    file_format = "appstore"

    def filter_files(self) -> Generator[PurePath]:
        """Filters possible file matches."""
        for path in self.finder.filter_files(
            "short_description.txt|full_description.txt|title.txt|description.txt|name.txt",
        ):
            yield path.parent
        for path in self.finder.filter_files(r".*\.txt", ".*/changelogs"):
            yield path.parent.parent

    def has_storage(self, name: str) -> bool:
        """Check whether finder has a storage."""
        return self.finder.has_dir(name)


@register_discovery
class JSONDiscovery(BaseDiscovery):
    """JSON files discovery."""

    file_format = "json-nested"
    mask = "*.json"

    def detect_dict(self, data: dict, level: int = 0) -> str | None:
        all_strings = True
        i18next = False
        i18nextv4 = False
        if "lang" in data and "messages" in data:
            return "gotext-json"
        for key, value in data.items():
            if (
                level == 0
                and isinstance(value, dict)
                and "message" in value
                and "description" in value
            ):
                return "webextension"
            if not isinstance(key, str):
                all_strings = False
                break
            if not isinstance(value, str):
                all_strings = False
                if isinstance(value, dict):
                    detected = self.detect_dict(value, level + 1)
                    i18next |= detected == "i18next"
                    i18nextv4 |= detected == "i18nextv4"
            elif key.endswith(("_one", "_many", "_other")):
                i18nextv4 = True
            elif key.endswith("_plural") or "{{" in value:
                i18next = True

        if i18nextv4:
            return "i18nextv4"
        if i18next:
            return "i18next"
        if all_strings:
            return "json"
        return None

    def adjust_format(self, result: ResultDict) -> None:
        if "template" not in result:
            return

        path = next(iter(self.finder.mask_matches(result["template"])))

        if not hasattr(path, "open"):
            return

        with self.finder.open(path, "r") as handle:
            try:
                data = json.load(handle)
            except ValueError:
                return
            if isinstance(data, list) and len(data) > 0 and "id" in data[0]:
                result["file_format"] = "go-i18n-json"
                return
            if not isinstance(data, dict):
                return

            detected = self.detect_dict(data)

            if detected is not None:
                result["file_format"] = detected


@register_discovery
class FluentDiscovery(BaseDiscovery):
    """Fluent files discovery."""

    file_format = "fluent"
    mask = "*.ftl"

    def get_language_aliases(self, language: str) -> list[str]:
        """Language code aliases."""
        result = super().get_language_aliases(language)
        if language == "en":
            result.append("en-US")
        return result


@register_discovery
class YAMLDiscovery(BaseDiscovery):
    """YAML files discovery."""

    file_format = "yaml"
    mask = ("*.yml", "*.yaml")

    def adjust_format(self, result: ResultDict) -> None:
        if "template" not in result:
            return

        path = next(iter(self.finder.mask_matches(result["template"])))

        if not hasattr(path, "open"):
            return

        with self.finder.open(path, "rb") as handle:
            yaml = YAML()
            try:
                data = yaml.load(handle)
            except (YAMLError, YAMLFutureWarning):
                return
            except Exception as error:  # noqa: BLE001
                # Weird errors can happen when parsing YAML, handle them gracefully, but
                # emit a warning
                warnings.warn(f"Could not parse YAML: {error}", stacklevel=0)
                return
            if isinstance(data, dict) and len(data) == 1:
                key = next(iter(data.keys()))
                if "filemask" in result:
                    if result["filemask"].replace("*", key) == result["template"]:
                        result["file_format"] = "ruby-yaml"
                elif key in result["template"]:
                    result["file_format"] = "ruby-yaml"


@register_discovery
class SRTDiscovery(MonoTemplateDiscovery):
    """SRT subtitle files discovery."""

    file_format = "srt"
    mask = "*.srt"


@register_discovery
class SUBDiscovery(MonoTemplateDiscovery):
    """SUB subtitle files discovery."""

    file_format = "sub"
    mask = "*.sub"


@register_discovery
class ASSDiscovery(MonoTemplateDiscovery):
    """ASS subtitle files discovery."""

    file_format = "ass"
    mask = "*.ass"


@register_discovery
class SSADiscovery(MonoTemplateDiscovery):
    """SSA subtitle files discovery."""

    file_format = "ssa"
    mask = "*.ssa"


@register_discovery
class PHPDiscovery(MonoTemplateDiscovery):
    """PHP files discovery."""

    file_format = "php"
    mask = "*.php"

    def adjust_format(self, result: ResultDict) -> None:
        if "template" not in result:
            return

        path = next(iter(self.finder.mask_matches(result["template"])))

        if not hasattr(path, "open"):
            return

        with self.finder.open(path, "r") as handle:
            content = handle.read()
            if "return [" in content and LARAVEL_RE.search(content):
                result["file_format"] = "laravel"


@register_discovery
class IDMLDiscovery(MonoTemplateDiscovery):
    """IDML files discovery."""

    file_format = "idml"
    mask = "*.idml"


@register_discovery
class HTMLDiscovery(MonoTemplateDiscovery):
    """HTML files discovery."""

    file_format = "html"
    mask = ("*.html", "*.htm")


@register_discovery
class TXTDiscovery(MonoTemplateDiscovery, EnglishVariantsDiscovery):
    """TXT files discovery."""

    file_format = "txt"
    mask = "*.txt"


@register_discovery
class ODFDiscovery(MonoTemplateDiscovery):
    """ODF files discovery."""

    file_format = "odf"
    mask = (
        "*.sxw",
        "*.odt",
        "*.ods",
        "*.odp",
        "*.odg",
        "*.odc",
        "*.odf",
        "*.odi",
        "*.odm",
        "*.ott",
        "*.ots",
        "*.otp",
        "*.otg",
        "*.otc",
        "*.otf",
        "*.oti",
        "*.oth",
    )


@register_discovery
class INIDiscovery(BaseDiscovery):
    """INI files discovery."""

    file_format = "ini"
    mask = "*.ini"


@register_discovery
class InnoSetupDiscovery(BaseDiscovery):
    """InnoSetup files discovery."""

    file_format = "islu"
    mask = "*.islu"


@register_discovery
class TOMLDiscovery(BaseDiscovery):
    """TOML files discovery."""

    file_format = "toml"
    mask = "*.toml"


@register_discovery
class ARBDiscovery(BaseDiscovery):
    """ARB files discovery."""

    file_format = "arb"
    mask = "*.arb"

    def fill_in_new_base(self, result: ResultDict) -> None:
        super().fill_in_new_base(result)
        if "intermediate" not in result:
            # Flutter intermediate files
            intermediate = result["filemask"].replace("*", "messages")
            if self.finder.has_file(intermediate):
                result["intermediate"] = intermediate


@register_discovery
class RCDiscovery(MonoTemplateDiscovery):
    """RC files discovery."""

    file_format = "rc"
    mask = ("*.rc",)

    def get_language_aliases(self, language: str) -> list[str]:
        """Language code aliases."""
        if language == "en":
            return [language, "enu", "ENU"]
        return [language]


@register_discovery
class TBXDiscovery(BaseDiscovery):
    """TBX files discovery."""

    file_format = "tbx"
    mask = "*.tbx"


@register_discovery
class FormatJSDiscovery(BaseDiscovery):
    """Format.JS JSON files discovery."""

    file_format = "formatjs"

    def get_masks(
        self, eager: bool = False, hint: str | None = None
    ) -> Generator[ResultDict]:
        """
        Return all file masks found in the directory.

        It is expected to contain duplicates.
        """
        for path in self.finder.filter_files(r"en.json", ".*/extracted"):
            mask = list(path.parts)
            mask[-1] = "*.json"
            mask[-2] = "lang"

            yield {"filemask": "/".join(mask), "template": path.as_posix()}
