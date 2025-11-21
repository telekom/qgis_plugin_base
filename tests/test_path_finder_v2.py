# -*- coding: utf-8 -*-
# SPDX-FileCopyrightText: 2025 Deutsche Telekom Technik GmbH <f.vonstudsinske@telekom.de>
# SPDX-License-Identifier: GPL-3.0-or-later

import pytest
from qgis.core import QgsVectorLayer, QgsPointXY, QgsFeature, QgsGeometry

from .fixtures import plugin_qgis_new_project


def __get_new_feature(wkt: str):
    feature = QgsFeature()
    feature.setGeometry(QgsGeometry.fromWkt(wkt))
    return feature


@pytest.fixture()
def __line_layer():

    line_layer = QgsVectorLayer("LineString?crs=epsg:25832", "test", "memory")
    assert line_layer.isValid()

    assert line_layer.dataProvider().addFeature(__get_new_feature("LineString (0.0 0.0, 1.0 0.0)"))
    assert line_layer.dataProvider().addFeature(__get_new_feature("LineString (1.0 0.0, 2.0 0.0)"))
    assert line_layer.dataProvider().addFeature(__get_new_feature("LineString (2.0 0.0, 3.0 0.0)"))
    assert line_layer.dataProvider().addFeature(__get_new_feature("LineString (3.0 0.0, 4.0 0.0)"))
    assert line_layer.dataProvider().addFeature(__get_new_feature("LineString (4.0 0.0, 5.0 0.0)"))
    assert line_layer.dataProvider().addFeature(__get_new_feature("LineString (5.0 0.0, 6.0 0.0)"))
    assert line_layer.dataProvider().addFeature(__get_new_feature("LineString (6.0 0.0, 7.0 0.0)"))
    assert line_layer.dataProvider().addFeature(__get_new_feature("LineString (7.0 0.0, 8.0 0.0)"))
    assert line_layer.dataProvider().addFeature(__get_new_feature("LineString (8.0 0.0, 9.0 0.0)"))
    assert line_layer.dataProvider().addFeature(__get_new_feature("LineString (9.0 0.0, 10.0 0.0)"))

    return line_layer


def test_path_finder_arguments(__line_layer, plugin_qgis_new_project):
    """ tests basic __init__ exceptions """

    from ..qgis.path_finder_v2 import PathFinderV2
    path_finder = PathFinderV2(__line_layer)

    with pytest.raises(ValueError):
        multi_line_layer = QgsVectorLayer("MultiLineString?crs=epsg:25832", "test", "memory")
        assert multi_line_layer.isValid()
        path_finder = PathFinderV2(multi_line_layer)


def test_path_finder_get_poly_line_dijkstra(__line_layer, plugin_qgis_new_project):

    from ..qgis.path_finder_v2 import PathFinderV2, PathFinderMethods
    from ..qgis.path_finder import PathFinder, PathFinderMethods as PathFinderMethodsV1

    start_point = QgsPointXY(0.0, 0.0)
    end_point = QgsPointXY(10.0, 0.0)

    path_finder_v2 = PathFinderV2(
        __line_layer, vector_layer_director_graph_points=[start_point, end_point])
    poly_line_v2 = path_finder_v2.get_poly_line(start_point, end_point, methods=[PathFinderMethods.Dijkstra])
    poly_line_v1 = PathFinder.get_polyline(__line_layer, start_point, end_point, method=PathFinderMethodsV1.DIJKSTRA)
    poly_line_v2_str = [p.toString(2) for p in poly_line_v2]
    poly_line_v1_str = [p.toString(2) for p in poly_line_v1]

    assert poly_line_v1
    assert poly_line_v2

    assert poly_line_v1_str == poly_line_v2_str, "PathFinder (V1) and PathFinderV2 result is not equal"


def test_path_finder_get_poly_line_processing_dijkstra(__line_layer, plugin_qgis_new_project):

    from ..qgis.path_finder_v2 import PathFinderV2, PathFinderMethods
    from ..qgis.path_finder import PathFinder, PathFinderMethods as PathFinderMethodsV1

    start_point = QgsPointXY(0.0, 0.0)
    end_point = QgsPointXY(10.0, 0.0)

    path_finder_v2 = PathFinderV2(
        __line_layer, vector_layer_director_graph_points=[start_point, end_point])

    poly_line_v2 = path_finder_v2.get_poly_line(start_point, end_point, methods=[PathFinderMethods.ProcessingDijkstra])
    poly_line_v1 = PathFinder.get_polyline(__line_layer, start_point, end_point, method=PathFinderMethodsV1.PROCESSING)
    poly_line_v2_str = [p.toString(2) for p in poly_line_v2]
    poly_line_v1_str = [p.toString(2) for p in poly_line_v1]

    assert poly_line_v1
    assert poly_line_v2

    assert poly_line_v1_str == poly_line_v2_str, "PathFinder (V1) and PathFinderV2 result is not equal"


