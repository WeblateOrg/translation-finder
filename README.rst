translation-finder
==================

`Weblate`_ translation finder in a directory.

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
repository.

Usage
-----

In can be used from Python:

.. code-block:: python

   >>> from translation_finder import discover
   >>> discover('.')
   [
       {
           "filemask": "locales/*/messages.po",
           "file_format": "po",
           "template": None,
       },
       {
           "filemask": "app/src/res/main/values-*/strings.xml",
           "file_format": "aresource",
           "template": "app/src/res/main/values/strings.xml",
       }
   ]

Or command line:

.. code-block:: console

   $ weblate-discovery translation_finder/test_data/
   == Match 1 ==
   file_format    : po
   filemask       : locales/*.po

   == Match 2 ==
   file_format    : aresource
   filemask       : app/src/res/main/values-*/strings.xml
   template       : app/src/res/main/values/strings.xml

.. _Weblate: https://weblate.org/
