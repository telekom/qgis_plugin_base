# -*- coding: utf-8 -*-
# SPDX-FileCopyrightText: 2025 Deutsche Telekom Technik GmbH <f.vonstudsinske@telekom.de>
# SPDX-License-Identifier: GPL-3.0-only

from typing import List, Tuple, Union, Optional

from qgis.core import (QgsPointXY, QgsGeometry, QgsFeature, QgsPoint, QgsFeatureIterator,
                       QgsVectorLayer, QgsWkbTypes, QgsFeatureRequest)

from .geometry import get_polyline
from ..constants import EPSILON, N_LEFT, N_RIGHT, N_LEFT_REVERSED, N_NONE, N_RIGHT_REVERSED, TO_STRING_PREC


def adjacent_to_geometry(poly_lines: List[List[QgsPointXY]], epsilon: float = EPSILON) -> List[QgsGeometry]:
    """ Combines a list of poly lines to geometries.
        Created geometries can be a single-type or multi-type geometry.

        :param poly_lines: list of (sorted) poly lines
        :param epsilon: epsilon value
        :return: list of new geometries
    """
    geometries = []
    for new_line in poly_lines:

        first = True
        out_geom = None

        for segment in new_line:
            geom = (QgsGeometry.fromPolyline([QgsPoint(p) for p in segment]))
            if first:
                out_geom = geom
                first = False
            else:
                out_geom = out_geom.combine(geom)

        if out_geom.isMultipart():
            # try to convert multi part geometry into single part type
            try:
                lines = sort_lines(out_geom.asMultiPolyline(), epsilon=epsilon)
                new_poly_line = []
                for segment in lines:
                    for p in segment:
                        if p not in new_poly_line:
                            new_poly_line.append(p)
                out_geom = QgsGeometry.fromPolylineXY(new_poly_line)
            except AttributeError:
                pass
        geometries.append(out_geom)

    return geometries


def get_neighbor_type(line1: List[QgsPointXY], line2: List[QgsPointXY], epsilon: float = EPSILON) -> int:
    """ compares to polyline-list and return neighbor type.

        :param line1: line of QgsPointXY
        :param line2: line of QgsPointXY
        :param epsilon: tolerance for comparing points, defaults to _EPSILON
        :return: value of _constants
    """

    # tolerance >= distance >= 0
    distance = line2[-1].distance(line1[0])
    if line2[-1].compare(line1[0], epsilon) or (epsilon >= distance >= 0):
        return N_LEFT

    distance = line2[0].distance(line1[-1])
    if line2[0].compare(line1[-1], epsilon) or (epsilon >= distance >= 0):
        return N_RIGHT

    distance = line2[0].distance(line1[0])
    if line2[0].compare(line1[0], epsilon) or (epsilon >= distance >= 0):
        return N_LEFT_REVERSED

    distance = line2[-1].distance(line1[-1])
    if line2[-1].compare(line1[-1], epsilon) or (epsilon >= distance >= 0):
        return N_RIGHT_REVERSED

    return N_NONE


def sort_lines(lines: List[List[QgsPointXY]],
               epsilon: float = EPSILON,
               expert_mode: bool = False) -> List[List[QgsPointXY]]:
    """ Sorts lines in order of their connection with line start on line end.

        :param lines: list of lines
        :param epsilon: tolerance for comparing points, defaults to _EPSILON
        :param expert_mode: Set to True, to get a list with sorted and a list with remaining objects
        :return: sorted line list
        :raises AttributeError: lines are not connected (only when expert_mode is False)
    """
    sorted_lines: List[List[QgsPointXY]] = [lines.pop()]
    found: bool = True
    while lines and found:

        found = False

        for i, _ in enumerate(lines):
            if get_neighbor_type(sorted_lines[0], lines[i], epsilon) == N_LEFT:
                sorted_lines = [lines.pop(i)] + sorted_lines
                found = True
                break

            if get_neighbor_type(sorted_lines[-1], lines[i], epsilon) == N_RIGHT:
                sorted_lines = sorted_lines + [lines.pop(i)]
                found = True
                break

            if get_neighbor_type(sorted_lines[0], lines[i], epsilon) == N_LEFT_REVERSED:
                lines[i].reverse()
                sorted_lines = [lines.pop(i)] + sorted_lines
                found = True
                break

            if get_neighbor_type(sorted_lines[-1], lines[i], epsilon) == N_RIGHT_REVERSED:
                lines[i].reverse()
                sorted_lines = sorted_lines + [lines.pop(i)]
                found = True
                break

        if not found:
            if expert_mode:
                return sorted_lines, lines

            raise AttributeError(
                f"sorted_lines = {sorted_lines}\nremaining points = {lines}"
            )

    if expert_mode:
        return sorted_lines, lines

    return sorted_lines


