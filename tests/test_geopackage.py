# -*- coding: utf-8 -*-
# SPDX-FileCopyrightText: 2025 Deutsche Telekom Technik GmbH <f.vonstudsinske@telekom.de>
# SPDX-License-Identifier: GPL-3.0-only

import tempfile
from pathlib import Path
from unittest.mock import MagicMock

import pytest
from qgis.core import QgsVectorLayer

from .constants import TEMP_TEST_RESULTS
from .fixtures import plugin_qgis_new_project
from ..qgis.geopackage import GeoPackage

ROOT_DIR = Path(__file__).parent


@pytest.mark.parametrize("method,args", [
    ("has_layer", ("test_layer",)),
    ("get_layers", ()),
    ("get_columns", ("test_layer",)),
    ("fetchone", ("SELECT 1",)),
    ("fetchmany", ("SELECT 1",)),
    ("fetchall", ("SELECT 1",)),
])
@pytest.mark.parametrize("failure_point", ["execute", "fetch"])
def test_geopackage_closes_connection_on_query_failure(monkeypatch, method, args, failure_point):
    gpkg = GeoPackage("unused.gpkg")
    connection = MagicMock()
    cursor = connection.cursor.return_value
    error = RuntimeError("query failed")
    monkeypatch.setattr(gpkg, "_GeoPackage__get_connection", lambda: connection)

    if method == "get_columns":
        # The existence check uses a separate connection; isolate the query under test.
        monkeypatch.setattr(gpkg, "has_layer", lambda name: True)

    if failure_point == "execute":
        cursor.execute.side_effect = error
    elif method == "get_columns":
        cursor.execute.return_value.__iter__.side_effect = error
    else:
        fetch_method = {"has_layer": "fetchone", "get_layers": "fetchall"}.get(method, method)
        getattr(cursor, fetch_method).side_effect = error

    with pytest.raises(RuntimeError) as exc_info:
        getattr(gpkg, method)(*args)

    assert exc_info.value is error
    connection.close.assert_called_once_with()


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
