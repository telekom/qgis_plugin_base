# -*- coding: utf-8 -*-
# SPDX-FileCopyrightText: 2025 Deutsche Telekom Technik GmbH <f.vonstudsinske@telekom.de>
# SPDX-License-Identifier: GPL-3.0-only
""" Test UI and plugin path utility functions. """

import os

from pathlib import Path

from .fixtures import plugin_qgis_new_project
from ..ui.functions import is_installed_in_qgis_plugin_folder


def test_is_installed_in_qgis_plugin_folder_os_environ_qgis_plugins(plugin_qgis_new_project):
    """ Test the plugin-folder lookup with a temporary QGIS_PLUGINPATH. """
    current_os_environ = os.environ.get("QGIS_PLUGINPATH", None)
    os.environ["QGIS_PLUGINPATH"] = Path(__file__).parent.parent.parent.parent.parent.as_posix()

    try:
        assert is_installed_in_qgis_plugin_folder()
    finally:
        if current_os_environ is not None:
            os.environ["QGIS_PLUGINPATH"] = current_os_environ
        else:
            os.environ.pop("QGIS_PLUGINPATH", None)
