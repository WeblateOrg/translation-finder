# Copyright © Michal Čihař <michal@weblate.org>
#
# SPDX-License-Identifier: GPL-3.0-or-later

"""Individual discovery rules for translation formats."""

from __future__ import annotations

import csv
import json
import re
import warnings
from io import StringIO
from itertools import product
from typing import TYPE_CHECKING, ClassVar
from xml.parsers import expat

from translation_finder.api import register_discovery

from .base import (
    FORMAT_SNIFF_MAX_BYTES,
    FORMAT_SNIFF_MAX_FILES,
    BaseDiscovery,
    EncodingDiscovery,
    EnglishVariantsDiscovery,
    MonoTemplateDiscovery,
)

if TYPE_CHECKING:
    from collections.abc import Generator
    from pathlib import PurePath

    from translation_finder.finder import Finder

    from .result import DiscoveryResult, ResultDict

# Anchoring limits matching to one attempt per line, while the atomic group
# prevents retrying the match from every subsequent ``=>`` on that line.
LARAVEL_BYTES_RE = re.compile(
    rb"^(?>[^\n]*?=>)[^\n]*\|",
    re.MULTILINE,
)
GWT_PLURAL_RE = re.compile(r"^[^#!\s][^:=\n]*\[[a-zA-Z_]+\]\s*[:=]", re.MULTILINE)
CSV_DIALECT_SNIFF_MAX_CHARS = 1024
CSV_SAMPLE_ROWS = 100
SIMPLE_CSV_COLUMNS = 2
CSV_DELIMITERS = ",;\t"
CSV_QUOTECHARS = "\"'"
RUBY_YAML_ROOT_RE = re.compile(
    r'^(?:"(?P<double>[A-Za-z0-9_.@-]+)"|\'(?P<single>[A-Za-z0-9_.@-]+)\'|'
    r"(?P<plain>[A-Za-z0-9_.@-]+)):(?=[ \t]|$)"
)
TOML_MESSAGES_KEY = r'(?:messages|"messages"|\'messages\')'
TOML_ID_KEY = r'(?:id|"id"|\'id\')'
TOML_MESSAGES_RE = re.compile(rf"^\s*\[\[\s*{TOML_MESSAGES_KEY}\s*\]\]\s*$")
TOML_INLINE_MESSAGES_RE = re.compile(rf"^\s*{TOML_MESSAGES_KEY}\s*=\s*\[")
TOML_TABLE_RE = re.compile(r"^\s*\[")
TOML_ID_RE = re.compile(rf"\s*{TOML_ID_KEY}\s*=")
CSV_FIELDNAMES = {
    "context",
    "developer_comments",
    "fuzzy",
    "id",
    "id_hash",
    "location",
    "source",
    "source_plural_form",
    "target",
    "target_plural_form",
    "translator_comments",
}


class _QtRootFoundError(Exception):
    """Stop Qt XML parsing after the root element."""


def _get_qt_ts_version(content: str) -> str | None:
    """Return the version from a Qt TS root element."""
    version: str | None = None
    parser = expat.ParserCreate()

    def handle_start(name: str, attributes: dict[str, str]) -> None:
        nonlocal version
        if name == "TS":
            version = attributes.get("version")
        raise _QtRootFoundError

    parser.StartElementHandler = handle_start
    try:
        parser.Parse(content, False)  # ruff: ignore[boolean-positional-value-in-call]
    except _QtRootFoundError:
        return version
    except expat.ExpatError:
        return None
    return None


def _detect_utf32_encoding(content: bytes) -> str | None:
    """Detect standard UTF-32 byte orders from a BOM or XML opening marker."""
    if content.startswith((b"\x00\x00\xfe\xff", b"\xff\xfe\x00\x00")):
        return "utf-32"
    if content.startswith(b"\x00\x00\x00<"):
        return "utf-32-be"
    if content.startswith(b"<\x00\x00\x00"):
        return "utf-32-le"
    return None


def _decode_content(content: bytes) -> str:
    """Decode sampled file content."""
    for encoding in ("utf-8-sig", "utf-16"):
        try:
            return content.decode(encoding)
        except UnicodeError:
            continue
    return content.decode("iso-8859-1")


def _decode_sample_content(content: bytes) -> str:
    """Decode sampled file content, ignoring incomplete trailing bytes."""
    if encoding := _detect_utf32_encoding(content):
        return content[: len(content) - len(content) % 4].decode(
            encoding, errors="replace"
        )

    try:
        return content.decode("utf-8-sig")
    except UnicodeDecodeError as error:
        if error.end == len(content) and error.reason == "unexpected end of data":
            return content[: error.start].decode("utf-8-sig")

    if content.startswith((b"\xff\xfe", b"\xfe\xff")):
        try:
            return content.decode("utf-16")
        except UnicodeDecodeError as error:
            if error.end == len(content) and error.reason == "truncated data":
                return content[: error.start].decode("utf-16")

    return content.decode("iso-8859-1")