def sort_lines_easy(lines: List[List[QgsPointXY]],
                    epsilon: float = EPSILON) -> Tuple[List[List[QgsPointXY]],
                                                                 List[List[QgsPointXY]]]:
    """ Sorts lines in order of their connection with line start on line end.

        :param lines: list of lines
        :param epsilon: tolerance for comparing points, defaults to _EPSILON
        :return: [sorted poly lines, not sortable poly lines]
    """
    sorted_lines: List[List[QgsPointXY]] = [lines.pop()]
    found: bool = True
    while lines and found:

        found = False

        for i, _ in enumerate(lines):
            if get_neighbor_type(sorted_lines[0], lines[i], epsilon) == N_LEFT:
                sorted_lines = [lines.pop(i)] + sorted_lines
                found = True
                break

            if get_neighbor_type(sorted_lines[-1], lines[i], epsilon) == N_RIGHT:
                sorted_lines = sorted_lines + [lines.pop(i)]
                found = True
                break

            if get_neighbor_type(sorted_lines[0], lines[i], epsilon) == N_LEFT_REVERSED:
                lines[i].reverse()
                sorted_lines = [lines.pop(i)] + sorted_lines
                found = True
                break

            if get_neighbor_type(sorted_lines[-1], lines[i], epsilon) == N_RIGHT_REVERSED:
                lines[i].reverse()
                sorted_lines = sorted_lines + [lines.pop(i)]
                found = True
                break

        if not found:
            break

    return sorted_lines, lines


def get_starting_feature_from_point(features: Union[List[QgsFeature], QgsFeatureIterator],
                                    point: QgsPointXY, epsilon: float = EPSILON) -> Optional[QgsFeature]:
    """ Returns the starting feature.
        Current geometry can be updated on returned feature, if direction update is needed.
        Only feature returned, where only one intersection is present with given point.
        Per feature only start end end vertex will be used.

        :param features: list or iterator of features
        :param point: point to use
        :param epsilon: epsilon for point comparison
    """
    # get first and last points for given feature
    points = {}
    def __get_edges(f):
        polyline = get_polyline(f.geometry())
        start = polyline[0]
        end = polyline[-1]

        for point_to_add in [start, end]:
            # add start vertex to dict
            for p in points:
                if p.compare(point_to_add, epsilon):
                    # add point to existing point
                    points[p].add(f)
                    break
            else:
                # no existing vertex found
                points[point_to_add] = {f}

        return start, end

    # save f and edges to points dict
    list(map(__get_edges, features))

    # get feature list by point and epsilon
    features_to_check = [fs for p, fs in points.items()
                         if p.compare(point, epsilon) and len(fs) == 1]
    if len(features_to_check) != 1:
        # to many features found
        return None

    # get first and lonely element from list and set
    feature = list(features_to_check[0])[0]
    polyline = get_polyline(feature.geometry())
    if polyline[-1].compare(point, epsilon):
        # end point equals to given point
        # reverse line
        polyline.reverse()
        feature.setGeometry(QgsGeometry.fromPolylineXY(polyline))

    return feature


def sort_lines_features(features: Union[List[QgsFeature], QgsFeatureIterator],
                        epsilon: float = EPSILON,
                        expert_mode: bool = False) -> List[QgsFeature]:
    """ Sorts list of features (wkb type -> LineString) in order of their connection with line start on line end.

        :param features: list of features
        :param epsilon: tolerance for comparing points, defaults to _EPSILON
        :param expert_mode: Set to True, to get a list with sorted and a list with remaining objects
        :return: sorted line list
        :raises AttributeError: features are not connected (only when expert_mode is False)
    """

    feature_list = [(f.id(), get_polyline(f.geometry()), f) for f in features]
    feature_dict = {fid: f for fid, _, f in feature_list}

    # -> [[fid, polyline], ...]
    sorted_geometries: List[Tuple[int, List[QgsPointXY], QgsFeature]] = [feature_list.pop()]
    while feature_list:

        found = False

        sorted_poly_first = sorted_geometries[0][1]
        sorted_poly_last = sorted_geometries[-1][1]

        for i, element in enumerate(feature_list):
            fid, polyline, _ = element
            if get_neighbor_type(sorted_poly_first, polyline, epsilon) == N_LEFT:
                sorted_geometries = [feature_list.pop(i)] + sorted_geometries
                found = True
                break

            if get_neighbor_type(sorted_poly_last, polyline, epsilon) == N_RIGHT:
                sorted_geometries = sorted_geometries + [feature_list.pop(i)]
                found = True
                break

            if get_neighbor_type(sorted_poly_first, polyline, epsilon) == N_LEFT_REVERSED:
                polyline.reverse()
                feature_dict[feature_list[i][0]].setGeometry(QgsGeometry.fromPolylineXY(polyline))
                sorted_geometries = [feature_list.pop(i)] + sorted_geometries
                found = True
                break

            if get_neighbor_type(sorted_poly_last, polyline, epsilon) == N_RIGHT_REVERSED:
                polyline.reverse()
                feature_dict[feature_list[i][0]].setGeometry(QgsGeometry.fromPolylineXY(polyline))
                sorted_geometries = sorted_geometries + [feature_list.pop(i)]
                found = True
                break

        if not found:
            if expert_mode:
                return [feature_dict[fid] for fid, *_ in sorted_geometries], feature_list

            raise AttributeError(
                f"sorted_geometries = {sorted_geometries}\nremaining points = {feature_list}"
            )

    if expert_mode:
        return [feature_dict[fid] for fid, *_ in sorted_geometries], feature_list

    return [feature_dict[fid] for fid, *_ in sorted_geometries]


