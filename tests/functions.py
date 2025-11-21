# -*- coding: utf-8 -*-
# SPDX-FileCopyrightText: 2025 Deutsche Telekom Technik GmbH <f.vonstudsinske@telekom.de>
# SPDX-License-Identifier: GPL-3.0-or-later

import os

from qgis.core import QgsApplication, QgsProject
from pathlib import Path

from ..qgis.qgis_env import activate_processing, setup_qgis


def new_qgis_project():
    """

        1. Starts a QgsApplication, if not active yet
        2. Activates the processing plugin and loads the processing algorithms
        3. Create an empty QgsProject
        4. <time for the test>
        5. Clear the QgsProject

        Uses the OS environment variable "QGIS_PYTEST_AUTHENTICATION_CONFIG_DIR"
        to load QGIS XML authentication files. The OS variable is optional to load configs from.

    """

    # read the path for several credentials to load per test
    credentials_path = os.environ.get("QGIS_PYTEST_AUTHENTICATION_CONFIG_DIR")
    if credentials_path:
        credentials_path = Path(credentials_path)

    if QgsApplication.instance() is None:
        # create instance
        setup_qgis(credentials_path)
    activate_processing()

    # on test start
    QgsProject.instance().clear()

    # running the test
    yield

    # on test end
    QgsProject.instance().clear()
