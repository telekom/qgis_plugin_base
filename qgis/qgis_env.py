# -*- coding: utf-8 -*-
# SPDX-FileCopyrightText: 2025 Deutsche Telekom Technik GmbH <f.vonstudsinske@telekom.de>
# SPDX-License-Identifier: GPL-3.0-or-later

import sys
import secrets

from pathlib import Path

from qgis.core import QgsApplication
from qgis.testing.mocked import get_iface

from qgis.utils import (updateAvailablePlugins, isPluginLoaded,
                        startPlugin, loadPlugin)

from typing import Optional

from .functions import get_prefix_path


def setup_qgis(path_to_credentials: Optional[Path] = None) -> QgsApplication:
    """ Starts a new QgsApplication instance and returns it.

        Usually used in test environments or standalone scripts.

        May crash, when incompatible PyQt versions are detected in the QGIS installation
        and in e.g. user-site packages path.
        Possible crash message on Windows: `Process finished with exit code -1073740791 (0xC0000409)`

    .. code-block:: python
        qgs = setup_qgis()
        ...  # run yur code here
        # after you script, exit QGIS!
        qgs.exitQgis()

    :param path_to_credentials: Optional path to a directory with QGIS authentication config files (xml).

    :return: created qgs application
    """

    if QgsApplication.instance() is not None:
        raise RuntimeError(f"QgsApplication already instantiated!")

    if prefix := get_prefix_path():
        # if available, use a prefix path
        # may be different per sys.platform
        # https://gis.stackexchange.com/questions/155745/layer-is-not-valid-error-in-my-standalone-pyqgis-script-app/155852#155852
        QgsApplication.setPrefixPath(prefix.as_posix(), True)

    iface = get_iface()
    import qgis.utils
    qgis.utils.iface = iface

    # get the current QGIS application instace
    app = QgsApplication.instance()

    app.initQgis()
    auth_mgr = app.authManager()

    # setup a secret "token"/"password" for the temporary QGIS application instance
    secret = secrets.token_urlsafe(32)
    if not auth_mgr.setMasterPassword(secret, True):
        raise RuntimeError("master password could not be set")

    if not auth_mgr.masterPasswordSame(secret):
        # should not the case, but be sure ...
        raise RuntimeError(f"{secret} not accepted")

    if path_to_credentials and not path_to_credentials.is_dir():
        raise NotADirectoryError(f"{path_to_credentials=} is not a directory")

    if path_to_credentials:
        # load configurations from the given config location
        __load_authentication_configs(path_to_credentials)

    activate_processing()

    return QgsApplication.instance()


def __load_authentication_configs(credentials_path: Path) -> int:
    """ Loads all XML files form the relative ".credentials" path, if present.
        Returns the amount of imported configs.

        :param credentials_path: Path to a directory with the credential configuration files (XMLs)

        :raises RuntimeError: In case of not importable config.
    """

    # get the current auth manager
    auth_manager = QgsApplication.instance().authManager()

    count = 0
    for path in credentials_path.iterdir():
        if path.is_file() and path.name.endswith(".xml"):
            ok = auth_manager.importAuthenticationConfigsFromXml(path.as_posix(), overwrite=True)
            if not ok:
                raise RuntimeError(f"{path} not loaded to the authentication database")
            count += 1

    return count


def activate_processing():
    """ Activates the processing algorithms.
        A QGIS environment must be already active.
    """

    if QgsApplication.instance() is None:
        raise RuntimeError(f"QgsApplication is not active!")

    # add python path to import default QGIS plugins (e.g. processing)
    qgis_py_plugins_path = Path(QgsApplication.instance().pkgDataPath()) / "python" / "plugins"
    if qgis_py_plugins_path.as_posix() not in sys.path:
        sys.path.insert(0, qgis_py_plugins_path.as_posix())

    from processing.core.Processing import Processing
    Processing.initialize()


def activate_processing_plugin():
    """ Activates the processing plugin with all its algorithms.
        A QGIS environment must be already active.
    """

    # check if processing plugin is active
    if not isPluginLoaded('processing'):
        # processing plugin not loaded
        try:
            loadPlugin('processing')
            startPlugin('processing')
            updateAvailablePlugins()
        except:
            updateAvailablePlugins()

    # import from qgis/processing
    activate_processing()

    return isPluginLoaded('processing')