def _read_binary_sample(
    finder: Finder,
    path: PurePath,
    size: int | None = None,
) -> bytes | None:
    """Read a bounded binary sample from a real finder path."""
    if size is None:
        size = FORMAT_SNIFF_MAX_BYTES
    if not hasattr(path, "open"):
        return None
    try:
        with finder.open(path, "rb") as handle:
            return handle.read(size)
    except OSError:
        return None


def _read_binary_sniff_sample(
    finder: Finder,
    path: PurePath,
    size: int | None = None,
) -> tuple[bytes, bool] | None:
    """Read a bounded binary sample and report whether it is the complete file."""
    if size is None:
        size = FORMAT_SNIFF_MAX_BYTES
    if not hasattr(path, "open"):
        return None
    try:
        with finder.open(path, "rb") as handle:
            content = handle.read(size + 1)
    except OSError:
        return None
    return content[:size], len(content) <= size


def _read_binary_sniff_content(
    finder: Finder,
    path: PurePath,
    size: int | None = None,
) -> bytes | None:
    """Read complete content only when it fits within the sniffing limit."""
    sample = _read_binary_sniff_sample(finder, path, size)
    if sample is None:
        return None
    content, complete = sample
    if not complete:
        return None
    return content


def _read_text_sample(
    finder: Finder,
    path: PurePath,
    size: int | None = None,
) -> str | None:
    """Read a text sample from a real finder path."""
    content = _read_binary_sample(finder, path, size)
    if content is None:
        return None
    return _decode_sample_content(content)


def _read_text_sniff_content(
    finder: Finder,
    path: PurePath,
    size: int | None = None,
) -> str | None:
    """Read complete text content only when it fits within the sniffing limit."""
    content = _read_binary_sniff_content(finder, path, size)
    if content is None:
        return None
    return _decode_content(content)


class _FormatSniffBudget:
    """Bound aggregate format sniffing across files in one result."""

    def __init__(self) -> None:
        self.remaining_bytes = FORMAT_SNIFF_MAX_BYTES
        self.remaining_files = FORMAT_SNIFF_MAX_FILES

    @property
    def exhausted(self) -> bool:
        """Whether another file can be inspected."""
        return self.remaining_bytes <= 0 or self.remaining_files <= 0

    def read(self, finder: Finder, path: PurePath) -> tuple[bytes, bool] | None:
        """Read one sample and charge it to the budget."""
        self.remaining_files -= 1
        sample = _read_binary_sniff_sample(finder, path, self.remaining_bytes)
        if sample is not None:
            self.remaining_bytes -= len(sample[0])
        return sample


def _parse_csv_rows(text: str) -> list[list[str]] | None:
    """Parse rows from a decoded CSV sample."""
    if not text or not any(delimiter in text for delimiter in ",;\t"):
        return None

    delimiter, quotechar, skipinitialspace = _detect_csv_dialect(
        text[:CSV_DIALECT_SNIFF_MAX_CHARS]
    )

    rows: list[list[str]] = []
    try:
        for row in csv.reader(
            StringIO(text),
            delimiter=delimiter,
            quotechar=quotechar,
            skipinitialspace=skipinitialspace,
        ):
            if not any(row):
                continue
            rows.append(row)
            if len(rows) >= CSV_SAMPLE_ROWS:
                break
    except csv.Error:
        return None
    return rows


def _read_csv_rows(finder: Finder, path: PurePath) -> list[list[str]] | None:
    """Read and parse a small CSV sample."""
    text = _read_text_sample(finder, path)
    if text is None:
        return None
    return _parse_csv_rows(text)


def _csv_dialect_syntax_score(
    sample: str, delimiter: str, quotechar: str, *, skipinitialspace: bool
) -> tuple[int, int]:
    """Score quote and whitespace syntax for a possible CSV dialect."""
    field_prefix = delimiter + (" " if skipinitialspace else "") + quotechar
    quote_starts = sample.count(field_prefix)
    quote_starts += sum(
        line.lstrip(" ").startswith(quotechar)
        if skipinitialspace
        else line.startswith(quotechar)
        for line in sample.splitlines()
    )
    delimiter_count = sample.count(delimiter)
    spaced_delimiters = sample.count(delimiter + " ")
    spacing_score = 2 * spaced_delimiters - delimiter_count
    if not skipinitialspace:
        spacing_score = -spacing_score
    return quote_starts, spacing_score


def _csv_width_counts(
    sample: str, delimiter: str, quotechar: str, *, skipinitialspace: bool
) -> dict[int, int]:
    """Count parsed row widths for a possible CSV dialect."""
    widths: dict[int, int] = {}
    try:
        for position, row in enumerate(
            csv.reader(
                StringIO(sample),
                delimiter=delimiter,
                quotechar=quotechar,
                skipinitialspace=skipinitialspace,
            )
        ):
            if position >= CSV_SAMPLE_ROWS:
                break
            if any(row):
                width = len(row)
                widths[width] = widths.get(width, 0) + 1
    except csv.Error:
        return {}
    return widths


