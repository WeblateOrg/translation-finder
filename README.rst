translation-finder
==================

A translation file finder for `Weblate`_, translation tool with tight version
control integration.

.. image:: https://travis-ci.com/WeblateOrg/translation-finder.svg?branch=master
    :target: https://travis-ci.com/WeblateOrg/translation-finder
    :alt: Build Status

.. image:: https://codecov.io/github/WeblateOrg/translation-finder/coverage.svg?branch=master
    :target: https://codecov.io/github/WeblateOrg/translation-finder?branch=master
    :alt: Code coverage

.. image:: https://img.shields.io/pypi/v/translation-finder.svg
    :target: https://pypi.org/project/translation-finder/
    :alt: PyPI package

This library is used by `Weblate`_ to discover translation files in a cloned
repository. It can operate on both file listings and actual filesystem.
Filesystem access is needed for more accurate detection in some cases
(detecting encoding or actual syntax of similar files).

Usage
-----

In can be used from Python:

.. code-block:: python

   >>> from translation_finder import discover
   >>> from pprint import pprint
   >>> results = discover('translation_finder/test_data/')
   >>> len(results)
   21
   >>> pprint(results[0].match)
   {'file_format': 'aresource',
    'filemask': 'app/src/res/main/values-*/strings.xml',
    'name': 'android',
    'template': 'app/src/res/main/values/strings.xml'}
   >>> pprint(results[10].match)
   {'file_format': 'po',
    'filemask': 'locales/*.po',
    'new_base': 'locales/messages.pot'}

Additional information about discovery can be obtained from meta attribute:

.. code-block:: python

   >>> pprint(results[0].meta)
   {'discovery': 'TransifexDiscovery', 'origin': 'Transifex', 'priority': 500}
   >>> pprint(results[10].meta)
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
