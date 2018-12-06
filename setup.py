#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# Copyright © 2018 Michal Čihař <michal@cihar.com>
#
# This file is part of Weblate translation-finder
# <https://github.com/WeblateOrg/translation-finder>
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.
#
"""Setup file for easy installation."""
from __future__ import unicode_literals
import os
import sys
from setuptools import setup, find_packages

VERSION = __import__("translation_finder").__version__

with open(os.path.join(os.path.dirname(__file__), "README.rst")) as readme:
    LONG_DESCRIPTION = readme.read()

REQUIRES = [
    line.split(";")[0]
    for line in open("requirements.txt").read().splitlines()
    if "python_version" not in line or sys.version_info < (3, 4)
]
REQUIRES_TEST = open("requirements-test.txt").read().splitlines()[1:]

setup(
    name="translation-finder",
    version=VERSION,
    author="Michal Čihař",
    author_email="michal@cihar.com",
    description="A translation file finder for Weblate, translation tool with tight version control integration",
    license="GPLv3+",
    keywords="i18n l10n gettext translate",
    url="https://weblate.org/",
    download_url="https://github.com/WeblateOrg/translation-finder",
    project_urls={
        "Issue Tracker": "https://github.com/WeblateOrg/translation-finder/issues",
        "Documentation": "https://docs.weblate.org/",
        "Source Code": "https://github.com/WeblateOrg/translation-finder",
        "Twitter": "https://twitter.com/WeblateOrg",
    },
    platforms=["any"],
    packages=find_packages(),
    long_description=LONG_DESCRIPTION,
    install_requires=REQUIRES,
    classifiers=[
        "Development Status :: 4 - Beta",
        "Topic :: Software Development :: Internationalization",
        "Topic :: Software Development :: Localization",
        "Topic :: Utilities",
        "License :: OSI Approved :: " "GNU General Public License v3 or later (GPLv3+)",
        "Operating System :: OS Independent",
        "Intended Audience :: Developers",
        "Programming Language :: Python",
        "Programming Language :: Python :: 2.7",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.2",
        "Programming Language :: Python :: 3.3",
        "Programming Language :: Python :: 3.4",
        "Programming Language :: Python :: 3.5",
    ],
    setup_requires=["pytest-runner"],
    tests_require=REQUIRES_TEST,
    entry_points={"console_scripts": ["weblate-discover = translation_finder.api:cli"]},
)
