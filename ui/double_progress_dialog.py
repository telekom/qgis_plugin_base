# -*- coding: utf-8 -*-
# SPDX-FileCopyrightText: 2025 Deutsche Telekom Technik GmbH <f.vonstudsinske@telekom.de>
# SPDX-License-Identifier: GPL-3.0-or-later

from typing import Optional

from qgis.core import QgsApplication
from qgis.PyQt.QtWidgets import QProgressBar, QDialog, QWidget, QGridLayout, QSizePolicy, QLabel
from qgis.PyQt.QtCore import Qt


class DoubleProgressDialog(QDialog):
    """ Basic dialog with 2 progressbars to show a progress with a main and a sub progressbar.
        Does not require a (Ui)ModuleBase.

        .. code-block:: python

            dialog = DoubleProgressDialog(title="Nice title")
            dialog.main_bar.setValue(2)
            ...
    """

    def __init__(self, parent: Optional[QWidget] = None, title: str = ""):
        super(QDialog, self).__init__(parent)
        self.resize(480, 120)
        self.canceled = False

        self.setLayout(QGridLayout())
        self.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Maximum)
        self._widget = QWidget()
        self._widget.setLayout(QGridLayout())
        self._widget.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Maximum)
        self.layout().addWidget(self._widget)
        self.layout().setAlignment(self._widget, Qt.AlignTop)

        self.label_title = QLabel()
        self._widget.layout().addWidget(self.label_title)
        self.label_title.setText("")
        self.label_title.setWordWrap(True)

        self.main_label = QLabel()
        self._widget.layout().addWidget(self.main_label)

        self.main_bar = QProgressBar()
        self._widget.layout().addWidget(self.main_bar)
        self.main_bar.setFormat("%p% (%v / %m)")

        self.sub_label = QLabel()
        self._widget.layout().addWidget(self.sub_label)

        self.sub_bar = QProgressBar()
        self._widget.layout().addWidget(self.sub_bar)
        self.sub_bar.setFormat("%p% (%v / %m)")

        for widget in self._widget.findChildren(QWidget):
            self._widget.layout().setAlignment(widget, Qt.AlignTop)

        self.main_bar.valueChanged.connect(self._process_events)
        self.sub_bar.valueChanged.connect(self._process_events)

        self.setWindowModality(Qt.ApplicationModal)
        self.setWindowTitle(title)

    def _process_events(self, value: int):
        QgsApplication.instance().processEvents()

    def reject(self):
        self._cancel()

    def _cancel(self, *args):
        self.canceled = True

    def is_canceled(self) -> bool:
        return self.canceled

    def change_progress(self, current: int, max_: int, text: Optional[str] = None):
        if text is not None:
            self.main_label.setText(text)

        if self.main_bar.maximum() != max_:
            self.main_bar.setValue(0)
            self.main_bar.setMaximum(max_)

        self.main_bar.setValue(current)

    def change_sub_progress(self, current: int, max_: int, text: Optional[str] = None):
        if text is not None:
            self.sub_label.setText(text)

        if self.sub_bar.maximum() != max_:
            self.sub_bar.setValue(0)
            self.sub_bar.setMaximum(max_)

        self.sub_bar.setValue(current)
