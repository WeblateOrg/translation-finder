.. image:: https://s.weblate.org/cdn/Logo-Darktext-borders.png
   :alt: Weblate
   :target: https://weblate.org/
   :height: 80px

**Weblate is libre software web-based continuous localization system,
used by over 2500 libre projects and companies in more than 165 countries.**

A translation file finder for `Weblate`_, translation tool with tight version
control integration.

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

This library is used by `Weblate`_ to discover translation files in a cloned
repository. It can operate on both file listings and actual filesystem.
Filesystem access is needed for more accurate detection in some cases
(detecting encoding or actual syntax of similar files).

Usage
-----

In can be used from Python:

.. code-block:: pycon

   >>> from translation_finder import discover
   >>> from pprint import pprint
   >>> results = discover("translation_finder/test_data/")
   >>> len(results)
   30
   >>> pprint(results[0].match)
   {'file_format': 'aresource',
    'filemask': 'app/src/res/main/values-*/strings.xml',
    'name': 'android',
    'template': 'app/src/res/main/values/strings.xml'}
   >>> pprint(results[16].match)
   {'file_format': 'po',
    'filemask': 'locales/*.po',
    'new_base': 'locales/messages.pot'}

Additional information about discovery can be obtained from meta attribute:

.. code-block:: pycon

   >>> pprint(results[0].meta)
   {'discovery': 'TransifexDiscovery', 'origin': 'Transifex', 'priority': 500}
   >>> pprint(results[16].meta)
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

.. _Weblate: https://weblate.org/
