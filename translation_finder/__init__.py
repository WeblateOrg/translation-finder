# Copyright © Michal Čihař <michal@weblate.org>
#
# SPDX-License-Identifier: GPL-3.0-or-later

"""Translation finder, a module to locate translatable files in a filesystem."""

from importlib import import_module

from .api import discover
from .discovery.result import DiscoveryResult
from .finder import Finder

__all__ = ("DiscoveryResult", "Finder", "discover")

# Make sure all discovery modules are imported
import_module("translation_finder.discovery.transifex")
import_module("translation_finder.discovery.files")
