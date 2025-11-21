# -*- coding: utf-8 -*-
# SPDX-FileCopyrightText: 2025 Deutsche Telekom Technik GmbH <f.vonstudsinske@telekom.de>
# SPDX-License-Identifier: GPL-3.0-or-later

import pytest

from qgis.core import QgsProject


@pytest.fixture(autouse=True)
def cleanup_qgs_project():
    # clears the current QgsProject.instance before running single test
    QgsProject.instance().clear()
    yield
    # clears the current QgsProject.instance before jumping to the next test
    QgsProject.instance().clear()
