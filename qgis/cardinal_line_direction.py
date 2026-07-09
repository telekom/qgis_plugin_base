# -*- coding: utf-8 -*-
# SPDX-FileCopyrightText: 2025 Deutsche Telekom Technik GmbH <f.vonstudsinske@telekom.de>
# SPDX-License-Identifier: GPL-3.0-only

from math import pi, cos, sin, atan2
from typing import List

from qgis.core import QgsGeometry, QgsFeatureRequest, QgsFeature, QgsVectorLayer, QgsPointXY

from .geometry_sort_line import sort_lines
from .. import constants


def get_cardinal_direction(point_feature: QgsFeature, line_features: List[QgsFeature],
                           point_layer: QgsVectorLayer) -> int:
    r""" detect direction of line from given point
                    N
            +---------------+
         NW |   \   0   /   | NE
            | 7  \     /  1 |
            |-    \   /    -|
            |   -  \ /  -   |
         W  | 6    - -    2 | E
            |   -  / \  -   |
            |-    /   \    -|
            | 5  /     \  3 |
         SW |   /   4   \   | SE
            +---------------+
                    S
    """

    # inner function
    def get_points_from_bounding_box(point) -> list[QgsFeature]:
        """ get all features from point layer which are intersecting with point

            :param point: QgsPointXY point to get intersecting features
            :return: list of QgsFeature which are intersecting with point
        """
        geom: QgsGeometry = QgsGeometry.fromPointXY(point)
        bounding_box = geom.boundingBox()
        # get bigger bounding box to find features intersecting
        bounding_box.grow(constants.EPSILON)
        filter_request = QgsFeatureRequest().setFilterRect(bounding_box)
        # filtered features which are intersecting with point
        filtered_features: list[QgsFeature] = point_layer.getFeatures(filter_request)

        return filtered_features
    # end of inner function

    line_geos: list[list[QgsPointXY]] = [f.geometry().asPolyline() for f in line_features]
    try:
        all_polylines: list[list[QgsPointXY]] = sort_lines(line_geos, constants.EPSILON)
    except AttributeError:
        # an exception is raisable, when the lines are not sortable
        return -1
    poly_point_first: QgsPointXY = all_polylines[0][0]
    poly_point_last: QgsPointXY = all_polylines[-1][-1]

    if point_feature in get_points_from_bounding_box(poly_point_first):
        pass
    elif point_feature in get_points_from_bounding_box(poly_point_last):
        # swap first and last
        poly_point_first, poly_point_last = poly_point_last, poly_point_first
    else:
        raise RuntimeError(f"get_cardinal_direction coordinate problem")

    degree = poly_point_first.azimuth(poly_point_last)

    return get_direction_number_from_degree(degree)


def get_direction_number_from_degree(degree: float) -> int:
    r""" matches degrees to cardinal direction as numbers from 0 - 7
                   N
           +---------------+
        NW |   \   0   /   | NE
           | 7  \     /  1 |
           |-    \   /    -|
           |   -  \ /  -   |
        W  | 6    - -    2 | E
           |   -  / \  -   |
           |-    /   \    -|
           | 5  /     \  3 |
        SW |   /   4   \   | SE
           +---------------+
                   S

        :param degree: float degree -> 12 till 6 o'clock is 0 till 180 degree; 6 till 12 o'clock is -180 till 0 degree
        :return: int converted direction number from degree (-1 if error)
    """
    degree = round((degree if degree > 0 else degree + 360), 2)

    if (0 <= degree < 22.6) or (337.5 <= degree <= 360):  # 0 North
        direction_nr = 0
    elif (22.5 <= degree < 67.5):  # 1 North-East
        direction_nr = 1
    elif (67.5 <= degree < 112.5):  # 2 East
        direction_nr = 2
    elif (112.5 <= degree < 157.5):  # 3 South-East
        direction_nr = 3
    elif (157.5 <= degree < 202.5):  # 4 South
        direction_nr = 4
    elif (202.5 <= degree < 247.5):  # 5 South-West
        direction_nr = 5
    elif (247.5 <= degree < 292.5):  # 6 West
        direction_nr = 6
    elif (292.5 <= degree < 337.5):  # 7 North-West
        direction_nr = 7
    else:
        direction_nr = -1  # ERROR

    return direction_nr


# mapping dict for direction numbers, to translate in readable direction
direction_number_mapping = {
    0: "Norden",
    1: "Nord-Osten",
    2: "Osten",
    3: "Süd-Osten",
    4: "Süden",
    5: "Süd-Westen",
    6: "Westen",
    7: "Nord-Westen",
    # default error case
    -1: "Keine Richtung ermittelt",
}


def get_outgoing_cardinal_direction_for_point(point: QgsFeature, line_features: List[QgsFeature]) -> List[int]:
    r""" get outgoing direction of every line for point, point has to be included in line_feature points

                   N
           +---------------+
        NW |   \   0   /   | NE
           | 7  \     /  1 |
           |-    \   /    -|
           |   -  \ /  -   |
        W  | 6    - -    2 | E
           |   -  / \  -   |
           |-    /   \    -|
           | 5  /     \  3 |
        SW |   /   4   \   | SE
           +---------------+
                   S

        :param point: point QgsFeature as starting position for outgoing cardinal direction
        :param line_features: list of line QgsFeatures for outgoing cardinal direction
        :return: list of int as cardinal dircetions
    """
    starting_point = point.geometry().asPoint()

    result_list = []

    for line_feature in line_features:

        line_feature_points = line_feature.geometry().asPolyline()

        # not a valid line
        if len(line_feature_points) < 2:
            result_list.append(-1)
            continue

        # check which end point of list is correct
        if line_feature_points[0].compare(starting_point, constants.EPSILON):
            direction_point = line_feature_points[1]
        elif line_feature_points[-1].compare(starting_point, constants.EPSILON):
            direction_point = line_feature_points[-2]
        # point not end point in point list
        else:
            result_list.append(-1)
            continue

        # get directional degree for both points
        degree = starting_point.azimuth(direction_point)
        result_list.append(get_direction_number_from_degree(degree))

    return result_list


def circular_mean_cardinal_direction_numbers(numbers: List[int]) -> int:
    """ Calculate the circular mean of a list of integers on a circular scale.

        :param numbers: list of integers in the range 0 - 7 (cardinal direction numbers)
        :return: circular mean of given list
    """
    n = len(numbers)
    # 8 -> max cardinal directions + 1
    angles = [2 * pi * num / 8 for num in numbers]
    x = sum(cos(a) for a in angles) / n
    y = sum(sin(a) for a in angles) / n
    mean_angle = atan2(y, x)

    # make sure angle is positive
    if mean_angle < 0:
        mean_angle += 2 * pi

    mean_num = round(mean_angle * 8 / (2 * pi)) % 8

    return mean_num
