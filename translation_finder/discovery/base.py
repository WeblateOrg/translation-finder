# Copyright © Michal Čihař <michal@weblate.org>
#
# SPDX-License-Identifier: GPL-3.0-or-later

"""Base discovery code."""

from __future__ import annotations

import fnmatch
import re
import warnings
from dataclasses import dataclass, fields
from functools import partial
from pathlib import Path
from typing import TYPE_CHECKING, ClassVar

from charset_normalizer import from_bytes
from weblate_language_data.country_codes import COUNTRIES
from weblate_language_data.language_codes import LANGUAGES

from translation_finder.data import LANGUAGES_BLACKLIST

from .result import DiscoveryCandidate, DiscoveryLimit, DiscoveryResult

if TYPE_CHECKING:
    from collections.abc import Generator
    from pathlib import PurePath

    from translation_finder.finder import Finder

    from .result import FileFormatParams, ResultDict

TOKEN_SPLIT = re.compile(r"([_.-])")

LOCALES = {"latn", "cyrl", "hant", "hans"}

FORMAT_SNIFF_MAX_BYTES = 1024 * 1024
FORMAT_SNIFF_MAX_FILES = 10
ENCODING_SNIFF_MAX_FILES = 10
DISCOVERY_SNIFF_MAX_BYTES = 64 * 1024 * 1024
DISCOVERY_SNIFF_MAX_FILES = 512
DISCOVERY_MAX_CANDIDATES = 4096
DISCOVERY_MAX_RESULTS = 4096
DISCOVERY_MAX_NEW_BASE_CHECKS = 65_536
MAX_MASKS_PER_PATH = 32
DISCOVERY_TRUNCATED_MESSAGE = (
    "Translation discovery reached its resource limit; results may be incomplete"
)


@dataclass(frozen=True)
class DiscoveryLimits:
    """Discovery resource bounds; None disables an individual limit."""

    max_candidates: int | None = DISCOVERY_MAX_CANDIDATES
    max_results: int | None = DISCOVERY_MAX_RESULTS
    max_new_base_checks: int | None = DISCOVERY_MAX_NEW_BASE_CHECKS
    max_masks_per_path: int | None = MAX_MASKS_PER_PATH
    sniff_max_bytes: int | None = DISCOVERY_SNIFF_MAX_BYTES
    sniff_max_files: int | None = DISCOVERY_SNIFF_MAX_FILES

    def __post_init__(self) -> None:
        """Reject negative resource bounds."""
        for field in fields(self):
            value = getattr(self, field.name)
            if value is not None and value < 0:
                msg = f"{field.name} must be nonnegative or None"
                raise ValueError(msg)

    @classmethod
    def unlimited(cls) -> DiscoveryLimits:
        """Disable discovery budgets, retaining internal parser safeguards."""
        return cls(**dict.fromkeys(field.name for field in fields(cls)))


class DiscoveryBudget:
    """Bound path-derived work across one discovery run."""

    def __init__(
        self,
        candidates: int | None = DISCOVERY_MAX_CANDIDATES,
        new_base_checks: int | None = DISCOVERY_MAX_NEW_BASE_CHECKS,
        masks_per_path: int | None = MAX_MASKS_PER_PATH,
    ) -> None:
        self.max_masks_per_path = masks_per_path
        self.remaining_candidates = candidates
        self.remaining_new_base_checks = new_base_checks
        self.limit_reasons: set[DiscoveryLimit] = set()

    @property
    def truncated(self) -> bool:
        """Whether a resource limit might have made results incomplete."""
        return bool(self.limit_reasons)

    def reach_limit(self, reason: DiscoveryLimit) -> None:
        """Record that a resource limit affected discovery."""
        self.limit_reasons.add(reason)

    @property
    def exhausted(self) -> bool:
        """Whether another candidate can be generated."""
        return self.remaining_candidates is not None and self.remaining_candidates <= 0

    def consume_candidate(self) -> bool:
        """Consume one generated candidate when capacity remains."""
        if self.exhausted:
            self.reach_limit(DiscoveryLimit.CANDIDATES)
            return False
        if self.remaining_candidates is not None:
            self.remaining_candidates -= 1
        return True

    def consume_new_base_check(self) -> bool:
        """Consume one new-base lookup when capacity remains."""
        if (
            self.remaining_new_base_checks is not None
            and self.remaining_new_base_checks <= 0
        ):
            self.reach_limit(DiscoveryLimit.NEW_BASE_CHECKS)
            return False
        if self.remaining_new_base_checks is not None:
            self.remaining_new_base_checks -= 1
        return True


