# -*- coding: utf-8 -*-
# SPDX-FileCopyrightText: 2025 Deutsche Telekom Technik GmbH <f.vonstudsinske@telekom.de>
# SPDX-License-Identifier: GPL-3.0-or-later

from typing import List

from qgis.PyQt.QtCore import pyqtSignal, Qt
from qgis.PyQt.QtWidgets import (QDialog, QLabel, QProgressBar, QWidget)

from .progressbar_extended import DoubleProgressGroup
from .base_class import UiModuleBase
from ..constants import STYLE_SHEET_NEUTRAL

FORM_CLASS, _ = UiModuleBase.get_uic_classes(__file__)


class BlockingProgressBar(UiModuleBase, QDialog, FORM_CLASS):
    """dialog for display of data in QTableWidget"""
    aborted = pyqtSignal(name="aborted")

    def __init__(self,
                 **kwargs):
        """can be used to open blocking progressbar, can not be closed till finished, blocking QGIS
        """
        super().__init__(**kwargs)
        QDialog.__init__(self, kwargs.get("parent"))
        self.setupUi(self)

        # prevent user from closing, dragging, resizing
        self.setWindowFlag(Qt.Dialog, True)
        self.setWindowFlag(Qt.FramelessWindowHint, True)
        self.setFixedSize(self.size())
        # sets window to foreground, so qgis is blocked
        self.setWindowModality(Qt.WindowModal)

        # link double progressbar for tracking / visual representation
        self.Widget_DoubleProgressBar = self.add_ui_module("DoubleProgressGroup", self.Widget_DoubleProgressBar, DoubleProgressGroup)

    def set_text_main(self, text: str, style: str = STYLE_SHEET_NEUTRAL) -> None:
        """ Set the text for main label.

            :param text: Labels text
            :param style: Stylesheet string, e.g. text color
        """
        self.Widget_DoubleProgressBar.set_text_main(text, style)

    def set_text_single(self, text: str, style: str = STYLE_SHEET_NEUTRAL) -> None:
        """ Setzt Text auf QLabel und setzt Textfarbe.

            :param text: text to show
            :param style: Stylesheet string, e.g. text color
        """
        self.Widget_DoubleProgressBar.set_text_single(text, style)

    def get_mainbar(self) -> QProgressBar:
        """ Returns main progressbar """
        return self.Widget_DoubleProgressBar.get_mainbar()

    def get_mainlabel(self) -> QLabel:
        """ Returns main text label """
        return self.Widget_DoubleProgressBar.get_mainlabel()

    def get_subbar(self) -> QProgressBar:
        """ Returns sub progressbar """
        return self.Widget_DoubleProgressBar.get_subbar()

    def get_sublabel(self) -> QLabel:
        """ Returns sub text label """
        return self.Widget_DoubleProgressBar.get_sublabel()

    def cancel(self) -> None:
        """ Save cancele state. Call `obj.canceled()` to check cancel state.

            :raises: InterruptedError: main progress canceled
        """
        self.Widget_DoubleProgressBar.cancel()
        self.close()

    def canceled(self) -> bool:
        """ Returns True, if user clicked on "Cancel" """
        return self.Widget_DoubleProgressBar.canceled()

    def restore(self, close_window: bool = True) -> None:
        """ Restores ui and auto-restore attribute closes window if not given False as parameter
        :param close_window: bool if window should be closed or progress only be reset
        """
        self.Widget_DoubleProgressBar.restore()
        if (close_window):
            self.close()

    def add_main(self, value: int = 1) -> None:
        """ Adds value on main bar.

            :param value: Value to add on current progress value state.
        """
        if (self.canceled()):
            self.cancel()
        else:
            self.Widget_DoubleProgressBar.add_main(value)

    def add_sub(self, value: int = 1) -> None:
        """ Adds value on sub bar.

            :param value: Value to add on current progress value state.
        """
        if (self.canceled()):
            self.cancel()
        else:
            self.Widget_DoubleProgressBar.add_sub(value)

    def reset_sub_bar(self, min_: int, max_: int, value: int = 0):
        self.Widget_DoubleProgressBar.reset_sub_bar(min_, max_, value)

    def reset_main_bar(self, min_: int, max_: int, value: int = 0):
        self.Widget_DoubleProgressBar.reset_main_bar(min_, max_, value)

    def start_progressbars(self, minimum: int, maximum: int, hide_widgets: List[QWidget] = [],
                           can_cancel: bool = False, use_subbar: bool = True,
                           bar_format: str = "%p % (%v / %m)",
                           auto_restore: bool = True) -> tuple:
        """ Initialize main bar and hide widgets in `hide_widgets`.

            :param minimum: minimum progress value for main progressbar
            :param maximum: maximum progress value for main progressbar
            :param hide_widgets: maximum progress value for main progressbar
            :param can_cancel: Is progress cancelable?
            :param bar_format: text format for main progressbar
            :param use_subbar: show second/sub bar
            :param auto_restore: auto reset progressbars,
                                 when main bar reached maximum (on reset set back to True)

            :return: Returns tuple with main progressbar (at 0) and main label (at 1)
        """
        self.show()
        return self.Widget_DoubleProgressBar.start_progressbars(minimum, maximum, hide_widgets,
                                                   can_cancel, use_subbar, bar_format,
                                                   auto_restore)

    def reject(self):
        """prevent ESC key of user closing window"""
        return

    def closeEvent(self, event):
        """cleanup before closing"""
        self.aborted.emit()
        self.unload(True)
        event.accept()

    @property
    def progressBar(self):
        return self.Widget_DoubleProgressBar

    def unload(self, self_unload: bool = False):
        super().unload(self_unload)
