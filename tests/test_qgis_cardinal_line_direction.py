# -*- coding: utf-8 -*-
# SPDX-FileCopyrightText: 2025 Deutsche Telekom Technik GmbH <f.vonstudsinske@telekom.de>
# SPDX-License-Identifier: GPL-3.0-only

import pytest

from qgis.core import QgsPointXY, QgsGeometry, QgsFeature, QgsVectorLayer

from .fixtures import plugin_qgis_new_project
from ..qgis.cardinal_line_direction import (get_cardinal_direction, get_direction_number_from_degree,
                                            get_outgoing_cardinal_direction_for_point,
                                            circular_mean_cardinal_direction_numbers)

CENTER = (1331231.412915, 6712613.907331)
LINE_0 = [[CENTER, (1331232.412915, 6712623.907331)]]  # North
LINE_2 = [[CENTER, (1331241.412915, 6712614.907331)]]  # East
LINE_4 = [[CENTER, (1331230.412915, 6712603.907331)]]  # South
LINE_6 = [[CENTER, (1331221.412915, 6712614.907331)]]  # West
LINE_0_R = [[(1331232.412915, 6712623.907331), CENTER]]  # North
LINE_2_R = [[(1331241.412915, 6712614.907331), CENTER]]  # East
LINE_4_R = [[(1331230.412915, 6712603.907331), CENTER]]  # South
LINE_6_R = [[(1331221.412915, 6712614.907331), CENTER]]  # West
LINE_7 = [[(960285.64421583863440901, 6991419.53881987743079662), (960285.64421583863440901, 6991433.06909938063472509)]]  # North

CARDINAL_DIRECTION_TESTDATA = [
    (CENTER, LINE_0, 0),
    (CENTER, LINE_2, 2),
    (CENTER, LINE_4, 4),
    (CENTER, LINE_6, 6),
    (CENTER, LINE_0_R, 0),
    (CENTER, LINE_2_R, 2),
    (CENTER, LINE_4_R, 4),
    (CENTER, LINE_6_R, 6),
    ((960285.64421583863440901, 6991419.53881987743079662), LINE_7, 0),
]

DEGREE_TESTDATA = [
    (10.0, 0),
    (40.0, 1),
    (90.0, 2),
    (135.5, 3),
    (198.76, 4),
    (233.333, 5),
    (247.6, 6),
    (300.0000001, 7),
    (-1.0, 0),
    (9000.0, -1)
]

CARDINAL_DIRECTION_FOR_POINT_TESTDATA = [
    ([
        QgsPointXY(982001.420821384, 6411567.7079500435),
        QgsPointXY(982174.2066315822, 6411743.334782532),
    ], [1]),

    ([
        QgsPointXY(982196.6765351506, 6411565.641752014),
        QgsPointXY(982196.9348099043, 6411585.270633292),
    ], [0]),

    ([
        QgsPointXY(982129.2668244455, 6411500.039964585),
        QgsPointXY(982130.2999234601, 6411492.2917219745),
        QgsPointXY(982121.7768565894, 6411488.6758754235),
        QgsPointXY(982129.2668244455, 6411479.377984292),
        QgsPointXY(982119.9689333137, 6411472.4045659425),
        QgsPointXY(982113.7703392259, 6411472.4045659425),
        QgsPointXY(982116.0948120088, 6411461.298751536),
        QgsPointXY(982118.4192847918, 6411459.49082826),
        QgsPointXY(982112.7372402112, 6411456.908080723),
        QgsPointXY(982113.5120644722, 6411453.033959419),
        QgsPointXY(982114.2868887333, 6411452.517409911),
    ], [4]),

    ([
        QgsPointXY(982061.5988389866, 6411579.330313958),
        QgsPointXY(982070.8967301184, 6411576.7475664215),
        QgsPointXY(982068.8305320891, 6411583.72098477),
        QgsPointXY(982075.2874009307, 6411576.231016914),
        QgsPointXY(982081.7442697721, 6411568.741049058),
        QgsPointXY(982084.3270173087, 6411575.197917899),
        QgsPointXY(982079.1615222355, 6411578.297214943),
        QgsPointXY(982092.5918094259, 6411577.780665436),
        QgsPointXY(982103.1810743258, 6411575.714467407),
    ], [2]),

    ([
        QgsPointXY(982126.4258021553, 6411641.57452959),
        QgsPointXY(982117.1279110234, 6411639.766606314),
        QgsPointXY(982112.9955149649, 6411644.157277127),
        QgsPointXY(982111.7041411967, 6411637.7004082855),
        QgsPointXY(982109.1213936601, 6411629.435616168),
        QgsPointXY(982103.9558985869, 6411639.5083315605),
        QgsPointXY(982099.5652277747, 6411631.243539443),
        QgsPointXY(982092.8500841794, 6411635.117660749),
        QgsPointXY(982093.1083589331, 6411628.660791907),
        QgsPointXY(982086.6514900917, 6411626.8528686315),
    ], [6]),

    ([
        QgsPointXY(982162.3259929139, 6411678.249544609),
        QgsPointXY(982173.9483568287, 6411671.792675768),
        QgsPointXY(982153.8029260432, 6411688.322260003),
    ], [3]),

    ([
        QgsPointXY(982001.420821384, 6411567.7079500435),
    ], [-1]),
]