def _detect_csv_dialect(sample: str) -> tuple[str, str, bool]:
    """Detect supported CSV dialect fields without regex-based sniffing."""
    best_dialect = (",", '"', False)
    best_score = (0, 0, 0, 0)
    for delimiter, quotechar, skipinitialspace in product(
        CSV_DELIMITERS, CSV_QUOTECHARS, (False, True)
    ):
        widths = _csv_width_counts(
            sample,
            delimiter,
            quotechar,
            skipinitialspace=skipinitialspace,
        )
        syntax_score = _csv_dialect_syntax_score(
            sample,
            delimiter,
            quotechar,
            skipinitialspace=skipinitialspace,
        )
        for width, count in widths.items():
            score = (count, -width, *syntax_score)
            if width > 1 and score > best_score:
                best_score = score
                best_dialect = (delimiter, quotechar, skipinitialspace)
    return best_dialect


def _get_ruby_yaml_root_key(content: str) -> str | None:
    """Return a conventional single Ruby-YAML root key without parsing YAML."""
    root_key: str | None = None
    document_ended = False
    for line in content.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if document_ended:
            return None
        if root_key is None:
            if stripped == "---" or stripped.startswith(("%", "--- #")):
                continue
            if line[0].isspace() or not (match := RUBY_YAML_ROOT_RE.match(line)):
                return None
            root_key = next(value for value in match.groupdict().values() if value)
            continue
        if stripped == "...":
            document_ended = True
        elif not line[0].isspace():
            return None
    return root_key


def _toml_line_code(line: str, multiline_quote: str | None) -> tuple[str, str | None]:
    """Return TOML syntax outside strings and the multiline string state."""
    code: list[str] = []
    position = 0
    while position < len(line):
        if multiline_quote is not None:
            end = _find_toml_multiline_end(line, multiline_quote, position)
            if end == -1:
                return "".join(code), multiline_quote
            position = end + len(multiline_quote)
            multiline_quote = None
            continue

        if line[position] == "#":
            break
        if line.startswith(('"""', "'''"), position):
            multiline_quote = line[position : position + 3]
            position += 3
            continue
        if line[position] in "\"'":
            quote = line[position]
            start = position
            position += 1
            while position < len(line):
                if quote == '"' and line[position] == "\\":
                    position += 2
                elif line[position] == quote:
                    position += 1
                    break
                else:
                    position += 1
            value = line[start + 1 : position - 1]
            code.append(
                line[start:position] if value in {"id", "messages"} else quote * 2
            )
            continue
        code.append(line[position])
        position += 1
    return "".join(code), multiline_quote


def _find_toml_multiline_end(line: str, quote: str, start: int) -> int:
    """Find an unescaped TOML multiline string delimiter."""
    position = line.find(quote, start)
    while position != -1 and quote == '"""':
        backslashes = 0
        previous = position - 1
        while previous >= start and line[previous] == "\\":
            backslashes += 1
            previous -= 1
        if backslashes % 2 == 0:
            break
        position = line.find(quote, position + 1)
    return position


def _is_go_i18n_toml(content: str) -> bool:
    """Detect go-i18n TOML using a bounded, linear lexical scan."""
    in_messages = False
    at_root = True
    inline_stack: list[str] | None = None
    inline_expects_key = False
    multiline_quote: str | None = None
    for line in content.splitlines():
        code, multiline_quote = _toml_line_code(line, multiline_quote)
        if not code.strip():
            continue
        if inline_stack is not None:
            found, inline_expects_key = _scan_toml_inline_message(
                code, inline_stack, expects_key=inline_expects_key
            )
            if found:
                return True
            if not inline_stack:
                return False
            continue
        if not in_messages:
            if TOML_MESSAGES_RE.fullmatch(code) is not None:
                in_messages = True
                continue
            if at_root and (match := TOML_INLINE_MESSAGES_RE.match(code)):
                inline_stack = ["["]
                found, inline_expects_key = _scan_toml_inline_message(
                    code[match.end() :], inline_stack, expects_key=False
                )
                if found:
                    return True
                if not inline_stack:
                    return False
                continue
            if TOML_TABLE_RE.match(code):
                at_root = False
            continue
        if (result := _toml_message_table_result(code)) is not None:
            return result
    return False


def _toml_message_table_result(code: str) -> bool | None:
    """Return a decision when a go-i18n messages table starts or ends."""
    if TOML_ID_RE.match(code):
        return True
    if TOML_TABLE_RE.match(code):
        return False
    return None


