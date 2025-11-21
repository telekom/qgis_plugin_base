# -*- coding: utf-8 -*-
# SPDX-FileCopyrightText: 2025 Deutsche Telekom Technik GmbH <f.vonstudsinske@telekom.de>
# SPDX-License-Identifier: GPL-3.0-or-later

""" Diese Tests bringen QGIS ggf. zum Crashen.
Nur ausführbar im Frontend.

QGIS issue: https://github.com/qgis/QGIS/issues/58205

lxml 5.2.1 ist aus unbekannten Gründen in dieser QGIS Version defekt.

Zuletzt mit Windows Installer für QGIS 3.40.7 getestet.
"""
import pytest
import tempfile
import openpyxl
from pathlib import Path

from qgis.core import QgsVectorLayer, QgsProject

from ...constants import TEMP_TEST_RESULTS
from ...fixtures import simple_point_vector_layer, plugin_qgis_new_project
from ...markers import skipif_no_qgis_app


@skipif_no_qgis_app
def test_lxml(simple_point_vector_layer, plugin_qgis_new_project):

    import processing

    with tempfile.TemporaryDirectory(prefix=TEMP_TEST_RESULTS, dir=Path(__file__).parent) as tempdir:

        for i in range(2):
            # create GeoPackage
            file_path = Path(tempdir) / f"test_lxml_{i}.gpkg"
            params = {'LAYERS': [simple_point_vector_layer], 'OUTPUT': file_path.as_posix(), 'OVERWRITE': True, 'SAVE_STYLES': True}
            processing.run("native:package", params)

            layer = QgsVectorLayer(f"{file_path.as_posix()}|layername={simple_point_vector_layer.name()}", "TEST", "ogr")
            assert layer.isValid()

            assert QgsProject.instance().addMapLayer(layer)

            from lxml.etree import Element

            el = Element("test")

        # clear the project to release the file lock/access
        QgsProject.instance().clear()


@skipif_no_qgis_app
def test_openpyxl(simple_point_vector_layer, plugin_qgis_new_project):
    import processing

    with tempfile.TemporaryDirectory(prefix=TEMP_TEST_RESULTS, dir=Path(__file__).parent) as tempdir:

        for i in range(2):
            # create GeoPackage
            file_path = Path(tempdir) / f"test_lxml_{i}.gpkg"
            params = {'LAYERS': [simple_point_vector_layer], 'OUTPUT': file_path.as_posix(), 'OVERWRITE': True, 'SAVE_STYLES': True}
            processing.run("native:package", params)

            layer = QgsVectorLayer(f"{file_path.as_posix()}|layername={simple_point_vector_layer.name()}", "TEST", "ogr")
            assert layer.isValid()

            assert QgsProject.instance().addMapLayer(layer)
            wb = openpyxl.Workbook()

        # clear the project to release the file lock/access
        QgsProject.instance().clear()
