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
"""Finder data."""


LANGUAGES_BLACKLIST = {
    # Clash with file formats
    "po",
    "ts",
    "tr",
    # Common names clashing with language codes
    "gl",
    "as",
    "is",
    "to",
    "my",
    "eg",
    "id",
    "in",
    "or",
    "if",
    "bi",
    "sa",
    "pr",
    "lt",
    "io",
    "no",
    "pi",
    "fa",
    "ss",
    "arg",
    "ext",
    "div",
    "fur",
    "nor",
    "bar",
    "cat",
    "cop",
    "cos",
    "hit",
    "new",
    "sin",
    "gun",
    "run",
    "sai",
    "sus",
    "nav",
    "per",
    "wol",
    "mac",
    "ter",
    "base",
    "source",
    "zen",
}
