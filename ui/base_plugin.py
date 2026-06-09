# -*- coding: utf-8 -*-
# SPDX-FileCopyrightText: 2025 Deutsche Telekom Technik GmbH <f.vonstudsinske@telekom.de>
# SPDX-License-Identifier: GPL-3.0-only

import os
import os.path
import sys
import traceback

if os.name == "nt":
    # Windows platform, win32 might by available
    try:
        import win32process
        import win32api
    except ModuleNotFoundError:
        win32process = None
        win32api = None
else:
    win32process = None
    win32api = None

from pathlib import Path
from pkg_resources import packaging

from qgis.PyQt.QtCore import (QObject, pyqtSignal, QTimer, Qt)

from qgis.PyQt.QtWidgets import (QMessageBox, QTabWidget, QMenu)
from qgis.PyQt.QtGui import QGuiApplication

from qgis.gui import QgsVertexMarker, QgsRubberBand
from qgis.core import (QgsSettings, QgsError, Qgis, QgsApplication)

from typing import List, Union, Optional

from .functions import get_expected_plugin_folder_name, is_installed_in_qgis_plugin_folder, get_expected_plugin_path
from .base_class import ModuleBase
from ..constants import UPDATE_HINT_COMPILED


class Plugin(ModuleBase, QObject):
    """ Use this class in plugin.py to identify it as a plugin class.
        This is necessary to find correct module to use plugin path attributes, e.g. "plugin_dir"

        .. Mark the plugin via Python console in QGIS as dev:

            .. code-block:: python

                # you need the plugins folder name
                plugin = qgis.utils.plugins['plugin_folder_name']
                plugin.set_dev_mode(True)

                # deactivate
                plugin.set_dev_mode(False)

    """
    # signals to catch added/unloaded submodules somewhere in this plugin
    submoduleAdded = pyqtSignal(object, object, name="submoduleAdded")
    submoduleUnloaded = pyqtSignal(object, object, name="submoduleUnloaded")

    # signals to catch added/unloaded Ui submodules somewhere in this plugin
    uiSubmoduleAdded = pyqtSignal(object, object, name="uiSubmoduleAdded")
    uiSubmoduleUnloaded = pyqtSignal(object, object, name="uiSubmoduleUnloaded")

    # plugin update available
    updateAvailable = pyqtSignal(name="updateAvailable")
    updateInstalled = pyqtSignal(str, name="updateInstalled")

    # option updated with set_option in a loaded module
    # signal: config-path, key, old value, new value
    profileOptionUpdated = pyqtSignal(str, str, object, object, name="profileOptionUpdated")

    pythonErrorLogged = pyqtSignal(name="pythonErrorLogged")

    def __init__(self, *args, **kwargs):
        # default values
        kwargs.setdefault("parent", None)
        kwargs["plugin"] = self
        kwargs["name"] = self.plugin_name

        QObject.__init__(self, None)
        ModuleBase.__init__(self, **kwargs)

        # may contain collected Python errors caught by the QGIS ui
        self.QGIS_Python_Errors = []

        # update action to update the plugin via the UI
        self.update_action = None

        # developer / debug options
        self.force_dev_mode = False

        # list of drawings to auto remove vertex markers on canvas
        self.drawings: List[Union[QgsVertexMarker, QgsRubberBand]] = []

        self.grass_icons = str(Path(sys.executable).parent.parent / "apps"
                               / "grass" / "grass78" / "gui" / "icons" / "grass")

        # setup QTimer
        self.__timer = QTimer(None)

        self.__compiled_files = []

    def clear_options(self):
        """ Clears/Removes all settings for this plugin from QGIS """
        plugin_dir = Path(self.get_plugin().plugin_dir).name
        path = f"plugins/{plugin_dir}"
        QgsSettings().remove(path)
        QgsSettings().sync()

    def initGui(self):
        self.connect(QGuiApplication.instance().focusObjectChanged,
                     self.__remove_basic_authentication)

    def __remove_basic_authentication(self, object_):
        """ Removes Tab for Basic Authentication.
            Prevent User from typing credentials in plaintext into project files.
        """

        if object_ is None:
            return

        if not hasattr(object_, "window"):
            return

        # Get parent window (QDialog, QWidget, QMainWindow) from current object_
        window = object_.window()

        if window.objectName() == "QgsNewHttpConnectionBase":
            # if window is the expected authentication dialog
            # iter over each tab widget
            children = window.findChildren(QTabWidget)
            for tab in children:
                # find tab widget with object name "tabAuth"
                if tab.objectName() == "tabAuth":
                    indices = []
                    for i in range(tab.count()):
                        # remember all indices with object name
                        if tab.widget(i).objectName() == "tabBasic":
                            self.log("QGIS's Basic Authentication Tab removed from authentication settings",
                                     level=self.WARNING)
                            indices.append(i)

                    indices.sort(reverse=True)
                    for i in indices:
                        # remove tabs
                        tab.removeTab(i)

    @property
    def dev_secret(self):
        return "Developer-Modus"

    def timer(self) -> QTimer:
        return self.__timer

    def is_dev_mode(self):
        """ Returns `True` if in development mode.
            Checks `force_dev_mode` state too and prefer this, if True.
        """
        return self.force_dev_mode or self.get_option(self.dev_secret) is not None

    def set_dev_mode(self, mode):
        """ Sets the current mode, if this plugin is in dev mode or not.
            Does not deactivate the forced dev mode in metadata.txt from plugin root folder.
        """

        if mode:
            self.set_option(self.dev_secret, "potato")
        else:
            self.set_option(self.dev_secret, None)

    def unload(self, self_unload: bool = False):
        QgsSettings().sync()
        return super().unload(self_unload)

    def enable_update_action(self):
        if self.update_action is not None:
            return

        self.update_action = self.add_action(
            f"Neue Version installieren",
            self.getThemeIcon("propertyicons/plugin-upgrade.svg"),
            lambda: self.ask_for_new_installation(),
            tool_tip="Plugin aktualisieren")

        self.updateAvailable.emit()

    def get_menu(self) -> Optional[QMenu]:
        """ Returns the plugin QMenu within the QGIS plugin menu bar (if exists) """
        menu = self.iface.pluginMenu()
        if not menu:
            return None

        for action in menu.actions():
            if action.text() == self.plugin_menu_name:
                return action.menu()

    def ask_for_new_installation(self):

        if self.is_compiled():

            box = QMessageBox()
            box.setIconPixmap(self.getThemePixmap("propertyicons/plugin-upgrade.svg", size=256).scaled(96, 96))
            box.setStandardButtons(box.Ok)
            box.setText(
                f"<p>Aktuell installiert: {self.plugin_version}</p>"
                f"<p>Version verfügbar: {self.repo_version}</p>"
                "<p><strong>Die neue Version kann nur nach folgenden Schritten geladen werden:</strong></p>"
                f"{UPDATE_HINT_COMPILED.format(NAME=self.plugin_name)}"
            )
            box.setTextFormat(Qt.RichText)
            box.setWindowTitle(f"{self.plugin_name} - Neue Version manuell laden")
            box.exec()
            return

        box = QMessageBox()
        box.setIconPixmap(self.getThemePixmap("propertyicons/plugin-upgrade.svg", size=256).scaled(96, 96))
        box.setStandardButtons(box.Yes | box.No)
        box.setText(f"Aktuell installiert: {self.plugin_version}\n"
                    f"Version verfügbar: {self.repo_version}\n\n"
                    f"Neue Version für {self.plugin_name} installieren?")
        box.setWindowTitle(f"{self.plugin_name} - Neue Version installieren")
        reply = box.exec()

        if reply != box.Yes:
            return

        self.install_new_version()

    def get_release_info(self) -> str:
        """ Returns a release info text for the current plugin.

            Can return "Hauptversion", "Entwicklerversion", "Testversion" or "ubk. Version".
        """
        root = get_expected_plugin_path()

        # is this plugin a main release (ending with _main)
        plugin_folder_name = root.name
        if (root / ".git").is_dir():
            # might be the locally cloned git folder
            release_info = "Entwicklerversion (.git)"
        elif plugin_folder_name.endswith("_main") and self.commit:
            release_info = "Hauptversion"
        elif self.commit:
            # if the commit hash is available, it is installed from a repository
            release_info = "Testversion"
        else:
            # unknown version/installation
            release_info = "ubk. Version"

        return release_info

    def install_new_version(self):
        """
        Install a new version based on the current available plugin.

        .. code-block:: python

            # manual check for new version
            plugin = qgis.utils.plugins['plugin_folder']
            print("commit", plugin.commit)
            print("plugin_version", plugin.plugin_version)
            print("repo_version", plugin.repo_version)
            plugin.set_ui_version_info()

        """
        if self.is_compiled():
            raise OSError(f"Update of the {self.plugin_name} due to pyd/dll libraries not possible")

        if not hasattr(self.get_plugin().repo_version_data, "qgis_minimum_version"):
            raise OSError(f"No repository entry found for plugin {self.plugin_name}")

        from ..qgis.functions import update_qgis_plugin

        name = Path(self.plugin_dir).name
        update_qgis_plugin(name, self.logger, reload_plugins=True, force_installation=True)

        self.updateInstalled.emit(name)

    def is_compiled(self) -> bool:
        """ Returns True, if plugin has compiled files, e.g. DLL or PYD.
            Call this method only via the main plugin object.
            It should inherit this class and will have the "plugin_dir" attribute.

            If available, loaded Assemblies from the .NET environment will be checked as well.
        """
        root = get_expected_plugin_path()
        plugin_path = os.path.normcase(os.path.normpath(str(root)))
        
        if os.name == "nt":
            try:
                # try to import clr for pythonnet/.NET
                import clr
                import System
                import System.Reflection
                check_pythonnet = True
            except ModuleNotFoundError:
                check_pythonnet = False
        else:
            check_pythonnet = False

        # estimate state and find files
        loaded_libraries = []

        if check_pythonnet:
            # Python package: pythonnet
            # does perform the check only for already loaded dlls from the plugin path
            # get the current app domain
            app_domain = System.AppDomain.CurrentDomain
            # check each loaded assembly to the current app domain
            for assembly in app_domain.GetAssemblies():
                try:
                    # normalize the case and the path
                    assembly_path = os.path.normcase(os.path.normpath(assembly.Location))
                    if assembly_path.startswith(plugin_path):
                        loaded_libraries.append(assembly_path)
                except System.NotSupportedException:
                    # location is not available for this assembly, skip it, not checkable
                    continue

        # check the current loaded dlls/pyds from python, in packages are available
        # only Windows
        if win32api is not None and win32process is not None:
            for h in win32process.EnumProcessModules(win32process.GetCurrentProcess()):
                library_path = os.path.normcase(os.path.normpath(win32api.GetModuleFileName(h)))

                if library_path.startswith(plugin_path):
                    # loaded library is in the current plugin path (somewhere)
                    loaded_libraries.append(library_path)

        self.__compiled_files = loaded_libraries

        return bool(loaded_libraries)

    @staticmethod
    def get_plugin_from_qgis_utils():
        """ Returns Plugin object from default path, starting form current dir.
            Optional None, if not found.

        """
        # up to root directory
        excepted_plugin_name = get_expected_plugin_folder_name()

        from qgis.utils import plugins

        if excepted_plugin_name in plugins:
            # activated plugin found
            return plugins[excepted_plugin_name]

        # plugin name not in loaded plugins found
        return None

    def qgis_message_received_python_error(self, msg_text: str, tag: str, level: int = Qgis.MessageLevel):
        """ per default attached with QgsMessageBar to track new messages, e.g. python errors

            :param msg_text: message bar text
            :param tag message tab(tag) in Qgis
            :param level: priority level
        """
        try:
            msg_text = msg_text.encode('utf-8').decode('utf-8').lower()
        except UnicodeEncodeError:
            # if the message text cannot be encoded/decoded, it is not processable, just skip it
            return False

        # logged msg_text via QgsApplication.logMessage contains a text to identify a Python error
        error_text = QgsApplication.translate("Python", "Python error").lower()  # DE: Python-Fehler, ...
        if msg_text.startswith(error_text):

            if hasattr(sys, "last_type"):
                cur_type = sys.last_type
            else:
                cur_type = None
            if hasattr(sys, "last_value"):
                cur_value = sys.last_value
            else:
                cur_value = None
            if hasattr(sys, "last_traceback"):
                cur_traceback = sys.last_traceback
                cur_trace_err = str(traceback.format_tb(cur_traceback))
            else:
                cur_traceback = None
                cur_trace_err = ""

            # remove these attributes from sys
            # see: https://docs.python.org/3/library/sys.html#sys.last_traceback
            if hasattr(sys, "last_value"):
                del sys.last_value

            if hasattr(sys, "last_type"):
                del sys.last_type

            if hasattr(sys, "last_traceback"):
                del sys.last_traceback
            if cur_traceback is None and cur_value is None and cur_type is None:
                # just skip this error message
                return

            self.QGIS_Python_Errors.append(cur_trace_err)
            self.python_error_checkcache()

            self.log(cur_trace_err, level=self.CRITICAL)

            self.pythonErrorLogged.emit()

            return True

        return False

    def python_error_checkcache(self):
        """ Checks how many errors are logged and informs user """

        from qgis.utils import iface

        count = len(self.QGIS_Python_Errors)
        if (count % 3) == 0 and count > 0:
            QMessageBox.information(
                iface.mainWindow(),
                'Python-Fehler Information',
                'Es liegt mindestens ein Python-Fehlerbericht vor.\n'
                f'Berichte: {count}\n\n'
                'Diese können per E-Mail an ein Postfach zur Fehlerbehebung bei Störungen gesendet werden.',
                QMessageBox.Ok,
                QMessageBox.NoButton
            )

    def python_errors_to_string(self, as_qgs_error: bool = False) -> Union[str, QgsError]:
        """ Joins all logged python errors to a string or creates a QgsError object.

            :param as_qgs_error: returns joined string or QgsError object
        """
        if as_qgs_error:
            errors = QgsError("Bitte markieren, kopieren und der Feedback-E-mail anfügen.\n"
                              "'Details >>' öffnen!",
                              f"{self.plugin_name}-Fehlerberichte ('Details >>' öffnen!)")
            # zeigen mit QgsErrorDialog.show(errors, None)
        else:
            errors = ""
        if self.QGIS_Python_Errors:
            if as_qgs_error:
                errors.append("", "****************************************************")
                errors.append("", f"-------- Beginn Fehlerberichte [{len(self.QGIS_Python_Errors)}] --------")
                for i, err in enumerate(self.QGIS_Python_Errors):
                    errors.append(err, f"~~~~ Fehler-Nummer {i + 1}")
                errors.append("", "--------- Ende Fehlerberichte ---------")
                errors.append("", "****************************************************")
            else:
                errors += "****************************************************\n"
                errors += "-------- Beginn Fehlerberichte --------\n"
                for i, err in enumerate(self.QGIS_Python_Errors):
                    errors += f"~~~~ Fehler-Nummer {i + 1}\n{err}\n"
                errors += "--------- Ende Fehlerberichte ---------\n"
                errors += "****************************************************\n\n"
        return errors

    @staticmethod
    def is_qgis_plugin():
        return is_installed_in_qgis_plugin_folder()
