# -*- coding: utf-8 -*-
# SPDX-FileCopyrightText: 2025 Deutsche Telekom Technik GmbH <f.vonstudsinske@telekom.de>
# SPDX-License-Identifier: GPL-3.0-or-later

from pathlib import Path
from datetime import datetime

from qgis.PyQt.QtWidgets import QLabel, QGroupBox
from qgis.PyQt.QtXml import QDomElement, QDomDocument
from qgis.PyQt import QtWidgets
from qgis.PyQt import uic
from qgis.core import QgsApplication

from typing import Optional

from ..constants import STYLE_SHEET_NEUTRAL, STYLE_SHEET_WARNING, STYLE_SHEET_ERROR, STYLE_SHEET_SUCCESS


def grp_visibility_changed(group: QGroupBox):
    """ Hides/Shows all children from group box, depends on check state.

        :param group:
    """
    state = group.isChecked()
    children = group.children()
    if state:
        for child in children:
            if not hasattr(child, 'show'):
                # kann nicht eingeblendet werden, bspw. QLayout
                continue
            child.show()
    else:
        for child in children:
            # kann nicht ausgeblendet werden, bspw. QLayout
            if not hasattr(child, 'hide'):
                continue
            child.hide()


def set_label_status(label: QLabel, text: str, style: str = STYLE_SHEET_NEUTRAL) -> None:
    """ sets labels text and css style

        :param label: label where to change text and stylesheet in css
        :param text: text to set, keep it empty and label will be hidden
        :param style: css stylesheet, defaults to `_qt_constants.STYLE_SHEET_NEUTRAL`
    """
    try:
        label.setText(text)
        if not text:
            label.hide()
            return

        label.setStyleSheet(style)
        label.show()
    except RuntimeError:
        # e.g. C++ object already deleted
        return


def set_label_error(label: QLabel, text: str) -> None:
    """ sets labels text

        :param label: label where to change text and stylesheet in css
        :param text: text to set, keep it empty and label will be hidden
    """
    set_label_status(label, text, STYLE_SHEET_ERROR)


def set_label_warning(label: QLabel, text: str) -> None:
    """ sets labels text

        :param label: label where to change text and stylesheet in css
        :param text: text to set, keep it empty and label will be hidden
    """
    set_label_status(label, text, STYLE_SHEET_WARNING)


def set_label_success(label: QLabel, text: str) -> None:
    """ sets labels text

        :param label: label where to change text and stylesheet in css
        :param text: text to set, keep it empty and label will be hidden
    """
    set_label_status(label, text, STYLE_SHEET_SUCCESS)


def generate(file: Path) -> Path:
    """
    Generates a .py file using uic from the given input file. The .py file is saved with the same name as the ui file,
    with name suffix '_generated_ui' appended.

    :param file: Path to the ui file you want compiled

    :return:
    """
    if not file.is_file() and not file.suffix == '.ui':
        raise ValueError(f"file {file.as_posix()} is not a ui file")

    pyfile = file.with_stem(file.stem + '_generated_ui').with_suffix('.py')
    with file.open('r') as opened_uifile:
        with pyfile.open('w') as opened_pyfile:
            uic.compileUi(uifile=opened_uifile, pyfile=opened_pyfile)

    pyfile_lines = pyfile.read_text('utf-8').split("\n")
    newlines = []
    for line in pyfile_lines:
        # some customizations
        newline = line
        if line.startswith('# Form implementation generated'):
            newline = f"# GENERATED ON {str(datetime.now())} FOR UI FILE '{file.name}'" # privacy
        if line.startswith('from PyQt5'):
            newline = line.replace('from PyQt5', 'from qgis.PyQt', 1) # qgis
        if line.startswith('# run again.'):
            # append some hints how to use this file
            newline = line + f'\n\n' \
                             f'# how to use this file: write this block on top of your {file.stem}.py file that is doing the operations\n' \
                             f'"""\n' \
                             f'FORM_CLASS, _ = UiModuleBase.get_uic_classes(__file__)\n' \
                             f'FORM_CLASS: \'Ui\'\n' \
                             f'try:\n' \
                             f'    from .{pyfile.stem} import Ui as FORM_CLASS\n' \
                             f'\n' \
                             f'except ModuleNotFoundError:\n' \
                             f'    pass\n' \
                             f'"""\n'
        if line.startswith('class'):
            newline = "class Ui(object):" # make every class name the same


        newlines.append(newline)

    pyfile.write_text("\n".join(newlines))
    return pyfile


def get_expected_plugin_path() -> Optional[Path]:
    """ Returns the expected plugin path in the QGIS profile python plugin folder.
        Returns None, if no folder found or no QgsApplication.instance() is active.

        <qgis profile>/plugins/python/<plugin folder>

    """
    if QgsApplication.instance() is None:
        return None

    profile_plugin_path = Path(QgsApplication.qgisSettingsDirPath()) / 'python' / 'plugins'
    if not profile_plugin_path.is_dir():
        return None

    file = Path(__file__)

    posix_profile_plugin_path = profile_plugin_path.as_posix()
    posix_file = file.as_posix()

    relative_path = posix_file.replace(posix_profile_plugin_path, "")[1:]

    plugin_folder_name = relative_path.split("/")[0]

    plugin_path = profile_plugin_path / plugin_folder_name
    if not plugin_path.is_dir():
        return None

    return profile_plugin_path / plugin_folder_name


def get_expected_plugin_folder_name() -> Optional[str]:
    """ Returns the expected QGIS plugin folder name from the file system.
        The module base submodule has to be placed into <plugin>/submodules/<module_base>.

        This function requires an active QgsApplication.instance() to find the default QGIS profile and python plugin folder.
    """
    if path := get_expected_plugin_path():
        return path.name

    return None


def get_relative_path(path: Path) -> Optional[str]:
    """ Returns a relative path inside the plugin from the root folder (e.g. where the plugin.py is.

        .. code-block:: python

            path = Path("<qgis profile>/plugins/python/<plugin folder>/modules/animal/roflcopter.py")
            relative_path = get_relative_path(path)
            print(relative_path)  # -> "/<plugin folder>/modules/animal/roflcopter.py"
    """
    if not (root := get_expected_plugin_path()):
        return None

    root_posix = root.as_posix()
    path_posix = path.as_posix()

    return path_posix.replace(root_posix, "")


def is_installed_in_qgis_plugin_folder() -> bool:
    """ Is this plugin the the QGIS plugin folder """
    if not (root := get_expected_plugin_path()):
        return False

    path = Path(QgsApplication.qgisSettingsDirPath()) / 'python' / 'plugins'

    return root.parent == path


def get_ui_class(ui_file: str | Path) -> str | None:
    """ Returns the first available widget within the UI file.
    """
    # red the UI file
    document = QDomDocument()
    document.setContent(Path(ui_file).read_bytes(), False)
    # get first widget, this widget is always the top widget -> BASE_CLASS
    widget: QDomElement = document.firstChildElement("ui").firstChildElement("widget")
    base_class_string = widget.attribute("class")

    # get the base class for the UI widget (QDialog, QWidget, QMainDialog etc.)
    ui_base_class = getattr(QtWidgets, base_class_string, None)
    return ui_base_class
