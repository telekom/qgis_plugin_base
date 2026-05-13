# -*- coding: utf-8 -*-
# SPDX-FileCopyrightText: 2025 Deutsche Telekom Technik GmbH <f.vonstudsinske@telekom.de>
# SPDX-License-Identifier: GPL-3.0-only

import inspect
import os.path
import sys
import sip
import json
import logging
import importlib.util
import configparser

from re import fullmatch, sub as re_sub, escape, search

from pathlib import Path
from pkg_resources import packaging

from qgis.PyQt.QtCore import (QMetaObject, QObject, pyqtBoundSignal, pyqtSignal,
                              QTranslator, QCoreApplication, QUrl)
from qgis.PyQt.QtXml import QDomDocument, QDomElement

from qgis.PyQt.QtWidgets import (QAction, QWidget, QFrame, QLabel, QApplication,
                                 QGridLayout, QToolBar, QMainWindow, QComboBox,
                                 QMessageBox, QPushButton, QToolTip, QLineEdit,
                                 QCheckBox, QSpinBox, QListWidget, QTreeWidget,
                                 QTableWidget, QTextBrowser, QTextEdit, QListView,
                                 QTreeView, QTableView, QRadioButton, QToolButton, QMenu)
from qgis.PyQt.QtGui import QIcon, QCursor, QDesktopServices
from qgis.PyQt import uic
from pyplugin_installer import installer as pyplugin_installer

from qgis.gui import QgisInterface, QgsFileWidget
from qgis.core import (QgsApplication, QgsMapLayer, QgsNetworkAccessManager,
                       QgsSettings, QgsLocatorFilter, Qgis)

from typing import Any, Type, Dict, Callable, List, Tuple, Union, Optional

from xml.sax.saxutils import escape
from .typing_ import MB, UIMB, PLUGIN
from .base_logging import Logging
from .signal_connection import Connection

from .widgets import apply_widget_options, is_widget_compatible
from .functions import get_expected_plugin_folder_name, get_relative_path, get_ui_class
from ..constants import (FILE_ENDINGS_PY_TO_UI, FILE_ENDINGS_RE_COMPILED, 
                         ACCESSIBILITY_DEFAULT_COLOR)
from ..qgis.qgis_env import activate_processing_plugin


