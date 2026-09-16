# Copyright © Michal Čihař
#
# SPDX-License-Identifier: MIT

# Standalone CI script, not an importable package.
# ruff: file-ignore[implicit-namespace-package]

"""Extract a release's changelog and convert it to GitHub-flavored Markdown."""

from __future__ import annotations

import argparse
import subprocess  # ruff: ignore[suspicious-subprocess-import]
from pathlib import Path


def extract_release(changelog: str, tag: str) -> str:
    """
    Extract the section matching the release tag.

    Returns:
        The section body as reStructuredText, with a trailing newline.

    Raises:
        ValueError: If the release section is missing, duplicated, or empty.

    """
    version = tag.removeprefix("v")
    lines = changelog.splitlines()
    headings = [
        index
        for index, line in enumerate(lines[:-1])
        if line
        and not line[0].isspace()
        and len(lines[index + 1]) >= len(line)
        and set(lines[index + 1]) == {"-"}
    ]
    matches = [index for index in headings if lines[index] == version]
    if len(matches) != 1 or version == "Unreleased":
        message = f"Expected exactly one changelog section for {version!r}"
        raise ValueError(message)
    start = matches[0]
    end = next((index for index in headings if index > start), len(lines))
    body = "\n".join(lines[start + 2 : end]).strip()
    if not body:
        message = f"Changelog section for {version!r} is empty"
        raise ValueError(message)
    return f"{body}\n"


def main() -> None:
    """Write release notes, failing before publication if extraction fails."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("tag")
    parser.add_argument("changelog", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    try:
        body = extract_release(args.changelog.read_text(encoding="utf-8"), args.tag)
    except ValueError as error:
        parser.error(str(error))
    result = subprocess.run(
        ["pandoc", "--from=rst", "--to=gfm", "--wrap=none", "--fail-if-warnings"],  # ruff: ignore[start-process-with-partial-path]
        input=body,
        text=True,
        encoding="utf-8",
        capture_output=True,
        check=True,
    )
    if not result.stdout.strip():
        parser.error("Changelog section produces empty release notes")
    args.output.write_text(result.stdout, encoding="utf-8")


if __name__ == "__main__":
    main()
