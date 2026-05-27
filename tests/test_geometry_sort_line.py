# -*- coding: utf-8 -*-
# SPDX-FileCopyrightText: 2025 Deutsche Telekom Technik GmbH <f.vonstudsinske@telekom.de>
# SPDX-License-Identifier: GPL-3.0-only

import pytest

from qgis.core import QgsGeometry, QgsFeature, QgsPointXY

from .fixtures import plugin_qgis_new_project


def test_get_neighbor_type(plugin_qgis_new_project):
    from ..qgis.geometry_sort_line import (get_neighbor_type, N_LEFT, N_RIGHT,
                                           N_LEFT_REVERSED, N_RIGHT_REVERSED)

    """
                         geom_4
                           | 
    geom_1 - geom_2+geom_3 - geom_5

    """
    # geom_1 is the START line
    geom_1 = QgsGeometry.fromWkt('LineString (0.0 0.0, 1.0 0.0)')
    geom_2 = QgsGeometry.fromWkt('LineString (1.0 0.0, 2.0 0.0)')  # overlapping with geom_3
    geom_3 = QgsGeometry.fromWkt('LineString (2.0 0.0, 1.0 0.0)')  # reversed geom_2, overlapping with geom_2
    geom_4 = QgsGeometry.fromWkt('LineString (2.0 0.0, 2.0 1.0)')
    geom_5 = QgsGeometry.fromWkt('LineString (2.0 0.0, 3.0 0.0)')

    assert get_neighbor_type(geom_1.asPolyline(), geom_2.asPolyline()) == N_RIGHT
    assert get_neighbor_type(geom_1.asPolyline(), geom_3.asPolyline()) == N_RIGHT_REVERSED
    assert get_neighbor_type(geom_2.asPolyline(), geom_4.asPolyline()) == N_RIGHT
    assert get_neighbor_type(geom_3.asPolyline(), geom_4.asPolyline()) == N_LEFT_REVERSED
    assert get_neighbor_type(geom_4.asPolyline(), geom_5.asPolyline()) == N_LEFT_REVERSED
    assert get_neighbor_type(geom_3.asPolyline(), geom_5.asPolyline()) == N_LEFT_REVERSED
    assert get_neighbor_type(geom_2.asPolyline(), geom_5.asPolyline()) == N_RIGHT
    assert get_neighbor_type(geom_2.asPolyline(), geom_1.asPolyline()) == N_LEFT


def test_realign_feature_geometries_1(plugin_qgis_new_project):
    from ..qgis.geometry_sort_line import realign_feature_geometries

    """
    geom_1 - geom_2 - geom_3[reversed] - geom_4

    """
    # geom_1 is the START line
    geom_1 = QgsGeometry.fromWkt('LineString (0.0 0.0, 1.0 0.0)')
    geom_2 = QgsGeometry.fromWkt('LineString (1.0 0.0, 2.0 0.0)')
    geom_3 = QgsGeometry.fromWkt('LineString (3.0 0.0, 2.0 0.0)')  # reversed geom_3
    geom_4 = QgsGeometry.fromWkt('LineString (3.0 0.0, 4.0 0.0)')

    def __get_feature(id_, geometry):
        feature = QgsFeature(id_)
        feature.setGeometry(geometry)
        return feature

    features = [
        __get_feature(i, geometry)
        for i, geometry in enumerate([geom_1, geom_2, geom_3, geom_4])
    ]

    # just realign
    realign_feature_geometries(features)

    with pytest.raises(ValueError):
        # must raise -> wrong start point, not in the first feature
        realign_feature_geometries(features, start_point=QgsPointXY(2.0, 0.0))

    with pytest.raises(ValueError):
        # must raise -> valid start point in first feature, but following features cannot be not correctly added
        # because geom_2 has no 0,0 coordinate
        realign_feature_geometries(features, start_point=QgsPointXY(1.0, 0.0))


@pytest.mark.parametrize("geometries", [
    # normal order, already aligned
    ['LineString (0.0 0.0, 1.0 0.0)',
     'LineString (1.0 0.0, 2.0 0.0)',
     'LineString (2.0 0.0, 3.0 0.0)'],
    # first geometry OK, 2nd reversed
    ['LineString (0.0 0.0, 1.0 0.0)',
     'LineString (2.0 0.0, 1.0 0.0)',
     'LineString (2.0 0.0, 3.0 0.0)'],
    # first geometry reversed, 2nd reversed
    ['LineString (1.0 0.0, 0.0 0.0)',
     'LineString (2.0 0.0, 1.0 0.0)',
     'LineString (2.0 0.0, 3.0 0.0)'],
    # first geometry reversed, 2nd ok
    ['LineString (1.0 0.0, 0.0 0.0)',
     'LineString (1.0 0.0, 2.0 0.0)',
     'LineString (2.0 0.0, 3.0 0.0)'],
])
def test_realign_feature_geometries_2(plugin_qgis_new_project, geometries: list[str]):
    from ..qgis.geometry_sort_line import realign_feature_geometries

    """
    geom_1[ok/reversed] - geom_2[ok/reversed] - geom_3

    """

    def __get_feature(id_, wkt):
        feature = QgsFeature(id_)
        feature.setGeometry(QgsGeometry.fromWkt(wkt))
        return feature

    features = [
        __get_feature(i, wkt)
        for i, wkt in enumerate(geometries)
    ]

    # just realign
    realign_feature_geometries(features)
