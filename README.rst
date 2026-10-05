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

In can be used from Python:

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

.. _Weblate: https://weblate.org/
