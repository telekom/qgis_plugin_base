# -*- coding: utf-8 -*-
# SPDX-FileCopyrightText: 2025 Deutsche Telekom Technik GmbH <f.vonstudsinske@telekom.de>
# SPDX-License-Identifier: GPL-3.0-or-later

from typing import Dict, List, Union, Tuple, Iterator, Optional

from qgis.PyQt.QtWidgets import (QFrame, QWidget,
                                 QTabWidget, QGridLayout)
from qgis.PyQt.QtCore import Qt, pyqtSignal
from qgis.PyQt.QtGui import QHideEvent

from .base_class import UiModuleBase
from .widgets import Widget, NoWheelTabBar


class TabModuleBase(UiModuleBase, QTabWidget):
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
        QTabWidget.__init__(self, kwargs.get('parent', None))

        # make tabs not scrollabe with re-implemented tab bar
        self.__tab_bar = NoWheelTabBar()
        self.setTabBar(self.__tab_bar)

        self.tab_object_names: Dict[str, List[str]] = {}

    def set_tab_text(self, index: int, text: str):
        """ Updates the tab text.
            Similar to the "QTabWidget.setTabText" method
            but handles some additional data for the ModuleBase.
        """
        # get the current tab text
        old_text = self.tabText(index)

        if text in self.tab_object_names:
            raise ValueError(f"tab name {text=} already in use")

        # copy the values from the old tab name
        self.tab_object_names[text] = self.tab_object_names[old_text]

        # remove old tab name
        del self.tab_object_names[old_text]

        # set the new tab name
        self.setTabText(index, text)

    def insert_module_tab(self, index: int, tab_name: str, object_name: str,
                          position: Optional[Tuple[int, int]] = None) -> Tuple[int, QFrame]:
        """ insert a new tab and prepare a are where a other module can be loaded in.

            :param index: index
            :param tab_name: tab name
            :param object_name: New object name for place holder widget to set modules.
                                This name will be available as new attribute on this object.
                                Only chars and underscores -> regex `[A-Za-z_][A-Za-z_0-9]+`
                                Minimum one char.
            :param position: tuple(row, column) with position data in layout

            :returns: tab index as integer and created QFrame for ModuleBase
        """

        # check, if object_name is unique and valid
        if self.is_tab_name_in_use(tab_name):
            raise AttributeError(f"tab name '{tab_name}' already in use")

        # append tab
        if index < 0:
            index = self.count()

        page_widget = Widget()
        index = self.insertTab(index, page_widget, tab_name)
        page_widget = self.widget(index)
        layout = QGridLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setAlignment(Qt.AlignTop)
        page_widget.setLayout(layout)

        page_frame = self._create_frame(layout, object_name, position=position)
        self.tab_object_names.setdefault(tab_name, [])
        self.tab_object_names[tab_name].append(object_name)

        return index, page_frame

    def is_tab_name_in_use(self, tab_name: str) -> bool:
        """ Check if tab name is in use. case-sensitive.

        :param tab_name: tab name
        :return: True if tab name already in use, else False
        """

        for index, name in self.get_iter_tab_names():
            if tab_name == name:
                return True

        return False

    def find_tab_index(self, tab_name: str) -> int:
        """ finds tab index with name.

        :param tab_name: tab name
        :return: index of tab or -1 when not found.
        """
        for index, name in self.get_iter_tab_names():
            if tab_name == name:
                return index

        return -1

    def get_iter_tab_names(self, reversed_: bool = False) -> Iterator[Tuple[int, str]]:

        def _iter_helper(i):
            return i, self.tabText(i)

        if reversed_:
            yield from (_iter_helper(index) for index in range(self.count() - 1, -1, -1))
        else:
            yield from (_iter_helper(index) for index in range(self.count()))

    def reset_all_tabs(self):
        """ Removes all tabs """

        for index, name in self.get_iter_tab_names(reversed_=True):
            self.unload_tab(index)

    @property
    def tab_order_widgets(self) -> List[QWidget]:
        """ Overwritten property from base class

            Handles Tab-Stop Order in TabWidget
        """
        tab_stop_widgets = []
        for index, _ in self.get_iter_tab_names():
            page_widget = self.widget(index)
            found_module = None
            for module in self._modules.values():
                module_widget = module.MainWidget or module
                if page_widget is module_widget.parent():
                    found_module = module
                    break

            # module widgets
            if found_module is not None:
                tab_stop_widgets.extend(found_module.tab_order_widgets)

        return tab_stop_widgets

    def unload(self, self_unload: bool = False):
        """ will be called, when module will be unloaded

            :param self_unload: only self unload, defaults to False
        """
        self.reset_all_tabs()
        super().unload(self_unload)

        self.hide()

        del self

    def unload_object_name(self, object_name: str, restore_empty_frame: bool = True):
        """ Unloads object with given Qt object name

        :param object_name: object name
        :param restore_empty_frame: True = replace old module with empty frame widget
        :return:
        """
        frame = self.get_widget(object_name)
        if frame:
            raise AttributeError(f"object with name '{object_name}' not found")

        module = self._get_module(frame)

        if restore_empty_frame:
            module.replace_with_empty_frame()
        else:
            module.unload(True)

    def unload_tab(self, tab: Union[int, str]):
        """ Unloads tab an inserted modules.

        :param tab: tab index or tab name
        :return:
        """
        if isinstance(tab, int):
            tab_index = tab
            tab_name = self.tabText(tab)
        else:
            tab_name = tab
            tab_index = self.find_tab_index(tab_name)

        if tab_index < 0:
            raise ValueError(f"found tab index '{tab_index}' is not valid")

        widget = self.widget(tab_index)
        children: List[UiModuleBase] = widget.findChildren(QWidget)
        for child in children:

            if isinstance(child, UiModuleBase):
                child.unload(True)
                continue

            if hasattr(child, "_ui_module_base"):
                module = child._ui_module_base
                module.unload(True)
                if hasattr(self, child.objectName()):
                    delattr(self, child.objectName())
                child.setObjectName("")

        if isinstance(widget, UiModuleBase):
            widget.unload(True)

        # unload used object names to make them available for later usage
        for name in self.tab_object_names[tab_name]:
            if hasattr(self, name):
                delattr(self, name)

        del self.tab_object_names[tab_name]

        self.removeTab(tab_index)

    def hideEvent(self, event: QHideEvent):
        event.accept()
        self.widgetVisibilityChanged.emit(False)

    def showEvent(self, event: QHideEvent):
        event.accept()
        self.widgetVisibilityChanged.emit(True)
