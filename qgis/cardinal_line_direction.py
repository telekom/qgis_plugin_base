# -*- coding: utf-8 -*-
# SPDX-FileCopyrightText: 2025 Deutsche Telekom Technik GmbH <f.vonstudsinske@telekom.de>
# SPDX-License-Identifier: GPL-3.0-only

from typing import List

from qgis.core import QgsGeometry, QgsFeatureRequest, QgsFeature, QgsVectorLayer, QgsPointXY

from .geometry_sort_line import sort_lines
from .. import constants


def get_cardinal_direction(point_feature: QgsFeature, line_features: List[QgsFeature],
                           point_layer: QgsVectorLayer) -> int:
    r""" detect direction of line from given point
             N
     +---------------+
     |   \   0   /   |
     | 7  \     /  1 |
     |-    \   /    -|
     |   -  \ /  -   |
    W| 6    - -    2 |E
     |   -  / \  -   |
     |-    /   \    -|
     | 5  /     \  3 |
     |   /   4   \   |
     +---------------+
             S
    """
    line_geos: list[list[QgsPointXY]] = [f.geometry().asPolyline() for f in line_features]
    try:
        all_polylines: list[list[QgsPointXY]] = sort_lines(line_geos, constants.EPSILON)
    except:
        # an exception is raisable, when the lines are not sortable
        return -1
    poly_point_first: QgsPointXY = all_polylines[0][0]
    poly_point_last: QgsPointXY = all_polylines[-1][-1]

    def get_points_from_bounding_box(point) -> list[QgsFeature]:
        geom: QgsGeometry = QgsGeometry.fromPointXY(point)
        bounding_box = geom.boundingBox()
        # get bigger bounding box to find features intersecting
        bounding_box.grow(0.00001)
        filter_request = QgsFeatureRequest().setFilterRect(bounding_box)
        # filtered features which are intersecting with point
        filtered_features: list[QgsFeature] = point_layer.getFeatures(filter_request)

        return filtered_features

    if point_feature in get_points_from_bounding_box(poly_point_first):
        pass
    elif point_feature in get_points_from_bounding_box(poly_point_last):
        # swap first and last
        poly_point_first, poly_point_last = poly_point_last, poly_point_first
    else:
        raise RuntimeError(f"get_cardinal_direction coordinate problem")

    degree = poly_point_first.azimuth(poly_point_last)
    """ 12 till 6 o'clock is 0 till 180 degree; 6 till 12 o'clock is -180 till 0 degree """
    degree = round((degree if degree > 0 else degree + 360), 2)

    match degree:
        case degree if (0 <= degree < 22.6) or (337.5 <= degree <= 360):  # 0 North
            direction_nr = 0
        case degree if (22.5 <= degree < 67.5):  # 1 North-East
            direction_nr = 1
        case degree if (67.5 <= degree < 112.5):  # 2 East
            direction_nr = 2
        case degree if (112.5 <= degree < 157.5):  # 3 South-East
            direction_nr = 3
        case degree if (157.5 <= degree < 202.5):  # 4 South
            direction_nr = 4
        case degree if (202.5 <= degree < 247.5):  # 5 South-West
            direction_nr = 5
        case degree if (247.5 <= degree < 292.5):  # 6 West
            direction_nr = 6
        case degree if (292.5 <= degree < 337.5):  # 7 North-West
            direction_nr = 7
        case _:
            direction_nr = -1  # ERROR

    return direction_nr