class ModuleBase(Logging):
    """ Base class for each module class (must be inherited!)

        Following attributes can not be set:

            - `attribute`s with value type QgsMapLayer
                -> when you need to disable this check: `self._unallowed_attribute_types = tuple()`
            - `iface` attribute - reserved ad property

        .. code-block:: python

            # minimum class inheritance structure
            # QObject is necessary to emit pyqt signals
            class MyModule(ModuleBase, QObject):
                ...


        Expecting key word arguments:
        :param parent_module: None or ModuleBase
        :param plugin: class Plugin (ModuleBase)
        :param name: str

    """
    WARNING = logging.WARNING
    DEBUG = logging.DEBUG
    INFO = logging.INFO
    ERROR = logging.ERROR
    CRITICAL = logging.CRITICAL

    IGNORE_LOG_NAMES = '(_(Ui)?ModuleBase.*)'

    # When the module itself will be unloaded
    beforeUnload = pyqtSignal(name="beforeUnload")
    afterUnload = pyqtSignal(name="afterUnload")

    # Module object not available
    moduleAdding = pyqtSignal(str, type, name="moduleAdding")
    # Module object available
    moduleAdded = pyqtSignal(object, name="moduleAdded")

    # Module Objects available, only available for UiModuleBase objects
    uiModuleAdding = pyqtSignal(object, name="uiModuleAdded")
    uiModuleAdded = pyqtSignal(object, name="uiModuleAdded")

    def __init__(self, **kwargs: dict):
        # check mro if highest class is a module base (ui or not)
        # this check is important to keep parent and child relationships valid

        self.__raise_for_invalid_inheritance()  # very important first check!

        self._translators: List[QTranslator] = []

        self._unallowed_attribute_types = (QgsMapLayer, )

        self._modules: Dict[str, MB] = {}
        self._connections: List[Tuple[Union[pyqtBoundSignal, pyqtSignal],
                                      Callable, QMetaObject.Connection,
                                      Connection]] = []
        self._parent: Optional[Union[UIMB, MB]] = kwargs.get("parent_module", None)
        self._plugin: PLUGIN = kwargs['plugin']
        self.module_name: str = kwargs["name"]
        self.logging_level_debug: bool = kwargs.get('logging_level_debug', False)

        # accessibility
        self._accessibility_config_path = self._plugin.accessibility_config_path
        self._accessibility_config = configparser.ConfigParser()

        self._translators: List[QTranslator] = []
        self._filters: List[QgsLocatorFilter] = []

        # ui relevant attributes
        self._toolbars_managed: Dict[str, Tuple[QToolBar, List[QAction]]] = {}  # {'toolbars object name': [action objects]}
        self._actions: List[QAction] = []
        self._actions_managed: List[QAction] = []
        self._tool_buttons: List[QToolButton] = []
        self._tool_buttons_managed: List[QToolButton] = []

        self.__unloaded = False
        self.unloaded = self.__unloaded

        QgsApplication.processEvents()

        Logging.__init__(self, self.get_module_logger_name(), kwargs.get("logging_file_path", ""))
        if self.logger:
            level = self.INFO if not self.logging_level_debug else self.DEBUG
            self.logger.setLevel(level)

        # auto-install the QTranslators for the UI and for the messaged.
        self.__auto_install_translators()

    def __auto_install_translators(self):
        """ Auto-install the QM files for UI and message translations. """

        # get the file stem for this module
        # "magic_interface_module.py" -> "magic_interface_module"
        ui_name = Path(inspect.getfile(self.__class__)).stem
        ui_context = f"{self.__class__.__name__}"
        # "magic_interface_module.py" -> "magic_interface_module_content"
        ui_content_context = f"{self.__class__.__name__}Content"
        ui_content = ui_name + "_content"

        # path to the translation files
        path_i18n = Path(self.get_plugin().plugin_dir) / "i18n"

        # load the qm files, if exists
        # > ui name <context> must be the class name, e.g. "ModuleBase"
        self.install_translator(path_i18n / self.get_qtranslator_file_name(ui_name), context=ui_context)
        # > ui content <context> must be the class name + "Content", e.g. "ModuleBaseContent"
        self.install_translator(path_i18n / self.get_qtranslator_file_name(ui_content), context=ui_content_context)

    def get_module_logger_name(self) -> str:
        """ Returns the logger name (usually relative file path from the plugin root). """

        try:
            # try to get the python file, where the class is defined
            file = inspect.getfile(self.__class__)
            file_name = get_relative_path(Path(file))
        except TypeError:
            # possible TypeError from inspect module, e.g. compiled libraries or not defined in a file
            file_name = f"<unknown>/{self.__class__.__name__}"

        return file_name

    def __raise_for_invalid_inheritance(self):
        """ Raises exceptions on class inheritance errors.
            Class inheritance check differs from compiled classes and normal classes from readable source code.
            There is a small challenge to validate class from compiled code.

        """

        mro = inspect.getmro(type(self))
        mro_class_names = [class_.__name__ for class_ in mro]
        allowed_modules_classes = (ModuleBase, UiModuleBase)
        allowed_modules_class_names = [class_.__name__ for class_ in allowed_modules_classes]

        if QObject.__name__ not in mro_class_names:
            raise TypeError("""<html><head/><body><p>Missing """
                            """<span style=" font-size:6pt; font-style:italic;">"""
                            """PyQt5.QtCore.</span><span style=" font-weight:600;">"""
                            """QObject</span> class inheritance in """
                            f"""module class {self.__class__.__name__}</p></body></html>""")

        if mro[0].__name__ not in allowed_modules_class_names and mro[1].__name__ not in allowed_modules_class_names:
            # no UiModuleBase and no ModuleBase used in inheritance
            module_class = UiModuleBase if UiModuleBase in mro else ModuleBase
            ok = False

            for i, class_ in enumerate(mro[1:]):
                # checks each class in inherited order to look for module bases
                class_mro = inspect.getmro(class_)
                class_mro_names = [class_.__name__ for class_ in class_mro]

                if module_class.__name__ in class_mro_names:
                    ok = True
                    break

                break

            if not ok:

                # find first class, which inherits a module base
                use_class = None
                for class_ in mro[1:]:
                    class_mro = inspect.getmro(class_)
                    class_mro_names = [class_.__name__ for class_ in class_mro]

                    if module_class.__name__ in class_mro_names:
                        use_class = class_
                        break

                use_class_names = (UiModuleBase.__name__, use_class.__name__,
                                   ModuleBase.__name__, self.__class__.__name__)
                new_mro = (use_class.__name__,) + tuple(x.__name__ for x in mro if x.__name__ not in use_class_names)
                origin_mro = tuple(x.__name__ for x in mro if x.__name__ != self.__class__.__name__)
                raise TypeError("\noriginal inheritance:\n\t"
                                f"{self.__class__.__name__}({', '.join(origin_mro)})\n\n"
                                "expected class inheritance (first inheritance should be a module base):\n\t"
                                f"{self.__class__.__name__}({', '.join(new_mro)})\n\n"
                                "Hint: class name 'Ui_MainWindow' is usually FORM_CLASS from ui file.\n"
                                "This is a approximate hint to let you fix your issue")

    @staticmethod
    def show_cursor_tool_tip(text: str):
        """ Shows the given text as tooltip on the current cursor position.

            :param text: Tooltip text to show
        """
        pos = QCursor.pos()
        QToolTip.showText(pos, text)

    @staticmethod
    def enable_processing() -> bool:
        """ Enables qgis processing module, if not active.
            Returns `True`, if processing plugin is enabled or has been enabled.
        """

        return activate_processing_plugin()

    @property
    def iface(self) -> Optional[QgisInterface]:
        from qgis.utils import iface

        _iface = getattr(self, "_iface", None)
        if isinstance(_iface, QgisInterface):
            return _iface

        return iface

    # noinspection PyPep8Naming
    def mainWindow(self) -> Optional[QWidget]:
        """ Returns QWidget/QMainWindow from current QgisInterface instance.
            If not iface present, it returns None.
        """
        iface = self.iface
        if iface:
            return iface.mainWindow()

        return None

    @property
    def unloaded(self) -> bool:
        return self.__unloaded

    @unloaded.setter
    def unloaded(self, value: bool):
        self.__unloaded = value

    def add_action(self, name: str, icon: QIcon, callback_action: Optional[Callable],
                   *,
                   manage: bool = False,
                   toolbar_name: Optional[str] = None,
                   toolbar_displayname: Optional[str] = None,
                   to_plugin_menu: bool = True,
                   init_enabled: bool = True,
                   tool_tip: str = "",
                   tool_button: Optional[QToolButton] = None,
                   is_tool_button_default: bool = False) -> QAction:
        """ Adds a new QAction with the given name and icon (and optional callback) to the module.

            :param name: visual action name for user
            :param icon: icon path, empty string means no icon
            :param manage: should the action should be "registered as managed" action for this module?
            :param callback_action: function/method/lambda to call or explicit None
            :param toolbar_name: object name for QToolBar
            :param toolbar_displayname: visual toolbar name for hide and show.
                                        only necessary, when no new bar is needed
            :param to_plugin_menu: Add to plugin menu bar in the QGIS Python plugin menu
            :param init_enabled: init enable state, defaults to True
            :param tool_tip: tool tip string
            :param tool_button: The QToolButton the action should be added to.
            :param is_tool_button_default: Sets the QToolButton default action to the created action.

            :return: new created QAction
        """
        from qgis.utils import iface

        if iface is not None:
            widget = iface.mainWindow()
        else:
            widget = None

        action = QAction(icon, name, None)
        if callback_action is not None:
            action.triggered.connect(callback_action)
        action.setEnabled(init_enabled)
        action.setToolTip(tool_tip)

        # Anzeige- sowie Objektname der Toolbar (Werkzeugleiste) sind vorhanden
        if toolbar_displayname and toolbar_name and not tool_button:
            toolbar = self.get_toolbar(toolbar_displayname, toolbar_name, widget)
            toolbar.addAction(action)
            self._toolbars_managed[toolbar_name][1].append(action)

        if tool_button:
            menu = tool_button.menu()
            if not menu:
                raise AttributeError(f"{tool_button} has no attribute `menu`")
            menu.addAction(action)
            if is_tool_button_default:
                tool_button.setDefaultAction(action)

        if to_plugin_menu:
            from qgis.utils import iface
            if not hasattr(self.get_plugin(), 'plugin_menu_name'):
                raise AttributeError(f"{self.get_plugin()} has no attribute `plugin_menu_name`")
            iface.addPluginToMenu(getattr(self.get_plugin(), 'plugin_menu_name'), action)

        if manage:
            self._actions_managed.append(action)

        self._actions.append(action)

        return action
    
    def add_tool_button(self, name: str, icon: QIcon, callback_action: Optional[Callable],
                        *,
                        manage: bool = False,
                        toolbar_name: Optional[str] = None,
                        toolbar_displayname: Optional[str] = None,
                        to_plugin_menu: bool = True,
                        init_enabled: bool = True,
                        tool_tip: str = "") -> QToolButton:
        """ Adds a new QToolButton with the given name and icon (and optional callback) to the module.

            :param name: visual button name for user
            :param icon: icon path, empty string means no icon
            :param manage: should the action should be "registered as managed" action for this module?
            :param callback_action: function/method/lambda to call or explicit None
            :param toolbar_name: object name for QToolBar
            :param toolbar_displayname: visual toolbar name for hide and show.
                                        only necessary, when no new bar is needed
            :param to_plugin_menu: Add to plugin menu bar in the QGIS Python plugin menu
            :param init_enabled: init enable state, defaults to True
            :param tool_tip: tool tip string

            :return: new created QToolButton
        """
        from qgis.utils import iface

        if iface is not None:
            widget = iface.mainWindow()
        else:
            widget = None

        tool_button: QToolButton = QToolButton(widget)
        tool_button.setAutoRaise(True)
        tool_button.setPopupMode(QToolButton.MenuButtonPopup)
        tool_button.setEnabled(init_enabled)
        tool_button.setToolTip(tool_tip)
        tool_button.setMenu(QMenu(widget))

        # Anzeige- sowie Objektname der Toolbar (Werkzeugleiste) sind vorhanden
        if toolbar_displayname and toolbar_name:
            toolbar = self.get_toolbar(toolbar_displayname, toolbar_name, widget)
            toolbar.addWidget(tool_button)
            self._toolbars_managed[toolbar_name][1].append(tool_button)

        if manage:
            self._tool_buttons_managed.append(tool_button)

        self._tool_buttons.append(tool_button)

        return tool_button

    def add_module(self, keyword: str, module_class: Type[MB], parent: Optional[QWidget] = None, *args: list,
                   **kwargs) -> MB:
        """ Add new module to this module and returns it. It can be a ModuleBase or UiModuleBase

            :param keyword: keyword for module dictionary (must be unique)
            :param module_class: module class to load
            :param parent: parent widget for WindowModality, defaults to None
        """
        if keyword in self._modules:
            raise KeyError(f"module '{keyword}' already loaded.")

        # check if module_class bases on ModuleBase
        if ModuleBase not in inspect.getmro(module_class):
            raise ValueError(f"module {module_class.__name__} does not inherit '{ModuleBase.__name__}'")

        self.moduleAdding.emit(keyword, module_class)

        # updating default arguments for new base module
        dict_ = {
            'parent': parent,
            'parent_module': self,
            'name': keyword,
            'module_name': keyword
        }
        kwargs.update(dict_)
        if not kwargs.get("plugin"):
            kwargs["plugin"] = self.get_plugin()

        if not kwargs.get("logging_file_path"):
            kwargs["logging_file_path"] = self.get_plugin().log_file_path

        if not kwargs.get("logging_level_debug"):
            kwargs["logging_level_debug"] = self.get_plugin().logging_level_debug

        module = module_class(**kwargs)
        self._modules[keyword] = module

        self.moduleAdded.emit(module)

        try:
            plugin = self.get_plugin()
            plugin.submoduleAdded.emit(self, module)
        except (StopIteration, ModuleNotFoundError):
            ...

        return module

    def disable_managed_actions(self):
        for action in self._actions_managed:
            action.setEnabled(False)

    def enable_managed_actions(self):
        for action in self._actions_managed:
            action.setEnabled(True)

    def get_icon_path(self, icon: str, folder: Optional[str] = None) -> str:
        """ Returns joined os path from icons folder.
            If no file ending is given, then only svg, png and jpg are valid.

            :param icon: icon name with or without file ending
            :param folder: optional folder path to search
        """

        plugin = self.get_plugin()

        icons_dir = plugin.icons_dir if not folder else folder

        check = icon.lower()
        endings = (".png", ".jpg", ".jpeg", ".svg")
        file_names = {icon + x for x in endings}
        if not check.endswith(endings):
            for file_name in os.listdir(icons_dir):
                path = os.path.join(icons_dir, file_name)
                if not Path(path).is_file():
                    continue

                if file_name in file_names:
                    icon = file_name
                    break

        path = os.path.join(icons_dir, icon)
        if not Path(path).is_file():
            raise FileNotFoundError(f"file '{icon}' not found in '{icons_dir}'")

        return path

    def install_translator(self, file: Union[str, Path], *, context: str = None) -> bool:
        """ Install translation file (.qm).

            :param file: path to the QM file
            :param context: Optional required context in the TS file for the QM file

            :return: True on success
        """

        if not isinstance(file, str):
            file = str(file)

        if not Path(file).is_file():
            # file not found, log it to debug
            # missing this file is not critical
            tag = f"{self.__class__.__module__}.{self.__class__.__name__}"
            self.log(f"{tag}: Translation file {file=} not found.", level=self.DEBUG)
            return False

        # pr-check for the context, if given in the source file for the QM file (looking into the TS file)
        ts_file = Path(file)
        ts_file = ts_file.parent / f"{ts_file.stem}.ts"
        if context and ts_file.is_file() and self.get_plugin().is_logging_debug_active():
            with ts_file.open(mode="r", encoding="utf-8") as tsf:
                ts_file_content = tsf.read()
                if f"<name>{context}</name>" not in ts_file_content:
                    self.log(f"Missing context '{context}' in file '{ts_file.as_posix()}'", level=self.DEBUG)

        translator = QTranslator()
        # file found and loaded
        if translator.load(file):
            # add loaded translator to instance
            if QCoreApplication.instance().installTranslator(translator):
                self._translators.append(translator)
                return True

        return False

    @staticmethod
    def get_qtranslator_file_name(name: str):
        """ returns the expected file name for the given name.
            "{name}_{language}.qm"
        """
        # get the current language/translation from QGIS
        #   can be the short version, e.g. "de" or the long version "de_DE"
        language = QgsApplication.instance().translation()

        return f"{name}_{language}.qm"

    def translate_ui(self, text: str):
        """ Returns the translated text for UI elements.
            If no translation is found, then the given text will be returned.

            The context "<class name>" is required.

            :param text: Text to translate
        """
        result = QgsApplication.instance().translate(
            f"{self.__class__.__name__}", text)
        return result

    def translate_content(self, text: str):
        """ Returns the translated text for further messages.
            If no translation is found, then the given message will be returned.

            The context "<class name>Content" is required.

            :param text: Text to translate
        """
        result = QgsApplication.instance().translate(
            f"{self.__class__.__name__}Content", text)
        return result

    def install_filter(self, filter_: QgsLocatorFilter):
        """ Register a locator filter for the search bar in QGIS.
        """

        if not isinstance(filter_, QgsLocatorFilter):
            raise TypeError(f"Expecting instance of type QgsLocatorFilter, got {filter_.__class__.__name__}")
        self._filters.append(filter_)
        self.iface.registerLocatorFilter(filter_)

    def remove_actions(self, only_managed: bool = False):
        """ Removes actions from all toolbars.
            Empty toolbars will be removed too.

         :param only_managed: Set to True to remove only "managed" actions from toolbars.

        """
        for toolbar_name in list(self._toolbars_managed):
            self.unload_toolbar(toolbar_name, only_managed)

    def unload_toolbar(self, toolbar_object_name: str, only_managed: bool = False):
        """ Unloads all actions from given toolbar name.
            Does nothing, if object name is not in the toolbar's list.

            :param toolbar_object_name: Toolbar's object name.
            :param only_managed: Set to True to remove only "managed" actions from toolbars.
        """
        if toolbar_object_name not in self._toolbars_managed:
            return

        toolbar, actions = self._toolbars_managed[toolbar_object_name]

        # create list of not deleted actions
        self._actions_managed = [action for action in self._actions_managed
                                 if not sip.isdeleted(action)]
        
        # create list of not deleted tool buttons
        self._tool_buttons_managed = [button for button in self._tool_buttons_managed
                                      if not sip.isdeleted(button)]

        if sip.isdeleted(toolbar):
            # c++ already deleted?
            return

        for action in actions.copy():

            if sip.isdeleted(action):
                actions.remove(action)
                continue

            # if only_managed is True check if the object is in the managed lists
            if (only_managed 
                    and action not in self._actions_managed
                    and action not in self._tool_buttons_managed):
                continue

            actions.remove(action)

            # actions can be directly removed
            if isinstance(action, QAction):
                toolbar.removeAction(action)
            # if the object is a tool button, get all the actions and their widgets, find the right one and remove it
            elif isinstance(action, QToolButton):
                for ac in toolbar.actions():
                    if toolbar.widgetForAction(ac) is action:
                        toolbar.removeAction(ac)
                        break

        if toolbar.actions():
            # return here to keep remaining actions visible
            return

        # toolbar is empty, remove it
        if parent := toolbar.parent():
            parent.removeToolBar(toolbar)

            # set parent to None to delete it later
            toolbar.setParent(None)

        # delete last known entries
        toolbar.close()
        toolbar.deleteLater()
        del self._toolbars_managed[toolbar_object_name]

    def connect(self, obj: Union[pyqtBoundSignal, pyqtSignal],
                callable_: Callable, **kwargs) -> Tuple[Union[pyqtBoundSignal, pyqtSignal],
                                                        Callable,
                                                        QMetaObject.Connection,
                                                        Connection]:
        """ Connects new callable to a Qt signal and store the connection.
            Set connections will be unloaded later in `unload` method.

            Keep in mind, that some Qt connections will call the connected method/function with extra arguments,
            e.g. sometimes QPushButton with a boolean.

            For further kwargs see description in Connection class.

            Hint:
                Do not save on `self` or in a similar way. On module unload let the ModuleBase disconnect all connection.
                When you have saved a returned connect-value on `self`, then the connection may stay alive.

            :param obj: QObject
            :param callable_: function/method

            :return: qt connection object
        """

        con = Connection(callable_, self.logger, **kwargs)

        connection = obj.connect(con.call)
        entry = (obj, callable_, connection, con)
        self._connections.append(entry)

        return entry

    def webbrowser_open(self, path: Union[str, Path]):
        """ Opens path/file with default programm.
            Opens Webbrowser, Excel and so on.

            Special handling for webaddresses:
                - priors chrome browser, firefox and the ms edge
                - fall back to system browser if path not found
        """

        if isinstance(path, Path):
            path = path.as_posix()
                
        opened = QDesktopServices.openUrl(QUrl.fromLocalFile(path))
        self.log(f"File/Path '{path}' {opened=}", level=self.INFO)

    def set_ui_version_info(self, label: Optional[QLabel] = None, show_new_version_info: bool = True,
                            show_network_error: bool = True):
        """
        Reads the version from the repo and the local installation
        and informs the user about possible updates.

        Returns `True`, if new update (commit or version number changed), otherwise `False`.
        """

        repo_version = self.get_plugin().repo_version
        error = self.get_plugin().repo_version_error
        version = self.get_plugin().plugin_version
        commit = self.get_plugin().commit
        repo_commit = self.get_plugin().repo_commit

        # extract the version number/syntax from the QGIS
        if qgis_version_int_str := search(r"\d+[.]\d+[.]\d+", Qgis.QGIS_VERSION).group(0):
            qgis_version_int = packaging.version.parse(qgis_version_int_str)
        else:
            qgis_version_int = None

        if hasattr(repo_version, "qgis_minimum_version"):
            # compare QGIS version with the found set QGIS version from the XML file (qgis plugin repo)
            if (repo_version.qgis_minimum_version
                    and qgis_version_int < repo_version.qgis_minimum_version):
                # QGIS version is to old, no further plugin version check
                return False

            if (repo_version.qgis_maximum_version
                    and qgis_version_int > repo_version.qgis_maximum_version):
                # QGIS version is to new, no further plugin version check
                return False

        if label is not None:
            label.setToolTip("")

        plugin_menu = self.get_plugin().plugin_menu_name
        release_info = self.get_plugin().get_release_info()

        if repo_version == "-1":
            # no XML URL defined in metadata.txt
            if label is not None:
                label.setText(f"Installiert: v{version} - Kein Pluginmanagement ({release_info})")
                label.setStyleSheet("font-weight: bold; color: rgb(120, 0, 0); }")
                label.setToolTip(f"Fehler: {error}")
            return False

        if repo_version is None:
            if label is not None:
                label.setText(f"Installiert: v{version} ({release_info}) - Updateserver nicht erreichbar")
                label.setStyleSheet("font-weight: bold; color: rgb(120, 0, 0); }")
                label.setToolTip(f"Fehler: {error}")
            self.log(error, level=self.ERROR)
            if show_network_error:
                QMessageBox.warning(
                    self.mainWindow(),
                    f"{plugin_menu} v{version} - Fehler",
                    "Bei der Abfrage der Online-Version ist ein Fehler aufgetreten.\n\n"
                    f"{error}\n\n"
                    "Bitte stelle sicher, dass du mit dem Firmennetz verbunden bist.\n"
                    "Sollte sich keine Lösung finden, wende dich bitte an den Support über 'Feedback'"
                )
            return False

        if version == repo_version:

            if repo_commit != commit and commit is not None:
                # commit value must be set in metadata.txt
                if label is not None:
                    label.setText(f"Installiert: v{version} ({release_info}) "
                                  f"- Update verfügbar - Commit-Status geändert")
                    label.setStyleSheet("font-weight: bold; color: rgb(200, 0, 0); }")
                if show_new_version_info:
                    box = QMessageBox()
                    box.setIconPixmap(self.getThemePixmap("propertyicons/plugin-upgrade.svg", size=256).scaled(96, 96))
                    box.setStandardButtons(box.Ok)
                    box.setText(
                        "Eine neue Version steht bereit.\n"
                        f"Aktuell installiert: {version} ({commit})\n"
                        f"Neue Version: {repo_version} ({repo_commit})\n"
                        "\n"
                        "Womöglich fand direkt nach einem regulären Versionsrollout eine minimale Nachkorrektur statt."
                        "\n"
                        "Wir empfehlen das Plugin über QGIS-Erweiterungen zu aktualisieren.\n"
                        "Wichtig: Bevor du ein Projekt aus einer älteren Version lädst, "
                        "erstelle bitte vorher eine Sicherung der zugehörigen Projektdateien."
                    )
                    box.setWindowTitle(f"{plugin_menu} ({version}) - Aktualisierungshinweis")
                    box.exec()

                self.get_plugin().enable_update_action()
                return True
            else:
                if label is not None:
                    label.setText(f"Installiert: v{version} ({release_info}) - aktuell")
                    label.setStyleSheet("color: rgb(0, 0, 255); }")

        elif version > repo_version:
            if label is not None:
                label.setText(f"Installiert: v{version} ({release_info})")
                label.setStyleSheet("font-weight: bold; color: rgb(200, 0, 0); }")
            if show_new_version_info:
                QMessageBox.critical(
                    self.mainWindow(),
                    f"{plugin_menu} ({version}) - Wichtiger Hinweis!",
                    f"Die Versionsüberprüfung ergab, dass die installierte {plugin_menu} ({version}) "
                    f"neuer ist als die über das Repositorium bereitgestellte Version ({repo_version}).\n"
                    "Bitte stelle sicher, dass du keine Version aus unsicheren Quellen installierst."
                )

                # reload plugin data in repo
                if pyplugin_installer.pluginInstaller and not self.get_plugin().is_dev_mode():
                    # clear current qgis network cache
                    QgsNetworkAccessManager.instance().cache().clear()
                    QgsNetworkAccessManager.instance().clearAccessCache()
                    QgsNetworkAccessManager.instance().clearConnectionCache()

                    pyplugin_installer.pluginInstaller.fetchAvailablePlugins(reloadMode=True)

        elif version < repo_version:
            if label is not None:
                label.setText(f"Installiert: v{version} ({release_info}) - Update verfügbar: v{repo_version}")
                label.setStyleSheet("font-weight: bold; color: rgb(200, 0, 0); }")
            if show_new_version_info:
                box = QMessageBox()
                box.setIconPixmap(self.getThemePixmap("propertyicons/plugin-upgrade.svg", size=256).scaled(96, 96))
                box.setStandardButtons(box.Ok)
                box.setText(
                    "Eine neue Version steht bereit.\n"
                    f"Aktuell installiert: {version}\n"
                    f"Neue Version: {repo_version}\n"
                    "\n"
                    "Wir empfehlen das Plugin über QGIS-Erweiterungen zu aktualisieren.\n"
                    "Wichtig: Bevor du ein Projekt aus einer älteren Version lädst, "
                    "erstelle bitte vorher eine Sicherung der zugehörigen Projektdateien."
                )
                box.setWindowTitle(f"{plugin_menu} ({version}) - Update steht bereit :)")
                box.exec()

            self.get_plugin().enable_update_action()

            return True

        return False

    def get_main_plugin(self, next_plugin=False) -> Union[MB, PLUGIN]:
        """ finds the highest available plugin-object.
            Plugin must base on Plugin class.

            :param next_plugin: True to find the next Plugin object in module hierarchy,
                                False to find the manager/the highest Plugin object

        """
        from .base_plugin import Plugin

        current = self.get_parent()

        if current is None and isinstance(self, Plugin):
            # no parent, plugin itself
            return self

        if current is None:
            raise ModuleNotFoundError(f"{self} has no parent and not based on Plugin")

        iterations = 0

        while True:

            if iterations > 100:
                raise StopIteration(f"{self} no plugin found")

            parent = current.get_parent()

            if (parent is None or next_plugin) and isinstance(current, Plugin):
                return current

            current = parent
            iterations += 1

    def get_plugin(self) -> Union[MB, PLUGIN]:
        """ Finds the next available plugin-object.
            Plugin must be based on Plugin class.
        """
        return self.get_main_plugin(next_plugin=True)

    def get_parent(self):
        return self._parent

    def get_toolbar(self, toolbar_name: str, toolbar_object_name: str, main_window: QMainWindow) -> QToolBar:
        """ Creates new toolbar or returns existing one with given params.

            :param toolbar_name: object name for QToolBar
            :param toolbar_object_name: object name for QToolBar
            :param main_window: QMainWindow with toolbar
            :return: found or created QToolBar
        """

        toolbar = None
        # find alls toolbar objects in given main window
        _menus_objects = main_window.findChildren(QToolBar)
        _menus = [x.objectName() for x in _menus_objects]

        if toolbar_object_name not in _menus:
            # no toolbar found with given object name, create new one
            toolbar = main_window.addToolBar(toolbar_name)
            toolbar.setObjectName(toolbar_object_name)
        else:
            for menu in _menus_objects:
                if menu.objectName() == toolbar_object_name:
                    # toolbar found
                    toolbar = menu

        self._toolbars_managed.setdefault(toolbar_object_name, (toolbar, []))

        return toolbar

    def reset_qt_connections(self):
        """ disconnects qt signal from QObject """
        for obj, callable_, *_ in self._connections:
            try:
                obj.disconnect(callable_)
            except (RuntimeError, TypeError):
                ...

        self._connections.clear()

    def unload(self, self_unload: bool = False):
        """ will be called, when module will be unloaded

            :param self_unload: only self unload, defaults to False
        """
        if self.unloaded:
            return

        parent = self.get_parent()

        self.beforeUnload.emit()

        self.reset_qt_connections()

        # uninstall translators
        for translator in self._translators:
            QCoreApplication.instance().removeTranslator(translator)
        self._translators.clear()

        # uninstall locators
        for filter_ in self._filters:
            self.iface.deregisterLocatorFilter(filter_)
        self._filters.clear()
        self.iface.invalidateLocatorResults()

        parent_name = getattr(self.get_parent(), 'module_name', '<no parent>')
        self.log(f"parent module {parent_name} unloads me ({self.module_name})")
        for module_name, module in tuple(self._modules.items()):
            self.log(f"module {self.module_name} unloads module {module_name}")
            module.unload(self_unload)
            self.log(f"module {self.module_name} unloaded module {module_name}")

        self.remove_actions()

        if self_unload and self.get_parent() is not None:
            del self.get_parent()._modules[self.module_name]

        self.afterUnload.emit()

        if isinstance(self, QObject):
            self.deleteLater()

        # unload the loggers
        Logging.unload(self)

        self.unloaded = True

        try:
            plugin = self.get_plugin()
            plugin.submoduleUnloaded.emit(parent, self)
        except (StopIteration, ModuleNotFoundError):
            ...

    def get_option(self, key: str, default=None, type_: type = str, overwrite_module_key: bool = False) -> Any:
        """ Get value from given ini-key.

            :param key: Key to save with in user profile
            :param default: Default value, if not value with key found (None).
            :param type_: Target type, when save ini-value has been fetched.
                          String value will be converted to target type.
            :param overwrite_module_key: True to use key, how it is provided.
                                         False to add module/plugin suffix (default).

        """
        plugin_dir = Path(self.get_plugin().plugin_dir).name
        if not overwrite_module_key:
            if self.get_plugin() is self:
                path = f"plugins/{plugin_dir}/{key}"
            else:
                path = f"plugins/{plugin_dir}/{self.get_plugin().__class__.__name__}/{self.__class__.__name__}/{key}"
        else:
            path = key

        value = QgsSettings().value(path)

        if value is None:
            return default

        if isinstance(value, type_):
            return value

        if type_ in [list, dict]:
            try:
                value = json.loads(value)
            except:
                # fall back to empty
                value = type_()

            return value

        if type_ == int:
            try:
                value = int(value)
            except:
                value = None

            return value

        if type_ == float:
            try:
                value = float(value)
            except:
                value = None

            return value

        if type_ == bool:
            if value == "1" or value.lower() == "true":
                value = True
            elif value == "0" or value.lower() == "false":
                value = False

            return bool(value)

        return value

    def set_option(self, key: str, value: Any, overwrite_module_key: bool = False) -> Any:
        """ Save value to current user profile (ini-file).

            :param key: Key to save with in user profile
            :param value: Value to save. will become a string (with str or json.dumps)
            :param overwrite_module_key: True to use key, how it is provided.
                                         False to add module/plugin suffix (default).

        """
        plugin_dir = Path(self.get_plugin().plugin_dir).name
        if not overwrite_module_key:
            if self.get_plugin() is self:
                path = f"plugins/{plugin_dir}/{key}"
            else:
                path = f"plugins/{plugin_dir}/{self.get_plugin().__class__.__name__}/{self.__class__.__name__}/{key}"
        else:
            path = key

        current_value = self.get_option(key,overwrite_module_key=overwrite_module_key)

        if value is None:
            # remove value from profile
            if current_value is not None:
                # log only, if existing value has been removed
                QgsSettings().remove(path)
                self.log(f"removing QGIS variable '{path}'")

                # emit a plugin signal :)
                plugin = self.get_plugin()
                if plugin is not None:
                    plugin.profileOptionUpdated.emit(path, key, current_value, None)
            return

        if isinstance(value, (list, dict)):
            value = json.dumps(value)
        else:
            value = str(value)

        if current_value != value:
            # log only on difference
            self.log(f"updating QGIS profile variable '{path}' to '{value}'")
            QgsSettings().setValue(path, value)

            # emit a plugin signal :)
            plugin = self.get_plugin()
            if plugin is not None:
                plugin.profileOptionUpdated.emit(path, key, current_value, value)

    # noinspection PyPep8Naming
    @staticmethod
    def getThemeIcon(icon: str):  # pylint: disable=invalid-name
        if not icon.endswith(".svg"):
            icon += ".svg"
        return QgsApplication.getThemeIcon(icon)

    # noinspection PyPep8Naming
    @staticmethod
    def getThemePixmap(icon: str, *args, **kwargs):  # pylint: disable=invalid-name
        if not icon.endswith(".svg"):
            icon += ".svg"
        return QgsApplication.getThemePixmap(icon, *args, **kwargs)

    def __setattr__(self, key, value):
        # some validity checks
        try:
            attr = super(ModuleBase, self).__getattribute__("_unallowed_attribute_types")
        except AttributeError:
            attr = tuple()

        if attr:
            if isinstance(value, attr):
                # escape ><
                s = escape(str(value))
                raise AttributeError(f"attribute {key} with value {s} of "
                                     f"type {type(value).__name__} can not be set")

        if key == "iface":
            raise AttributeError("attribute `iface` is reserved as property to get local `_iface` "
                                 "or import from qgis.utils")

        super().__setattr__(key, value)

    def __contains__(self, item: Union[str, MB]):

        # works, if item is str
        if item in self._modules:
            return True

        return item in self._modules.values()

    def __iter__(self):

        yield from self._modules.items()

    def __getitem__(self, item):
        try:
            return self._modules[item]
        except KeyError:
            raise KeyError(f"module '{self.module_name}' has no sub module '{item}'")

    def __repr__(self):
        name = self.module_name if self.module_name else "< no name >"
        parent = self.get_parent()
        if parent is None:
            parent = "None"
        else:
            parent = parent.module_name
        return f"{self.__class__.__name__}('{name}', parent={parent})"


