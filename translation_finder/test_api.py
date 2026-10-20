# Copyright © Michal Čihař <michal@weblate.org>
#
# SPDX-License-Identifier: GPL-3.0-or-later
"""High level API tests."""

from __future__ import annotations

import pathlib
import tempfile
import warnings
from dataclasses import FrozenInstanceError, fields
from io import StringIO
from typing import TYPE_CHECKING
from unittest.mock import Mock, patch

from . import api as api_module
from .api import DiscoveryLimits, cli, discover
from .discovery import base as base_module
from .discovery.base import BaseDiscovery
from .discovery.files import GettextDiscovery
from .discovery.result import (
    DiscoveryCandidate,
    DiscoveryLimit,
    DiscoveryResult,
    DiscoveryResults,
)
from .finder import PathMockType, PurePath
from .test_discovery import DiscoveryTestCase

if TYPE_CHECKING:
    from collections.abc import Generator

TEST_DATA = pathlib.Path(__file__).parent / "test_data"


class APITest(DiscoveryTestCase):
    maxDiff = None

    def test_discover_limits_results_without_warning(self) -> None:
        generated = 0

        class ExpandingDiscovery(BaseDiscovery):
            def discover(  # ruff: ignore[no-self-use]
                self, *, eager: bool = False, hint: str | None = None
            ) -> Generator[DiscoveryResult]:
                nonlocal generated
                del eager, hint
                for index in range(4):
                    generated += 1
                    yield DiscoveryResult(
                        {"filemask": f"locale/{index}.json", "file_format": "json"}
                    )

        with (
            patch.object(api_module, "BACKENDS", [ExpandingDiscovery]),
            warnings.catch_warnings(record=True) as caught,
        ):
            warnings.simplefilter("error")
            results = discover(
                PurePath(), mock=([], []), limits=DiscoveryLimits(max_results=2)
            )

        self.assertEqual(len(results), 2)
        self.assertEqual(caught, [])
        self.assertEqual(generated, 3)
        self.assertIsInstance(results, DiscoveryResults)
        self.assertTrue(results.truncated)
        self.assertEqual(results.limit_reasons, {DiscoveryLimit.RESULTS})

    def test_discover_exact_result_limit_is_not_truncated(self) -> None:
        generated = 0

        class ExactDiscovery(BaseDiscovery):
            def discover(  # ruff: ignore[no-self-use]
                self, *, eager: bool = False, hint: str | None = None
            ) -> Generator[DiscoveryResult]:
                nonlocal generated
                del eager, hint
                for index in range(2):
                    generated += 1
                    yield DiscoveryResult(
                        {"filemask": f"locale/{index}.json", "file_format": "json"}
                    )

        with (
            patch.object(api_module, "BACKENDS", [ExactDiscovery]),
            warnings.catch_warnings(record=True) as caught,
        ):
            warnings.simplefilter("error")
            results = discover(
                PurePath(), mock=([], []), limits=DiscoveryLimits(max_results=2)
            )

        self.assertEqual(len(results), 2)
        self.assertEqual(generated, 2)
        self.assertEqual(caught, [])
        self.assertFalse(results.truncated)
        self.assertEqual(results.limit_reasons, set())

    def test_exhausted_candidate_budget_skips_later_backends(self) -> None:
        generated = 0

        class FirstDiscovery(BaseDiscovery):
            file_format = "json"

            def get_masks(  # ruff: ignore[no-self-use]
                self, *, eager: bool = False, hint: str | None = None
            ) -> Generator[DiscoveryCandidate]:
                nonlocal generated
                del eager, hint
                for index in range(2):
                    generated += 1
                    yield DiscoveryCandidate(
                        {"filemask": f"locale/{index}.json"},
                        [PurePath(f"locale/{index}.json")],
                    )

        later_discovery = Mock(side_effect=AssertionError)

        with (
            patch.object(api_module, "BACKENDS", [FirstDiscovery, later_discovery]),
        ):
            results = discover(
                PurePath(), mock=([], []), limits=DiscoveryLimits(max_candidates=1)
            )

        self.assertEqual(len(results), 1)
        self.assertEqual(generated, 2)
        self.assertEqual(results.limit_reasons, {DiscoveryLimit.CANDIDATES})
        later_discovery.assert_not_called()

    def test_exact_candidate_limit_is_not_truncated(self) -> None:
        generated = 0

        class ExactDiscovery(BaseDiscovery):
            file_format = "json"

            def get_masks(  # ruff: ignore[no-self-use]
                self, *, eager: bool = False, hint: str | None = None
            ) -> Generator[DiscoveryCandidate]:
                nonlocal generated
                del eager, hint
                generated += 1
                yield DiscoveryCandidate(
                    {"filemask": "locale/*.json"},
                    [PurePath("locale/cs.json")],
                )

        with (
            patch.object(api_module, "BACKENDS", [ExactDiscovery]),
            warnings.catch_warnings(record=True) as caught,
        ):
            warnings.simplefilter("error")
            results = discover(
                PurePath(), mock=([], []), limits=DiscoveryLimits(max_candidates=1)
            )

        self.assertEqual(len(results), 1)
        self.assertEqual(generated, 1)
        self.assertEqual(caught, [])
        self.assertFalse(results.truncated)
        self.assertEqual(results.limit_reasons, set())

    def test_candidate_limit_probes_later_backends(self) -> None:
        generated = 0

        class SingleCandidateDiscovery(BaseDiscovery):
            file_format = "json"

            def get_masks(  # ruff: ignore[no-self-use]
                self, *, eager: bool = False, hint: str | None = None
            ) -> Generator[DiscoveryCandidate]:
                nonlocal generated
                del eager, hint
                generated += 1
                yield DiscoveryCandidate(
                    {"filemask": f"locale/{generated}.json"},
                    [PurePath(f"locale/{generated}.json")],
                )

        with (
            patch.object(
                api_module,
                "BACKENDS",
                [SingleCandidateDiscovery, SingleCandidateDiscovery],
            ),
        ):
            results = discover(
                PurePath(), mock=([], []), limits=DiscoveryLimits(max_candidates=1)
            )

        self.assertEqual(len(results), 1)
        self.assertEqual(generated, 2)
        self.assertTrue(results.truncated)
        self.assertEqual(results.limit_reasons, {DiscoveryLimit.CANDIDATES})

    def test_discover_reports_new_base_limit(self) -> None:
        paths = ["locale/cs/messages.po", "templates/messages.pot"]
        files = [(PurePath(path), PurePath(path), path) for path in paths]

        with (
            patch.object(api_module, "BACKENDS", [GettextDiscovery]),
        ):
            results = discover(
                PurePath(),
                mock=(files, []),
                limits=DiscoveryLimits(max_new_base_checks=0),
            )

        self.assertEqual(len(results), 1)
        self.assertNotIn("new_base", results[0])
        self.assertEqual(
            results.limit_reasons,
            {DiscoveryLimit.NEW_BASE_CHECKS},
        )

    def test_discover_nonexistent_hint(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            for hint in ("ghost.xlf", "*.xlf", "ghost.po", "*.po"):
                with self.subTest(hint=hint):
                    self.assert_discovery(discover(tmpdir, hint=hint), [])

    def test_discover(self) -> None:
        paths = ["locales/cs/messages.po", "locales/de/messages.po"]
        results = discover(
            PurePath("."),
            mock=([(PurePath(path), PurePath(path), path) for path in paths], []),
        )
        self.assertIsInstance(results, list)
        self.assertIsInstance(results, DiscoveryResults)
        self.assertFalse(results.truncated)
        self.assertEqual(results.limit_reasons, frozenset())
        self.assert_discovery(
            results,
            [{"filemask": "locales/*/messages.po", "file_format": "po"}],
        )

    def test_discover_mock_transifex_config(self) -> None:
        paths = [".tx/config", "locale/en.json", "locale/cs.json"]
        self.assert_discovery(
            discover(
                PurePath(),
                mock=(
                    [(PurePath(path), PurePath(path), path) for path in paths],
                    [],
                ),
            ),
            [
                {
                    "filemask": "locale/*.json",
                    "file_format": "json-nested",
                    "template": "locale/en.json",
                },
            ],
        )

    def test_discover_deeply_nested_json(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = pathlib.Path(tmpdir)
            content = '{"a":' * 2000 + "1" + "}" * 2000
            (root / "en.json").write_text(content, encoding="utf-8")
            (root / "cs.json").write_text(content, encoding="utf-8")

            results = discover(root)

        self.assert_discovery(
            results,
            [
                {
                    "filemask": "*.json",
                    "file_format": "json-nested",
                    "template": "en.json",
                },
            ],
        )

    def test_discover_files(self) -> None:
        self.assert_discovery(
            discover(TEST_DATA),
            [
                {
                    "file_format": "po",
                    "filemask": "locales/*.po",
                    "new_base": "locales/messages.pot",
                    "name": "translation",
                },
                {
                    "file_format": "po",
                    "filemask": "test/*.po",
                    "new_base": "test/messages.pot",
                },
                {
                    "file_format": "po",
                    "filemask": "other/locales/*.po",
                    "new_base": "other/locales/messages.pot",
                    "name": "auto",
                },
                {
                    "file_format": "aresource",
                    "filemask": "app/src/res/main/values-*/strings.xml",
                    "name": "android",
                    "template": "app/src/res/main/values/strings.xml",
                },
                {"file_format": "json-nested", "filemask": "json/bi-*.json"},
                {
                    "file_format": "json-nested",
                    "filemask": "json/bom-*.json",
                    "template": "json/bom-en.json",
                },
                {
                    "file_format": "i18next",
                    "filemask": "json/i18next-*.json",
                    "template": "json/i18next-en.json",
                },
                {
                    "file_format": "i18nextv4",
                    "filemask": "json/i18nextv4-*.json",
                    "template": "json/i18nextv4-en.json",
                },
                {
                    "file_format": "json-nested",
                    "filemask": "json/nested-*.json",
                    "template": "json/nested-en.json",
                },
                {
                    "file_format": "go-i18n-json",
                    "filemask": "json/go-*.json",
                    "template": "json/go-en.json",
                },
                {
                    "file_format": "webextension",
                    "filemask": "json/webext-*.json",
                    "template": "json/webext-en.json",
                },
                {
                    "file_format": "json",
                    "filemask": "json/flat-*.json",
                    "template": "json/flat-en.json",
                },
                # New JSON format variants
                {
                    "file_format": "go-i18n-json-v2",
                    "filemask": "json/go-i18n-v2-*.json",
                    "template": "json/go-i18n-v2-en.json",
                },
                {
                    "file_format": "nextcloud-json",
                    "filemask": "json/nextcloud-*.json",
                    "template": "json/nextcloud-en.json",
                },
                {
                    "file_format": "resjson",
                    "filemask": "json/resjson-*.json",
                    "template": "json/resjson-en.json",
                },
                {
                    "filemask": "locales/*.po",
                    "new_base": "locales/messages.pot",
                    "file_format": "po",
                },
                {"file_format": "po", "filemask": "monopo/*.po"},
                {
                    "file_format": "po-mono",
                    "filemask": "monopo/*.po",
                    "template": "monopo/en.po",
                },
                {
                    "filemask": "app/src/res/main/values-*/strings.xml",
                    "file_format": "aresource",
                    "template": "app/src/res/main/values/strings.xml",
                },
                {
                    "filemask": "java/utf-8_*.properties",
                    "template": "java/utf-8.properties",
                    "file_format": "properties",
                    "file_format_params": {"properties_encoding": "utf-8"},
                },
                {
                    "filemask": "java/utf-16_*.properties",
                    "template": "java/utf-16.properties",
                    "file_format": "properties",
                    "file_format_params": {"properties_encoding": "utf-16"},
                },
                {
                    "filemask": "java/iso_*.properties",
                    "template": "java/iso.properties",
                    "file_format": "properties",
                },
                {
                    "filemask": "po/*.po",
                    "file_format": "po",
                    "new_base": "po/messages.pot",
                    "name": "implicit",
                },
                {
                    "filemask": "yaml/*/*.yml",
                    "file_format": "yaml",
                    "template": "yaml/en/en.yml",
                },
                {
                    "filemask": "yaml/*.yml",
                    "file_format": "ruby-yaml",
                    "template": "yaml/en.yml",
                },
                {
                    "filemask": "yaml/*/nomatch.yml",
                    "template": "yaml/en/nomatch.yml",
                    "file_format": "yaml",
                },
                {
                    "filemask": "yaml/*/corrupt.yml",
                    "template": "yaml/en/corrupt.yml",
                    "file_format": "yaml",
                },
                {
                    "file_format": "php",
                    "filemask": "php/*.php",
                    "new_base": "php/en.php",
                    "template": "php/en.php",
                },
                {
                    "file_format": "laravel",
                    "filemask": "laravel/*.php",
                    "new_base": "laravel/en.php",
                    "template": "laravel/en.php",
                },
                {"file_format": "poxliff", "filemask": "xliff/*.poxliff"},
                {
                    "file_format": "xliff",
                    "filemask": "xliff/*.xliff",
                    "template": "xliff/en.xliff",
                },
                {
                    "file_format": "xliff",
                    "filemask": "xliff/*.xlf",
                    "template": "xliff/en.xlf",
                    "file_format_params": {"xliff_placeables": "plain"},
                },
                # New XLIFF2 formats
                {
                    "file_format": "xliff2",
                    "filemask": "xliff2/*.xliff",
                    "file_format_params": {"xliff_placeables": "plain"},
                },
                {
                    "file_format": "xliff2",
                    "filemask": "xliff2/*-placeables.xliff",
                    "file_format_params": {"xliff_placeables": "placeables"},
                },
                {
                    "file_format": "gotext",
                    "filemask": "json/gotext-*.json",
                    "template": "json/gotext-en.json",
                },
                # New format discoveries (DTD, Catkeys, Mi18n, TOML)
                {
                    "file_format": "dtd",
                    "filemask": "dtd/*.dtd",
                    "template": "dtd/en.dtd",
                },
                {
                    "file_format": "catkeys",
                    "filemask": "catkeys/*.catkeys",
                    "template": "catkeys/en.catkeys",
                },
                {
                    "file_format": "mi18n-lang",
                    "filemask": "lang/*.lang",
                    "template": "lang/en.lang",
                },
                {
                    "file_format": "go-i18n-toml",
                    "filemask": "toml/go-i18n-*.toml",
                    "template": "toml/go-i18n-en.toml",
                },
                {
                    "file_format": "toml",
                    "filemask": "toml/regular-*.toml",
                    "template": "toml/regular-en.toml",
                },
            ],
        )

    def test_cli(self) -> None:
        output = StringIO()
        cli(args=[TEST_DATA.as_posix()], stdout=output)
        self.assertIn("Match 2", output.getvalue())

    def test_cli_nonexistent_directory(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            missing = (pathlib.Path(tmpdir) / "does_not_exist").as_posix()
            stderr = StringIO()
            with patch("sys.stderr", stderr), self.assertRaises(SystemExit) as ctx:
                cli(args=[missing])
            self.assertEqual(ctx.exception.code, 2)
        self.assertIn("no such directory", stderr.getvalue())

    def test_cli_nonexistent_directory_escapes_controls(self) -> None:
        # Control characters in the path must not inject lines or terminal
        # escape sequences into the argparse error output.
        path = "missing\nINJECTED_LINE\x1b[31m"
        stderr = StringIO()
        with patch("sys.stderr", stderr), self.assertRaises(SystemExit) as ctx:
            cli(args=[path])
        self.assertEqual(ctx.exception.code, 2)

        message = stderr.getvalue()
        self.assertNotIn("\x1b", message)
        error_lines = [
            line for line in message.splitlines() if "no such directory" in line
        ]
        self.assertEqual(len(error_lines), 1, message)
        self.assertTrue(
            error_lines[0].endswith(
                "no such directory: missing\\nINJECTED_LINE\\x1b[31m"
            ),
            error_lines[0],
        )

    def test_cli_escape_controls(self) -> None:
        controls = "".join(chr(code) for code in (*range(32), *range(127, 160)))
        value = f"překlady/日本語{controls}\u2028\u2029\u202e\udcff.po"
        result = DiscoveryResult({"filemask": value})
        result.meta["origin"] = value
        output = StringIO()
        with patch(
            "translation_finder.api.discover", return_value=DiscoveryResults([result])
        ):
            self.assertEqual(cli(args=["."], stdout=output), 0)

        lines = output.getvalue().splitlines()
        self.assertEqual(len(lines), 3)
        self.assertTrue(all(line.isprintable() for line in lines))
        self.assertIn("překlady/日本語", lines[1])
        self.assertIn(r"\x1b", lines[1])
        self.assertIn(r"\n", lines[1])
        self.assertIn(r"\u2028\u2029\u202e\udcff.po", lines[1])
        self.assertEqual(result["filemask"], value)
        self.assertEqual(result.meta["origin"], value)

    def test_cli_escape_filename(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = pathlib.Path(tmpdir)
            source = root / "cs.po"
            source.touch()
            # Windows forbids control characters in real filesystem paths.
            path = "locales\n\x1b[31m/cs.po"
            results = discover(root, mock=([(source, PurePath(path), path)], []))
            output = StringIO()
            with patch("translation_finder.api.discover", return_value=results):
                cli(args=[tmpdir], stdout=output)

        self.assertEqual(
            output.getvalue(),
            "== Match 1 ==\n"
            "file_format    : po\n"
            "filemask       : locales\\n\\x1b[31m/*.po\n\n",
        )

    def test_cli_escape_transifex(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = pathlib.Path(tmpdir)
            (root / ".tx").mkdir()
            (root / ".tx" / "config").write_text(
                "[překlady\x1b]0;title\x07]\n"
                "file_filter = locales/<lang>.po\n"
                "source_file = source\n"
                "  injected\x1b[31m.pot\n"
                "type = PO\n",
                encoding="utf-8",
            )
            output = StringIO()
            cli(args=[tmpdir], stdout=output)

        self.assertEqual(
            output.getvalue(),
            "== Match 1 (Transifex) ==\n"
            "file_format    : po\n"
            "filemask       : locales/*.po\n"
            "name           : překlady\\x1b]0;title\\x07\n"
            "new_base       : source\\ninjected\\x1b[31m.pot\n\n",
        )

    def test_no_match(self) -> None:
        paths = ["files/document.odt"]
        self.assert_discovery(
            discover(
                PurePath("."),
                mock=([(PurePath(path), PurePath(path), path) for path in paths], []),
                eager=True,
            ),
            [
                {
                    "filemask": "files/*.odt",
                    "new_base": "files/document.odt",
                    "template": "files/document.odt",
                    "file_format": "odf",
                },
            ],
        )


class DiscoveryLimitsTest(DiscoveryTestCase):
    def test_limits_configuration(self) -> None:
        defaults = DiscoveryLimits()
        self.assertEqual(
            [getattr(defaults, field.name) for field in fields(defaults)],
            [
                4096,
                4096,
                65536,
                32,
                67108864,
                512,
                100000,
                20000,
                64,
                150000,
                65536,
            ],
        )
        for field in fields(defaults):
            with (
                self.subTest(field=field.name),
                self.assertRaisesRegex(ValueError, field.name),
            ):
                DiscoveryLimits(**{field.name: -1})
            with self.assertRaises(FrozenInstanceError):
                setattr(defaults, field.name, 1)
        unlimited = DiscoveryLimits.unlimited()
        self.assertTrue(
            all(getattr(unlimited, field.name) is None for field in fields(unlimited))
        )

    def test_cli_limit_configuration(self) -> None:
        for field in fields(DiscoveryLimits):
            option = "--" + field.name.replace("_", "-")
            for value in (0, 1, 100000000):
                with (
                    self.subTest(option=option, value=value),
                    patch.object(
                        api_module, "discover", return_value=DiscoveryResults()
                    ) as discovery,
                ):
                    self.assertEqual(
                        cli(args=[".", option, str(value)], stdout=StringIO()), 0
                    )
                    self.assertEqual(
                        discovery.call_args.kwargs["limits"],
                        DiscoveryLimits(**{field.name: value}),
                    )
        for args, expected in (
            (["."], DiscoveryLimits()),
            ([".", "--unlimited"], DiscoveryLimits.unlimited()),
        ):
            with (
                self.subTest(args=args),
                patch.object(
                    api_module, "discover", return_value=DiscoveryResults()
                ) as discovery,
            ):
                self.assertEqual(cli(args=args, stdout=StringIO()), 0)
                self.assertEqual(discovery.call_args.kwargs["limits"], expected)

    def test_cli_invalid_limits(self) -> None:
        for field in fields(DiscoveryLimits):
            option = "--" + field.name.replace("_", "-")
            for arguments in (
                [option, "-1"],
                [option, "bad"],
                ["--unlimited", option, "0"],
                [option, "1", "--unlimited"],
            ):
                with (
                    self.subTest(arguments=arguments),
                    patch("sys.stderr", StringIO()),
                    self.assertRaises(SystemExit) as error,
                ):
                    cli(args=[".", *arguments])
                self.assertEqual(error.exception.code, 2)

    def test_cli_truncation(self) -> None:
        output, stderr = StringIO(), StringIO()
        result = DiscoveryResult({"filemask": "locale/*.po", "file_format": "po"})
        with (
            patch.object(
                api_module,
                "discover",
                return_value=DiscoveryResults(
                    [result],
                    limit_reasons=[DiscoveryLimit.RESULTS, DiscoveryLimit.CANDIDATES],
                ),
            ),
            patch("sys.stderr", stderr),
        ):
            self.assertEqual(cli(args=["."], stdout=output), 3)
        self.assertIn("Match 1", output.getvalue())
        self.assertEqual(
            stderr.getvalue(),
            "warning: Translation discovery reached its resource limit; results may be incomplete (limits: candidates, results)\n",
        )

    def test_cli_result_limit(self) -> None:
        output, stderr = StringIO(), StringIO()
        with patch("sys.stderr", stderr), warnings.catch_warnings():
            warnings.simplefilter("error")
            self.assertEqual(
                cli(args=[str(TEST_DATA), "--max-results", "1"], stdout=output), 3
            )
        self.assertIn("Match 1", output.getvalue())
        self.assertNotIn("Match 2", output.getvalue())
        self.assertIn("limits: results", stderr.getvalue())

    def test_discover_unlimited_across_backends(self) -> None:
        class ExpandingDiscovery(BaseDiscovery):
            file_format = "po"

            def get_masks(
                self, *, eager: bool = False, hint: str | None = None
            ) -> Generator[DiscoveryCandidate]:
                for index in range(4100):
                    yield DiscoveryCandidate(
                        {"filemask": f"{self.source_language}/{index}.po"}, []
                    )

        with patch.object(
            api_module, "BACKENDS", [ExpandingDiscovery, ExpandingDiscovery]
        ):
            results = discover(
                PurePath(), mock=([], []), limits=DiscoveryLimits.unlimited()
            )
        self.assertEqual(len(results), 8200)
        self.assertFalse(results.truncated)

    def test_discover_zero_limits(self) -> None:
        for field, reason in (
            ("max_results", DiscoveryLimit.RESULTS),
            ("max_candidates", DiscoveryLimit.CANDIDATES),
            ("max_masks_per_path", DiscoveryLimit.MASKS_PER_PATH),
        ):
            with self.subTest(field=field):
                path = PurePath("locale/cs/messages.po")
                with patch.object(api_module, "BACKENDS", [GettextDiscovery]):
                    results = discover(
                        PurePath(),
                        mock=([(path, path, path.as_posix())], []),
                        limits=DiscoveryLimits(**{field: 0}),
                    )
                self.assertIn(reason, results.limit_reasons)
                self.assertEqual(len(results), 0)

    def test_zero_results_skips_finder_and_validates_root(self) -> None:
        with (
            tempfile.TemporaryDirectory() as tmpdir,
            patch.object(api_module, "Finder", side_effect=AssertionError),
        ):
            results = discover(tmpdir, limits=DiscoveryLimits(max_results=0))
            self.assertEqual(results.limit_reasons, {DiscoveryLimit.RESULTS})
            self.assertTrue(results.truncated)
            with self.assertRaises(FileNotFoundError):
                discover(
                    pathlib.Path(tmpdir) / "missing",
                    limits=DiscoveryLimits(max_results=0),
                )
            stderr = StringIO()
            with patch("sys.stderr", stderr):
                status = cli(
                    args=[
                        tmpdir,
                        *(
                            item
                            for field in fields(DiscoveryLimits)
                            for item in ("--" + field.name.replace("_", "-"), "0")
                        ),
                    ],
                    stdout=StringIO(),
                )
            self.assertEqual(status, 3)
            self.assertIn("limits: results", stderr.getvalue())

    def test_finder_limit_reason_reaches_cli(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = pathlib.Path(tmpdir)
            (root / "messages_en.po").touch()
            (root / "messages_cs.po").touch()
            limits = DiscoveryLimits(max_files=1)
            results = discover(root, limits=limits)
            self.assertIn(DiscoveryLimit.FILES, results.limit_reasons)
            self.assertTrue(results.truncated)
            stderr = StringIO()
            with patch("sys.stderr", stderr):
                status = cli(args=[tmpdir, "--max-files", "1"], stdout=StringIO())
            self.assertEqual(status, 3)
            self.assertIn("limits: files", stderr.getvalue())

    def test_hint_matching_reports_limit(self) -> None:
        paths = [PurePath(f"messages_{language}.po") for language in ("en", "cs", "de")]
        mock: PathMockType = ([(path, path, path.as_posix()) for path in paths], [])
        with patch.object(api_module, "BACKENDS", [GettextDiscovery]):
            results = discover(
                PurePath(),
                mock=mock,
                hint="*.po",
                limits=DiscoveryLimits(max_match_checks=1),
            )
        self.assertIn(DiscoveryLimit.MATCH_CHECKS, results.limit_reasons)

    def test_unlimited_masks_and_new_base(self) -> None:
        codes = sorted(
            code
            for code in base_module.LANGUAGES
            if BaseDiscovery.is_language_code(code)
        )[:33]
        path = PurePath(*codes, "messages.po")
        template = PurePath("messages.pot")
        files = [(entry, entry, entry.as_posix()) for entry in (path, template)]
        with patch.object(api_module, "BACKENDS", [GettextDiscovery]):
            results = discover(
                PurePath(), mock=(files, []), limits=DiscoveryLimits.unlimited()
            )
        self.assertEqual(len(results), 33)
        paths = [PurePath("locale/cs/messages.po"), PurePath("locale/messages.pot")]
        with patch.object(api_module, "BACKENDS", [GettextDiscovery]):
            results = discover(
                PurePath(),
                mock=([(entry, entry, entry.as_posix()) for entry in paths], []),
                limits=DiscoveryLimits.unlimited(),
            )
        self.assertEqual(results[0]["new_base"], "locale/messages.pot")
        self.assertFalse(results.truncated)

    def test_unlimited_sniff_budget_retains_local_bounds(self) -> None:
        parent = base_module.SniffBudget(None, None)
        child = base_module.SniffBudget(10, 2, parent=parent)
        self.assertEqual(child.reserve(20), 10)
        child.charge(4)
        self.assertEqual(child.reserve(20), 6)
        self.assertTrue(child.exhausted)
        self.assertFalse(parent.exhausted)
        self.assertIsNone(parent.remaining_bytes)
        self.assertIsNone(parent.remaining_files)
        self.assertIsNone(child.reserve(20))
        budget = base_module.DiscoveryBudget(None, None)
        self.assertTrue(budget.consume_candidate())
        self.assertTrue(budget.consume_new_base_check())
        self.assertFalse(budget.truncated)

    def test_sniff_limits_zero_and_unlimited(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = pathlib.Path(tmpdir)
            for language in ("en", "cs"):
                (root / f"messages_{language}.json").write_text(
                    '[ {"id": "hello", "translation": "Hello"} ]', encoding="utf-8"
                )
            for limits in (
                DiscoveryLimits(sniff_max_bytes=0),
                DiscoveryLimits(sniff_max_files=0),
            ):
                with (
                    self.subTest(limits=limits),
                    patch.object(api_module.Finder, "open", side_effect=AssertionError),
                ):
                    results = discover(root, limits=limits)
                self.assertEqual(results[0]["file_format"], "json-nested")
                self.assertFalse(results.truncated)
            results = discover(root, limits=DiscoveryLimits.unlimited())
            self.assertEqual(results[0]["file_format"], "go-i18n-json")
            self.assertFalse(results.truncated)
