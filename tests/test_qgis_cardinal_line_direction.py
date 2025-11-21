# -*- coding: utf-8 -*-
# SPDX-FileCopyrightText: 2025 Deutsche Telekom Technik GmbH <f.vonstudsinske@telekom.de>
# SPDX-License-Identifier: GPL-3.0-or-later

import pytest

from qgis.core import QgsPointXY, QgsGeometry, QgsFeature, QgsVectorLayer

from .fixtures import plugin_qgis_new_project
from ..qgis.cardinal_line_direction import get_cardinal_direction

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

TESTDATA = [
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


@pytest.mark.parametrize("point,line,expected", TESTDATA)
def test_get_cardinal_direction_success(point: tuple[float, float],
                                        line: list[list[tuple[float, float]]],
                                        expected: int):

    point_feature: QgsFeature
    line_features: list[QgsFeature]
    point_feature, line_features = _get_point_line_feature(point, line)

    point_layer = QgsVectorLayer("Point?crs=epsg:3857", "PyTestPoint", "memory")
    point_layer.dataProvider().addFeature(point_feature)

    assert get_cardinal_direction(point_feature=point_feature, line_features=line_features,
                                  point_layer=point_layer) == expected


@pytest.mark.parametrize("point,line,expected", TESTDATA)
def test_test_get_cardinal_direction_success_failed(point: tuple[float, float],
                                                    line: list[list[tuple[float, float]]],
                                                    expected: int):

    point_feature: QgsFeature
    line_features: list[QgsFeature]
    point_feature, line_features = _get_point_line_feature(point, line)

    point_layer = QgsVectorLayer("Point?crs=epsg:3857", "PyTestPoint", "memory")
    point_layer.dataProvider().addFeature(point_feature)

    assert not get_cardinal_direction(point_feature=point_feature, line_features=line_features,
                                      point_layer=point_layer) != expected
