# Copyright © Michal Čihař <michal@weblate.org>
#
# SPDX-License-Identifier: GPL-3.0-or-later

"""Transifex configuration discovery."""

from __future__ import annotations

import re
from configparser import Error as ConfigParserError
from configparser import RawConfigParser
from pathlib import PureWindowsPath
from typing import TYPE_CHECKING, ClassVar

from translation_finder.api import register_discovery

from .base import BaseDiscovery

if TYPE_CHECKING:
    from collections.abc import Generator

    from .result import DiscoveryResult, FileFormatParams, ResultDict


@register_discovery
class TransifexDiscovery(BaseDiscovery):
    """Transifex configuration discovery."""

    origin = "Transifex"
    priority = 500

    typemap: ClassVar[dict[str, str]] = {
        "ANDROID": "aresource",
        "STRINGS": "strings",
        "CHROME": "webextension",
        "PO": "po",
        "PROPERTIES": "properties",
        "UNICODEPROPERTIES": "properties",
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
    format_params: ClassVar[dict[str, FileFormatParams]] = {
        "UNICODEPROPERTIES": {"properties_encoding": "utf-8"},
    }

    def extract_format(self, transifex: str) -> tuple[str, FileFormatParams | None]:
        """Convert Transifex format to Weblate."""
        transifex = transifex.upper()
        try:
            file_format = self.typemap[transifex]
        except KeyError:
            return "", None
        params = self.format_params.get(transifex)
        return file_format, params.copy() if params is not None else None

    @staticmethod
    def normalize_config_path(path: str) -> str:
        """Normalize path separators used in Transifex configuration."""
        return path.strip().replace("\\", "/")

    @classmethod
    def is_safe_config_path(cls, path: str) -> bool:
        """Check whether a Transifex configuration path stays in the repository."""
        normalized = cls.normalize_config_path(path)
        return not (
            normalized.startswith("/")
            or PureWindowsPath(normalized).drive
            or ".." in normalized.split("/")
        )

    def extract_section(
        self, config: RawConfigParser, section: str
    ) -> ResultDict | None:
        """Extract single section from Transifex configuration."""
        if section == "main" or not config.has_option(section, "file_filter"):
            return None
        filemask = self.normalize_config_path(
            config.get(section, "file_filter").replace("<lang>", "*")
        )
        if not self.is_safe_config_path(filemask):
            return None
        result: ResultDict = {
            "name": section,
            "filemask": filemask,
            "file_format": "",
        }

        if config.has_option(section, "type"):
            file_format, file_format_params = self.extract_format(
                config.get(section, "type")
            )
            result["file_format"] = file_format
            if file_format_params is not None:
                result["file_format_params"] = file_format_params

        if not result["file_format"]:
            result["file_format"] = self.detect_format(result["filemask"])
        if not result["file_format"]:
            return None

        if config.has_option(section, "source_file"):
            template = self.normalize_config_path(config.get(section, "source_file"))
            if not self.is_safe_config_path(template):
                return None
            if template.lower().endswith(".pot"):
                result["new_base"] = template
            else:
                result["template"] = template

        return result

    @staticmethod
    def get_language_regex(filemask: str, source_file: str) -> str | None:
        """Return filter excluding the source language matched by the file mask."""
        pattern = re.escape(filemask).replace(r"\*", r"([^/]+)")
        match = re.fullmatch(pattern, source_file)
        if match is None:
            return None
        return rf"^(?!{re.escape(match.group(1))}$).+$"

    def discover(
        self, *, eager: bool = False, hint: str | None = None
    ) -> Generator[DiscoveryResult]:
        """Yield translation configurations matching Transifex configuration."""
        for result in super().discover(eager=eager, hint=hint):
            if (
                result.get("file_format") != "po"
                or "template" not in result
                or not result["template"].lower().endswith(".po")
            ):
                yield result
                continue

            template = result["template"]
            language_regex = self.get_language_regex(result["filemask"], template)

            bilingual = result.copy()
            del bilingual["template"]
            bilingual["new_base"] = template
            if language_regex is not None:
                bilingual["language_regex"] = language_regex
            yield bilingual

            monolingual = result.copy()
            monolingual["file_format"] = "po-mono"
            yield monolingual

    def get_masks(
        self, *, eager: bool = False, hint: str | None = None
    ) -> Generator[ResultDict]:
        """Retuns matches from transifex files."""
        for path in self.finder.filter_files(
            "config",
            "(?:.*/|^).tx",
            candidate_names=("config",),
        ):
            config = RawConfigParser()
            with self.finder.open(path) as handle:
                try:
                    config.read_file(handle)
                except ConfigParserError:
                    # Skip invalid files
                    continue
            for section in config.sections():
                result = self.extract_section(config, section)
                if result:
                    yield result