class SniffBudget:
    """Bound content sniffing and optionally charge a parent budget."""

    def __init__(
        self,
        max_bytes: int | None,
        max_files: int | None,
        *,
        parent: SniffBudget | None = None,
    ) -> None:
        self.remaining_bytes = max_bytes
        self.remaining_files = max_files
        self.parent = parent

    @property
    def exhausted(self) -> bool:
        """Whether another file can be inspected."""
        return (
            (self.remaining_bytes is not None and self.remaining_bytes <= 0)
            or (self.remaining_files is not None and self.remaining_files <= 0)
            or (self.parent is not None and self.parent.exhausted)
        )

    def read(
        self,
        finder: Finder,
        path: PurePath,
        size: int = FORMAT_SNIFF_MAX_BYTES,
    ) -> tuple[bytes, bool] | None:
        """Read one sample and charge it to this and all parent budgets."""
        allowance = self.reserve(size)
        if allowance is None:
            return None

        if not hasattr(path, "open"):
            return None
        try:
            with finder.open(path, "rb") as handle:
                content = handle.read(allowance + 1)
        except (OSError, TypeError):
            return None

        sample = content[:allowance]
        self.charge(len(sample))
        return sample, len(content) <= allowance

    def reserve(self, size: int) -> int | None:
        """Reserve one file attempt and return the available byte allowance."""
        budgets = [self]
        parent = self.parent
        while parent is not None:
            budgets.append(parent)
            parent = parent.parent

        if any(budget.exhausted for budget in budgets):
            return None

        allowance = min(
            [
                size,
                *[
                    budget.remaining_bytes
                    for budget in budgets
                    if budget.remaining_bytes is not None
                ],
            ]
        )
        for budget in budgets:
            if budget.remaining_files is not None:
                budget.remaining_files -= 1
        return allowance

    def charge(self, size: int) -> None:
        """Charge sampled bytes to this and all parent budgets."""
        budgets = [self]
        parent = self.parent
        while parent is not None:
            budgets.append(parent)
            parent = parent.parent
        for budget in budgets:
            if budget.remaining_bytes is not None:
                budget.remaining_bytes -= size


def _replace_with_wildcard(found: re.Match[str], *, wildcard: str) -> str:
    """Replace a match while treating the wildcard as literal text."""
    return f"{found.group(1)}{wildcard}{found.group(2)}"