def _scan_toml_inline_message(
    code: str, stack: list[str], *, expects_key: bool
) -> tuple[bool, bool]:
    """Scan the first table in an inline go-i18n messages array."""
    closing = {"[": "]", "{": "}"}
    position = 0
    while position < len(code):
        character = code[position]
        if character.isspace():
            position += 1
            continue
        if stack == ["[", "{"] and expects_key and TOML_ID_RE.match(code, position):
            return True, False
        if stack == ["["]:
            if character != "{":
                stack.clear()
                return False, False
            stack.append(character)
            expects_key = True
            position += 1
            continue
        if character in closing:
            stack.append(character)
        elif character in closing.values():
            if not stack or closing[stack[-1]] != character:
                stack.clear()
                return False, False
            closes_message = stack == ["[", "{"]
            stack.pop()
            if closes_message or not stack:
                stack.clear()
                return False, False
        elif stack == ["[", "{"]:
            expects_key = character == ","
        position += 1
    return False, expects_key


def _csv_header(rows: list[list[str]]) -> list[str]:
    """Return normalized CSV header if it looks like a Weblate CSV header."""
    if not rows:
        return []
    header = [field.strip().lower() for field in rows[0]]
    if header and all(field in CSV_FIELDNAMES for field in header):
        return header
    return []


def _is_csv_multi(rows: list[list[str]]) -> bool:
    """Check whether CSV rows look like a multivalue CSV file."""
    header = _csv_header(rows)
    if not header:
        return False

    if "context" not in header:
        return False
    if "source" in header:
        key_indexes: tuple[int, ...]
        key_indexes = (header.index("context"), header.index("source"))
    elif "target" in header:
        key_indexes = (header.index("context"),)
    else:
        return False

    seen: set[tuple[str, ...]] = set()
    for row in rows[1:]:
        if len(row) <= max(key_indexes):
            continue
        key = tuple(row[index] for index in key_indexes)
        if key in seen:
            return True
        seen.add(key)
    return False


def _is_csv_simple(rows: list[list[str]]) -> bool:
    """Check whether CSV rows look like a simple two-column CSV file."""
    if not rows or any(len(row) != SIMPLE_CSV_COLUMNS for row in rows):
        return False
    header = _csv_header(rows)
    return not header or set(header) <= {"context", "id", "source", "target"}


def _detect_csv_format(discovery: BaseDiscovery, result: ResultDict) -> str | None:
    """Detect CSV format variants based on file content."""
    detected_simple = False
    budget = _FormatSniffBudget()
    for path in discovery._result_paths(result):  # ruff: ignore[private-member-access]
        if budget.exhausted:
            break
        sample = budget.read(discovery.finder, path)
        if sample is None:
            continue
        rows = _parse_csv_rows(_decode_sample_content(sample[0]))
        if rows is None:
            continue
        if _is_csv_multi(rows):
            return "csv-multi"
        detected_simple |= _is_csv_simple(rows)
    if detected_simple:
        return "csv-simple"
    return None


@register_discovery
class GettextDiscovery(BaseDiscovery):
    """Gettext PO files discovery."""

    file_format = "po"
    mask = "*.po"
    new_base_mask = "*.pot"

    def discover(
        self, *, eager: bool = False, hint: str | None = None
    ) -> Generator[DiscoveryResult]:
        """Yield translation configurations matching this discovery."""
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
        """Extend the result for new_base and intermediate parameters."""
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

    def adjust_format(self, result: ResultDict) -> None:
        """Detect legacy Qt Linguist files based on the TS root version."""
        path = next(iter(self.finder.mask_matches(result["filemask"])), None)
        if path is None:
            return

        content = _read_text_sample(self.finder, path)
        if content is None:
            return

        version = _get_qt_ts_version(content)
        if version is not None and version.startswith("1."):
            result["file_format"] = "ts1"