def test_path_finder_get_poly_line_shortest(__line_layer, plugin_qgis_new_project):

    from ..qgis.path_finder_v2 import PathFinderV2, PathFinderMethods
    from ..qgis.path_finder import PathFinder, PathFinderMethods as PathFinderMethodsV1

    start_point = QgsPointXY(0.0, 0.0)
    end_point = QgsPointXY(10.0, 0.0)

    path_finder_v2 = PathFinderV2(
        __line_layer, vector_layer_director_graph_points=[start_point, end_point])

    poly_line_v2 = path_finder_v2.get_poly_line(start_point, end_point, methods=[PathFinderMethods.ShortestTree])
    poly_line_v1 = PathFinder.get_polyline(__line_layer, start_point, end_point, method=PathFinderMethodsV1.SHORTEST_PATH)
    poly_line_v2_str = [p.toString(2) for p in poly_line_v2]
    poly_line_v1_str = [p.toString(2) for p in poly_line_v1]

    assert poly_line_v1
    assert poly_line_v2

    assert poly_line_v1_str == poly_line_v2_str, "PathFinder (V1) and PathFinderV2 result is not equal"


def test_path_finder_get_poly_line_tracer(__line_layer, plugin_qgis_new_project):

    from ..qgis.path_finder_v2 import PathFinderV2, PathFinderMethods
    from ..qgis.path_finder import PathFinder, PathFinderMethods as PathFinderMethodsV1

    start_point = QgsPointXY(0.0, 0.0)
    end_point = QgsPointXY(10.0, 0.0)

    path_finder_v2 = PathFinderV2(
        __line_layer, vector_layer_director_graph_points=[start_point, end_point])

    poly_line_v2 = path_finder_v2.get_poly_line(start_point, end_point, methods=[PathFinderMethods.Tracer])
    poly_line_v1 = PathFinder.get_polyline(__line_layer, start_point, end_point, method=PathFinderMethodsV1.TRACER)
    poly_line_v2_str = [p.toString(2) for p in poly_line_v2]
    poly_line_v1_str = [p.toString(2) for p in poly_line_v1]

    assert poly_line_v1
    assert poly_line_v2

    assert poly_line_v1_str == poly_line_v2_str, "PathFinder (V1) and PathFinderV2 result is not equal"


def test_path_finder_get_poly_line_dijkstra_reuse(__line_layer, plugin_qgis_new_project):
    import processing

    from ..qgis.path_finder_v2 import PathFinderV2, PathFinderMethods
    from ..qgis.path_finder import PathFinder, PathFinderMethods as PathFinderMethodsV1

    params = {'INPUT': __line_layer, 'OUTPUT': 'TEMPORARY_OUTPUT'}
    points_layer = processing.run("native:extractvertices", params)["OUTPUT"]
    all_vertices = list(set(f.geometry().asPoint() for f in points_layer.getFeatures()))

    for a,b in zip(range(0, 11), reversed(range(0, 11))):
        start_point = QgsPointXY(a, 0.0)
        end_point = QgsPointXY(b, 0.0)

        path_finder_v2 = PathFinderV2(
            __line_layer, vector_layer_director_graph_points=[start_point, end_point]+all_vertices)

        poly_line_v2 = path_finder_v2.get_poly_line(start_point, end_point, methods=[PathFinderMethods.Dijkstra])
        poly_line_v1 = PathFinder.get_polyline(__line_layer, start_point, end_point, method=PathFinderMethodsV1.DIJKSTRA)
        poly_line_v2_str = [p.toString(2) for p in poly_line_v2]
        poly_line_v1_str = [p.toString(2) for p in poly_line_v1]

        if a == b:
            # start and end are equal, no route should be found
            assert not poly_line_v1
            assert not poly_line_v2
        else:
            assert poly_line_v1
            assert poly_line_v2

        assert poly_line_v1_str == poly_line_v2_str, "PathFinder (V1) and PathFinderV2 result is not equal"
