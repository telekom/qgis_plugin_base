# -*- coding: utf-8 -*-
# SPDX-FileCopyrightText: 2025 Deutsche Telekom Technik GmbH <f.vonstudsinske@telekom.de>
# SPDX-License-Identifier: GPL-3.0-only

from qgis.PyQt.QtWidgets import (QDialog, QLabel, QProgressBar, QWidget, QStyleFactory)
from qgis.PyQt.QtCore import QCoreApplication
from typing import List

from .base_class import UiModuleBase
from ..constants import STYLE_SHEET_NEUTRAL

FORM_CLASS, _ = UiModuleBase.get_uic_classes(__file__)


class DoubleProgressGroup(UiModuleBase, QDialog, FORM_CLASS):
    """ Progress container with two progress bars.
        Progress container restores gui after main bar reached 100 %.
        Finishing sub bar will not trigger main bar!

        You have to restore the ui `obj.restore()`!

        :param parent: QWidget as parent
        :param name: Module name
    """

    def __init__(self, *args, **kwargs: dict):
        QDialog.__init__(self, kwargs.get('parent', None))
        UiModuleBase.__init__(self, *args, **kwargs)
        self.setupUi(self)

        if "windowsvista" in QStyleFactory.keys():
            self.setStyle(QStyleFactory.create('windowsvista'))

        self.progress_active = False
        self._auto_restore = True

        # gui connections
        self.Progress_All.valueChanged.connect(self._value_changed_main)
        self.Progress_Single.valueChanged.connect(self._value_changed_sub)
        self.But_Cancel.clicked.connect(self.cancel)

        # on setup call, this list will contain the widgets to hide
        self.hidden_widgets = []

        # has been canceled?
        self._canceled = False

        self.restore()

        self.tab_order_widgets = self.get_tab_stop_widgets(self.get_tab_stops_from_ui_file(__file__))

    def set_text_main(self, text: str, style: str = STYLE_SHEET_NEUTRAL) -> None:
        """ Set the text for main label.

            :param text: Labels text
            :param style: Stylesheet string, e.g. text color
        """
        self._set_label_status(self.Label_Progress_All, text, style)

    def set_text_single(self, text: str, style: str = STYLE_SHEET_NEUTRAL) -> None:
        """ Setzt Text auf QLabel und setzt Textfarbe.

            :param text: text to show
            :param style: Stylesheet string, e.g. text color
        """
        self._set_label_status(self.Label_Progress_Single, text, style)

    def _set_label_status(self, label: QLabel, text: str, style: str = STYLE_SHEET_NEUTRAL) -> None:
        """ Set the text and css stylesheet on label.

            :param text: Labels text
            :param style: Stylesheet string, e.g. text color
        """
        label.setText(text)
        if not text:
            label.hide()
            return

        label.setStyleSheet(style)
        label.show()
        self.log(f"{label.objectName()}:: {text}", level=self.DEBUG)

    def _value_changed_main(self, pos: int) -> None:
        """ Handles hiding and restoring """
        if not self.progress_active: return
        QCoreApplication.processEvents()

        try:
            if pos >= self.get_mainbar().maximum() and self._auto_restore:
                # Maximum der Progressbar erreicht.
                # Stelle Standard wieder her
                self.restore()
            else:
                # Progress noch im Gange. Verstecke Sachen.

                for widget in self.hidden_widgets:
                    widget.hide()
                self.Group_Progress.show()
        except RuntimeError:
            ...

    def _value_changed_sub(self, pos: int) -> None:
        """ Does nothing """
        if not self.progress_active: return
        QCoreApplication.processEvents()

    def get_mainbar(self) -> QProgressBar:
        """ Returns main progressbar """
        return self.Progress_All

    def get_mainlabel(self) -> QLabel:
        """ Returns main text label """
        return self.Label_Progress_All

    def get_subbar(self) -> QProgressBar:
        """ Returns sub progressbar """
        return self.Progress_Single

    def get_sublabel(self) -> QLabel:
        """ Returns sub text label """
        return self.Label_Progress_Single

    def cancel(self) -> None:
        """ Save cancele state. Call `obj.canceled()` to check cancel state.

            :raises: InterruptedError: main progress canceled
        """
        self._canceled = True
        self.add_main(-1)

    def canceled(self) -> bool:
        """ Returns True, if user clicked on "Cancel" """
        return self._canceled

    def restore(self) -> None:
        """ Restores ui and auto-restore attribute"""
        if self.unloaded:
            # already unloaded, nothing to restore
            # prevents RuntimeError
            return

        self._auto_restore = True
        self.get_mainbar().setValue(0)
        self.get_mainbar().setMaximum(100)

        self.get_subbar().setValue(0)
        self.get_subbar().setMaximum(100)

        self.Group_Progress.hide()

        for widget in self.hidden_widgets:
            widget.show()
        self.hidden_widgets.clear()
        self._canceled = False
        self.progress_active = False

    def add_main(self, value: int = 1) -> None:
        """ Adds value on main bar.

            :param value: Value to add on current progress value state.
        """
        self._add(self.get_mainbar(), value)

    def add_sub(self, value: int = 1) -> None:
        """ Adds value on sub bar.

            :param value: Value to add on current progress value state.
        """
        # print("add", value)
        self._add(self.get_subbar(), value)

    def _add(self, bar: QProgressBar, value: int) -> None:
        """ Add progress value by the given value to add.

            :param bar: progress bar
            :param value: Value to increase. Given float will be converted to int with `int(value)`
        """
        bar.setValue(bar.value() + int(value))

    @staticmethod
    def _reset_bar(bar: QProgressBar, min_: int, max_: int, value: int = 0):
        """ Resets the progress min and max values and the current progress value.

            :param bar: progressbar to reset
            :param min_: Minimum value to set on the progressbar.
                         Given float will be converted to int with `int(min_)`.
            :param max_: Maximum value to set on the progressbar.
                         Given float will be converted to int with `int(max_)`.
            :param value: Value to set on the progressbar.
                          Given float will be converted to int with `int(value)`.
        """
        bar.setValue(int(value))
        bar.setMinimum(int(min_))
        bar.setMaximum(int(max_))

    def reset_sub_bar(self, min_: int, max_: int, value: int = 0):
        self._reset_bar(self.get_subbar(), min_, max_, value)

    def reset_main_bar(self, min_: int, max_: int, value: int = 0):
        self._reset_bar(self.get_mainbar(), min_, max_, value)

    def start_progressbars(self, minimum: int, maximum: int, hide_widgets: List[QWidget],
                           can_cancel: bool = False, use_subbar: bool = True,
                           bar_format: str = "%p % (%v / %m)",
                           auto_restore: bool = True) -> tuple:
        """ Initialize main bar and hide widgets in `hide_widgets`.

            :param minimum: minimum progress value for main progressbar (given float will be converted to int)
            :param maximum: maximum progress value for main progressbar (given float will be converted to int)
            :param hide_widgets: maximum progress value for main progressbar
            :param can_cancel: Is progress cancelable?
            :param bar_format: text format for main progressbar
            :param use_subbar: show second/sub bar
            :param auto_restore: auto reset progressbars,
                                 when main bar reached maximum (on reset set back to True)

            :return: Returns tuple with main progressbar (at 0) and main label (at 1)
        """

        if self.progress_active:
            raise ValueError("Progressbar already active")

        self.progress_active = True
        self._auto_restore = auto_restore

        self.get_mainbar().setValue(0)
        self.get_mainbar().setMinimum(int(minimum))
        self.get_mainbar().setMaximum(int(maximum))
        self.get_mainbar().setFormat(bar_format)

        if can_cancel:
            self.But_Cancel.show()
        else:
            self.But_Cancel.hide()

        for widget in hide_widgets:
            widget.hide()
            self.hidden_widgets.append(widget)

        self.Group_Progress.show()
        if not use_subbar:
            self.get_subbar().hide()
            self.get_sublabel().hide()
        else:
            self.get_subbar().show()
            self.get_sublabel().show()

        return self.get_mainbar(), self.get_mainlabel()

    def closeEvent(self, event) -> None:
        event.accept()
        self.unload(True)

    def unload(self, self_unload: bool = False):
        """ Module will be unloaded """
        self.cancel()

        self.setParent(None)
        self.close()

        super().unload(self_unload)