@register_discovery
class XliffDiscovery(BaseDiscovery):
    """XLIFF files discovery."""

    file_format = "xliff"
    mask = ("*.xliff", "*.xlf", "*.sdlxliff", "*.mxliff", "*.poxliff")

    def adjust_format(self, result: ResultDict) -> None:
        """Override detected format, based on the file content."""
        base = result["template"] if "template" in result else result["filemask"]

        path = next(iter(self.finder.mask_matches(base)), None)

        if path is None or not hasattr(path, "open"):
            return

        sample = _read_binary_sniff_sample(self.finder, path)
        if sample is None:
            return
        content, _complete = sample
        # Check for XLIFF 2.0 first
        if b'version="2.0"' in content or b'version="2.1"' in content:
            result["file_format"] = "xliff2"
            params = result.setdefault("file_format_params", {})
            if b"<pc" in content or b"<sc" in content or b"<ec" in content:
                params["xliff_placeables"] = "placeables"
            else:
                params["xliff_placeables"] = "plain"
        elif b'restype="x-gettext' in content:
            result["file_format"] = "poxliff"
        elif (
            b"NSStringPluralRuleType" in content
            or b'original="Localizable.strings"' in content
            or b":dict" in content
        ):
            result["file_format"] = "apple-xliff"
        elif b"<x " not in content and b"<g " not in content:
            result["file_format"] = "xliff"
            result.setdefault("file_format_params", {})["xliff_placeables"] = "plain"


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

    def adjust_format(self, result: ResultDict) -> None:
        """Override detected format, based on the file content."""
        detected = _detect_csv_format(self, result)
        if detected is not None:
            result["file_format"] = detected

    def discover(
        self, *, eager: bool = False, hint: str | None = None
    ) -> Generator[DiscoveryResult]:
        """Yield translation configurations matching this discovery."""
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
        self, *, eager: bool = False, hint: str | None = None
    ) -> Generator[ResultDict]:
        """
        Return all file masks found in the directory.

        It is expected to contain duplicates.
        """
        for path in self.finder.filter_files(
            r"(strings.*|.*strings)\.xml",
            ".*/values",
            candidate_suffixes=(".xml",),
        ):
            # Skip Compose Multiplatform resources
            if "composeResources" in path.as_posix():
                continue

            mask = list(path.parts)
            mask[-2] = "values-*"

            yield {"filemask": "/".join(mask), "template": path.as_posix()}

    def adjust_format(self, result: ResultDict) -> None:
        """Override detected format, based on the file content."""
        if "template" not in result:
            return

        path = next(iter(self.finder.mask_matches(result["template"])))

        if not hasattr(path, "open"):
            return

        content = _read_binary_sample(self.finder, path)
        if content is not None and b"<plural " in content:
            result["file_format"] = "moko-resource"


@register_discovery
class MOKODiscovery(BaseDiscovery):
    """Mobile Kotlin resources discovery."""

    file_format = "moko-resource"

    def get_masks(
        self, *, eager: bool = False, hint: str | None = None
    ) -> Generator[ResultDict]:
        """
        Return all file masks found in the directory.

        It is expected to contain duplicates.
        """
        for path in self.finder.filter_files(
            r"(strings|plurals)\.xml",
            ".*/resources/mr/base",
            candidate_names=("strings.xml", "plurals.xml"),
        ):
            mask = list(path.parts)
            mask[-2] = "*"

            yield {"filemask": "/".join(mask), "template": path.as_posix()}


@register_discovery
class OSXDiscovery(EncodingDiscovery):
    """OSX string properties files discovery."""

    file_format: ClassVar[str] = "strings"
    file_format_params: ClassVar[dict[str, str | int | bool]] = {
        "strings_encoding": "utf-8",
    }
    encoding_parameter: ClassVar[str] = "strings_encoding"
    encoding_map: ClassVar[dict[str, str]] = {
        "utf_8": "utf-8",
        "utf_16": "utf-16",
    }

    def possible_templates(self, language: str, mask: str) -> Generator[str]:
        """Yield possible template filenames."""
        yield mask.replace("*", "Base")
        yield from super().possible_templates(language, mask)

    def get_masks(
        self, *, eager: bool = False, hint: str | None = None
    ) -> Generator[ResultDict]:
        """
        Return all file masks found in the directory.

        It is expected to contain duplicates.
        """
        for path in self.finder.filter_files(
            r".*\.strings",
            r".*/(base|en(-[a-z]{2})?)\.lproj",
            candidate_suffixes=(".strings",),
        ):
            mask = list(path.parts)
            mask[-2] = "*.lproj"

            yield {"filemask": "/".join(mask), "template": path.as_posix()}

        for path in self.finder.filter_files(
            r"base\.strings",
            candidate_names=("base.strings",),
        ):
            mask = list(path.parts)
            mask[-1] = "*.strings"

            yield {"filemask": "/".join(mask), "template": path.as_posix()}


@register_discovery
class StringsdictDiscovery(BaseDiscovery):
    """Stringsdict files discovery."""

    file_format = "stringsdict"

    def get_masks(
        self, *, eager: bool = False, hint: str | None = None
    ) -> Generator[ResultDict]:
        """
        Return all file masks found in the directory.

        It is expected to contain duplicates.
        """
        for path in self.finder.filter_files(
            r".*\.stringsdict",
            r".*/(base|en)\.lproj",
            candidate_suffixes=(".stringsdict",),
        ):
            mask = list(path.parts)
            mask[-2] = "*.lproj"

            yield {"filemask": "/".join(mask), "template": path.as_posix()}


