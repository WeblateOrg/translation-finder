Translation Finder
==================

.. image:: https://img.shields.io/badge/website-weblate.org-blue.svg
    :alt: Website
    :target: https://weblate.org/

.. image:: https://hosted.weblate.org/widgets/weblate/-/svg-badge.svg
    :alt: Translation status
    :target: https://hosted.weblate.org/engage/weblate/?utm_source=widget

.. image:: https://bestpractices.coreinfrastructure.org/projects/552/badge
    :alt: CII Best Practices
    :target: https://bestpractices.coreinfrastructure.org/projects/552

.. image:: https://img.shields.io/pypi/v/translation-finder.svg
    :target: https://pypi.org/project/translation-finder/
    :alt: PyPI package

.. image:: https://readthedocs.org/projects/weblate/badge/
    :alt: Documentation
    :target: https://docs.weblate.org/

Translation file discovery library used by `Weblate`_ to identify translation files and their configuration in source repositories.

Discovery can operate on file listings alone or inspect the filesystem when more accurate detection is needed, such as determining file encoding or distinguishing formats with similar syntax.

.. image:: https://s.weblate.org/cdn/Logo-Darktext-borders.png
   :target: https://weblate.org/
   :alt: Weblate
   :height: 55px

Maintained by `Weblate <https://weblate.org/>`_ — a privacy-respecting localization platform built on open-source foundations.

Usage
-----

It can be used from Python:

.. code-block:: pycon

   >>> from translation_finder import discover
   >>> from pprint import pprint
   >>> results = discover("translation_finder/test_data/")
   >>> len(results)
   40
   >>> pprint(results[0].match)
   {'file_format': 'aresource',
    'filemask': 'app/src/res/main/values-*/strings.xml',
    'name': 'android',
    'template': 'app/src/res/main/values/strings.xml'}
   >>> pprint(results[1].match)
   {'file_format': 'po',
    'filemask': 'locales/*.po',
    'name': 'translation',
    'new_base': 'locales/messages.pot'}

Additional information about discovery can be obtained from meta attribute:

.. code-block:: pycon

   >>> pprint(results[0].meta)
   {'discovery': 'TransifexDiscovery', 'origin': 'Transifex', 'priority': 500}
   >>> pprint(results[22].meta)
   {'discovery': 'GettextDiscovery', 'origin': None, 'priority': 1000}


Or command line:

.. code-block:: console

   $ weblate-discovery translation_finder/test_data/
   == Match 1 (Transifex) ==
   file_format    : aresource
   filemask       : app/src/res/main/values-*/strings.xml
   name           : android
   template       : app/src/res/main/values/strings.xml
   ...

   == Match 7 ==
   file_format    : po
   filemask       : locales/*.po
   new_base       : locales/messages.pot

Non-printable characters in command-line results are displayed as visible
escapes (for example, ``\n`` and ``\x1b``). The Python API returns the original
values unchanged.

Discovery result fields
-----------------------

Each result describes a suggested configuration. Paths are relative to the
discovery root, and ``filemask`` identifies the translation files belonging to
that configuration. Two optional fields describe files with different roles:

``template``
   The source file containing string definitions for a monolingual
   configuration. This maps to Weblate's `Monolingual base language file`_.
   Translations are interpreted using the string definitions in this file.

``new_base``
   The file used to create translation files for additional languages. This
   maps to Weblate's `Template for new translations`_. It can be an untranslated
   source file, a Gettext POT file, or an existing bilingual translation whose
   translations will be cleared when creating the new language file.
   Setting ``new_base`` alone does not make a configuration monolingual.

For example, the Gettext result in the usage example has only ``new_base``:
``locales/messages.pot`` supplies the messages for new languages, while existing
PO files contain their own source strings. Similarly, Qt's translation
repository can produce this bilingual configuration, using an existing Arabic
translation to create new languages:

.. code-block:: python

   {
       "file_format": "ts",
       "filemask": "translations/designer_*.ts",
       "new_base": "translations/designer_ar.ts",
   }

Both fields can refer to the same file. For example, the PHP and Laravel
fixtures use their English source files both to define strings and to create
new language files:

.. code-block:: pycon

   >>> pprint(sorted(
   ...     (r["file_format"], r["template"], r["new_base"])
   ...     for r in results if r["file_format"] in {"php", "laravel"}
   ... ))
   [('laravel', 'laravel/en.php', 'laravel/en.php'),
    ('php', 'php/en.php', 'php/en.php')]

Either field can appear independently, both can appear, or both can be absent.
An absent field means discovery did not provide that setting; it does not
necessarily mean the format does not support it. Discovery backends may also
read settings from repository configuration, such as Transifex configuration.

Filename-based discovery first looks for an exact name derived from the
filemask for ``new_base``. Otherwise, it prefers a discovered ``template`` when
that file is eligible for creating translations. Formats using the same file
extension for sources and translations then prefer a translation from the same
discovered filemask. If those checks do not identify a file, discovery retains
a deterministic fallback from the nearest directory containing an eligible
file. These are heuristics: review suggestions when a directory contains
unrelated catalogs or several possible templates.

.. _Monolingual base language file: https://docs.weblate.org/en/latest/admin/projects.html#monolingual-base-language-file
.. _Template for new translations: https://docs.weblate.org/en/latest/admin/projects.html#template-for-new-translations

Discovery limits
----------------

The CLI accepts nonnegative integer limits. Zero permits no work for that
budget. Defaults are:

* ``--max-candidates``: 4096 generated candidates across all backends.
* ``--max-results``: 4096 returned matches.
* ``--max-new-base-checks``: 65536 new-base lookups across all backends.
* ``--max-masks-per-path``: 32 generated masks per path.
* ``--sniff-max-bytes``: 67108864 bytes (64 MiB) sampled across the run.
* ``--sniff-max-files``: 512 content-sniffing file attempts across the run.

For example, ``weblate-discover --max-results 10000 translations/`` raises
only the result limit. ``weblate-discover --unlimited translations/`` disables
all six discovery budgets; it cannot be combined with individual limit options.
Internal parser safeguards and per-result format and encoding sampling limits
remain active.

The CLI prints collected matches to stdout, including partial results. If
candidate, result, new-base, or per-path mask limits cause truncation, it prints
one warning with the limit reasons to stderr and exits with status 3. Complete
discovery exits with status 0; invalid arguments exit with status 2.
Sniff-budget exhaustion uses best-effort detection and does not itself report
truncation.

Python callers can import ``DiscoveryLimits`` from ``translation_finder.api``
and pass it as the keyword-only ``limits`` argument to ``discover()``. Defaults
match the CLI; a field set to ``None`` disables that limit, and
``DiscoveryLimits.unlimited()`` disables all six. Negative values raise
``ValueError``. Inspect ``results.truncated`` and ``results.limit_reasons`` for
truncation; high-level discovery does not emit Python warnings.

Custom discovery backends
-------------------------

Custom ``BaseDiscovery`` implementations return ``DiscoveryCandidate`` objects
from ``get_masks()``. Each candidate associates the result with the paths which
actually generated it, allowing content detection to inspect the group without
expanding its wildcard mask again:

Candidate generation, new-base resolution, and returned results are bounded
across each discovery run. The returned ``DiscoveryResults`` object behaves as
a list and exposes ``truncated`` and ``limit_reasons`` attributes. These report whether a safety limit made results potentially
incomplete, without emitting a Python warning.

Calling ``get_masks()`` directly is a low-level interface with only the
per-path mask limit. Use ``discover()`` for run-wide resource bounds and
structured limit status.

.. code-block:: python

   from translation_finder.discovery.base import BaseDiscovery
   from translation_finder.discovery.result import DiscoveryCandidate


   class CustomDiscovery(BaseDiscovery):
       def get_masks(self, *, eager=False, hint=None):
           for path in self.filter_files():
               yield DiscoveryCandidate({"filemask": "locale/*.json"}, [path])

.. _Weblate: https://weblate.org/
