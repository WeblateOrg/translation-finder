#
# Copyright © 2012 - 2021 Michal Čihař <michal@cihar.com>
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
"""Translation finder, a module to locate translatable files in a filesystem."""

from importlib import import_module

from .api import discover
from .discovery.result import DiscoveryResult
from .finder import Finder

__all__ = ("Finder", "discover", "DiscoveryResult")

# Make sure all discovery modules are imported
import_module("translation_finder.discovery.transifex")
import_module("translation_finder.discovery.files")