@register_discovery
class JavaDiscovery(EncodingDiscovery):
    """Java string properties files discovery."""

    file_format = "properties"
    encoding_parameter: ClassVar[str] = "properties_encoding"
    encoding_parameters_by_format: ClassVar[dict[str, str]] = {
        "properties": "properties_encoding",
        "gwt": "gwt_encoding",
    }
    encoding_map: ClassVar[dict[str, str]] = {
        "utf_8": "utf-8",
        "utf_16": "utf-16",
    }
    mask = ("*_*.properties", "*.properties")

    def possible_templates(self, language: str, mask: str) -> Generator[str]:
        """Yield possible template filenames."""
        yield mask.replace("_*", "")
        yield from super().possible_templates(language, mask)

    def adjust_format(self, result: ResultDict) -> None:
        """Override detected format, based on the file content."""
        self.adjust_encoding(result)
        budget = _FormatSniffBudget()
        for path in self._result_paths(result):
            if budget.exhausted:
                break
            sample = budget.read(self.finder, path)
            if sample is None:
                continue
            content = _decode_sample_content(sample[0])
            if (
                "xwiki" in path.as_posix().lower()
                or "XWiki Core localization" in content
                or "# XWiki" in content
            ):
                result["file_format"] = "xwiki-java-properties"
                self.normalize_encoding_parameters(result)
                return
            if GWT_PLURAL_RE.search(content):
                result["file_format"] = "gwt"
                self.normalize_encoding_parameters(result)
                return


@register_discovery
class RESXDiscovery(BaseDiscovery):
    """RESX files discovery."""

    file_format = "resx"
    mask = "resources.res[xw]"

    def possible_templates(self, language: str, mask: str) -> Generator[str]:
        """Yield possible template filenames."""
        yield mask.replace(".*", "")
        yield from super().possible_templates(language, mask)

    def get_masks(
        self, *, eager: bool = False, hint: str | None = None
    ) -> Generator[ResultDict]:
        """
        Return all file masks found in the directory.

        It is expected to contain duplicates.
        """
        for path in self.finder.filter_files(
            r".*\..*\.res[xw]",
            candidate_suffixes=(".resx", ".resw"),
        ):
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
    mask = ""

    def filter_files(self) -> Generator[PurePath]:
        """Filter possible file matches."""
        for path in self.finder.filter_files(
            "short_description.txt|full_description.txt|title.txt|description.txt|name.txt",
            candidate_names=(
                "short_description.txt",
                "full_description.txt",
                "title.txt",
                "description.txt",
                "name.txt",
            ),
        ):
            yield path.parent
        for path in self.finder.filter_files(
            r".*\.txt",
            ".*/changelogs",
            candidate_suffixes=(".txt",),
        ):
            yield path.parent.parent

    def get_masks(
        self, *, eager: bool = False, hint: str | None = None
    ) -> Generator[ResultDict]:
        """
        Return all file masks found in the directory.

        App store metadata is represented by language directories, so eager
        discovery should keep the regular directory mask behavior.
        """
        yield from super().get_masks(eager=False, hint=hint)

    def has_storage(self, name: str) -> bool:
        """Check whether finder has a storage."""
        return self.finder.has_dir(name)


