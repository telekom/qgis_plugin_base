# -*- coding: utf-8 -*-
# (C) 2025 Deutsche Telekom Technik GmbH
# Author: Felix von Studsinske (f.vonstudsinske / GitHub: felixvons)
# License: GNU GPL v3

import pytest
from pathlib import Path
from qgis.core import QgsVectorLayer, QgsPointXY, QgsFeature, QgsGeometry

from .fixtures import plugin_qgis_new_project


def __get_new_feature(wkt: str, feature_id: int):
    feature = QgsFeature(feature_id)
    feature.setGeometry(QgsGeometry.fromWkt(wkt))
    return feature


@pytest.fixture()
def __line_layer():

    line_layer = QgsVectorLayer("LineString?crs=epsg:25832", "test", "memory")
    assert line_layer.isValid()

    assert line_layer.dataProvider().addFeature(__get_new_feature("LineString (0.0 0.0, 1.0 0.0)", 1))
    assert line_layer.dataProvider().addFeature(__get_new_feature("LineString (1.0 0.0, 2.0 0.0)", 2))
    assert line_layer.dataProvider().addFeature(__get_new_feature("LineString (2.0 0.0, 3.0 0.0)", 3))
    assert line_layer.dataProvider().addFeature(__get_new_feature("LineString (3.0 0.0, 4.0 0.0)", 4))
    assert line_layer.dataProvider().addFeature(__get_new_feature("LineString (4.0 0.0, 5.0 0.0)", 5))
    assert line_layer.dataProvider().addFeature(__get_new_feature("LineString (5.0 0.0, 6.0 0.0)", 5))
    assert line_layer.dataProvider().addFeature(__get_new_feature("LineString (6.0 0.0, 7.0 0.0)", 7))
    assert line_layer.dataProvider().addFeature(__get_new_feature("LineString (7.0 0.0, 8.0 0.0)", 8))
    assert line_layer.dataProvider().addFeature(__get_new_feature("LineString (8.0 0.0, 9.0 0.0)", 9))
    assert line_layer.dataProvider().addFeature(__get_new_feature("LineString (9.0 0.0, 10.0 0.0)", 10))
    assert line_layer.dataProvider().addFeature(__get_new_feature("LineString (10.0 0.0, 11.0 0.0, 12.0 0.0, 13.0 0.0)", 11))
    assert line_layer.dataProvider().addFeature(__get_new_feature("LineString (13.0 0.0, 14.0 0.0)", 12))
    assert line_layer.dataProvider().addFeature(__get_new_feature("LineString (14.0 0.0, 15.0 0.0, 16.0 0.0)", 13))
    assert line_layer.dataProvider().addFeature(__get_new_feature("LineString (16.0 0.0, 17.0 0.0, 18.0 0.0)", 14))

    return line_layer


def test_path_finder_arguments(__line_layer, plugin_qgis_new_project):
    """ tests basic __init__ exceptions """

    from ..qgis.path_finder_v2 import PathFinderV2
    PathFinderV2(__line_layer)

    with pytest.raises(ValueError):
        multi_line_layer = QgsVectorLayer("MultiLineString?crs=epsg:25832", "test", "memory")
        assert multi_line_layer.isValid()
        PathFinderV2(multi_line_layer)


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


def test_path_finder_get_fid_route(__line_layer, plugin_qgis_new_project):

    from ..qgis.path_finder_v2 import PathFinderV2, PathFinderFidRouteModes
    from ..qgis.path_finder import PathFinder

    start_point = QgsPointXY(0.0, 0.0)
    end_point = QgsPointXY(10.0, 0.0)

    path_finder_v2 = PathFinderV2(__line_layer)

    # region strict
    # 1 to 10
    fid_route_old = PathFinder.get_fid_route(__line_layer, start_point, end_point)[0]
    fid_route_v2 = path_finder_v2.get_fid_route(start_point, end_point)
    assert fid_route_old == fid_route_v2

    # 1 to 11
    fid_route_old = PathFinder.get_fid_route(__line_layer, start_point, QgsPointXY(11.0, 0.0))[0]
    fid_route_v2 = path_finder_v2.get_fid_route(start_point, QgsPointXY(11.0, 0.0))
    assert len(fid_route_v2) == 0
    assert len(fid_route_old) == 11

    # 1 to 7
    fid_route_old = PathFinder.get_fid_route(__line_layer, start_point, QgsPointXY(7.0, 0.0))[0]
    fid_route_v2 = path_finder_v2.get_fid_route(start_point, QgsPointXY(7.0, 0.0))
    assert fid_route_old == fid_route_v2
    # endregion strict

    # region contains
    fid_route_v2_10_18 = path_finder_v2.get_fid_route(QgsPointXY(10.0, 0.0), QgsPointXY(18.0, 0.0),
                                                      mode=PathFinderFidRouteModes.CONTAINS)
    assert fid_route_v2_10_18 == [11, 12, 13, 14]

    fid_route_v2_11_18 = path_finder_v2.get_fid_route(QgsPointXY(11.0, 0.0), QgsPointXY(18.0, 0.0),
                                                      mode=PathFinderFidRouteModes.CONTAINS)
    assert fid_route_v2_11_18 == [11, 12, 13, 14]

    fid_route_v2_11_18 = path_finder_v2.get_fid_route(QgsPointXY(12.0, 0.0), QgsPointXY(18.0, 0.0),
                                                      mode=PathFinderFidRouteModes.CONTAINS)
    assert fid_route_v2_11_18 == [11, 12, 13, 14]

    fid_route_v2_13_18 = path_finder_v2.get_fid_route(QgsPointXY(13.0, 0.0), QgsPointXY(18.0, 0.0),
                                                      mode=PathFinderFidRouteModes.CONTAINS)
    assert fid_route_v2_13_18 == [12, 13, 14]

    fid_route_v2_13_17 = path_finder_v2.get_fid_route(QgsPointXY(13.0, 0.0), QgsPointXY(17.0, 0.0),
                                                      mode=PathFinderFidRouteModes.CONTAINS)
    assert fid_route_v2_13_17 == [12, 13, 14]

    fid_route_v2_15_17 = path_finder_v2.get_fid_route(QgsPointXY(15.0, 0.0), QgsPointXY(17.0, 0.0),
                                                      mode=PathFinderFidRouteModes.CONTAINS)
    assert fid_route_v2_15_17 == [13, 14]

    fid_route_v2_15_17 = path_finder_v2.get_fid_route(QgsPointXY(11.0, 0.0), QgsPointXY(12.0, 0.0),
                                                      mode=PathFinderFidRouteModes.CONTAINS)
    assert fid_route_v2_15_17 == [11]
    # endregion contains


