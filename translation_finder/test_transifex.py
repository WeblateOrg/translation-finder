# Copyright © Michal Čihař <michal@weblate.org>
#
# SPDX-License-Identifier: GPL-3.0-or-later

"""Transifex client INI dialect and resource processing regressions."""

from __future__ import annotations

import tempfile
from pathlib import Path
from unittest import TestCase
from unittest.mock import patch

from .api import DiscoveryLimits, cli, discover
from .discovery import transifex as transifex_module
from .discovery._transifex import TransifexConfig
from .discovery.base import DiscoveryBudget
from .discovery.result import DiscoveryLimit
from .discovery.transifex import TransifexDiscovery
from .finder import Finder


class TransifexConfigTest(TestCase):
    @staticmethod
    def parse(content: str, max_bytes: int = 4096) -> dict[str, dict[str, str]]:
        config = TransifexConfig(content, DiscoveryBudget())
        return dict(config.resources(max_bytes))

    def test_client_syntax(self) -> None:
        content = """
; ignored comment
   # another comment
[main]
host = https://app.transifex.com
[o:org:p:project:r:resource] # trailing comment
  file_filter : locale/<lang>.po ; comment
"source_file" = 'locale/messages.pot'
`type` = "PO"
unknown = ignored
"""
        self.assertEqual(
            self.parse(content),
            {
                "o:org:p:project:r:resource": {
                    "file_filter": "locale/<lang>.po",
                    "source_file": "locale/messages.pot",
                    "type": "PO",
                },
            },
        )

    def test_header_and_key_case(self) -> None:
        self.assertEqual(
            self.parse('[a[b]] trailing text\nTYPE=PO\n"""type""":JSON\n'),
            {"a[b]": {"type": "JSON"}},
        )

    def test_repeated_sections_merge(self) -> None:
        self.assertEqual(
            self.parse(
                "[resource]\nfile_filter=old\ntype=PO\n"
                "[other]\n[resource]\nfile_filter=locale/<lang>.po\n"
            ),
            {
                "resource": {"file_filter": "locale/<lang>.po", "type": "PO"},
                "other": {},
            },
        )

    def test_values(self) -> None:
        checks = (
            ("'PO'", "PO"),
            ('"PO"', "PO"),
            ('"P"O"', '"P"O"'),
            ("PO#comment", "PO"),
            ('"PO#comment"', '"PO'),
            ("`PO#;` ignored", "PO#;"),
            ('"""PO#;""" ignored', "PO#;"),
            ("", ""),
            ("PO\\\n    T", "POT"),
            ("P\\\n O\\\n T", "POT"),
            ("PO\\\n\n", "PO"),
            ("PO\\", "PO"),
            ('"""P\nO""" # comment', "P\nO"),
            ("`P\n\nO`", "P\n\nO"),
            ("`P\r\nO`", "P\r\nO"),
        )
        for raw, expected in checks:
            with self.subTest(raw=raw):
                self.assertEqual(
                    self.parse(f"[a]\ntype={raw}"), {"a": {"type": expected}}
                )

    def test_line_endings(self) -> None:
        for separator in ("\n", "\r\n", "\r"):
            with self.subTest(separator=separator):
                self.assertEqual(
                    self.parse(separator.join(("[a]", "type=PO", ""))),
                    {"a": {"type": "PO"}},
                )

    def test_malformed_section_recovery(self) -> None:
        for malformed in (
            "not an assignment",
            '"unclosed = value',
            "= empty key",
            '"" = empty quoted key',
            '"type" missing delimiter',
            "  continuation without assignment",
        ):
            with self.subTest(malformed=malformed):
                self.assertEqual(
                    self.parse(f"[bad]\ntype=PO\n{malformed}\n[good]\ntype=JSON"),
                    {"good": {"type": "JSON"}},
                )

    def test_unterminated_multiline_value(self) -> None:
        self.assertEqual(self.parse('[a]\ntype="""P\nO\n'), {})

    def test_malformed_header_preserves_adjacent_resources(self) -> None:
        for header in ("[unclosed", "[]", "["):
            with self.subTest(header=header):
                self.assertEqual(
                    self.parse(
                        "[before]\nfile_filter=first/<lang>.po\ntype=PO\n"
                        f"{header}\nfile_filter=wrong/<lang>.po\n"
                        'type="""unterminated\n'
                        "[after]\nfile_filter=last/<lang>.po\ntype=JSON\n"
                    ),
                    {
                        "before": {"file_filter": "first/<lang>.po", "type": "PO"},
                        "after": {"file_filter": "last/<lang>.po", "type": "JSON"},
                    },
                )

    def test_malformed_header_before_resources(self) -> None:
        self.assertEqual(
            self.parse(
                "directory=locale\n[unclosed\ndirectory=wrong\n"
                "[good]\nfile_filter=%(directory)s/<lang>.po\n"
            ),
            {"good": {"file_filter": "locale/<lang>.po"}},
        )

    def test_forward_and_default_references(self) -> None:
        self.assertEqual(
            self.parse(
                "[a]\nfile_filter=%(directory)s/<lang>.po\n"
                "directory=locale\nsource_file=%(source)s\ntype=%(type)s\n"
                "[DEFAULT]\nsource=locale/messages.pot\ntype=PO\n"
                "[b]\nfile_filter=%(missing)s/<lang>.po\n"
            ),
            {
                "a": {
                    "file_filter": "locale/<lang>.po",
                    "source_file": "locale/messages.pot",
                    "type": "PO",
                },
                "b": {"file_filter": "%(missing)s/<lang>.po"},
            },
        )

    def test_no_implicit_default_inheritance(self) -> None:
        self.assertEqual(
            self.parse("type=PO\n[DEFAULT]\nsource_file=en.po\n[a]"), {"a": {}}
        )

    def test_dotted_parents(self) -> None:
        self.assertEqual(
            self.parse(
                "[parent]\nfile_filter=%(directory)s/<lang>.po\ndirectory=locale\n"
                "type=PO\n[parent.absent.child]\n[parent.child]\ntype=JSON\n"
            ),
            {
                "parent": {"file_filter": "locale/<lang>.po", "type": "PO"},
                "parent.absent.child": {
                    "file_filter": "locale/<lang>.po",
                    "type": "PO",
                },
                "parent.child": {"file_filter": "locale/<lang>.po", "type": "JSON"},
            },
        )

    def test_invalid_parent(self) -> None:
        self.assertEqual(
            self.parse("[a]\nbroken\n[a.b]\ntype=PO"), {"a.b": {"type": "PO"}}
        )

    def test_deep_dotted_parents(self) -> None:
        child = "root." + ".child" * 600
        result = self.parse(
            f"[{child}]\ndirectory=ignored\n"
            "[root!]\ntype=JSON\n"
            "[root.]\nfile_filter=%(directory)s/<lang>.po\ndirectory=locale\n"
            "[root]\ntype=PO\n"
            "[root.other]\nbroken\n[root.other.child]\n"
        )
        self.assertEqual(
            list(result), [child, "root!", "root.", "root", "root.other.child"]
        )
        self.assertEqual(
            result[child], {"file_filter": "locale/<lang>.po", "type": "PO"}
        )
        self.assertEqual(result["root.other.child"], {})

    def test_automatic_keys(self) -> None:
        self.assertEqual(self.parse("[a]\n-=PO\ntype=`%(#1)s`"), {"a": {"type": "PO"}})

    def test_reference_scan(self) -> None:
        for raw, expected in (
            ("%(%(value)s", "nested"),
            ("%()s%(broken)x%(value)s%(value)s", "%()s%(broken)xPOPO"),
            ("%(value)s%(not closed", "PO%(not closed"),
            ("%(" * 2000, "%(" * 2000),
        ):
            with self.subTest(raw=raw[:80]):
                self.assertEqual(
                    self.parse(f"[a]\ntype={raw}\nvalue=PO\n%(value=nested"),
                    {"a": {"type": expected}},
                )

    def test_reference_cycles(self) -> None:
        self.assertEqual(
            self.parse("[a]\ntype=%(other)s\nother=%(type)s"),
            {"a": {"type": "%(type)s"}},
        )
        lookups: list[tuple[str, str]] = []

        class RecordingConfig(TransifexConfig):
            def _lookup(self, section: str, key: str) -> tuple[str, str] | None:
                lookups.append((section, key))
                return super()._lookup(section, key)

        config = RecordingConfig(
            "[DEFAULT]\nvalue=%(value)s\n[a]\ntype=prefix%(value)s", DiscoveryBudget()
        )
        self.assertEqual(
            dict(config.resources(4096)), {"a": {"type": "prefix%(value)s"}}
        )
        self.assertEqual(lookups.count(("DEFAULT", "value")), 1)

    def test_resolved_value_limit(self) -> None:
        checks = (
            "type=12345",
            "type=ééé",
            "type=%(value)s\nvalue=12345",
            "type=%(value)s%(value)s\nvalue=123",
            "type=%(value)s\nvalue=%(value)s%(value)s",
        )
        for options in checks:
            with self.subTest(options=options):
                self.assertEqual(self.parse(f"[a]\n{options}", max_bytes=4), {})
        self.assertEqual(self.parse("[a]\ntype=éé", max_bytes=4), {"a": {"type": "éé"}})
        self.assertEqual(self.parse("[a]\ntype=%(v)s\nv=123456789", max_bytes=8), {})

    def test_reference_substitution_limit(self) -> None:
        self.assertEqual(
            self.parse("[a]\ntype=%(first)s\nfirst=%(second)s\nsecond=%(first)s"),
            {"a": {"type": "%(second)s"}},
        )


