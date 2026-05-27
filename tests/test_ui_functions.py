# -*- coding: utf-8 -*-
# SPDX-FileCopyrightText: 2025 Deutsche Telekom Technik GmbH <f.vonstudsinske@telekom.de>
# SPDX-License-Identifier: GPL-3.0-only

import os

from pathlib import Path

from qgis.PyQt.QtWidgets import QDialog

from .fixtures import plugin_qgis_new_project
from ..ui.functions import get_ui_class, is_installed_in_qgis_plugin_folder


def test_get_compiled_uic_classes():

    file = Path(__file__).parent / "test_ui_base_class.ui"
    widget_type = get_ui_class(file.as_posix())
    assert widget_type == QDialog


def test_is_installed_in_qgis_plugin_folder_os_environ_qgis_plugins(plugin_qgis_new_project):

    # store temp os plugin path variable
    current_os_environ = os.environ.get("QGIS_PLUGINPATH", None)

    # set temp variable to the parent folder of this plugin
    os.environ["QGIS_PLUGINPATH"] = Path(__file__).parent.parent.parent.parent.parent.as_posix()

    assert is_installed_in_qgis_plugin_folder()

    # restore temp variable
    if current_os_environ is not None:
        os.environ["QGIS_PLUGINPATH"] = current_os_environ
    else:
        # remove previous set test variable
        del os.environ["QGIS_PLUGINPATH"]