def sort_and_group_features(features: Union[List[QgsFeature], QgsFeatureIterator],
                            epsilon: float = EPSILON) -> List[List[QgsFeature]]:
    """ Sorts a list of QgsFeature (geometry = LineString) by given line end points.
        Not connected features will be sorted in a separate feature list.

        :param features: list of features
        :param epsilon: tolerance for comparing points, defaults to _EPSILON
    """
    # relative import and prevent recursive import errors
    from .mergable_line_features import GroupMergableLineFeatures

    grouper = GroupMergableLineFeatures(features=features, epsilon=epsilon)
    result = grouper.run()

    return result


def realign_feature_geometries(features: Union[List[QgsFeature], QgsFeatureIterator],
                               start_point: Optional[QgsPointXY] = None,
                               epsilon: float = EPSILON) -> List[QgsFeature]:
    """ Returns a list with keeping the features order, but may realign the poly line.
        The given feature list is already sorted.
        Only the given geometry per feature may be reversed from the vertices to re-align the poly line
        to the next and previous feature.
        The given feature list and features will be updated in a mutable way!

        .. code-block:: python

            # geom_1 is the START line
            geom_1 = QgsGeometry.fromWkt('LineString (0.0 0.0, 1.0 0.0)')
            geom_2 = QgsGeometry.fromWkt('LineString (1.0 0.0, 2.0 0.0)')
            geom_3 = QgsGeometry.fromWkt('LineString (3.0 0.0, 2.0 0.0)')  # reversed geom_3
            geom_4 = QgsGeometry.fromWkt('LineString (3.0 0.0, 4.0 0.0)')

            # becomes the following geometries
            # geom_3 will be reversed, to align to the other poly lines
            geom_1 = QgsGeometry.fromWkt('LineString (0.0 0.0, 1.0 0.0)')
            geom_2 = QgsGeometry.fromWkt('LineString (1.0 0.0, 2.0 0.0)')
            geom_3 = QgsGeometry.fromWkt('LineString (2.0 0.0, 3.0 0.0)')
            geom_4 = QgsGeometry.fromWkt('LineString (3.0 0.0, 4.0 0.0)')

        :param features: sorted list of features
        :param start_point: Start point for the first feature.
                            Defaults to keep the current first feature poly line direction.

        :param features: list of features
        :param epsilon: tolerance for comparing points, defaults to _EPSILON
    """

    if not isinstance(features, list):
        features: List[QgsFeature] = list(features)

    if not features:
        return []

    # get the first feature from the sorted list
    first_feature = features[0]
    first_geometry = first_feature.geometry()
    poly_line = get_polyline(first_geometry)
    if len(poly_line) < 2:
        raise ValueError("first feature geometry must contain at least 2 vertices for realignment, "
                         f"got geometry wkt of '{first_geometry.asWkt()}'")

    if start_point is not None:
        if poly_line[-1].compare(start_point, epsilon):
            # reverse the poly line
            poly_line.reverse()
            # write back to the QgsFeature (will not write it back to the data source)
            first_feature.setGeometry(QgsGeometry.fromPolylineXY(poly_line))
            next_point = poly_line[-1]
        elif poly_line[0].compare(start_point, epsilon):
            # no feature update, keep poly line as it is
            next_point = poly_line[-1]
        else:
            raise ValueError(f"given {start_point.toString(TO_STRING_PREC)=} not in the first_feature's poly line"
                             f"with geometry wkt of '{first_feature.geometry().asWkt()}'")

        if len(features) == 1:
            # no further handling, return here
            return features

    else:
        if len(features) == 1:
            # no further handling
            return features

        next_point = poly_line[-1]

        # get the start and end vertices from the first feature
        first_start_point = poly_line[0]  # A
        first_end_point = poly_line[-1]   # B

        # get the next feature and its start/end vertices
        next_feature = features[1]
        next_geometry = next_feature.geometry()
        poly_line_next = get_polyline(next_geometry)
        next_start_point = poly_line_next[0] # C
        next_end_point = poly_line_next[-1]  # D

        # compare the first feature vertices with the next feature vertices
        # this handle the direction of the poly line
        if first_start_point.compare(next_end_point, epsilon):
            # first_end_point:first_start_point | next_end_point:next_start_point -> first_start_point
            # next feature is reversed from the poly line vertices
            next_point = next_end_point
            # reverse the first poly line
            poly_line.reverse()
            # write back to the QgsFeature (will not write it back to the data source)
            first_feature.setGeometry(QgsGeometry.fromPolylineXY(poly_line))

        elif first_start_point.compare(next_start_point, epsilon):
            # first_end_point:first_start_point | next_start_point:next_end_point -> first_start_point
            # next feature is already well-ordered
            next_point = next_start_point

            # reverse the first poly line
            poly_line.reverse()
            # write back to the QgsFeature (will not write it back to the data source)
            first_feature.setGeometry(QgsGeometry.fromPolylineXY(poly_line))

        elif first_end_point.compare(next_start_point, epsilon):
            # first_start_point:first_end_point | next_start_point:next_end_point -> first_end_point
            next_point = next_start_point
        elif first_end_point.compare(next_end_point, epsilon):
            # first_start_point:first_end_point | next_end_point:next_start_point -> first_end_point
            next_point = next_end_point
        else:
            raise ValueError(f"Sorting not possible between {first_geometry.asWkt()=} and {next_geometry.asWkt()=}")

    for feature in features[1:]:
        poly_line = get_polyline(feature.geometry())
        if poly_line[-1].compare(next_point, epsilon):
            # reverse the poly line
            poly_line.reverse()
            # write back to the QgsFeature (will not write it back to the data source)
            feature.setGeometry(QgsGeometry.fromPolylineXY(poly_line))
            next_point = poly_line[-1]
        elif poly_line[0].compare(next_point, epsilon):
            # no feature update, keep poly line as it is
            next_point = poly_line[-1]
        else:
            raise ValueError(f"given {next_point.toString(TO_STRING_PREC)=} not in the feature's poly line "
                             f"of fid {feature.id()=} with geometry wkt of '{feature.geometry().asWkt()}'")

    return features