@register_discovery
class JSONDiscovery(BaseDiscovery):
    """JSON files discovery."""

    file_format = "json-nested"
    mask = "*.json"

    @staticmethod
    def _parse_json_data(content: bytes) -> object | None:
        """Parse JSON data from complete binary content."""
        try:
            return json.loads(_decode_content(content))
        except (OSError, RecursionError, ValueError):
            return None

    def read_json_data(self, path: PurePath) -> object | None:
        """Read and parse a complete JSON file."""
        content = _read_binary_sniff_content(self.finder, path)
        if content is None:
            return None
        return self._parse_json_data(content)

    def has_template_less_content(self, result: ResultDict) -> bool:
        """Check whether a template-less JSON result looks translatable."""
        budget = _FormatSniffBudget()
        for path in self._result_paths(result):
            if not hasattr(path, "open"):
                return True

            if budget.exhausted:
                return True

            sample = budget.read(self.finder, path)
            if sample is None:
                continue
            content, complete = sample
            if not complete:
                return True
            data = self._parse_json_data(content)
            if isinstance(data, dict) and self.detect_dict(data) is not None:
                return True
        return False

    def discover(
        self, *, eager: bool = False, hint: str | None = None
    ) -> Generator[DiscoveryResult]:
        """Yield JSON configurations matching this discovery."""
        for result in super().discover(eager=eager, hint=hint):
            if (
                not eager
                and "template" not in result
                and not self.has_template_less_content(result.match)
            ):
                continue
            yield result

    @staticmethod
    def is_go_i18n_v2_dict(data: dict) -> bool:
        """Check if dict matches go-i18n-v2 format pattern."""
        return "hash" in data and (
            "message" in data or "one" in data or "other" in data
        )

    def _detect_top_level_format(self, data: dict) -> str | None:
        """Detect formats that are only determined from the top-level object."""
        if "lang" in data and "messages" in data:
            return "gotext"
        # go-i18n-v2 detection at top level
        if self.is_go_i18n_v2_dict(data):
            return "go-i18n-json-v2"
        # Nextcloud JSON format detection
        if (
            "translations" in data
            and isinstance(data["translations"], list)
            and len(data["translations"]) > 0
        ):
            first = data["translations"][0]
            if isinstance(first, dict) and "key" in first:
                return "nextcloud-json"
        # RESJSON format detection
        if "_strings" in data or "_locales" in data:
            return "resjson"
        return None

    def _detect_first_level_format(self, value: dict) -> str | None:
        if "message" in value and "description" in value:
            return "webextension"
        if "defaultMessage" in value and "description" in value:
            return "formatjs"
        # go-i18n-v2 detection in nested objects
        if self.is_go_i18n_v2_dict(value):
            return "go-i18n-json-v2"
        return None

    @staticmethod
    def _iter_nested_dicts(data: dict, level: int) -> Generator[tuple[dict, int]]:
        seen: set[int] = set()
        stack = [(data, level)]

        while stack:
            current, current_level = stack.pop()
            current_id = id(current)
            if current_id in seen:
                continue
            seen.add(current_id)
            yield current, current_level

            stack.extend(
                (value, current_level + 1)
                for value in current.values()
                if isinstance(value, dict)
            )

    @staticmethod
    def _detect_i18next_format(key: str, value: str) -> str | None:
        if key.endswith(("_one", "_many", "_other")):
            return "i18nextv4"
        if key.endswith("_plural") or "{{" in value:
            return "i18next"
        return None

    def _detect_nested_format(self, data: dict, level: int) -> str | None:
        i18next = False
        i18nextv4 = False
        all_strings = True

        for current, current_level in self._iter_nested_dicts(data, level):
            # Single loop to detect nested formats and i18next patterns
            for key, value in current.items():
                # Check for nested formats at level 0
                if (
                    current_level == 0
                    and isinstance(value, dict)
                    and (detected := self._detect_first_level_format(value))
                ):
                    return detected

                # Check for i18next patterns
                if not isinstance(key, str):
                    if current is data:
                        all_strings = False
                    break
                if not isinstance(value, str):
                    if current is data:
                        all_strings = False
                    continue

                detected = self._detect_i18next_format(key, value)
                i18nextv4 |= detected == "i18nextv4"
                i18next |= detected == "i18next"

        if i18nextv4:
            return "i18nextv4"
        if i18next:
            return "i18next"
        if all_strings:
            return "json"
        return None

    def detect_dict(self, data: dict) -> str | None:
        """Detect JSON variant based on JSON content."""
        top_level_format = self._detect_top_level_format(data)
        if top_level_format is not None:
            return top_level_format

        return self._detect_nested_format(data, 0)

    def adjust_format(self, result: ResultDict) -> None:
        """Override detected format, based on the file content."""
        if "template" not in result:
            return

        path = next(iter(self.finder.mask_matches(result["template"])))

        if not hasattr(path, "open"):
            return

        content = _read_binary_sniff_content(self.finder, path)
        if content is None:
            return
        try:
            data = json.loads(content.decode())
        except (RecursionError, UnicodeError, ValueError) as error:
            warnings.warn(f"Could not parse JSON: {error}", stacklevel=0)
            return
        if (
            isinstance(data, list)
            and len(data) > 0
            and isinstance(data[0], dict)
            and "id" in data[0]
        ):
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
        """Override detected format, based on the file content."""
        if "template" not in result:
            return

        path = next(iter(self.finder.mask_matches(result["template"])))

        if not hasattr(path, "open"):
            return

        content = _read_text_sniff_content(self.finder, path)
        if content is None:
            return
        key = _get_ruby_yaml_root_key(content)
        if key is None:
            return
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
        """Override detected format, based on the file content."""
        if "template" not in result:
            return

        path = next(iter(self.finder.mask_matches(result["template"])))

        if not hasattr(path, "open"):
            return

        content = _read_binary_sample(self.finder, path)
        if (
            content is not None
            and b"return [" in content
            and LARAVEL_BYTES_RE.search(content)
        ):
            result["file_format"] = "laravel"


@register_discovery
class IDMLDiscovery(MonoTemplateDiscovery):
    """IDML files discovery."""

    file_format = "idml"
    mask = ("*.idml", "*.idms")


@register_discovery
class HTMLDiscovery(MonoTemplateDiscovery):
    """HTML files discovery."""

    file_format = "html"
    mask = ("*.html", "*.htm")
    requires_template = True


@register_discovery
class TXTDiscovery(MonoTemplateDiscovery, EnglishVariantsDiscovery):
    """TXT files discovery."""

    file_format = "txt"
    mask = "*.txt"

    def adjust_format(self, result: ResultDict) -> None:
        """Override detected format, based on the file content."""
        if _detect_csv_format(self, result) == "csv-simple":
            result["file_format"] = "csv-simple"


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
class XLSXDiscovery(CSVDiscovery):
    """Excel Open XML files discovery."""

    file_format = "xlsx"
    mask = "*.xlsx"

    def adjust_format(self, result: ResultDict) -> None:  # ruff:ignore[no-self-use]
        """Keep Excel files on the Excel format."""
        return


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

    def adjust_format(self, result: ResultDict) -> None:
        """Override detected format, based on the file content."""
        if "template" not in result:
            return

        path = next(iter(self.finder.mask_matches(result["template"])))

        if not hasattr(path, "open"):
            return

        content = _read_text_sniff_content(self.finder, path)
        if content is not None and _is_go_i18n_toml(content):
            result["file_format"] = "go-i18n-toml"


