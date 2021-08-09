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
"""Individual discovery rules for translation formats."""

import json
import re
from itertools import chain
from typing import Dict

from ruamel.yaml import YAML
from ruamel.yaml.error import YAMLError, YAMLFutureWarning

from ..api import register_discovery
from .base import BaseDiscovery, EncodingDiscovery, MonoTemplateDiscovery

LARAVEL_RE = re.compile(r"=>.*\|")


@register_discovery
class GettextDiscovery(BaseDiscovery):
    """Gettext PO files discovery."""

    file_format = "po"
    mask = "*.po"
    new_base_mask = "*.pot"

    def discover(self, eager: bool = False):
        for result in super().discover(eager=eager):
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
    mask = ("*.xliff", "*.xlf", "*.sdlxliff", "*.mxliff")


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


@register_discovery
class WebExtensionDiscovery(BaseDiscovery):
    """web extension files discovery."""

    file_format = "webextension"
    mask = "messages.json"


@register_discovery
class AndroidDiscovery(BaseDiscovery):
    """Android string files discovery."""

    file_format = "aresource"

    def get_masks(self, eager: bool = False):
        """Return all file masks found in the directory.

        It is expected to contain duplicates."""
        for path in self.finder.filter_files("strings*.xml", "*/values"):
            mask = list(path.parts)
            mask[-2] = "values-*"

            yield {"filemask": "/".join(mask), "template": path.as_posix()}


@register_discovery
class OSXDiscovery(EncodingDiscovery):
    """OSX string properties files discovery."""

    file_format = "strings-utf8"
    encoding_map = {
        "utf-16": "strings-utf16",
    }

    def get_masks(self, eager: bool = False):
        """Return all file masks found in the directory.

        It is expected to contain duplicates."""
        for path in chain(
            self.finder.filter_files("*.strings", "*/base.lproj"),
            self.finder.filter_files("*.strings", "*/en.lproj"),
        ):
            mask = list(path.parts)
            mask[-2] = "*.lproj"

            yield {"filemask": "/".join(mask), "template": path.as_posix()}


@register_discovery
class StringsdictDiscovery(BaseDiscovery):
    """Stringsdoct files discovery."""

    file_format = "stringsdict"

    def get_masks(self, eager: bool = False):
        """Return all file masks found in the directory.

        It is expected to contain duplicates."""
        for path in chain(
            self.finder.filter_files("*.stringsdict", "*/base.lproj"),
            self.finder.filter_files("*.stringsdict", "*/en.lproj"),
        ):
            mask = list(path.parts)
            mask[-2] = "*.lproj"

            yield {"filemask": "/".join(mask), "template": path.as_posix()}


@register_discovery
class JavaDiscovery(EncodingDiscovery):
    """Java string properties files discovery."""

    file_format = "properties"
    encoding_map = {
        "utf-8": "properties-utf8",
        "utf-16": "properties-utf16",
    }
    mask = ["*_*.properties", "*.properties"]

    def possible_templates(self, language: str, mask: str):
        yield mask.replace("_*", "")
        yield from super().possible_templates(language, mask)


@register_discovery
class RESXDiscovery(BaseDiscovery):
    """RESX files discovery."""

    file_format = "resx"
    mask = "resources.res[xw]"

    def possible_templates(self, language: str, mask: str):
        yield mask.replace(".*", "")
        yield from super().possible_templates(language, mask)

    def get_masks(self, eager: bool = False):
        """Return all file masks found in the directory.

        It is expected to contain duplicates."""
        for path in self.finder.filter_files("*.*.res[xw]"):
            mask = list(path.parts)
            base, code, ext = mask[-1].rsplit(".", 2)
            if not self.is_language_code(code):
                continue
            mask[-1] = f"{base}.*.{ext}"
            yield {"filemask": "/".join(mask)}
        yield from super().get_masks(eager=eager)


@register_discovery
class AppStoreDiscovery(BaseDiscovery):
    """App store metadata."""

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

    def has_storage(self, name: str):
        """Check whether finder has a storage."""
        return self.finder.has_dir(name)

    def get_language_aliases(self, language: str):
        """Language code aliases."""
        result = super().get_language_aliases(language)
        if language == "en":
            result.extend(["en-US", "en-GB", "en-AU"])
        return result


@register_discovery
class JSONDiscovery(BaseDiscovery):
    """JSON files discovery."""

    file_format = "json-nested"
    mask = "*.json"

    def detect_dict(self, data, level=0):
        all_strings = True
        i18next = False
        for key, value in data.items():
            if (
                level == 0
                and isinstance(value, dict)
                and "message" in value
                and "description" in value
            ):
                return False, False, True
            if not isinstance(key, str):
                all_strings = False
                break
            if not isinstance(value, str):
                all_strings = False
                if isinstance(value, dict):
                    i18next |= self.detect_dict(value, level + 1)[1]
            elif key.endswith("_plural") or "{{" in value:
                i18next = True

        return all_strings, i18next, False

    def adjust_format(self, result: Dict[str, str]):
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
            if isinstance(data, list) and len(data) > 0 and "id" in data[0]:
                result["file_format"] = "go-i18n-json"
                return
            if not isinstance(data, dict):
                return

            all_strings, i18next, webext = self.detect_dict(data)

            if webext:
                result["file_format"] = "webextension"
            elif i18next:
                result["file_format"] = "i18next"
            elif all_strings:
                result["file_format"] = "json"


@register_discovery
class FluentDiscovery(BaseDiscovery):
    """Fluent files discovery."""

    file_format = "fluent"
    mask = "*.ftl"

    def get_language_aliases(self, language: str):
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

    def adjust_format(self, result: Dict[str, str]):
        if "template" not in result:
            return

        path = list(self.finder.mask_matches(result["template"]))[0]

        if not hasattr(path, "open"):
            return

        with self.finder.open(path, "rb") as handle:
            yaml = YAML()
            try:
                data = yaml.load(handle)
            except (YAMLError, YAMLFutureWarning):
                return
            if isinstance(data, dict) and len(data) == 1:
                key = list(data.keys())[0]
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

    def adjust_format(self, result: Dict[str, str]):
        if "template" not in result:
            return

        path = list(self.finder.mask_matches(result["template"]))[0]

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

    def fill_in_new_base(self, result: Dict[str, str]):
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

    @staticmethod
    def get_language_aliases(language: str):
        """Language code aliases."""
        if language == "en":
            return [language, "enu", "ENU"]
        return [language]


@register_discovery
class TBXDiscovery(BaseDiscovery):
    """TBX files discovery."""

    file_format = "tbx"
    mask = "*.tbx"