def sort_lines_features_and_keep_poly_line_order(features: Union[List[QgsFeature], QgsFeatureIterator],
                                                 epsilon: float = EPSILON) -> List[QgsFeature]:
    """ Sorts given list of QgsFeatures with given geometry of type LineString.
        The feature's geometry will not be updated.

        :param features: list of features
        :param epsilon: tolerance for comparing points, defaults to _EPSILON

        :return: sorted line list
        :raises AttributeError: features are not connected (only when expert_mode is False)
    """

    feature_list = [(f.id(), get_polyline(f.geometry()), f) for f in features]
    feature_dict = {fid: f for fid, _, f in feature_list}

    # -> [[fid, polyline], ...]
    sorted_geometries: List[Tuple[int, List[QgsPointXY], QgsFeature]] = [feature_list.pop()]
    while feature_list:

        found = False

        sorted_poly_first = sorted_geometries[0][1]
        sorted_poly_last = sorted_geometries[-1][1]

        for i, element in enumerate(feature_list):
            fid, polyline, _ = element

            # add feature to the left side
            if get_neighbor_type(sorted_poly_first, polyline, epsilon) == N_LEFT:
                sorted_geometries = [feature_list.pop(i)] + sorted_geometries
                found = True
                break

            # add feature the right side in this list
            if get_neighbor_type(sorted_poly_last, polyline, epsilon) == N_RIGHT:
                sorted_geometries = sorted_geometries + [feature_list.pop(i)]
                found = True
                break

        if not found:
            raise AttributeError("sorting failed")

    return [feature_dict[fid] for fid, *_ in sorted_geometries]


def sort_feature_ids(layer: QgsVectorLayer, feature_ids: set, epsilon: float = EPSILON) -> List[int]:
    """ sorts featureids on vector layer of linefeatures

        :param layer: vector layer of line geometry as linestring
        :type layer: QgsVectorLayer

        :param feature_ids: feature-ids
        :type feature_ids: List[int]

        :param epsilon: tolerance for comparing points, defaults to EPSILON
        :type epsilon: float

        :return: returns ordered feature-id list
        :rtype: List[int]
    """
    if layer.wkbType() != QgsWkbTypes.LineString:
        raise ValueError(f"vector layer is not linestring layer {layer.id()}")

    feature_ids = list(set(feature_ids))

    try:
        req = QgsFeatureRequest().setFilterFids(feature_ids)
        req = req.setNoAttributes()
        return [f.id() for f in sort_lines_features(layer.getFeatures(req), epsilon=epsilon)]
    except AttributeError:
        return []
