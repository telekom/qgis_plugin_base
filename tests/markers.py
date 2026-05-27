# -*- coding: utf-8 -*-
# SPDX-FileCopyrightText: 2025 Deutsche Telekom Technik GmbH <f.vonstudsinske@telekom.de>
# SPDX-License-Identifier: GPL-3.0-only

import pytest
import sys


skipif_no_python_exe = pytest.mark.skipif(not sys.executable.endswith('python.exe') or not sys.platform == "win32",
                                          reason=f"Aktuelle Python-Executable ist nicht Python.exe ({sys.executable=})")
""" Skip test if the main executable is not python.exe (on Windows). Skip if not Windows.
Usage: @skipif_no_python_exe
"""


skipif_no_qgis_app = pytest.mark.skipif(not sys.executable.endswith(('qgis-ltr-bin.exe', 'qgis-ltr-dev-bin.exe'))
                                        or not sys.platform == "win32",
                                        reason=f"Aktuelle Python-Executable ist nicht QGIS(.EXE) ({sys.executable=})")
""" Skip test if the main executable is not the QGIS.exe (on Windows). Skip if not Windows.
Usage: @skipif_no_qgis_app
"""


skipif_no_win32 = pytest.mark.skipif(sys.platform != "win32",
                                     reason=f"Tst kann nur auf Plattform win32 ausgeführt werden.")
""" Skip if not Windows.
Usage: @skipif_no_win32
"""