def _trim_incomplete_unicode_tail(content: bytes) -> bytes:
    """Remove an incomplete Unicode character from a truncated sample."""
    if content.startswith((b"\x00\x00\xfe\xff", b"\xff\xfe\x00\x00")):
        return content[: len(content) - len(content) % 4]

    encoding = (
        "utf-16" if content.startswith((b"\xff\xfe", b"\xfe\xff")) else "utf-8-sig"
    )
    try:
        content.decode(encoding)
    except UnicodeDecodeError as error:
        if error.end == len(content) and error.reason in {
            "truncated data",
            "unexpected end of data",
        }:
            return content[: error.start]
    return content


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
    (".mdx", "mdx"),
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
    requires_template: ClassVar[bool] = False
    uses_template: ClassVar[bool] = False

    def __init__(self, finder: Finder, source_language: str = "en") -> None:
        self.finder: Finder = finder
        self.source_language: str = source_language
        self._run_discovery_budget: DiscoveryBudget | None = None
        self._run_sniff_budget: SniffBudget | None = None
        self._new_base_by_directory: dict[str, tuple[int, PurePath]] | None = None
        self._new_base_by_name: dict[tuple[str, str], tuple[int, PurePath]] | None = (
            None
        )
        self._new_bases_by_name: (
            dict[str, list[tuple[str, tuple[int, PurePath]]]] | None
        ) = None
        self._new_base_fallback_cache: dict[str, str | None] = {}

    def _set_run_discovery_budget(self, budget: DiscoveryBudget) -> None:
        """Use a shared candidate budget for this discovery run."""
        self._run_discovery_budget = budget

    def _set_run_sniff_budget(self, budget: SniffBudget) -> None:
        """Use a shared content-sniffing budget for this discovery run."""
        self._run_sniff_budget = budget

    def _new_sniff_budget(
        self,
        max_bytes: int = FORMAT_SNIFF_MAX_BYTES,
        max_files: int = FORMAT_SNIFF_MAX_FILES,
    ) -> SniffBudget:
        """Create a local sniffing budget linked to the current run."""
        return SniffBudget(max_bytes, max_files, parent=self._run_sniff_budget)

    def _read_run_sniff_sample(
        self,
        path: PurePath,
        size: int = FORMAT_SNIFF_MAX_BYTES,
    ) -> tuple[bytes, bool] | None:
        """Read a sample charged directly to the current run."""
        budget = self._run_sniff_budget or SniffBudget(size, 1)
        return budget.read(self.finder, path, size)

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

        best_result: str | None = None
        new_base_by_directory, _new_base_by_name = self._index_new_bases()
        if not new_base_by_directory:
            return

        directory_signature = path.rsplit("/", 1)[0] if "/" in path else ""
        exact_complete, exact_result = self._find_exact_new_base(
            directory_signature, new_name
        )
        if not exact_complete:
            return
        if exact_result is not None:
            result["new_base"] = exact_result
            return

        cached_fallback = self._new_base_fallback_cache.get(directory_signature, ...)
        if cached_fallback is not ...:
            if isinstance(cached_fallback, str):
                result["new_base"] = cached_fallback
            return

        while "/" in path:
            if (
                self._run_discovery_budget is not None
                and not self._run_discovery_budget.consume_new_base_check()
            ):
                return
            path = path.rsplit("/", 1)[0]
            path_wild = path.replace("*", "")
            directories = {path, path_wild}
            fallback_matches = (
                new_base_by_directory[directory]
                for directory in directories
                if directory in new_base_by_directory
            )
            fallback_match = min(fallback_matches, default=None)
            if fallback_match is not None:
                best_result = "/".join(fallback_match[1].parts)
                break

        self._new_base_fallback_cache[directory_signature] = best_result

        if best_result is not None:
            result["new_base"] = best_result

    def _find_exact_new_base(
        self, directory_signature: str, new_name: str
    ) -> tuple[bool, str | None]:
        """Find the nearest exact new base without walking every ancestor."""
        candidates = (self._new_bases_by_name or {}).get(new_name, ())
        if not candidates:
            return True, None

        path_wild = directory_signature.replace("*", "")
        for directory, candidate in candidates:
            if (
                self._run_discovery_budget is not None
                and not self._run_discovery_budget.consume_new_base_check()
            ):
                return False, None
            if any(
                path == directory or path.startswith(f"{directory}/")
                for path in (directory_signature, path_wild)
            ):
                return True, "/".join(candidate[1].parts)
        return True, None

    def _index_new_bases(
        self,
    ) -> tuple[
        dict[str, tuple[int, PurePath]],
        dict[tuple[str, str], tuple[int, PurePath]],
    ]:
        """Index possible new-base files for repeated constant-time lookups."""
        if (
            self._new_base_by_directory is None
            or self._new_base_by_name is None
            or self._new_bases_by_name is None
        ):
            self._new_base_by_directory = {}
            self._new_base_by_name = {}
            self._new_bases_by_name = {}
            if self.new_base_mask is not None:
                for position, match in enumerate(
                    self.finder.filter_masks(self.new_base_mask)
                ):
                    directory = "/".join(match.parts[:-1]).lower()
                    candidate = (position, match)
                    self._new_base_by_directory.setdefault(directory, candidate)
                    name = match.parts[-1].lower()
                    key = (directory, name)
                    if key not in self._new_base_by_name:
                        self._new_base_by_name[key] = candidate
                        self._new_bases_by_name.setdefault(name, []).append(
                            (directory, candidate)
                        )
                for candidates in self._new_bases_by_name.values():
                    candidates.sort(
                        key=lambda item: (
                            -(item[0].count("/") + bool(item[0])),
                            item[1][0],
                        )
                    )

        return self._new_base_by_directory, self._new_base_by_name

    def has_storage(self, name: str) -> bool:
        """Check whether finder has a storage."""
        return self.finder.has_file(name)

    def get_language_aliases(self, language: str) -> list[str]:  # ruff:ignore[no-self-use]
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

    def adjust_format(  # ruff: ignore[no-self-use]
        self, candidate: DiscoveryCandidate
    ) -> None:
        """Override detected format, based on the file content."""
        return

    def _result_paths(
        self,
        candidate: DiscoveryCandidate,
        *,
        template_first: bool = True,
    ) -> Generator[PurePath]:
        """Yield unique confirmed paths referenced by a discovery candidate."""
        result = candidate.result
        seen: set[str] = set()
        template = result.get("template")
        files_by_path = getattr(self.finder, "files_by_path", {})
        template_path = files_by_path.get(template) if template is not None else None
        paths = (
            ([template_path] if template_path is not None else []) + candidate.paths
            if template_first
            else candidate.paths
            + ([template_path] if template_path is not None else [])
        )
        for path in paths:
            key = path.as_posix()
            if key in seen:
                continue
            seen.add(key)
            yield path

    def include_candidate(  # ruff: ignore[no-self-use]
        self, candidate: DiscoveryCandidate, *, eager: bool
    ) -> bool:
        """Return whether a fully adjusted candidate should be emitted."""
        return True

    def discover(
        self, *, eager: bool = False, hint: str | None = None
    ) -> Generator[DiscoveryResult]:
        """Yield translation configurations matching this discovery."""
        owns_budget = self._run_discovery_budget is None
        budget = self._run_discovery_budget or DiscoveryBudget()
        if owns_budget:
            self._run_discovery_budget = budget
        candidates: dict[str, DiscoveryCandidate] = {}
        try:
            for candidate in self.get_masks(eager=eager, hint=hint):
                if not budget.consume_candidate():
                    break
                filemask = candidate.result["filemask"]
                if filemask in candidates:
                    candidates[filemask].merge_paths(candidate.paths)
                else:
                    candidates[filemask] = candidate

            for candidate in candidates.values():
                result = candidate.result
                self.fill_in_template(result)
                if self.requires_template and "template" not in result:
                    continue
                self.adjust_format(candidate)
                self.fill_in_new_base(result)
                self.fill_in_file_format(result)
                self.fill_in_file_format_params(result)
                if not self.include_candidate(candidate, eager=eager):
                    continue
                discovery_result = DiscoveryResult(result)
                discovery_result.meta["discovery"] = self.__class__.__name__
                discovery_result.meta["origin"] = self.origin
                discovery_result.meta["priority"] = self.priority
                yield discovery_result
        finally:
            if owns_budget:
                self._run_discovery_budget = None
                if budget.truncated:
                    warnings.warn(
                        DISCOVERY_TRUNCATED_MESSAGE,
                        RuntimeWarning,
                        stacklevel=2,
                    )

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
        return self.finder.filter_masks(self.masks_list)

    def get_masks(  # ruff: ignore[too-many-branches]
        self, *, eager: bool = False, hint: str | None = None
    ) -> Generator[DiscoveryCandidate]:
        """
        Return all file masks found in the directory.

        It is expected to contain duplicates.
        """
        if hint:
            for mask in self.masks_list:
                if fnmatch.fnmatch(hint, mask):
                    paths = list(self.finder.mask_matches(hint))
                    if paths:
                        yield DiscoveryCandidate({"filemask": hint}, paths)
        for path in self.filter_files():
            parts = list(path.parts)
            if eager:
                filename = parts[-1]
                if "." not in filename:
                    continue
                parts[-1] = "*.{}".format(filename.rsplit(".", 1)[1])
                result: ResultDict = {"filemask": "/".join(parts)}
                if self.uses_template:
                    result["new_base"] = result["template"] = "/".join(path.parts)
                yield DiscoveryCandidate(result, [path])
                continue
            skip = set()
            generated_masks = 0
            for pos, part in enumerate(parts):
                if pos in skip:
                    continue
                wildcard = self.get_wildcard(part)
                if wildcard:
                    mask_limit = (
                        self._run_discovery_budget.max_masks_per_path
                        if self._run_discovery_budget is not None
                        else MAX_MASKS_PER_PATH
                    )
                    if mask_limit is not None and generated_masks >= mask_limit:
                        if self._run_discovery_budget is not None:
                            self._run_discovery_budget.reach_limit(
                                DiscoveryLimit.MASKS_PER_PATH
                            )
                        else:
                            warnings.warn(
                                DISCOVERY_TRUNCATED_MESSAGE,
                                RuntimeWarning,
                                stacklevel=2,
                            )
                        break
                    mask_parts = parts.copy()
                    match = re.compile(f"(^|[._-]){re.escape(part)}($|[._-])")
                    for i, current in enumerate(mask_parts):
                        if match.search(current):
                            skip.add(i)
                            mask_parts[i] = match.sub(
                                partial(_replace_with_wildcard, wildcard=wildcard),
                                current,
                            )
                    mask_parts[pos] = wildcard
                    generated_masks += 1
                    yield DiscoveryCandidate({"filemask": "/".join(mask_parts)}, [path])


