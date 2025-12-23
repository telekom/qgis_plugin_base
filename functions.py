# -*- coding: utf-8 -*-
# SPDX-FileCopyrightText: 2025 Deutsche Telekom Technik GmbH <f.vonstudsinske@telekom.de>
# SPDX-License-Identifier: GPL-3.0-only

import os
import site
import sys
import re
import shutil

from collections import OrderedDict
from datetime import datetime
from pathlib import Path
from re import Pattern
from typing import List, Optional, Union, Tuple

from qgis.core import QgsApplication
from qgis.gui import QgisInterface
from qgis.PyQt.QtWidgets import QMessageBox

from . import constants


def qgis_unload_keyerror(plugin_dir: str) -> None:
    """ A special KeyError workaround in QGIS unloading mechanism of plugins.

        :param plugin_dir: plugin path
    """
    import qgis.utils

    _loaded_qgs_mod = {}
    count = 0

    # Stored Modules from QGIS
    plugin_dir = os.path.basename(os.path.normpath(plugin_dir))
    loaded_qgs_mod = [i for i in qgis.utils._plugin_modules[plugin_dir]]

    # Stored Modules from sys
    loaded_sys_mod = [i for i in sys.modules if i.startswith(plugin_dir)]

    for smod in loaded_sys_mod:
        if smod not in loaded_qgs_mod:
            loaded_qgs_mod.append(smod)  # Add to qgis-list

    for qmod in loaded_qgs_mod.copy():
        if qmod not in loaded_sys_mod:
            loaded_qgs_mod.remove(qmod)  # Del from qgis-list

    for mod in loaded_qgs_mod.copy():
        path = mod.split(".")
        path_len = len(mod.split("."))
        if path_len > 1:
            key = path[0] + path[1]
        elif path_len == 1:
            key = path[0]
        else:
            key = 'ERROR'
        key = str(path_len) + "/" + key + "/" + str(count)
        count += 1
        _loaded_qgs_mod.setdefault(key, mod)

    _loaded_qgs_mod = OrderedDict(sorted(_loaded_qgs_mod.copy().items(),
                                         reverse=True))
    sorted_list = [value for key, value in _loaded_qgs_mod.items()]
    qgis.utils._plugin_modules[plugin_dir] = sorted_list


def is_qgis_ltr() -> bool:
    """ is current qgis version a LTR? """
    exec_path = sys.executable
    value = "qgis-ltr-bin" in exec_path

    return value


def check_qgis_algorithm(iface: Optional[QgisInterface] = None, inform: bool = False,
                         algorithms: Optional[list] = None) -> List[str]:
    """ Checks if all important/given processing algorithms are available.
        If missing algorithms found, they can be directly shown to the use.

        :param iface:
        :param inform: directly popup?
        :param algorithms: list of algorithm names

        :return: list of not found algorithms
    """
    if algorithms is None:
        algorithms = constants.DEFAULT_ALGORITHM_NAMES

    not_found = []

    registry = QgsApplication.processingRegistry()

    parent = iface
    if isinstance(parent, QgisInterface):
        parent = parent.mainWindow()

    for a in algorithms:
        if registry.algorithmById(a) is None:
            not_found.append(a)

    if not_found:
        if inform:
            QMessageBox.warning(
                parent,
                'QGIS-/Plugin-Fehler',
                'Es wurde mindestens ein Verarbeitungsmodul (von QGIS) nicht gefunden.\n\n'
                'Eine vollständige Nutzung des Plugins ist gegebenenfalls nicht möglich.\n'
                'Nicht gefunden: %s\n\n'
                'Bitte folgendes prüfen:\n'
                '    1. QGIS-Erweiterung (Plugin) `Processing` ist aktiviert\n'
                '    2. Nach Update des gestarteten Plugins suchen\n'
                '    3. kompatible QGIS-Version in Verwendung\n' % ", ".join(not_found),
                QMessageBox.Ok,
                QMessageBox.NoButton
            )
        return not_found
    return []


