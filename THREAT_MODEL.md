# Translation Finder threat model

<!--
Copyright © Michal Čihař <michal@weblate.org>
SPDX-License-Identifier: GPL-3.0-or-later
-->

## Purpose and scope

Translation Finder inspects a source checkout and suggests translation component
configurations. A repository author can influence both the work discovery does
and the values it returns. This model covers the high-level `discover()`
interface, the `weblate-discover` CLI, and every production use of the library
in Weblate, including low-level interfaces and exported data.

## Trust boundaries

- The caller selects the discovery root and controls the runtime, installed
  backends, and resource policy. Built-in discovery assumes a stable checkout.
  Repository names, directory layout, file contents, and project configuration
  such as `.tx/config` are untrusted.
- Discovery treats the file-mask hint and source-language string as potentially
  hostile, including when Weblate supplies them from component settings.
- Weblate uses ordinary discovery and may retry in eager mode. It stores
  results and truncation status in the component-creation session, displays
  choices, and applies the selected settings. It also derives discovery
  presets from results. Paths, masks, format parameters, and generated
  language expressions retain their repository origin throughout these flows.
- Weblate also uses the library's `EXCLUDES` entries when filtering archive
  paths. This shared data is part of the supported integration. Weblate owns
  path normalization, destination validation, and extraction.

## Security guarantees

With the built-in backends and default budgets, a single `discover()` call
must bound the work a hostile checkout, hint, or source-language string can
induce in ordinary and eager mode. This covers traversal, indexing, matching,
candidate generation, content inspection, and collecting results. A small input that makes a
built-in matcher or parser consume prohibitive CPU or memory is grounds for a
security report, even if the operation eventually finishes or the expensive
step occurs inside `Finder`.

Discovery bounds the length of the hint and source language before scanning.
This limits the input to wildcard matching and template path construction
even when the caller disables discovery budgets.

Built-in filesystem discovery skips symlink entries during traversal and
reads regular files to identify formats. Repository configuration is data.
Paths it supplies must refer to the selected checkout, and literal repository
text used in a generated language expression must retain its literal meaning.

Discovery can return partial results. Callers can inspect `truncated` and
`limit_reasons` for reported limits. Content sampling is best effort, so even
a result set without a truncation flag can omit files or misidentify formats.
The [README](README.rst#discovery-limits) documents limit and CLI behavior.

## Limitations and caller responsibilities

- Direct `Finder` calls give the application control over matching.
  `filter_files()` accepts basename and directory regular expressions.
  `filter_masks()` accepts basename wildcard masks and an optional directory
  regular expression. `mask_matches()` accepts a relative-path wildcard mask.
  Callers own the size, complexity, and frequency of these queries. A match
  counter cannot bound the time spent evaluating one caller-supplied regex.
- Applications choose custom backends, mock path providers, and any raised or
  disabled budgets. These choices can increase or remove the bounds on a run.
  Operators control concurrent scans, retries, filesystem latency, and hard
  deadlines or process memory quotas.
- Keep the checkout stable while scanning it. Discovery cannot secure a
  directory namespace that another process replaces during the scan.
  Consumers must validate suggested settings before using them to open files,
  configure components, evaluate patterns, or render output in another context.

## Maintenance and security reports

Review this model when supported entry points, trust assumptions, or Weblate's
use of the library changes. When assessing a report, trace the attacker-controlled
input through the affected release to its effect. For example, a caller
choosing an expensive regex for a direct query assumes that cost. If Weblate
forwards hostile input to the same helper, or a hostile checkout triggers
expensive matching through a built-in backend, the path is in scope. Triage
integration findings across both projects and fix the component responsible
for the violated boundary.

Report issues through the [Weblate security policy](SECURITY.md).