class MonoTemplateDiscovery(BaseDiscovery):
    """Base class for monolingual template based files."""

    uses_template = True

    def fill_in_new_base(self, result: ResultDict) -> None:  # ruff:ignore[no-self-use]
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

    def detect_encoding(self, candidate: DiscoveryCandidate) -> str | None:
        """Detect file encoding and translate it to a Weblate parameter value."""
        budget = self._new_sniff_budget(
            FORMAT_SNIFF_MAX_BYTES, ENCODING_SNIFF_MAX_FILES
        )
        for path in self._result_paths(candidate, template_first=False):
            if budget.exhausted:
                break
            if not isinstance(path, Path):
                # PurePath only
                continue
            sample = budget.read(self.finder, path)
            if sample is None:
                continue
            content, complete = sample
            if not complete:
                content = _trim_incomplete_unicode_tail(content)
            detection_result = from_bytes(
                content,
                cp_isolation=["ascii", *self.encoding_map],
            ).best()
            if detection_result is None:
                continue

            encoding = detection_result.encoding.lower()
            if encoding in self.encoding_map:
                return self.encoding_map[encoding]
        return None

    def adjust_encoding(self, candidate: DiscoveryCandidate) -> str | None:
        """Detect and set encoding parameter."""
        result = candidate.result
        encoding = self.detect_encoding(candidate)
        if encoding is None:
            self.normalize_encoding_parameters(result)
        else:
            self.set_encoding_parameter(result, encoding)
        return encoding

    def adjust_format(self, candidate: DiscoveryCandidate) -> None:
        """Override detected format, based on the file content."""
        self.adjust_encoding(candidate)


class EnglishVariantsDiscovery(BaseDiscovery):
    """Discovery supporting widely used English variants."""

    def get_language_aliases(self, language: str) -> list[str]:
        """Language code aliases."""
        result = super().get_language_aliases(language)
        if language == "en":
            result.extend(["en-US", "en-GB", "en-AU"])
        return result