CIRCULAR_MEAN_TESTDATA = [
    ([7, 1, 2], 1),
    ([5, 4, 3], 4),
    ([0, 0, 7], 0),
    ([], -1),
    ([0, 0, 0, 0, 1, 2, 3, 4, 0, 0, 0], 0),
    ([1, 2, 3, 4, 5, 6, 7], 4),
    ([0], 0)
]


def _get_point_line_feature(point: tuple[float, float], lines: list[list[tuple[float, float]]]) \
        -> tuple['QgsFeature', list['QgsFeature']]:
    point_xy = QgsPointXY(point[0], point[1])
    point_geom = QgsGeometry.fromPointXY(point_xy)
    point_feat = QgsFeature()
    point_feat.setGeometry(point_geom)

    line_feats = []
    for line in lines:
        line_geom = QgsGeometry.fromPolylineXY([QgsPointXY(seg[0], seg[1]) for seg in line])
        line_feat = QgsFeature()
        line_feat.setGeometry(line_geom)

        line_feats.append(line_feat)

    return point_feat, line_feats


@pytest.mark.parametrize("point,line,expected", CARDINAL_DIRECTION_TESTDATA)
def test_get_cardinal_direction_success(point: tuple[float, float],
                                        line: list[list[tuple[float, float]]], expected: int):

    point_feature: QgsFeature
    line_features: list[QgsFeature]
    point_feature, line_features = _get_point_line_feature(point, line)

    point_layer = QgsVectorLayer("Point?crs=epsg:3857", "PyTestPoint", "memory")
    point_layer.dataProvider().addFeature(point_feature)

    assert get_cardinal_direction(point_feature=point_feature, line_features=line_features,
                                  point_layer=point_layer) == expected


@pytest.mark.parametrize("point,line,expected", CARDINAL_DIRECTION_TESTDATA)
def test_get_cardinal_direction_failed(point: tuple[float, float],
                                       line: list[list[tuple[float, float]]], expected: int):

    point_feature: QgsFeature
    line_features: list[QgsFeature]
    point_feature, line_features = _get_point_line_feature(point, line)

    point_layer = QgsVectorLayer("Point?crs=epsg:3857", "PyTestPoint", "memory")
    point_layer.dataProvider().addFeature(point_feature)

    assert not get_cardinal_direction(point_feature=point_feature, line_features=line_features,
                                      point_layer=point_layer) != expected


@pytest.mark.parametrize("degree,expected", DEGREE_TESTDATA)
def test_get_direction_number_from_degree(degree: float, expected: int):
    assert get_direction_number_from_degree(degree) == expected


def test_get_direction_number_from_degree_error():
    with pytest.raises(TypeError):
        get_direction_number_from_degree("a")


@pytest.mark.parametrize("point_list,expected", CARDINAL_DIRECTION_FOR_POINT_TESTDATA)
def test_get_outgoing_cardinal_direction_for_point(point_list, expected):
    point = QgsFeature()
    point.setGeometry(QgsGeometry.fromPointXY(QgsPointXY(point_list[0][0], point_list[0][1])))

    line = QgsFeature()
    line.setGeometry(QgsGeometry.fromPolylineXY(point_list))

    assert get_outgoing_cardinal_direction_for_point(point, [line]) == expected


def test_get_outgoing_cardinal_direction_for_point_point_not_included():
    point = QgsFeature()
    point.setGeometry(QgsGeometry.fromPointXY(QgsPointXY(982001.420821384, 6411567.7079500435)))

    line = QgsFeature()
    line.setGeometry(QgsGeometry.fromPolylineXY(
        [QgsPointXY(982196.6765351506, 6411565.641752014),
         QgsPointXY(982196.9348099043, 6411585.270633292),]))

    assert get_outgoing_cardinal_direction_for_point(point, [line]) == [-1]


@pytest.mark.parametrize("numbers,expected", CIRCULAR_MEAN_TESTDATA)
def test_circular_mean_cardinal_direction_numbers(numbers, expected):
    assert circular_mean_cardinal_direction_numbers(numbers) == expected
