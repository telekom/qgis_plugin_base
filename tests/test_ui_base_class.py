# -*- coding: utf-8 -*-
# SPDX-FileCopyrightText: 2025 Deutsche Telekom Technik GmbH <f.vonstudsinske@telekom.de>
# SPDX-License-Identifier: GPL-3.0-only

from pathlib import Path

from ..ui.base_class import UiModuleBase


def test_get_tab_stops_from_ui_file():

    file = Path(__file__).parent / "test_ui_base_class.ui"
    tab_stops = UiModuleBase.get_tab_stops_from_ui_file(file.as_posix())
    assert tab_stops == ["But_A", "But_B", "But_C"]
