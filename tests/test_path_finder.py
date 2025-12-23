# -*- coding: utf-8 -*-
# SPDX-FileCopyrightText: 2025 Deutsche Telekom Technik GmbH <f.vonstudsinske@telekom.de>
# SPDX-License-Identifier: GPL-3.0-only

from qgis.core import QgsVectorLayer, QgsPointXY, QgsGeometry, QgsFeature

from .fixtures import plugin_qgis_new_project
from ..qgis.geometry import get_polyline

# Line vertices 0 and 2 are valid. The vertice 1 may cause issues in the processing algorithm "native:shortestpathpointtopoint"
BROKEN_WKT_FOR_QGIS_PROCESSING = "LineString (1331285.13022258994169533 6712536.29855360370129347, 1331239.12636794336140156 6712602.7632201099768281, 1331231.41291520278900862 6712613.90733114071190357)"


def test_path_finder_ok(plugin_qgis_new_project):

    # test with the given line vertices

    # nested import, to activate processing first
    from ..qgis.path_finder import PathFinder, PathFinderMethods

    # get the start and end point to route with
    geometry = QgsGeometry.fromWkt(BROKEN_WKT_FOR_QGIS_PROCESSING)
    poly_line = get_polyline(geometry)
    start_point = poly_line[0]
    end_point = poly_line[-1]

    # create the test layer
    layer = QgsVectorLayer("LineString?crs=epsg:3857", "test", "memory")
    feature = QgsFeature()
    feature.setGeometry(geometry)
    layer.dataProvider().addFeature(feature)

    assert PathFinder.get_polyline(layer, start_point, end_point, method=PathFinderMethods.FIRST_MATCH)


def test_path_finder_error(plugin_qgis_new_project):

    # test with round line vertices

    # nested import, to activate processing first
    from ..qgis.path_finder import PathFinder, PathFinderMethods

    geometry_processing_1 = QgsGeometry.fromWkt(BROKEN_WKT_FOR_QGIS_PROCESSING)
    geometry_processing_2 = QgsGeometry.fromPolyline([geometry_processing_1.vertexAt(0),
                                                      geometry_processing_1.vertexAt(2)])

    # 1331231.41291520278900862 6712613.90733114071190357
    start_point = QgsPointXY(1331231.412915, 6712613.907331)

    # 1331285.13022258994169533 6712536.29855360370129347
    end_point = QgsPointXY(1331285.130223, 6712536.298554)

    # create the test layer
    layer_processing_1 = QgsVectorLayer("LineString?crs=epsg:3857", "test", "memory")
    feature_processing_1 = QgsFeature()
    feature_processing_1.setGeometry(geometry_processing_1)
    layer_processing_1.dataProvider().addFeature(feature_processing_1)

    # no path should be found (unknown why)
    assert not PathFinder.get_polyline(layer_processing_1, start_point, end_point, method=PathFinderMethods.PROCESSING)

    # create the test layer
    layer_processing_2 = QgsVectorLayer("LineString?crs=epsg:3857", "test", "memory")
    feature_processing_2 = QgsFeature()
    feature_processing_2.setGeometry(geometry_processing_2)
    layer_processing_2.dataProvider().addFeature(feature_processing_2)

    # a path should be found know with less vertices (unknown why)
    assert PathFinder.get_polyline(layer_processing_2, start_point, end_point, method=PathFinderMethods.PROCESSING)