class TransifexSectionBudgetTest(TestCase):
    def test_useful_resources_are_not_charged_twice(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            path = root / ".tx" / "config"
            path.parent.mkdir()
            path.write_text(
                "[a]\nfile_filter=a/<lang>.po\ntype=PO\n"
                "[b]\nfile_filter=b/<lang>.po\ntype=PO\n"
            )
            results = discover(root, limits=DiscoveryLimits(max_candidates=2))
            self.assertEqual({result["name"] for result in results}, {"a", "b"})
            self.assertFalse(results.truncated)

    def test_resolved_paths_are_validated(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            path = root / ".tx" / "config"
            path.parent.mkdir()
            path.write_text(
                "[DEFAULT]\nparent=../..\nabsolute=/etc\n"
                "[unsafe_mask]\nfile_filter=%(parent)s/<lang>.po\ntype=PO\n"
                "[unsafe_source]\nfile_filter=locale/<lang>.po\n"
                "source_file=%(absolute)s/messages.pot\ntype=PO\n"
                "[good]\nfile_filter=locale/<lang>.po\ntype=PO\n"
            )
            self.assertEqual([result["name"] for result in discover(root)], ["good"])

    def test_exact_and_exceeded_allowance(self) -> None:
        for trailing, truncated in (("", False), ("[third]\n", True)):
            with self.subTest(trailing=trailing):
                budget = DiscoveryBudget(2)
                config = TransifexConfig(
                    "[main]\n[DEFAULT]\n[first]\n[second]\n" + trailing, budget
                )
                self.assertEqual(
                    dict(config.resources(4096)), {"first": {}, "second": {}}
                )
                self.assertEqual(budget.truncated, truncated)

    def test_repeated_sections_consume_allowance(self) -> None:
        budget = DiscoveryBudget(1)
        config = TransifexConfig("[a]\ntype=PO\n[a]\ntype=JSON", budget)
        self.assertEqual(dict(config.resources(4096)), {"a": {"type": "PO"}})
        self.assertEqual(budget.limit_reasons, {DiscoveryLimit.CANDIDATES})

    def test_zero_and_unlimited(self) -> None:
        for limit, expected in ((0, {}), (None, {"a": {}})):
            with self.subTest(limit=limit):
                budget = DiscoveryBudget(limit)
                self.assertEqual(
                    dict(TransifexConfig("[a]", budget).resources(4096)), expected
                )

    def test_discovery_budget_across_files(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            for name, content in (
                ("a", "[first]\n"),
                ("b", "[second]\nfile_filter=locale/<lang>.po\ntype=PO\n"),
                ("c", "[third]\n"),
            ):
                path = root / name / ".tx" / "config"
                path.parent.mkdir(parents=True)
                path.write_text(content)
            (root / "locale").mkdir()
            (root / "locale" / "cs.po").touch()
            results = discover(root, limits=DiscoveryLimits(max_candidates=2))
            self.assertEqual([result["name"] for result in results], ["second"])
            self.assertEqual(results.limit_reasons, {DiscoveryLimit.CANDIDATES})

    def test_attack_and_cli_status(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            path = root / ".tx" / "config"
            path.parent.mkdir()
            path.write_text("".join(f"[s{number}] #x\n" for number in range(5000)))
            results = discover(root)
            self.assertEqual(results, [])
            self.assertEqual(results.limit_reasons, {DiscoveryLimit.CANDIDATES})
            self.assertFalse(
                discover(root, limits=DiscoveryLimits(max_candidates=5000)).truncated
            )
            self.assertFalse(
                discover(root, limits=DiscoveryLimits.unlimited()).truncated
            )
            with self.assertWarns(RuntimeWarning):
                self.assertEqual(list(TransifexDiscovery(Finder(root)).discover()), [])
            with (
                patch("sys.argv", ["weblate-discover", str(root)]),
                patch("sys.stderr") as stderr,
            ):
                self.assertEqual(cli(), 3)
                self.assertIn(
                    "candidates",
                    "".join(call.args[0] for call in stderr.write.call_args_list),
                )
            with patch.object(transifex_module, "DISCOVERY_MAX_CANDIDATES", 1):
                self.assertEqual(list(TransifexDiscovery(Finder(root)).get_masks()), [])
