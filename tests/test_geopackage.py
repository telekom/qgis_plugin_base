# -*- coding: utf-8 -*-
# SPDX-FileCopyrightText: 2025 Deutsche Telekom Technik GmbH <f.vonstudsinske@telekom.de>
# SPDX-License-Identifier: GPL-3.0-or-later

import tempfile

from pathlib import Path
from qgis.core import QgsVectorLayer
from .constants import TEMP_TEST_RESULTS
from .fixtures import plugin_qgis_new_project
from ..qgis.geopackage import GeoPackage

ROOT_DIR = Path(__file__).parent


def test_geopackage_only_layers(plugin_qgis_new_project):

    import processing

    # create test vector layers
    layer_1 = QgsVectorLayer("LineString?crs=epsg:4326", "test_layer_1", "memory")
    layer_2 = QgsVectorLayer("Point?crs=epsg:4326", "test_layer_2", "memory")
    assert layer_1.isValid()
    assert layer_2.isValid()

    with tempfile.TemporaryDirectory(prefix=TEMP_TEST_RESULTS, dir=ROOT_DIR) as tempdir:
        gpkg_test = Path(tempdir) / "test.gpkg"
        params = {'LAYERS': [layer_1, layer_2], 'OUTPUT': gpkg_test.as_posix(), 'OVERWRITE': True,
                  'SAVE_STYLES': False}
        processing.run("native:package", params)

        assert gpkg_test.is_file()

        gpkg = GeoPackage(gpkg_test.as_posix())
        assert gpkg.has_layer("test_layer_1")
        assert gpkg.has_layer("test_layer_2")

        assert len(gpkg.get_layers()) == 2
        assert gpkg.get_layers()["test_layer_1"]["data_type"] == "features"
        assert gpkg.get_layers()["test_layer_1"]["identifier"] == "test_layer_1"
        assert gpkg.get_layers()["test_layer_1"]["srs"]["srsid"] == 4326
        assert gpkg.get_layers()["test_layer_2"]["data_type"] == "features"
        assert gpkg.get_layers()["test_layer_2"]["identifier"] == "test_layer_2"
        assert gpkg.get_layers()["test_layer_2"]["srs"]["srsid"] == 4326


def test_geopackage_with_layers_and_table(plugin_qgis_new_project):

    import processing

    # create test vector layers
    layer_1 = QgsVectorLayer("LineString?crs=epsg:4326", "test_layer_1", "memory")
    layer_2 = QgsVectorLayer("Point?crs=epsg:4326", "test_layer_2", "memory")
    layer_3 = QgsVectorLayer("NoGeometry", "test_layer_3", "memory")
    assert layer_1.isValid()
    assert layer_2.isValid()
    assert layer_3.isValid()

    with tempfile.TemporaryDirectory(prefix=TEMP_TEST_RESULTS, dir=ROOT_DIR) as tempdir:
        gpkg_test = Path(tempdir) / "test.gpkg"
        params = {'LAYERS': [layer_1, layer_2, layer_3], 'OUTPUT': gpkg_test.as_posix(), 'OVERWRITE': True,
                  'SAVE_STYLES': False}
        processing.run("native:package", params)

        assert gpkg_test.is_file()

        gpkg = GeoPackage(gpkg_test.as_posix())
        assert gpkg.has_layer("test_layer_1")
        assert gpkg.has_layer("test_layer_2")
        assert gpkg.has_layer("test_layer_3")

        assert len(gpkg.get_layers()) == 3
        assert gpkg.get_layers()["test_layer_1"]["data_type"] == "features"
        assert gpkg.get_layers()["test_layer_1"]["identifier"] == "test_layer_1"
        assert gpkg.get_layers()["test_layer_1"]["srs"]["srsid"] == 4326
        assert gpkg.get_layers()["test_layer_2"]["data_type"] == "features"
        assert gpkg.get_layers()["test_layer_2"]["identifier"] == "test_layer_2"
        assert gpkg.get_layers()["test_layer_2"]["srs"]["srsid"] == 4326

        # no geometries, no srs - "attributes"
        assert gpkg.get_layers()["test_layer_3"]["data_type"] == "attributes"
        assert gpkg.get_layers()["test_layer_3"]["identifier"] == "test_layer_3"
        assert gpkg.get_layers()["test_layer_3"]["srs"]["srsid"] is None
