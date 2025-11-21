# -*- coding: utf-8 -*-
# SPDX-FileCopyrightText: 2025 Deutsche Telekom Technik GmbH <f.vonstudsinske@telekom.de>
# SPDX-License-Identifier: GPL-3.0-or-later

"""
Small tests to test the expected behavior from Python in QGIS e.g., test the set "sys.path" path order
"""

import site
import sys

from pathlib import Path

from .markers import skipif_no_win32


@skipif_no_win32
def test_sys_path():
    # test the expected sys path order
    # users's site-packages path must be always before the Python's site-package path in the sys.path list

    # resolve the given paths
    paths = [Path(path).resolve() for path in sys.path]

    user_site = Path(site.USER_SITE).resolve()

    index_user_site = paths.index(user_site)

    # get the expected site-packages path from the Python installation
    for path in site.getsitepackages():
        if path.endswith("site-packages") and Path(path) != user_site:
            py_site_packages = Path(path).resolve()
            break
    else:
        # e.g., "Python312\\Lib\\site-packages" not found
        raise ValueError("Python site-packages not found")

    index_py_site = paths.index(py_site_packages)

    # the user's site path must have a lower index than the Python's site path
    #   -> import order, prefer from user's site path
    assert index_user_site < index_py_site