def test_path_finder_get_fid_route(plugin_qgis_new_project):
    """

    .. code-block:: python

        from <package>.submodules.base.qgis.path_finder_v2 import PathFinderV2

        point_layer = QgsProject.instance().mapLayersByName("Punktobjekte")[0]
        line_layer = QgsProject.instance().mapLayersByName("Trasse")[0]

        start_feature, end_feature = iface.activeLayer().selectedFeatures()
        start_point = start_feature.geometry().asPoint()
        end_point = end_feature.geometry().asPoint()

        print(f"START: QgsPointXY({start_point.x()}, {start_point.y()})")
        print(f"END: QgsPointXY({end_point.x()}, {end_point.y()})")
        print("ROUTE:", PathFinderV2(line_layer).get_fid_route(start_point, end_point)[0])

        print(f"(QgsPointXY({start_point.x()}, {start_point.y()}),", f"QgsPointXY({end_point.x()}, {end_point.y()}),", f"{PathFinder.get_fid_route(line_layer, start_point, end_point)[0]})")

    """

    from ..qgis.path_finder_v2 import PathFinderV2, PathFinderMethods
    from ..qgis.path_finder import PathFinder

    geojson = (Path(__file__).parent / "test_path_finder_v2.geojson").as_posix()
    layer = QgsVectorLayer(geojson, "test", "ogr")

    path_finder_v2 = PathFinderV2(layer)

    CONFIG = [
        (QgsPointXY(2534662.9116416723, 15879077.673362624), QgsPointXY(2535361.32466705, 15878500.705561217), [40]),
        (QgsPointXY(2534662.9116416723, 15879077.673362624), QgsPointXY(2534483.359213288, 15877393.329773579),
         [40, 21, 47, 18, 20]),
        (QgsPointXY(2535361.32466705, 15878500.705561217), QgsPointXY(2534363.089840602, 15877481.684316106),
         [21, 47, 35, 7, 10, 8, 49, 6, 19, 55]),
        (QgsPointXY(2534483.359213288, 15877393.329773579), QgsPointXY(2534376.0695787165, 15877410.072197765),
         [20, 26, 25, 31, 27, 34, 54, 56, 52, 53, 32, 23]),
        (QgsPointXY(2534282.625968749, 15877256.291979125), QgsPointXY(2534141.8663761015, 15877345.785895415),
         [41, 45, 29, 50, 14, 11, 12, 63, 65, 59, 61, 4, 5, 1, 24, 43]),
        (QgsPointXY(2534282.625968749, 15877256.291979125), QgsPointXY(2534376.0695787165, 15877410.072197765),
         [41, 51, 48, 60, 36, 38, 33, 62, 57, 58, 46, 0, 64, 3, 2, 15, 13, 17, 16, 44, 9, 37, 31, 27, 34, 54, 56, 52,
          53, 32, 23]),
        (QgsPointXY(2534363.089840602, 15877481.684316106), QgsPointXY(2534141.8663761015, 15877345.785895415),
         [55, 19, 6, 49, 8, 10, 7, 35, 18, 26, 25, 37, 9, 44, 16, 17, 13, 15, 2, 3, 64, 0, 46, 58, 57, 62, 33, 38, 36,
          60, 48, 51, 45, 29, 50, 14, 11, 12, 63, 65, 59, 61, 4, 5, 1, 24, 43])
    ]
    print("START")

    import time
    s = time.time()
    for index, (start_point, end_point, expected_path) in enumerate(CONFIG):
        result = path_finder_v2.get_fid_route(start_point, end_point, methods=[PathFinderMethods.Dijkstra])
        assert result == expected_path
    str_ende_v2 = f"ENDE PathFinderV2: {time.time() - s}"

    s = time.time()
    for index, (start_point, end_point, expected_path) in enumerate(CONFIG):
        result = PathFinder.get_fid_route(layer, start_point, end_point, method=2)[0]  # Dijkstra
        assert result == expected_path
    str_ende_v1 = f"ENDE PathFinder(V1): {time.time() - s}"

    print(str_ende_v2)
    print(str_ende_v1)

    print("END")
