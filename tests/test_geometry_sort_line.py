# -*- coding: utf-8 -*-
# SPDX-FileCopyrightText: 2025 Deutsche Telekom Technik GmbH <f.vonstudsinske@telekom.de>
# SPDX-License-Identifier: GPL-3.0-or-later

from qgis.core import QgsGeometry

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
