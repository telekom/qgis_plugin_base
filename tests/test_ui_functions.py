# -*- coding: utf-8 -*-
# SPDX-FileCopyrightText: 2025 Deutsche Telekom Technik GmbH <f.vonstudsinske@telekom.de>
# SPDX-License-Identifier: GPL-3.0-only

from pathlib import Path

from qgis.PyQt.QtWidgets import QDialog

from ..ui.functions import get_ui_class


def test_get_compiled_uic_classes():

    file = Path(__file__).parent / "test_ui_base_class.ui"
    widget_type = get_ui_class(file.as_posix())
    assert widget_type == QDialog
