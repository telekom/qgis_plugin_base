# -*- coding: utf-8 -*-
# SPDX-FileCopyrightText: 2025 Deutsche Telekom Technik GmbH <f.vonstudsinske@telekom.de>
# SPDX-License-Identifier: GPL-3.0-or-later

from qgis.PyQt.QtCore import pyqtSignal, Qt
from qgis.PyQt.QtGui import QHideEvent
from qgis.PyQt.QtWidgets import (QFrame, QGridLayout, QScrollArea,
                                 QWidget)
from qgis.gui import QgsDockWidget

from .base_class import UiModuleBase


class DockWidgetModuleBase(UiModuleBase, QgsDockWidget):
    """ Base class for a QTabWidget.

        Do not use following methods from outside this class:
            - `insertTab`
            - `removeTab`
        Use instead:
            - `insert_module_tab`
    """
    # True=visible, False=not visible
    widgetVisibilityChanged = pyqtSignal(bool, name="widgetVisibilityChanged")

    def __init__(self, **kwargs: dict):
        UiModuleBase.__init__(self, **kwargs)
        if hasattr(kwargs, 'parent'):
            if hasattr(kwargs['parent'], 'plugin_name'):
                QgsDockWidget.__init__(self, kwargs['parent']['plugin_name'])
        else:
            QgsDockWidget.__init__(self)

        self._load_empty_frame = False

        # layout options
        # keep this order of new objects, layout references etc. in mind!
        dock_layout = QGridLayout()
        dock_layout.setContentsMargins(0, 0, 0, 0)
        dock_layout.setAlignment(Qt.AlignTop)
        self.setWidget(QWidget(self))
        self.widget().setLayout(dock_layout)

        # setup default scroll area
        self.scroll_area = QScrollArea()
        dock_layout.addWidget(self.scroll_area)
        self.scroll_area.setFrameShape(QFrame.NoFrame)
        self.scroll_area.setWidgetResizable(True)

        # scroll area widget layout
        area_widget_layout = QGridLayout()
        area_widget_layout.setContentsMargins(0, 0, 0, 0)
        area_widget_layout.setAlignment(Qt.AlignTop)
        self.scroll_area.setLayout(area_widget_layout)
        area_widget = QWidget()
        self.scroll_area.setWidget(area_widget)

        scroll_area_widget_layout = QGridLayout()
        scroll_area_widget_layout.setContentsMargins(0, 0, 0, 0)
        scroll_area_widget_layout.setAlignment(Qt.AlignTop)
        area_widget.setLayout(scroll_area_widget_layout)

        self.scroll_area.show()
        area_widget.show()

        self.scroll_area.widget().layout().setAlignment(Qt.AlignTop)

    def load_empty_frame(self, object_name: str = 'Frame') -> QFrame:
        """ Can only called once.
            Can be accessed with `self.Frame`
        """
        if self._load_empty_frame:
            raise ValueError("load_empty_frame already called")

        self._load_empty_frame = True

        layout = self.scroll_area.widget().layout()
        frame = self._create_frame(layout, object_name)

        return frame

    def unload(self, self_unload: bool = False):
        """ will be called, when module will be unloaded

            :param self_unload: only self unload, defaults to False
        """
        if self.parent():
            self.parent().removeDockWidget(self)

        super().unload(self_unload)

    def hideEvent(self, event: QHideEvent):
        event.accept()
        self.widgetVisibilityChanged.emit(False)

    def showEvent(self, event: QHideEvent):
        event.accept()
        self.widgetVisibilityChanged.emit(True)

    def closeEvent(self, event) -> None:
        event.accept()
        self.unload(True)
