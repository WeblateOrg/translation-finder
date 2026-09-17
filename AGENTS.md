# Repository Guidelines

<!--
Copyright © Michal Čihař <michal@weblate.org>
SPDX-License-Identifier: GPL-3.0-or-later
-->

## Project structure

`translation_finder/` contains the Python library: `api.py` exposes discovery and
CLI entry points, `finder.py` handles file matching, and `discovery/` implements
format detection and result handling. Tests live alongside source as `test_*.py`;
`test_data/` holds translation fixtures. Usage documentation is in `README.rst`,
and release history is in `CHANGES.rst`.

## Development commands

Use Python 3.11 or newer. Run commands from the repository root:

- `uv sync --dev`: install the project and development dependencies into `.venv`.
- `uv run weblate-discover translation_finder/test_data/`: try discovery locally.
- `uv build`: build source and wheel distributions.
- `uv run pytest --cov=translation_finder translation_finder README.rst`: run tests,
  README doctests, and coverage checks.
- `uv run prek run --all-files`: run configured formatting, lint, and repository checks.
- `uv run mypy --show-column-numbers translation_finder` and `uv run ty check`:
  run the type checkers used in CI.

Prefer `uv run` after syncing. Use prek for Ruff checks and formatting; Ruff may
be available only inside the hook environment.

## Coding conventions

Follow `.editorconfig`: four spaces for Python, UTF-8, LF endings, and final
newlines. Use snake_case functions and variables and PascalCase classes. Prefer
type hints, `from __future__ import annotations`, and `TYPE_CHECKING` imports
for type-only dependencies. Follow configured Ruff rules; use human-readable
rule names in overrides. Include the usual copyright and GPL-3.0-or-later SPDX
header in new Python files.

## Testing guidelines

Pytest runs unittest-style tests and Hypothesis property tests. Name test modules
`test_*.py` and methods `test_*`. Add focused regression tests for fixes and
coverage for new discovery behavior, including malformed inputs. Preserve
intentionally malformed fixtures. Coverage must reach 100% line coverage under
the configured exclusions; `test_fuzz.py` is excluded from coverage measurement.

## Commits and pull requests

Use Conventional Commits: `<type>(<optional scope>): <description>`, for example
`fix(discovery): handle empty translation files`. Include a concise motivation
in the body and `Fixes #123` when resolving an issue.

Keep PRs focused; describe changes and related issues, add relevant tests, and
ensure lint and tests pass. Document changed behavior. Add significant user-visible
changes to an upcoming-release section in `CHANGES.rst`; preserve released sections.
Minor fixes and fixes to unreleased features do not require changelog entries.