def remove_timestamps(path_with_stamp: str, set_new_timestamp: bool = False) -> str:
    """ removes possible timestamps from given string and returns cleaned string

        :param path_with_stamp: str with possible timestamps
        :type: str
        :param set_new_timestamp: generate new timestamp
        :type: Optional[str]
        :return: cleaned string without timestamps
        :rtype: str
    """
    # regex pattern to remove date timestamps
    clean_date_pattern = r"_\d{1,4}-\d{1,2}-\d{1,4}"
    # regex pattern to remove additional time timestamps
    clean_time_pattern = r"_\d+-\d+"
    # remove all date timestamps from given string
    cleaned_str = re.sub(clean_date_pattern, "", path_with_stamp)
    # remove all time timestamps eventually set
    cleaned_str = re.sub(clean_time_pattern, "", cleaned_str)

    # set new timestamp
    if set_new_timestamp:
        cleaned_str += "_" + datetime.now().strftime("%Y-%m-%d_%H-%M")

    return cleaned_str


def get_new_timestamp(path_with_stamp: str) -> str:
    """ removes possible timestamps from given string and returns cleaned string

        :param path_with_stamp: str with possible timestamps
        :type: str
        :return: cleaned string without timestamps
        :rtype: str
    """
    return remove_timestamps(path_with_stamp=path_with_stamp, set_new_timestamp=True)



def get_test_folders(root_folder: Union[str, Path], ends_with: Optional[List[str]] = None,
                     ignore_paths: Optional[List[Union[str, re.Pattern]]] = None) -> List[str]:
    """ Get all "tests"-folder within the given root- und subfolders.

        :param root_folder:
        :param ends_with: Found tests folder must ends with one of the given names. If None, defaults to `("tests", )`
        :param ignore_paths: Optional paths to ignore, defaults to None to ignore no paths
    """

    if not ignore_paths:
        ignore_paths = []

    if ends_with is None:
        ends_with = ["tests"]

    test_folders = [folder.as_posix() for folder in root_folder.glob("**/*")
                    if folder.is_dir() and folder.name.endswith(tuple(ends_with))
                        and not file_matches_pattern(folder, root_folder, ignore_paths)]

    return test_folders


def get_uri_mode(uri: str):
    """ Checks if given uri string is a web address or local file """
    if uri.casefold().startswith(("http://", "https://", "www.")):
        return constants.URI_WEB

    if Path(uri).is_file():
        return constants.URI_OS

    return constants.URI_ERROR


def get_python_site_version_folder_name() -> str:
    """ Returns the PythonXXX folder name e.g., Python312.
    Normalize the site-package path/folder name the Windows style.
        - Windows: Python312
        - Unix: python3.12 -> Python312
    """

    # On Windows: 'C:\\Users\\%USERNAME%\\AppData\\Roaming\\Python\\Python312\\site-packages'
    site_package_path = Path(site.USER_SITE)

    if not str(site_package_path).endswith("site-packages"):
        raise ValueError(f"{site_package_path=} does not end with 'site-packages'")

    python_version = site_package_path.parent.name
    if sys.platform == "win32":
        normalized_python_version = python_version
    else:
        normalized_python_version = python_version.capitalize().replace(".", "")

    return normalized_python_version


def get_pyd_file_name_suffix() -> str:
    """ Returns the file name suffix for compiled PYD files.

        Python 3.9: ".cp39-win_amd64.pyd"
        Python 3.12: ".cp312-win_amd64.pyd"
    """

    # get expected new file names
    python_version = get_python_site_version_folder_name()
    if python_version == "Python39":
        return '.cp39-win_amd64.pyd'
    elif python_version == "Python312":
        return '.cp312-win_amd64.pyd'
    else:
        raise SystemError(f"{python_version=} is not supported")


