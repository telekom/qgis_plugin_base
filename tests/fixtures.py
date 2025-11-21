# -*- coding: utf-8 -*-
# SPDX-FileCopyrightText: 2025 Deutsche Telekom Technik GmbH <f.vonstudsinske@telekom.de>
# SPDX-License-Identifier: GPL-3.0-or-later

import pytest

from qgis.core import (QgsVectorLayer, QgsFeature, QgsGeometry, QgsPointXY,
                       QgsNetworkAccessManager, QgsSettings)

from .functions import new_qgis_project

def get_test_point_feature(test_point_layer: QgsVectorLayer) -> QgsFeature:
    """
    Expecting the simple_point_vector_layer below!
    Returns a test feature (not added to the vector layer).

    :param test_point_layer: simple_point_vector_layer from below
    """

    count = test_point_layer.featureCount()
    feature = QgsFeature(test_point_layer.dataProvider().fields())
    feature["id"] = count
    feature.setGeometry(QgsGeometry.fromPointXY(QgsPointXY(float(count), float(count))))

    return feature


@pytest.fixture()
def simple_point_vector_layer() -> QgsVectorLayer:
    """ Returns a basic memory vector layer with the geometry type of point.
        The returned layer has the CRS EPSG:4326, with containing features (first fid is 1) and the attribute field "id"

    """

    # create a memory layer with the given URI (from the PyQGIS documentation)
    uri = "point?crs=epsg:4326&field=id:integer"
    layer = QgsVectorLayer(uri, "scratch_point_layer", "memory")
    assert layer.isValid()

    # create some test features
    for i in range(1, 101):
        feature = QgsFeature(layer.dataProvider().fields())
        feature["id"] = i
        feature.setGeometry(QgsGeometry.fromPointXY(QgsPointXY(float(i), float(i))))

        assert layer.dataProvider().addFeature(feature)

    assert layer.featureCount() == 100

    return layer


@pytest.fixture()
def qgis_activate_internet_proxy():
    """ Activates temporary the DefaultProxy from QGIS.
            Usually to the common Internet.
            The proxy cannot be deactivated (C++ error / windows fatal exception)

            .. code-block:: python

                with temp_activate_qgis_proxy():
                    ...
        """

    def __reset_network():

        # clear the existing caches
        QgsNetworkAccessManager.instance().cache().clear()
        QgsNetworkAccessManager.instance().clearAccessCache()

        # setup the default proxies
        QgsNetworkAccessManager.instance().setupDefaultProxyAndCache()

    # current settings
    settings = QgsSettings()

    # back values to restore later
    old_proxy_enabled = settings.value("proxy/proxyEnabled")
    old_proxy_type = settings.value("proxy/proxyType")
    old_proxy_host = settings.value("proxy/proxyHost")
    old_proxy_port = settings.value("proxy/proxyPort")
    old_proxy_user = settings.value("proxy/proxyUser")
    old_proxy_password = settings.value("proxy/proxyPassword")

    # activate proxy
    settings.setValue("proxy/proxyEnabled", True)
    settings.setValue("proxy/proxyType", "DefaultProxy")
    settings.setValue("proxy/proxyHost", "")
    settings.setValue("proxy/proxyPort", "")
    settings.setValue("proxy/proxyUser", "")
    settings.setValue("proxy/proxyPassword", "")
    settings.sync()

    __reset_network()

    yield None

    # restore the old values
    settings = QgsSettings()
    settings.setValue("proxy/proxyEnabled", old_proxy_enabled)
    settings.setValue("proxy/proxyType", old_proxy_type)
    settings.setValue("proxy/proxyHost", old_proxy_host)
    settings.setValue("proxy/proxyPort", old_proxy_port)
    settings.setValue("proxy/proxyUser", old_proxy_user)
    settings.setValue("proxy/proxyPassword", old_proxy_password)
    settings.sync()

    __reset_network()


@pytest.fixture()
def plugin_qgis_new_project():
    """
        1. Starts a QgsApplication, if not active yet
        2. Activates the processing plugin and loads the processing algorithms
        3. Create an empty QgsProject
        4. <time for the test>
        5. Clear the QgsProject

        Uses the OS environment variable "QGIS_PYTEST_AUTHENTICATION_CONFIG_DIR"
        to load QGIS XML authentication files. The OS variable is optional to load configs from.

    """
    yield from new_qgis_project()