@register_discovery
class ARBDiscovery(BaseDiscovery):
    """ARB files discovery."""

    file_format = "arb"
    mask = "*.arb"

    def fill_in_new_base(self, result: ResultDict) -> None:
        """Extend the result for new_base and intermediate parameters."""
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
        return super().get_language_aliases(language)


@register_discovery
class TBXDiscovery(BaseDiscovery):
    """TBX files discovery."""

    file_format = "tbx"
    mask = "*.tbx"


@register_discovery
class MarkdownDiscovery(MonoTemplateDiscovery):
    """Markdown files discovery."""

    file_format = "markdown"
    mask = ("*.md", "*.markdown")


@register_discovery
class MDXDiscovery(MonoTemplateDiscovery):
    """MDX files discovery."""

    file_format = "mdx"
    mask = "*.mdx"


@register_discovery
class DokuWikiDiscovery(MonoTemplateDiscovery):
    """DokuWiki text files discovery."""

    file_format = "dokuwiki"
    mask = "*.dw"


@register_discovery
class MediaWikiDiscovery(MonoTemplateDiscovery):
    """MediaWiki text files discovery."""

    file_format = "mediawiki"
    mask = "*.mw"


@register_discovery
class AsciiDocDiscovery(MonoTemplateDiscovery):
    """AsciiDoc files discovery."""

    file_format = "asciidoc"
    mask = ("*.ad", "*.adoc", "*.asciidoc")


@register_discovery
class WXLDiscovery(MonoTemplateDiscovery):
    """WiX localization files discovery."""

    file_format = "wxl"
    mask = "*.wxl"


@register_discovery
class FormatJSDiscovery(BaseDiscovery):
    """Format.JS JSON files discovery."""

    file_format = "formatjs"

    def get_masks(
        self, *, eager: bool = False, hint: str | None = None
    ) -> Generator[ResultDict]:
        """
        Return all file masks found in the directory.

        It is expected to contain duplicates.
        """
        for path in self.finder.filter_files(
            r"en.json",
            ".*/extracted",
            candidate_names=("en.json",),
        ):
            mask = list(path.parts)
            mask[-1] = "*.json"
            mask[-2] = "lang"

            yield {"filemask": "/".join(mask), "template": path.as_posix()}


@register_discovery
class DTDDiscovery(BaseDiscovery):
    """DTD files discovery."""

    file_format = "dtd"
    mask = "*.dtd"


@register_discovery
class FlatXMLDiscovery(MonoTemplateDiscovery):
    """Flat XML files discovery."""

    file_format = "flatxml"
    mask = "*.xml"
    requires_template = True

    def adjust_format(self, result: ResultDict) -> None:
        """Override detected format, based on the file content."""
        budget = _FormatSniffBudget()
        for path in self._result_paths(result):
            if budget.exhausted:
                break
            sample = budget.read(self.finder, path)
            if sample is None:
                continue
            content = _decode_sample_content(sample[0])
            if "<xwikidoc" not in content:
                continue
            if (
                "XWiki.TranslationDocumentClass" in content
                or "<syntaxId>plain/" in content
            ):
                result["file_format"] = "xwiki-page-properties"
            else:
                result["file_format"] = "xwiki-fullpage"
            return


@register_discovery
class CatkeysDiscovery(BaseDiscovery):
    """Haiku catkeys files discovery."""

    file_format = "catkeys"
    mask = "*.catkeys"


@register_discovery
class CMPDiscovery(BaseDiscovery):
    """Compose Multiplatform Resource files discovery."""

    file_format = "cmp-resource"

    def get_masks(
        self, *, eager: bool = False, hint: str | None = None
    ) -> Generator[ResultDict]:
        """
        Return all file masks found in the directory.

        It is expected to contain duplicates.
        """
        for path in self.finder.filter_files(
            r"(strings.*|.*strings)\.xml",
            ".*/values",
            candidate_suffixes=(".xml",),
        ):
            # Only match files in composeResources directories
            if "composeResources" not in path.as_posix():
                continue

            mask = list(path.parts)
            mask[-2] = "values-*"

            yield {"filemask": "/".join(mask), "template": path.as_posix()}


@register_discovery
class Mi18nDiscovery(BaseDiscovery):
    """@draggable/i18n lang files discovery."""

    file_format = "mi18n-lang"
    mask = "*.lang"