def file_matches_pattern(file_path_or_dir: Path, root_dir: Optional[Path] = None,
                         names_and_patterns: Optional[List[Union[str, Pattern]]] = None) -> bool:
    """ Returns True, if one of the given name or pattern matches the file_path_or_dir
        If not found in the list, it returns False.

        :param file_path_or_dir: file path or path to directory
        :param root_dir: Optional root directory to simplify the path check. If not set the given file_path will not be splitted.
        :param names_and_patterns: Optional list of absolute path names or regex patterns.
    """

    if not names_and_patterns:
        names_and_patterns = []

    # get the paths as strings for further checks
    file_or_path_str = file_path_or_dir.as_posix()
    if root_dir:
        plugin_dir_str = root_dir.as_posix()
        # remove the leading root_dir from the file_path_or_dir
        to_validate_file = file_or_path_str.replace(plugin_dir_str, '')
    else:
        to_validate_file = file_or_path_str

    origin_to_validate_file = to_validate_file
    if to_validate_file.startswith("/"):
        # remove "/" prefix if set
        to_validate_file = to_validate_file[1:]

    for value in names_and_patterns:
        if isinstance(value, str):
            if (Path(value) == Path(origin_to_validate_file)
                    or Path(value) == Path(to_validate_file)):
                return True

            if value == to_validate_file:
                # ignore text/string equals to file
                # explicit ignore
                return True
        else:
            # compare regex
            if value.search(to_validate_file) is not None:
                # regex match found, ignore it
                return True

    # file should not be ignored
    return False


def get_files(path, recursive: bool = True, ignore_paths: Optional[List[str]] = None):
    """ Get all files from folder.

        .. code-block:: python

            # walk through each folder and prints file and folder
            for file in get_files("C:/"):
                print("file", file")


        :param path: start path
        :param recursive: Can go in sub folders?
        :param ignore_paths: List of paths to ignore.
                             Current path in iteration is checked with "startswith" in `ignore_paths`.
    """
    if ignore_paths is None:
        ignore_paths = []

    ignored_roots = []

    def skip_root(file_):
        for x in ignored_roots:
            if file_.startswith(x):
                return True

        return False

    for root, _, files in os.walk(path):

        # current iter path should be ignored
        root = os.path.normpath(root)
        if root in ignore_paths:
            ignored_roots.append(root)
            continue

        if skip_root(root):
            continue

        for file in files:

            if skip_root(file):
                continue

            path = os.path.normpath(os.path.join(root, file))

            # file path should be ignored
            if path in ignore_paths:
                continue

            yield path

        # do not go deeper in folder structure
        if not recursive:
            break


def check_storage_capacity(path: Union[str, Path], min_storage: float) -> Tuple[bool, float]:
    """ Checks if the needed space is free

        :param path: path
        :param min_storage: minimum free storage on drive
        :return: bool (0, True =  enough there), free space in megabytes (1)
    """
    try:
        directory = path if isinstance(path, str) else str(path.parent)
        free_storage = [i / 1000000 for i in shutil.disk_usage(directory)]
        free_storage = free_storage[-1]

        if free_storage < min_storage:
            return False, free_storage

        return True, free_storage

    except FileNotFoundError:
        return False, 0.0


def get_additional_sys_path_folders() -> List[Path]:
    """ Returns additional paths to add to sys.path.
        Keep the path-order to prioritize the imports!
        First comes, first serves.
    """
    paths = []

    if sys.platform == "win32":
        # when running with the python-qgis-ltr.bat, usally nothing needs to be set
        paths = []
    if sys.platform == "linux":
        # for the docker image (debian)
        # inspired by:https://github.com/qgis/QGIS/blob/master/.docker/qgis.dockerfile#L74
        paths = [Path("/usr/share/qgis/python/"),
                 Path("/usr/share/qgis/python/plugins"),  # processing plugins and other plugins from QGIS itself
                 Path("/usr/lib/python3/dist-packages/qgis"),
                 Path("/usr/share/qgis/python/qgis")]


    return paths
