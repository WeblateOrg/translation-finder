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
"""Simple charset detection."""

from codecs import BOM_UTF8, BOM_UTF16_BE, BOM_UTF16_LE
from typing import Optional

BOM_MAP = (
    (BOM_UTF8, "utf-8"),
    (BOM_UTF16_BE, "utf-16"),
    (BOM_UTF16_LE, "utf-16"),
)

DECODES = (("ascii", None), ("utf-8", "utf-8"))


def detect_charset(text: bytes) -> Optional[str]:
    """Simplified charset detection."""
    # Detect based on BOM
    for prefix, charset in BOM_MAP:
        if text.startswith(prefix):
            return charset

    # Try decoding some charsets
    for decode, charset in DECODES:
        try:
            text.decode(decode)
            return charset
        except UnicodeDecodeError:
            continue

    return None