class UiModuleBase(ModuleBase):
    """ Needs a widget named `MainWidget` in inherited class or ui file.
        `MainWidget` gets a new attribute `_ui_module_base` to have a reference to this module.

        Information: If you want to use this base class to create a directy usable widget, e.g. TabWidget,
                     then call `make_valid` method.

        .. code-block:: python

            # minimum class inheritance structure
            # `QMainWindow` example, depends on use case
            # extra definition of QObject not necessary. It is in QMainWindow
            class MyUiModule(UiModuleBase, QMainWindow):
                ...
    """
    Yes = QMessageBox.Yes
    No = QMessageBox.No

    def __init__(self, **kwargs):
        # will be set via self.setupUI during ui dings bums wuahhahaha
        self.MainWidget: Optional[QWidget] = None

        super().__init__(**kwargs)

        if hasattr(self, 'setupUi'):
            original_setupUi = self.setupUi

            def enhanced_setupUi(*args: Any, **kwargs: Any) -> Any:
                """ Enhances the setupUi method
                    Calls the original setupUi method and then sets up the accessibility Ui
                    right at the creation of the Ui

                    :param args: Positional arguments passed to the original `setupUi` method.
                    :param kwargs: Keyword arguments passed to the original `setupUi` method.
                    :return: The result of the original `setupUi` method.
                """
                # Call the original setupUi method
                result = original_setupUi(*args, **kwargs)
                self._accessibility_config.read(self._accessibility_config_path)
                # Apply accessibility settings if enabled
                if self._accessibility_config.getboolean('accessibility', 'enable', fallback=False):
                    self.setup_accessibility()
                return result

            # Replace the original setupUi with the enhanced version
            self.setupUi = enhanced_setupUi
        else:
            # If setupUi is not defined, still set up accessibility
            self.setup_accessibility()

        self.connect(QApplication.instance().aboutToQuit, self.about_to_quit)

        self._post_check_results: List[str] = []
        self._tab_order_widgets: List[QWidget] = []

        self.__file__: Optional[str] = sys.modules[self.__class__.__module__].__file__

    def setup_accessibility(self):
        """ Sets up enhanced focus borders for various input widgets
            for better accessibility and visibility.
        """

        # Define widget types with their section names and classes
        widget_types = [
            ('QWidget.QLineEdit', QLineEdit),
            ('QWidget.QComboBox', QComboBox),
            ('QWidget.QSpinBox', QSpinBox),
            ('QWidget.QCheckBox', QCheckBox),
            ('QWidget.QPushButton', QPushButton),
            ('QWidget.QListWidget', QListWidget),
            ('QWidget.QTreeWidget', QTreeWidget),
            ('QWidget.QTableWidget', QTableWidget),
            ('QWidget.QTextBrowser', QTextBrowser),
            ('QWidget.QTextEdit', QTextEdit),
            ('QWidget.QListView', QListView),
            ('QWidget.QTreeView', QTreeView),
            ('QWidget.QTableView', QTableView),
            ('QWidget.QRadioButton', QRadioButton),
        ]

        # Ensure the 'enhanced-borders' option exists in the accessibility config
        # If it doesn't exist, create it with a default value of 'true'
        if not self._accessibility_config.has_option('accessibility', 'enhanced-borders'):
            self._accessibility_config.set('accessibility', 'enhanced-borders', 'true')
            # Save the updated configuration to file
            with open(self._accessibility_config_path, 'w', encoding='utf-8') as configfile:
                self._accessibility_config.write(configfile)

        # Read the enhanced borders setting from config (defaults to True if not found)
        enhanced_borders = self._accessibility_config.getboolean('accessibility', 'enhanced-borders', fallback=True)
        # Set border width based on enhanced borders setting: 2px if enhanced, 1px if normal
        border_width = 2 if enhanced_borders else 1

        # Iterate through each widget type and apply accessibility styling
        for section, widget_type in widget_types:
            # Ensure each widget type has its own configuration section
            if not self._accessibility_config.has_section(section):
                # Create new section for this widget type
                self._accessibility_config.add_section(section)
                # Set default focus color for this widget type
                self._accessibility_config.set(section, 'focus', ACCESSIBILITY_DEFAULT_COLOR)
                # Save the configuration with the new section
                with open(self._accessibility_config_path, 'w', encoding='utf-8') as configfile:
                    self._accessibility_config.write(configfile)

            # Read the focus color from config for this widget type
            focus_color = tuple(map(int, self._accessibility_config.get(section, 'focus').split(',')))

            # Find all widgets of this type in the current module and apply styling
            for widget in self.findChildren(widget_type):
                # Create QGIS Style Sheet string
                style = f"""
                    {widget_type.__name__}::focus {{
                        border: {border_width}px solid rgb{focus_color};
                        outline-color: rgb{focus_color};
                    }}
                """
                # Apply the focus styling to the widget
                widget.setStyleSheet(style)

                # Apply additional frame styling for certain widget types when enhanced borders are enabled
                # This is needed because some widgets can't have bigger borders by default
                if (widget_type in (QListWidget, QTreeWidget, QListView, QTreeView, QTableView, QTextBrowser, QTextEdit)
                    and enhanced_borders):
                    widget.setFrameShape(QListWidget.WinPanel)

    def add_subcomponent_module(self,
                                keyword: str,
                                plugin_widget_left: Union[QWidget, None],
                                plugin_widget_right: Union[QWidget, None],
                                module_class: Type[UIMB],
                                use_directly: bool = False,
                                parent: Optional[QWidget] = None,
                                *args: list,
                                **kwargs
                                ) -> UIMB:
        """ Adds a new subcomponent module to this and returns it. It splits the submodule into two sections and adds
            them to the left or right panel of the form layout

            :param keyword: keyword for module dictionary (must be unique)
            :param plugin_widget_left: Left Widget to replace. Needs a parent with a set QLayout. QGridLayout recommended.
            :param plugin_widget_right: Right Widget to replace. Needs a parent with a set QLayout. QGridLayout recommended.
            :param module_class: module class to load
            :param use_directly: use given module class directly as new widget?
            :param parent: parent widget for WindowModality, defaults to None
        """
        if UiModuleBase not in inspect.getmro(module_class):
            raise ValueError(f"'{module_class.__class__.__name__}' must inherit UiBaseModule")

        module = self.add_module(keyword, module_class, parent, *args, **kwargs)
        self.uiModuleAdding.emit(module)

        if use_directly:
            module.make_valid()

        if plugin_widget_left is not None and plugin_widget_right is not None:
            # where to place the new widget into
            parent_widget = plugin_widget_left.parent()
            plugin_layout = parent_widget.layout()

            object_name_left = plugin_widget_left.objectName()
            object_name_right = plugin_widget_right.objectName()
            self.is_object_name_valid(object_name_left)
            self.is_object_name_valid(object_name_right)

            if plugin_layout is not None:
                # load module into existing module
                # more information in `UiModuleBase`
                # gui references are set, load it

                widget: QWidget = module.MainWidget

                if widget is None:
                    raise AttributeError(f"missing MainWidget object name on {self.__class__.__name__}/in ui file")
                widget._ui_module_base = module

                # Counters for obtaining the correct Widgets
                # Counter for SubcomponentLabel, ContentContainer pairs
                count = 1
                # Counter for StaticButton widgets
                button_count = 1
                # Counter for WideLabel widgets
                wide_label_count = 1
                # Counter for WideWidget widgets
                wide_widget_count = 1

                # Lists containing found widgets
                label_references: List[QLabel] = []
                content_references: List[QWidget] = []
                button_references: List[QPushButton] = []
                wide_label_references: List[QLabel] = []
                wide_widget_references: List[QWidget] = []  # labels, widgets, lists, ...

                # Loop until no more elements are found
                while True:
                    # Widget's object names must follow the patterns below, only changing the count respectively
                    # e.g. First WideLabel will be named WideLabel_1, second WideLabel_2 etc.
                    label_reference = f"SubcomponentLabel_{count}"
                    content_reference = f"ContentContainer_{count}"
                    button_reference = f"StaticButton_{button_count}"
                    wide_label_reference = f"WideLabel_{wide_label_count}"
                    wide_widget_reference = f"WideWidget_{wide_widget_count}"

                    # get only specific widgets from expected QWidget-Typ (label, etc.)
                    label: QLabel = widget.findChild(QLabel, label_reference)
                    content: QWidget = widget.findChild(QWidget, content_reference)
                    button: QPushButton = widget.findChild(QPushButton, button_reference)
                    wide_label: QLabel = widget.findChild(QLabel, wide_label_reference)

                    # get a widget to load, no specific QWidget type, any type allowed
                    # QObject, allow any object inherit from QObject
                    wide_widget: QWidget = widget.findChild(QObject, wide_widget_reference)

                    # SubcomponentLabel, ContentContainer pair found
                    if label and content:
                        label_references.append(label)
                        content_references.append(content)
                        count += 1
                    # StaticButton widget found
                    elif button:
                        button_references.append(button)
                        button_count += 1
                    # WideLabel widget found
                    elif wide_label:
                        wide_label_references.append(wide_label)
                        wide_label_count += 1
                    # WideWidget widget found
                    elif wide_widget:
                        wide_widget_references.append(wide_widget)
                        wide_widget_count += 1
                    else:
                        break

                # removes all children from widget to replace
                for child in plugin_widget_left.findChildren(QWidget):
                    child.setParent(None)
                    child.deleteLater()

                for child in plugin_widget_right.findChildren(QWidget):
                    child.setParent(None)
                    child.deleteLater()

                # Append WideLabel widgets to a new row in the GridLayout, span them across both columns
                for k in range(len(wide_label_references)):
                    row = plugin_layout.rowCount()

                    plugin_layout.addWidget(wide_label_references[k], row + k, 0, 1, 2)

                # Append SubcomponentLabel, ContentContainer pairs to a new row in the GridLayout, using column 1 and 2
                for i in range(len(label_references)):
                    row = plugin_layout.rowCount()

                    plugin_layout.addWidget(label_references[i], row, 0)
                    plugin_layout.addWidget(content_references[i], row, 1)

                # Append StaticButton widgets to a new row in the GridLayout, span them across both columns
                for j in range(len(button_references)):
                    row = plugin_layout.rowCount()

                    plugin_layout.addWidget(button_references[j], row + j, 0, 1, 2)

                # Append WideWidgets widgets to a new row in the GridLayout, span them across both columns
                # QWidget, QLabel, QList, ... undefined here, but crossing both columns
                for c in range(len(wide_widget_references)):
                    row = plugin_layout.rowCount()

                    plugin_layout.addWidget(wide_widget_references[c], row + c, 0, 1, 2)

                widget.show()

        self.uiModuleAdded.emit(module)

        try:
            plugin = self.get_plugin()
            plugin.uiSubmoduleAdded.emit(self, module)
        except (StopIteration, ModuleNotFoundError):
            ...

        return module

    def add_ui_module(self, keyword: str, plugin_widget: Union[QWidget, None],
                      module_class: Type[UIMB], use_directly: bool = False,
                      parent: Optional[QWidget] = None, *args: list,
                      **kwargs) -> UIMB:
        """ Add new module to this module and returns it. It can be a ModuleBase or UiModuleBase

        Example:
            self.register_module('A Tab',  # Internale module dict key
                                 self.Widget,  # widget to replace with this module
                                 MyUiModuleType)  #  new module class

            :param keyword: keyword for module dictionary (must be unique)
            :param plugin_widget: Widget to replace. Needs a parent with a set QLayout. QGridLayout recommended.
            :param module_class: module class to load
            :param use_directly: use given module class directly as new widget?
            :param parent: parent widget for WindowModality, defaults to None
        """

        if UiModuleBase not in inspect.getmro(module_class):
            raise ValueError(f"'{module_class.__class__.__name__}' must inherit UiBaseModule")

        module = self.add_module(keyword, module_class, parent, *args, **kwargs)
        self.uiModuleAdding.emit(module)

        if use_directly:
            module.make_valid()

        if plugin_widget is not None:
            # where to place the new widget into
            parent_widget = plugin_widget.parent()
            plugin_layout = parent_widget.layout()

            object_name = plugin_widget.objectName()
            self.is_object_name_valid(object_name)

            if plugin_layout is not None:
                # load module into existing module
                # more information in `UiModuleBase`
                # gui references are set, load it
                widget: QWidget = module.MainWidget
                if widget is None:
                    raise AttributeError(f"missing MainWidget object name on {self.__class__.__name__}/in ui file")
                widget._ui_module_base = module

                # removes all children from widget to replace
                for child in plugin_widget.findChildren(QWidget):
                    child.setParent(None)
                    child.deleteLater()

                replaced_widget_item = plugin_layout.replaceWidget(plugin_widget, widget)
                widget.show()
                plugin_widget.hide()
                plugin_widget.setParent(None)

                # set new object on old object/attribute name in module
                source_object_name = plugin_widget.objectName()
                setattr(self, source_object_name, widget)

                plugin_widget.deleteLater()

                if replaced_widget_item is not None:
                    if replaced_widget := replaced_widget_item.widget():
                        replaced_widget.setParent(None)
                        plugin_layout.removeWidget(replaced_widget)

                # resets object name to origin "MainWidget" from ui becomes e.g. "Frame_Progressbar"
                widget.setObjectName(source_object_name)

        self.uiModuleAdded.emit(module)

        try:
            plugin = self.get_plugin()
            plugin.uiSubmoduleAdded.emit(self, module)
        except (StopIteration, ModuleNotFoundError):
            ...

        return module

    def get_widget(self, object_name: str) -> Optional[QWidget]:
        """ returns widget with given objectName """
        return self.findChild(QWidget, object_name)

    # noinspection PyPep8Naming
    def setupUi(self, widget: QWidget):

        use = None
        for x in reversed(self.__class__.__mro__[1:]):
            if hasattr(x, "setupUi"):
                use = x
                break

        use.setupUi(self, widget)
        self.post_checks()

        if self._post_check_results:

            QMessageBox.warning(
                self,
                "developer post process warnings ( after self.setupUi(self) )",
                "\n".join(self._post_check_results)
            )

    @staticmethod
    def is_object_name_valid(object_name: str) -> bool:
        """ Checks if object name is valid.

        :param object_name: object name
        :return: True if ok, else raises ValueError
        """
        if not fullmatch(r'[A-Za-z_][A-Za-z_0-9]+', object_name):
            raise ValueError(f"object name '{object_name}' is not valid")

        return True

    def is_object_name_free(self, object_name: str) -> bool:
        """ Checks if object name is free and valid.

        :param object_name: object name
        :return: True if ok, else raises ValueError
        """
        objects = self.findChildren(QWidget, object_name)
        names = [x.objectName() for x in objects]

        if not object_name not in names:
            raise ValueError(f"object name '{object_name}' already in use by a child")

        if not object_name not in dir(self):
            raise ValueError(f"object name '{object_name}' already in use by self")

        self.is_object_name_valid(object_name)

        return True

    def _create_frame(self, layout: QGridLayout, object_name: str,
                      position: Optional[Tuple[int, int]] = None) -> QFrame:
        """ creates an empty frame in given layout as dummy.

        :param layout: Layout where to insert new frame
        :param object_name: object_name for new frame and attribute name for `self`
        :param position: tuple(row, column) with position data in layout
        :return: created frame
        """
        # self.is_object_name_free(object_name)
        if not isinstance(layout, QGridLayout):
            raise TypeError(f"wrong layout type, expecting QGridLayout, got {layout.__class__.__name__}")

        # create frame widget for ModuleBase
        page_frame = self._create_widget(layout, QFrame, object_name, position)
        page_frame.setObjectName(object_name)
        page_frame.setFrameShape(QFrame.NoFrame)
        page_frame.setContentsMargins(1, 1, 1, 1)

        # adds QLabel to frame with dummy text
        frame_layout = QGridLayout()
        page_frame.setLayout(frame_layout)
        frame_label = QLabel()
        frame_label.setText("I am a dummy who likes bugs bunny")
        frame_layout.addWidget(frame_label)

        return page_frame

    def _create_widget(self, layout: QGridLayout, widget_type: Type[QWidget], object_name: str,
                       position: Optional[Tuple[int, int]] = None) -> QFrame:
        """ creates an empty frame in given layout as dummy.

        :param layout: Layout where to insert new widget
        :param widget_type: widget type to create
        :param object_name: object_name for new frame and attribute name for `self`
        :param position: tuple(row, column) with position data in layout
        :return: created frame
        """
        # self.is_object_name_free(object_name)
        if not isinstance(layout, QGridLayout):
            raise TypeError(f"wrong layout type, expecting QGridLayout, got {layout.__class__.__name__}")

        # QFrame for ModuleBase
        widget = widget_type()
        widget.setObjectName(object_name)

        if position is None:
            layout.addWidget(widget)
        else:
            layout.addWidget(widget, position[0], position[1])

        setattr(self, object_name, widget)

        return widget

    @staticmethod
    def _get_module(module_or_widget: Union[QWidget, MB]) -> Optional[Union[UIMB, QWidget]]:

        # simple loaded element
        if hasattr(module_or_widget, '_ui_module_base'):
            return getattr(module_or_widget, '_ui_module_base')

        iteration = 0
        while not isinstance(module_or_widget, ModuleBase):
            if iteration > 100:
                raise StopIteration(f"no module found for object '{module_or_widget.objectName()}'")

            if module_or_widget is None:
                return None

            module_or_widget = module_or_widget.parent()

            # parent has no this information
            if hasattr(module_or_widget, '_ui_module_base'):
                return getattr(module_or_widget, '_ui_module_base')

            iteration += 1

        return module_or_widget

    @staticmethod
    def is_my_plugin_in_dev_mode() -> bool:
        """
        checks if the plugin this submodule is a submodule to is in dev mode
        """
        my_plugin_name = get_expected_plugin_folder_name()
        settings_path = f"plugins/{my_plugin_name}/Developer-Modus"
        dev_mode = QgsSettings().value(settings_path) is not None
        return dev_mode

    @classmethod
    def get_ui_file(cls, python_file: str) -> str:
        """ Returns found ui file in same directory of `python_file`
            and instead of 'py' as file ending looks for 'ui'.
            Python file and ui file must be in same folder.

        :param python_file: path to python file -> __file__
        :return:
        """
        base = os.path.basename(python_file)
        folder = os.path.dirname(python_file)

        if not base.endswith(FILE_ENDINGS_PY_TO_UI):
            raise ValueError(f"file name '{base}' must end with one value of '{FILE_ENDINGS_PY_TO_UI}'")

        # replace file ending with ".ui"
        ui_file = re_sub(FILE_ENDINGS_RE_COMPILED, ".ui", base)

        ui_file_path = os.path.join(folder, ui_file)
        if not Path(ui_file_path).is_file():
            raise FileNotFoundError(f"no ui file found '{ui_file_path}'")

        return ui_file_path

    @classmethod
    def get_uic_classes(cls, python_or_ui_file: str, force_compile: bool = False) -> Tuple[Any, Type[QWidget]]:
        """
        Returns ui classes for given .py/.ui file.
        When called in a developer environment (dev mode of the plugin is active where module_base is a submodule to)
        or force_compile is set to True, .py files are always generated when this method is called.
        When dev mode is inactive, either a corresponding .py file is used for the pyqt classes, or,
        if a .ui file is found, uic.loadUiType is used to dynamically generate the pyqt ui class.

        .. code-block: python

            FORM_CLASS, _ = UiModuleBase.get_uic_classes(__file__)
            FORM_CLASS: 'Ui'
            try:
                from .my_cool_plugin_generated_ui import Ui as FORM_CLASS # overwrite FORM_CLASS for type hinting, use your module instead of 'my_cool_plugin'

            except ModuleNotFoundError:
                pass

        :param python_or_ui_file: python file path or path to ui file
        :param force_compile: set to True to always recompile (like in dev mode). Defaults to False.
        :return: tuple of form class (most needed) and Qt base class from Qt Designer, e.g QMainWindow
        """

        if not python_or_ui_file.endswith((".ui", ) + FILE_ENDINGS_PY_TO_UI):
            raise ValueError(f"unexpected file ending for '{python_or_ui_file}'")

        if python_or_ui_file.endswith(FILE_ENDINGS_PY_TO_UI):
            # python file is given, get ui file path
            python_or_ui_file = cls.get_ui_file(python_or_ui_file)

        if cls.is_my_plugin_in_dev_mode() or force_compile:
            from .functions import generate
            result = generate(Path(python_or_ui_file))

        # CLIENT MODE, .py wont be created at runtime, only used, if found
        pyuic_file = Path(python_or_ui_file).with_stem(Path(python_or_ui_file).stem + '_generated_ui').with_suffix('.py')
        if not pyuic_file.exists():
            # compiled .py doesnt exist, use loadUiType with ui file (legacy method)
            # print(f"compiled pyuic file not found for {python_or_ui_file}, using get_uic_classes()")
            return cls.get_dynamic_uic_classes(python_or_ui_file)
        else:
            return cls.get_compiled_uic_classes(pyuic_file.as_posix(), python_or_ui_file)

    @classmethod
    def get_compiled_uic_classes(cls, pyuic_compiled_file: str, ui_file: str) -> Tuple[Any, Type[QWidget]]:
        # import from generated .py
        # https://stackoverflow.com/questions/67631/how-can-i-import-a-module-dynamically-given-the-full-path
        # FORM_CLASS:
        module_name = Path(pyuic_compiled_file).stem
        spec = importlib.util.spec_from_file_location(module_name, pyuic_compiled_file)
        ui_module = importlib.util.module_from_spec(spec)
        sys.modules[module_name] = ui_module
        spec.loader.exec_module(ui_module)

        return ui_module.Ui, get_ui_class(ui_file)

    @classmethod
    def get_dynamic_uic_classes(cls, python_or_ui_file: str) -> Tuple[Any, Type[QWidget]]:
        """ Returns objects/classes from uic.loadType.
            Python file and ui file must be in same folder.

            See `qgis.PyQt.uic.loadUiType` for more information.

            :param python_or_ui_file: python file path or path to ui file
            :return: form class (most needed) and Qt base class from Qt Designer, e.g QMainWindow
        """
        if not python_or_ui_file.endswith((".ui", ) + FILE_ENDINGS_PY_TO_UI):
            raise ValueError(f"unexpected file ending for '{python_or_ui_file}'")

        if python_or_ui_file.endswith(FILE_ENDINGS_PY_TO_UI):
            # python file is given, get ui file path
            python_or_ui_file = cls.get_ui_file(python_or_ui_file)

        form_class, base_class = uic.loadUiType(python_or_ui_file)

        return form_class, base_class

    @classmethod
    def get_tab_stops_from_ui_file(cls, python_or_ui_file: str) -> List[str]:
        """ Returns a list of defined Tabstops in the given ui file. """

        if not python_or_ui_file.endswith((".ui", ) + FILE_ENDINGS_PY_TO_UI):
            raise ValueError(f"unexpected file ending for '{python_or_ui_file}'")

        if python_or_ui_file.endswith(FILE_ENDINGS_PY_TO_UI):
            # python file is given, get ui file path
            python_or_ui_file = cls.get_ui_file(python_or_ui_file)

        object_names = []

        # parse the UI file
        document = QDomDocument()
        document.setContent(Path(python_or_ui_file).read_bytes(), False)

        # get the object names from the tab stops
        tab_stops_parent: QDomElement = document.firstChildElement("ui").firstChildElement("tabstops")
        tab_stops = tab_stops_parent.elementsByTagName("tabstop")
        for i in range(tab_stops.size()):
            object_names.append(tab_stops.item(i).toElement().text().strip())

        return object_names

    def get_tab_stop_widgets(self, object_names: List[str]):
        main_object = self.MainWidget or self

        objects = []
        for name in object_names:
            obj = main_object.findChild(QWidget, name)
            if obj is not None:
                objects.append(obj)

                # special Handling to unpack children from pre defined qt classes, e.g. from Qgis directly
                if isinstance(obj, QgsFileWidget):
                    objects.extend(obj.findChildren(QWidget))

        return objects

    def initialize_tab_stop_widgets(self):
        names = self.get_tab_stops_from_ui_file(self.__file__)
        self.tab_order_widgets = self.get_tab_stop_widgets(names)
        if not self.tab_order_widgets and names:
            raise ValueError(f"No Widgets found with names: {names}")

    def insert_tab_stop_widgets_behind(self, widget_behind: QWidget, widgets: List[QWidget]):
        """ Inserts the given widgets behind the `widget_behind` on defined widgets.
            `self._tab_order_widgets` must be filled first and `widget_behind` has to be in this list.
        """
        len_ = len(self._tab_order_widgets)
        index = self._tab_order_widgets.index(widget_behind)
        self._tab_order_widgets = self._tab_order_widgets[:min(index + 1, len_)] + widgets + self._tab_order_widgets[min(index + 1, len_):]

    def insert_tab_stop_widgets_before(self, widget_before: QWidget, widgets: List[QWidget]):
        """ Inserts the given widgets before the `widget_before` on defined widgets.
            `self._tab_order_widgets` must be filled first and `widget_before` has to be in this list.
        """
        index = self._tab_order_widgets.index(widget_before)
        self._tab_order_widgets = self._tab_order_widgets[:index] + widgets + self._tab_order_widgets[index:]

    def reload_tab_stop_order(self):
        """ Sets the tab stop order with defined tab stops """
        widgets = self.tab_order_widgets
        # clean up widget list
        remove = []
        for w in widgets:
            try:
                w.objectName()  # raises RuntimeError, when no more available
            except RuntimeError:
                remove.append(w)

        for w in remove:
            widgets.remove(w)

        for i in range(len(widgets) - 1):
            QWidget.setTabOrder(widgets[i], widgets[i + 1])

    @property
    def tab_order_widgets(self) -> List[QWidget]:
        """ Overwrite this property, when neccessary """
        return self._tab_order_widgets

    @tab_order_widgets.setter
    def tab_order_widgets(self, widgets: List[QWidget]):
        """ Overwrite this property, when neccessary """
        if not isinstance(widgets, list):
            raise TypeError("widget is not a list")
        self._tab_order_widgets = widgets

    def make_valid(self):
        """ make object valid to use itself als 'MainWidget' """
        if getattr(self, 'MainWidget', None) is not None:
            raise TypeError("make_valid cannot be called, already 'MainWidget' here")

        self.MainWidget: QWidget = self

    def post_checks(self):
        """ Runs some basic checks.

            Following checks are made:

                * QComboBox's have expected sizeAdjustPolicy for adjusting in layouts correctly

            This method has to be called manually in __init__.
        """

        # check combo boxes, if their sizeAdjustPolicy is ok for layouts
        for child in self.findChildren(QComboBox):
            policy = child.sizeAdjustPolicy()
            expects = (QComboBox.AdjustToMinimumContentsLengthWithIcon,
                       QComboBox.AdjustToContents)
            if policy not in expects and child.objectName():
                text = f"post_checks(): QComboBox {child.objectName()} " \
                       f"has possible invalid Qt configuration in 'sizeAdjustPolicy'. " \
                       f"Got '{policy}' expecting '{expects}' "

                if text in self._post_check_results:
                    continue

                self.log(text, level=self.WARNING)
                self._post_check_results.append(text)

    def replace_with_empty_frame(self):
        """ unload this module and replace it with an empty frame """

        layout = self.MainWidget.parent().layout()
        if layout is None:
            # print("not layout found for", self.__class__.__name__, "parent of MainWidget")
            return

        if not isinstance(layout, QGridLayout):
            raise NotImplementedError(f"Layout '{layout.__class__.__name__}' is not a QGridLayout. Not implemented yet")

        for column in range(layout.columnCount()):
            for row in range(layout.rowCount()):

                # locate item at row and column in grid
                layout_item = layout.itemAtPosition(row, column)
                layout_widget = layout_item.widget()
                module = self._get_module(layout_widget)
                if not hasattr(layout_widget, 'MainWidget') and not hasattr(module, 'MainWidget'):
                    continue

                module = self._get_module(layout_widget)
                if self is module:
                    frame = self.get_parent()._create_frame(layout, layout_widget.objectName(), (row, column))
                    for child in frame.findChildren(QWidget):
                        child.setParent(None)
                        child.deleteLater()
                    replaced_widget_item = layout.replaceWidget(self.MainWidget, frame)
                    if replaced_widget_item is not None:
                        if replaced_widget := replaced_widget_item.widget():
                            layout.removeWidget(replaced_widget)
                            replaced_widget.setParent(None)

                    self.unload(True)
                    return

        raise TypeError("Nothing found to replace :o")

    def replace_widget_with_class(self, current: QWidget, class_: Type[QWidget]) -> QWidget:
        """ replace current QWidget with another base class """
        new = class_(parent=current.parent())

        # copy font settings
        old_font = current.font()
        new.setFont(old_font)

        # copy the tooltip, if available
        if hasattr(current, "toolTip") and hasattr(new, "setToolTip"):
            new.setToolTip(current.toolTip())
        if is_widget_compatible(current, class_):
            apply_widget_options(current, new)
        else:
            self.log(f"No options applied from the given {current.objectName()} ({type(current).__name__}) "
                     f"to the new type {class_.__name__}", level=self.DEBUG)

        return self.replace_widget_with_widget(current, new)

    def replace_widget_with_widget(self, current: QWidget, new: QWidget) -> QWidget:
        """ replace current QWidget with another widget """
        name = current.objectName()
        layout = current.parent().layout()
        current.setObjectName("")

        # replace old widget in layout with new widget
        replaced_widget_item = layout.replaceWidget(current, new)
        new.show()

        # copy font settings
        old_font = current.font()
        new.setFont(old_font)

        current.setParent(None)
        current.hide()
        current.deleteLater()
        if replaced_widget_item is not None:
            if replaced_widget := replaced_widget_item.widget():
                layout.removeWidget(replaced_widget)

        # re-set the object on attribute name
        if name:
            setattr(self, name, new)
            new.setObjectName(name)

        return new

    def about_to_quit(self):
        """ QCoreApplication is about to quit/close """

        self.log(f"QApplication is about to quit, cancel progress")

        # cancel something?
        if hasattr(self, "cancel"):
            self.cancel()

    def question(self, title: str, question: str, parent: Optional[QWidget] = None) -> QMessageBox.StandardButton:
        """ Create QMessageBox from question type.

            :param title: message box's title
            :param question: message box's question
            :param parent: message box's parent widget, defaults to `self`
        """
        if parent is None:
            parent = self

        return QMessageBox.question(parent, title, question)

    def information(self, title: str, text: str, parent: Optional[QWidget] = None) -> QMessageBox.StandardButton:
        """ Create QMessageBox from information type.

            :param title: message box's title
            :param text: message box's text
            :param parent: message box's parent widget, defaults to `self`
        """
        if parent is None:
            parent = self

        return QMessageBox.information(parent, title, text)

    def critical(self, title: str, text: str, parent: Optional[QWidget] = None) -> QMessageBox.StandardButton:
        """ Create QMessageBox from critical type.

            :param title: message box's title
            :param text: message box's text
            :param parent: message box's parent widget, defaults to `self`
        """
        if parent is None:
            parent = self

        return QMessageBox.critical(parent, title, text)

    def warning(self, title: str, text: str, parent: Optional[QWidget] = None) -> QMessageBox.StandardButton:
        """ Create QMessageBox from warning type.

            :param title: message box's title
            :param text: message box's text
            :param parent: message box's parent widget, defaults to `self`
        """
        if parent is None:
            parent = self

        return QMessageBox.warning(parent, title, text)

    def unload(self, self_unload: bool = False):
        """ will be called, when module will be unloaded

            :param self_unload: only self unload, defaults to False
        """
        if self.unloaded:
            return

        parent = self.get_parent()

        super().unload(self_unload)

        try:
            plugin = self.get_plugin()
            plugin.uiSubmoduleUnloaded.emit(parent, self)
        except (StopIteration, ModuleNotFoundError):
            ...

        if isinstance(self, QWidget):
            self.close()
            self.setParent(None)
            self.deleteLater()
