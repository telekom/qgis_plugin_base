# -*- coding: utf-8 -*-
# SPDX-FileCopyrightText: 2025 Deutsche Telekom Technik GmbH <f.vonstudsinske@telekom.de>
# SPDX-License-Identifier: GPL-3.0-or-later

import re

from dataclasses import dataclass
from pkg_resources import packaging
from typing import Optional
from xml.sax.saxutils import escape


FILE_ENDINGS_PY_TO_UI = (".py", ".cp39-win_amd64.pyd", ".cp312-win_amd64.pyd")
FILE_ENDINGS_RE_PATTERN = "|".join(map(escape, FILE_ENDINGS_PY_TO_UI))
FILE_ENDINGS_RE_COMPILED = re.compile(FILE_ENDINGS_RE_PATTERN)

UPDATE_HINT_COMPILED = """
<ol>
<li>QGIS-Erweiterung '{NAME}' in der Erweiterungsliste deaktivieren</li>
<li>Alle QGIS-Fenster schließen</li>
<li>QGIS starten</li>
<li>QGIS-Erweiterungen öffnen<ol>
<li><strong>Nur</strong> die Pluginzeile wählen, <strong>nicht</strong> aktivieren</li>
<li>Plugin aktualisieren</li>
<li>Plugin aktivieren / Haken setzen</li>
</ol>
</li>
</ol>
"""


# geometry handling
N_NONE = 0 # no neighbor
N_LEFT = 1 # falls line2 ein linker Nachbar von line1 ist (d.h. der Endpunkt von line2 berührt den Anfangspunkt von Line1)
N_RIGHT = 2 # falls line2 ein rechter Nachbar von line1 ist (d.h. der Anfangspunkt von line2 berührt den Endpunkt von Line1)
N_LEFT_REVERSED = 3 # falls line2.reverse() ein linker Nachbar von line1 ist (d.h. der Anfangspunkt von line2 berührt den Anfangspunkt
N_RIGHT_REVERSED = 4 # falls line2.reverse() ein rechter Nachbar von line1 ist (d.h. der Endpunkt von line2 berührt den Endpunkt von

# tolerances
EPSILON = 0.000001  # default
EPSILON_GEOGRAPHIC = 0.00001  # sometimes recommended for EPSG:4326 or other cases
EPSILON_METRES = 0.03  # Angabe in Meter
TO_STRING_PREC = 4  # QgsPointXY.toString(TO_STRING)

# Buffer Radius von Objekten in Meter (Kartesisch)
RADIUS_BUFFER = 4000

# URI Location
URI_OS = 0  # local file or on network drive
URI_WEB = 1  # web url
URI_ERROR = 2  # lol

# REGEX
RE_DATECHANGE = r'\d{1,2}\.\d{1,2}\.\d{1,4}( \d{2}:\d{2})?'  # "12.12.2020" oder "12.12.2020 23:60"

# default processing names needed in most use cases
DEFAULT_ALGORITHM_NAMES = [
    "qgis:snapgeometries",
    "native:selectbylocation",
    "native:multiparttosingleparts",
    "native:fixgeometries",
    "native:simplifygeometries",
    "native:splitwithlines",
    "native:removeduplicatevertices",
    "qgis:extractspecificvertices",
    "native:shortestpathpointtopoint",
]


@dataclass
class VersionInfo:
    version: packaging.version.Version
    version_str: str
    commit: str
    qgis_minimum_version: Optional[packaging.version.Version]
    qgis_maximum_version: Optional[packaging.version.Version]


@dataclass
class VersionError:
    error: str

# pyqt
STYLE_SHEET_ERROR = "font-weight: bold; color: rgb(255, 0, 0);"
STYLE_SHEET_WARNING = "font-weight: bold; color: rgb(255, 150, 0);"
STYLE_SHEET_SUCCESS = "font-weight: bold; color: rgb(0, 125, 0);"
STYLE_SHEET_NEUTRAL = "font-weight: bold; color: rgb(0, 0, 0);"

STYLE_SHEET_EDIT_ERROR = "QLineEdit { background: rgb(255, 0, 0, 60);}"
STYLE_SHEET_EDIT_WARNING = "QLineEdit { background: rgb(255, 150, 0, 60);}"
STYLE_SHEET_EDIT_NEUTRAL = ""

STYLE_SHEET_SPIN_ERROR = "QSpinBox { background: rgb(255, 0, 0, 60);}"
STYLE_SHEET_SPIN_NEUTRAL = ""

STYLE_SHEET_COMBO_ERROR = "QComboBox { background: rgb(255, 0, 0, 60);}"
STYLE_SHEET_COMBO_WARNING = "QComboBox { background: rgb(255, 150, 60);}"
STYLE_SHEET_COMBO_NEUTRAL = ""

# accessibility
ACCESSIBILITY_DEFAULT_COLOR = '190,0,90'
