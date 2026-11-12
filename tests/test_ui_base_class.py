# -*- coding: utf-8 -*-
# SPDX-FileCopyrightText: 2025 Deutsche Telekom Technik GmbH <f.vonstudsinske@telekom.de>
# SPDX-License-Identifier: GPL-3.0-only
import pytest

from pathlib import Path

from qgis.PyQt import sip
from qgis.PyQt.QtCore import QObject
from qgis.PyQt.QtWidgets import QTabWidget, QWidget

from .fixtures import plugin_qgis_new_project

from ..ui.base_class import UiModuleBase
from ..ui.base_tab_widget import TabModuleBase


def test_get_tab_stops_from_ui_file():

    file = Path(__file__).parent / "test_ui_base_class.ui"
    tab_stops = UiModuleBase.get_tab_stops_from_ui_file(file.as_posix())
    assert tab_stops == ["Btn_A", "Btn_B", "Btn_C"]


def test_ui_module_lifecycle_signals_have_distinct_names():
    class SignalProbe(UiModuleBase, QObject):
        pass

    meta_object = SignalProbe.staticMetaObject
    signal_names = {
        bytes(meta_object.method(index).name()).decode()
        for index in range(meta_object.methodOffset(), meta_object.methodCount())
    }

    assert "uiModuleAdding" in signal_names
    assert "uiModuleAdded" in signal_names


def test_legacy_subcomponent_module_api_is_removed():
    assert not hasattr(UiModuleBase, "add_subcomponent_module")


@pytest.fixture()
def tab_module_class():
    class Module(UiModuleBase, QWidget):
        def __init__(self, parent=None):
            QWidget.__init__(self, parent)
            self.MainWidget = self
            self.unloaded = False
            self.unload_calls = []
            self.modules = []
            self.delete_nested_widgets = True

        def unload(self, self_unload=False):
            self.unload_calls.append(self_unload)
            self.MainWidget.objectName()
            for module in self.modules:
                module.unload(self_unload)
                if self.delete_nested_widgets:
                    sip.delete(module.MainWidget)
            self.unloaded = True

    return Module


@pytest.mark.parametrize("delete_nested_widgets", [False, True])
@pytest.mark.parametrize("separate_main_widget", [False, True])
@pytest.mark.parametrize("tab_reference", [0, "test"])
def test_unload_tab_skips_recursively_unloaded_modules(
        plugin_qgis_new_project, tab_module_class, separate_main_widget,
        tab_reference, delete_nested_widgets):
    tabs = TabModuleBase.__new__(TabModuleBase)
    QTabWidget.__init__(tabs)
    page = QWidget()
    outer = tab_module_class(page)
    outer.delete_nested_widgets = delete_nested_widgets
    nested = tab_module_class(None if separate_main_widget else outer)
    if separate_main_widget:
        nested.MainWidget = QWidget(outer)
        nested.MainWidget._ui_module_base = nested
    nested.MainWidget.setObjectName("nested")
    outer.modules.append(nested)
    tabs.addTab(page, "test")
    tabs.tab_object_names = {"test": ["registered_frame"]}
    tabs.registered_frame = outer
    tabs.nested = nested.MainWidget

    try:
        tabs.unload_tab(tab_reference)

        assert outer.unload_calls == [True]
        assert nested.unload_calls == [True]
        assert sip.isdeleted(nested.MainWidget) == delete_nested_widgets
        if not delete_nested_widgets:
            assert nested.MainWidget.objectName() == ""
        assert tabs.count() == 0
        assert tabs.tab_object_names == {}
        assert not hasattr(tabs, "nested")
        assert not hasattr(tabs, "registered_frame")
    finally:
        sip.delete(tabs)
        if separate_main_widget:
            sip.delete(nested)


@pytest.mark.parametrize("separate_main_widget", [False, True])
def test_reload_tabs_with_optional_same_named_module(
        plugin_qgis_new_project, tab_module_class, separate_main_widget):
    tabs = TabModuleBase.__new__(TabModuleBase)
    QTabWidget.__init__(tabs)
    tabs.tab_object_names = {}
    detached_modules = []

    try:
        for with_xyz in [True, False, True, False, True]:
            assert not hasattr(tabs, "xyz")
            assert not hasattr(tabs, "tab_frame")
            assert tabs.findChildren(QWidget, "xyz") == []
            _, frame = tabs.insert_module_tab(0, "test", "tab_frame")
            outer = tab_module_class()
            outer.delete_nested_widgets = False
            tabs._install_ui_module_widget(frame, outer)
            nested = None

            if with_xyz:
                nested = tab_module_class(None if separate_main_widget else outer)
                if separate_main_widget:
                    detached_modules.append(nested)
                    nested.MainWidget = QWidget(outer)
                    nested.MainWidget._ui_module_base = nested
                nested.MainWidget.setObjectName("xyz")
                outer.modules.append(nested)
                tabs.xyz = nested.MainWidget
                assert tabs.findChildren(QWidget, "xyz") == [nested.MainWidget]

            assert tabs.count() == 1
            assert hasattr(tabs, "xyz") == with_xyz
            assert tabs.tab_frame is outer

            tabs.unload_tab("test")

            assert outer.unload_calls == [True]
            if nested is not None:
                assert nested.unload_calls == [True]
                assert nested.MainWidget.objectName() == ""
            assert outer.objectName() == ""
            assert tabs.count() == 0
            assert tabs.tab_object_names == {}
            assert not hasattr(tabs, "xyz")
            assert not hasattr(tabs, "tab_frame")
            assert tabs.findChildren(QWidget, "xyz") == []
    finally:
        sip.delete(tabs)
        for module in detached_modules:
            sip.delete(module)
