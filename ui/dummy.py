# -*- coding: utf-8 -*-
# SPDX-FileCopyrightText: 2025 Deutsche Telekom Technik GmbH <f.vonstudsinske@telekom.de>
# SPDX-License-Identifier: GPL-3.0-or-later

from qgis.PyQt.QtWidgets import QMainWindow

from .base_class import UiModuleBase


FORM_CLASS, _ = UiModuleBase.get_uic_classes(__file__)
FORM_CLASS: 'Ui'
try:
    from .dummy_generated_ui import Ui as FORM_CLASS

except ModuleNotFoundError:
    pass


class ModuleDummy(UiModuleBase, QMainWindow, FORM_CLASS):

    def __init__(self, *args, **kwargs: dict):
        UiModuleBase.__init__(self, *args, **kwargs)
        QMainWindow.__init__(self, kwargs.get('parent', None))
        self.setupUi(self)

    def set_text(self, text: str):
        self.Lab_Status.setText(text)
