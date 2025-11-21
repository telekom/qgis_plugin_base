# -*- coding: utf-8 -*-
# SPDX-FileCopyrightText: 2025 Deutsche Telekom Technik GmbH <f.vonstudsinske@telekom.de>
# SPDX-License-Identifier: GPL-3.0-only

import math

from typing import List, Union, Optional

from qgis.core import (QgsCoordinateReferenceSystem, QgsCoordinateTransform,
                       QgsGeometry, QgsProject, QgsPointXY, QgsWkbTypes, QgsFeature,
                       QgsDistanceArea, QgsPoint, QgsFeatureRequest, QgsVectorLayer)

from ..constants import EPSILON


def get_transform(src_coordinate_system: QgsCoordinateReferenceSystem,
                  dst_coordinate_system: QgsCoordinateReferenceSystem) -> QgsCoordinateTransform:
    """ get transform object.
        Transforming geometry is needed, when you want to use a geometry in a different coordinate reference system.

        :param src_coordinate_system: source coordinate system
        :param dst_coordinate_system: destination coordinate system
        :return: transform object
    """
    transform_params = QgsCoordinateTransform(
        src_coordinate_system,
        dst_coordinate_system,
        QgsProject.instance())

    return transform_params


def transform_geometry(geometry: QgsGeometry, src_coordinate_system: QgsCoordinateReferenceSystem,
                       dst_coordinate_system: QgsCoordinateReferenceSystem) -> QgsGeometry:
    """ Transform Geometry-Points to another coordinate
        reference system

        :param geometry: geometry to transform
        :param src_coordinate_system: source coordinate system
        :param dst_coordinate_system: destination coordinate system
        :return: converted point
    """

    # get geometry from point
    copy_geometry = QgsGeometry(geometry)

    transform_params = get_transform(src_coordinate_system, dst_coordinate_system)
    copy_geometry.transform(transform_params)

    return copy_geometry


def transform_point(point: QgsPointXY, src_coordinate_system: QgsCoordinateReferenceSystem,
                    dst_coordinate_system: QgsCoordinateReferenceSystem) -> QgsPointXY:
    """ Transform 2 coordinates (Point, given by coordinates) to another coordinate
        reference system

        :param point: point to transform
        :param src_coordinate_system: source coordinate system
        :param dst_coordinate_system: destination coordinate system
        :return: converted point
        :rtype: QgsPointXY
    """

    # get geometry from point
    point_geometry = QgsGeometry.fromPointXY(point)

    transform_params = get_transform(src_coordinate_system, dst_coordinate_system)
    point_geometry.transform(transform_params)

    result = QgsPointXY(point_geometry.vertexAt(0).x(),
                        point_geometry.vertexAt(0).y())

    return result


def get_point(geometry: QgsGeometry) -> QgsPointXY:
    """ Returns from a point geometry the single point
        If geometry is a multi point, than the first point in list will be returned.

        :param geometry: point geometry
        :return: point
    """
    geom_type = QgsWkbTypes.geometryDisplayString(geometry.type())
    if geometry.type() != QgsWkbTypes.PointGeometry:
        raise TypeError(f"point '{geom_type}' is not a point geometry")

    if geometry.isMultipart():
        point: QgsPointXY = geometry.asMultiPoint()[0]
    else:
        point: QgsPointXY = geometry.asPoint()

    return point


def get_multi_point(geometry: QgsGeometry) -> List[QgsPointXY]:
    """ Returns from a point geometry the point geometry as multi point (list of points)

        :param geometry: point geometry
        :return: points
    """
    geom_type = QgsWkbTypes.geometryDisplayString(geometry.type())
    if geometry.type() != QgsWkbTypes.PointGeometry:
        raise TypeError(f"point '{geom_type}' is not a point geometry")

    if geometry.isMultipart():
        points: List[QgsPointXY] = geometry.asMultiPoint()
    else:
        points: List[QgsPointXY] = [geometry.asPoint()]

    return points


def get_multi_polyline(geometry: QgsGeometry) -> List[List[QgsPointXY]]:
    """ Returns line as multi poly line. Empty/invalid segments will be removed/ignored

        :param geometry: line geometry
        :return: found poly line list
    """

    geom_type = QgsWkbTypes.geometryDisplayString(geometry.type())
    if geometry.type() != QgsWkbTypes.LineGeometry:
        raise TypeError(f"geometry '{geom_type}' is not a line geometry")

    # empty geometry
    if geometry.isEmpty() or geometry.isNull():
        return []

    if geometry.isMultipart():
        # reduce poly line list, to keep only valid parts
        multi_poly_lines = geometry.asMultiPolyline()
        multi_poly_lines = [m for m in multi_poly_lines
                            if is_line_geometry_valid(QgsGeometry.fromPolylineXY(m)) and m]
        return multi_poly_lines
    else:
        return [geometry.asPolyline()]


def get_polyline(geometry: QgsGeometry) -> List[QgsPointXY]:
    """ returns first available and valid poly line.
        From multi line geometry the first valid line will be returned!

        :param geometry: line geometry
        :return: found poly line list
    """
    geom_type = QgsWkbTypes.geometryDisplayString(geometry.type())
    if geometry.type() != QgsWkbTypes.LineGeometry:
        raise TypeError(f"geometry '{geom_type}' is not a line geometry")

    # empty geometry
    if geometry.isEmpty() or geometry.isNull():
        return []

    if geometry.isMultipart():
        multi_poly_lines = geometry.asMultiPolyline()
        for poly_line in multi_poly_lines:
            if poly_line:
                # return a filled poly line
                return poly_line
        else:
            return []
    else:
        return geometry.asPolyline()


def get_simple_polygon(geometry: QgsGeometry) -> List[QgsPointXY]:
    """ returns first available polygon (without inner rings)

        :param geometry: polygon geometry
        :return: found poly line list
    """
    geom_type = QgsWkbTypes.geometryDisplayString(geometry.type())
    if geometry.type() != QgsWkbTypes.PolygonGeometry:
        raise TypeError(f"geometry '{geom_type}' is not a polygon geometry")

    # empty geometry
    if geometry.isEmpty() or geometry.isNull():
        return []

    if geometry.isMultipart():
        point_list_polygon = geometry.asMultiPolygon()[0][0]
    else:
        point_list_polygon = geometry.asPolygon()[0]

    return point_list_polygon


def is_point_on_segment(point: QgsPointXY, line: List[QgsPointXY], epsilon: float = EPSILON) -> bool:
    """ checks, if point is between two points with epsilon value

        :param point: point
        :param line: point list
        :param epsilon: tolerance for comparing points, defaults to _constants.EPSILON
        :return: True = point is on "line", otherwise False
    """
    # works only for segments, use is_point_on_line otherwise
    if len(line) != 2:
        raise ValueError(f"line length invalid. Got {len(line)}, expected 2")
    # point x is on line (x_1, x_2) exactly if dist(x_1, x) + dist(x,x_2) = dist(x_1,x_2)
    dist1 = point.distance(line[0]) + point.distance(line[1])
    dist2 = line[0].distance(line[1])
    return abs(dist1 - dist2) < epsilon


def is_point_on_line(point: QgsPointXY, line: List[QgsPointXY], epsilon: float = EPSILON) -> bool:
    """ checks, if point is on line and between the vertex-pairs

        :param point: point
        :param line: point list
        :param epsilon: tolerance for comparing points, defaults to _constants.EPSILON
        :return: True = point is on line, otherwise False
    """
    for i in range(len(line) - 1):
        if is_point_on_segment(point, line[i:i + 2], epsilon):
            return True
    return False


def is_point_in_polylist(point: QgsPointXY, line: List[QgsPointXY], epsilon: float = EPSILON) -> bool:
    """ checks, if point is on line

        :param point: point
        :param line: point list
        :param epsilon: tolerance for comparing points, defaults to _constants.EPSILON
        :return: True = point is on line-vertex, otherwise False
    """
    for p in line:
        if p.compare(point, epsilon):
            return True
    return False


def is_line_geometry_equal(geometry_0: QgsGeometry, geometry_1: QgsGeometry) -> bool:
    """ Compares given line geometries if they are equal. Draw direction of poly lines does not matter.

        :param geometry_0: geometry to compare
        :param geometry_1: geometry to compare
        :return: returns True, if `geometry_0` equals the `geometry_1` and vice versa (both polyline directions
    """
    g0 = QgsGeometry.fromPolylineXY(get_polyline(geometry_0))
    g0_r = QgsGeometry.fromPolylineXY(reversed(get_polyline(geometry_0)))
    g1 = QgsGeometry.fromPolylineXY(get_polyline(geometry_1))

    if g0.equals(g1):
        return True

    if g0_r.equals(g1):
        # Eine Geometrie einmal umdrehen
        return True

    return False


def is_line_geometry_equal_v2(geometry_0, geometry_1, distance_area: QgsDistanceArea, tolerance: float):
    """ Compares two line geometries.
        Draw direction will not be checked.
        Try to use only line geometries with only two vertices.

        :param geometry_0: geometry
        :param geometry_1: geometry
        :param distance_area: distance area for tolerance check in meter
        :param tolerance: meter
    """
    if geometry_0.isGeosEqual(geometry_1):
        return True

    if geometry_0.isGeosEqual(QgsGeometry.fromPolylineXY(reversed(geometry_1.asPolyline()))):
        # Eine Geometrie einmal umdrehen
        return True

    if not geometry_0.isGeosValid() or geometry_0.isEmpty() or geometry_0.isNull():
        return False

    if not geometry_1.isGeosValid() or geometry_1.isEmpty() or geometry_1.isNull():
        return False

    polyline_0 = get_polyline(geometry_0)
    polyline_1 = get_polyline(geometry_1)

    if len(polyline_0) != 2:
        raise ValueError(f"geometry 0 has no 2 points: {geometry_0}")
    if len(polyline_1) != 2:
        raise ValueError(f"geometry 1 has no 2 points: {geometry_1}")

    # vorne, list(zwischen), hinten
    a1, b1 = geometry_0.asPolyline()
    c1, d1 = geometry_1.asPolyline()

    # Sehr kurze Linien. Sie werden als gleich anerkannt, wenn diese unter die Toleranzschwelle fallen
    if distance_area.measureLine(a1, c1) < tolerance and \
        distance_area.measureLine(b1, d1) < tolerance:
        # 1:1 Verlauf prüfen
        # Abgleich in Meter
        return True

    if distance_area.measureLine(a1, d1) < tolerance and \
        distance_area.measureLine(b1, c1) < tolerance:
        # 1:1 Verlauf prüfen, nur umgekehrte Punktfolge..
        # Abgleich in Meter
        return True

    return False


def is_line_geometry_equal_v3(geometry_0: QgsGeometry,
                              geometry_1: QgsGeometry,
                              compare_tolerance: float = EPSILON) -> bool:
    """ checks if given geometries share all points and are so equal to each other (needs to be in same EPSG)

        :param geometry_0: first geometry for check
        :type geometry_0: QgsGeometry
        :param geometry_1: second geometry for check
        :type geometry_1: QgsGeometry
        :param compare_tolerance: float as tolerance for compare
        :type compare_tolerance: float

        :return: is polyline equal
        :rtype: bool
    """
    def point_in_list(point: QgsPointXY, point_list: List[QgsPointXY]) -> bool:
        """ checks if given point is in given list of points included

            :param point: point to check if included in list
            :type point: QgsPointXY
            :param point_list: list of points to check for
            :type point_list: List[QgsPointXY]
        """
        return any(map(lambda p: p.compare(point, compare_tolerance), point_list))

    polyline_0 = get_polyline(geometry_0)
    polyline_1 = get_polyline(geometry_1)

    if len(polyline_0) != len(polyline_1):
        return False

    return all(map(lambda p: point_in_list(p, polyline_1), polyline_0))


def is_feat_geometry_valid(feature: QgsFeature) -> bool:
    """ Checks features geometry validness

        :param feature: feature
        :return: True = is valid
    """

    return is_geometry_valid(feature.geometry())


def is_geometry_valid(geometry: QgsGeometry) -> bool:
    """ Checks geometry validness

        :param geometry: geometry
        :return: True = is valid
    """

    if geometry.wkbType() in [QgsWkbTypes.LineString, QgsWkbTypes.MultiLineString]:
        return is_line_geometry_valid(geometry)

    valid = not geometry.isNull() and not geometry.isEmpty() and geometry.isGeosValid()

    if not valid:
        return valid

    # check if "nan" or "inf" number value is in WKT string
    wkt_valid = geometry.asWkt()
    wkt_valid = "inf" not in wkt_valid and "nan" not in wkt_valid

    return valid and wkt_valid


def is_line_geometry_valid(geometry: QgsGeometry) -> bool:
    """ Checks line geometry validness

        .. code-block:: python

            # valid line geometry
            geom_1 = QgsGeometry.fromWkt('LineString (-0.60004549644407645 0.30430419253580521,'
                                                      '-0.60004291632156226 0.30430480288736772,'
                                                      '-0.60004317525858875 0.30430365616625027)')

            # invalid line geometry 1, start end and equal
            geom_2 = QgsGeometry.fromWkt('LineString (-0.60004549644407645 0.30430419253580521,'
                                                      '-0.60004291632156226 0.30430480288736772,'
                                                      '-0.60004549644407645 0.30430419253580521)')

            # invalid line geometry 2, only one vertex
            geom_3 = QgsGeometry.fromWkt('LineString (-0.60004549644407645 0.30430419253580521)')

            print("geom_1", is_line_geometry_valid(geom_1))  # True
            print("geom_2", is_line_geometry_valid(geom_2))  # False
            print("geom_3", is_line_geometry_valid(geom_3))  # False

        :param geometry: geometry
        :return: True = is valid
    """
    if geometry.wkbType() not in [QgsWkbTypes.LineString, QgsWkbTypes.MultiLineString]:
        return False

    valid = not geometry.isNull() and not geometry.isEmpty() and geometry.isGeosValid()

    if not valid:
        return valid

    # check if "nan" or "inf" number value is in WKT string
    wkt_valid = geometry.asWkt()
    wkt_valid = "inf" not in wkt_valid and "nan" not in wkt_valid

    # one special check for line string to prevent some error cases
    lines = geometry.asMultiPolyline() if geometry.isMultipart() else [geometry.asPolyline()]
    for line in lines:

        if not line:
            continue

        # line has only one vertex?
        if len(line) == 1:
            return False

        # start and end vertex are equal
        start, *_, end = line
        if start.compare(end, EPSILON):
            return False

    return valid and wkt_valid


def get_opposite_point_from_c(a: Union[QgsPoint, QgsPointXY], b: Union[QgsPoint, QgsPointXY],
                              c: Union[QgsPoint, QgsPointXY]):
    """
    finds opposite point from c in a triangle.
    """

    def get_z(point):

        if not hasattr(point, "z"):
            return 0.0

        if math.isnan(point.z()):
            return 0.0
        else:
            return point.z()

    # benötigt für c (Fußpunkt)
    vector_ab_x = b.x() - a.x()
    vector_ab_y = b.y() - a.y()
    vector_ab_z = get_z(b) - get_z(a)

    vector_ac_x = c.x() - a.x()
    vector_ac_y = c.y() - a.y()
    vector_ac_z = get_z(c) - get_z(a)

    normal_x = (-1 * vector_ab_x) * vector_ac_x
    normal_y = (-1 * vector_ab_y) * vector_ac_y
    normal_z = (-1 * vector_ab_z) * vector_ac_z
    normal = normal_x + normal_y + normal_z

    r_x = -1 * vector_ab_x * vector_ab_x
    r_y = -1 * vector_ab_y * vector_ab_y
    r_z = -1 * vector_ab_z * vector_ab_z
    r = r_x + r_y + r_z

    # factor from vector of a-b
    r_ac = (-1 * normal) / (-1 * r)

    new_vector_x = a.x() + (r_ac * vector_ab_x)
    new_vector_y = a.y() + (r_ac * vector_ab_y)
    new_vector_z = get_z(a) + (r_ac * vector_ab_z)

    return QgsPoint(new_vector_x, new_vector_y, new_vector_z)


def get_point_index(point: QgsPointXY, line: List[QgsPointXY], epsilon: float = EPSILON) -> int:
    """ gets index if point in list

        :param point: point
        :param line: point list
        :param epsilon: tolerance for comparing points, defaults to _constants.EPSILON
        :return: index = point is on line-vertex, otherwise raises ValueError exception
    """
    for i, p in enumerate(line):
        if p.compare(point, epsilon):
            return i
    raise ValueError(f"point {point} not on line with epsilon {epsilon}")


def remove_duplicated_points(points: List[QgsPointXY], epsilon: float = EPSILON) -> List[QgsPointXY]:
    """ remove duplicated points.

        :param points: point list where to remove duplicated points
        :param epsilon: tolerance for comparing points, defaults to _constants.EPSILON
        :return: Neue Liste mit ggf. weniger doppelten Punkten
    """

    new_points = []
    for p in points:

        if is_point_in_polylist(p, new_points, epsilon):
            continue

        new_points.append(p)

    return new_points


def simplify_line_geometry(geometry: QgsGeometry, epsilon: float,
                           ignore_simplify: Optional[List[QgsPointXY]] = None,
                           precision: int = 17) -> QgsGeometry:
    """ Simplifies line geometry by given epsilon and returns the new line geometry.

        :param geometry: source map units from coordinate reference system
        :param epsilon: destination map units from coordinate reference system
        :param ignore_simplify: value to convert
        :param precision: value to convert
        :return: new geometry
    """
    # get poly line from geometry
    poly_line = get_polyline(geometry)

    if ignore_simplify is None:
        ignore_simplify = []

    indices = [0, len(poly_line) - 1]
    points_on_poly = []
    for i, point in enumerate(poly_line):

        if i == 0 or i == len(poly_line) - 1:
            continue

        point_str = point.toString(precision)
        if point_str in ignore_simplify or point in ignore_simplify:
            indices.insert(-1, i)
            points_on_poly.append(point)

    new_poly_line = []
    for i, index in enumerate(indices):
        if (i + 1) > (len(indices) - 1):
            break

        next_index = indices[i + 1]
        points = poly_line[index:next_index + 1]
        simplify = QgsGeometry.fromPolylineXY(points)
        simplify = simplify.simplify(epsilon)
        new_poly_line.extend(simplify.asPolyline())

    _c = new_poly_line.copy()
    new_poly_line = []
    for p in _c:
        if p not in new_poly_line:
            new_poly_line.append(p)

    return QgsGeometry.fromPolylineXY(new_poly_line)


def remove_duplicated_ranges(poly_line: List[QgsPointXY]) -> List[QgsPointXY]:
    """ Returns a new poly line.
        Duplicated ranges between points will be skipped.

        Example:
            polyline = [1, 2, 3, 4, 10, 11, 4, 5, 6, 6, 7, 9, 7]
            out = [1, 2, 3, 4, 5, 6, 7]
            duplicates and spaces between duplicates ignored

        :param poly_line: list of points, likely in dijkstra
    """
    polyline_new = []
    skip = []
    for i in range(len(poly_line)):
        current = poly_line[i]

        if i in skip:
            continue

        if poly_line.count(current) > 1:
            index = poly_line.index(current)

            while True:
                try:
                    index = poly_line.index(current, index + 1)
                except ValueError:
                    break

            for skip_i in range(i, index + 1):
                skip.append(skip_i)

        polyline_new.append(current)

    return polyline_new


def reorder_points_in_poly_lines(poly_lines, start_point,
                                 epsilon: float = EPSILON):
    """ Reverse or keep ordner in given pre-sorted polylines
        to become a ordered group of poly lines and connected like train coaches.

        :raises ValueError: missing point in a poly list
        :raises ValueError: poly lines not connected with given epsilon

        :param poly_lines: pre-sorted list of poly lines
        :param start_point: start point for firs poly line in lines
        :param epsilon: tolerance for comparing points, defaults to _constants.EPSILON
    """
    if not poly_lines:
        return poly_lines

    new_poly_lines = []

    def __get_poly_line(line, point):
        if line[0].compare(point, epsilon):
            # already expected dir
            return line.copy()
        elif line[-1].compare(point, epsilon):
            # reverse the line
            return list(reversed(line))
        else:
            raise ValueError(f"point {point.toString(6)} not in poly line list of {line}")

    first_line = poly_lines[0]
    new_poly_lines.append(__get_poly_line(first_line, start_point))

    for i, remaining in enumerate(poly_lines[1:]):
        try:
            new_poly_lines.append(__get_poly_line(remaining, new_poly_lines[-1][-1]))
        except ValueError as e:
            raise ValueError(f"resort error in index {i + 1} from {poly_lines}") from e

    return new_poly_lines


def get_line_features_on_points(point: QgsPointXY, layer: QgsVectorLayer,
                                include_end_points: bool = False,
                                epsilon: float = EPSILON) -> List[QgsFeature]:
    """ Returns a list of features, which geometry intersects with given point on layer.

        :param layer: point to intersect with
        :param point: point to intersect with
        :param include_end_points: include features
        :param epsilon: epsilon

    """

    if layer.wkbType() != QgsWkbTypes.LineString:
        raise TypeError("layer is not a line string layer (single type)")

    # find all features interacting with point
    point_geom = QgsGeometry().fromPointXY(point)

    bounding_box = point_geom.boundingBox()
    bounding_box.grow(5.0)
    filter_request = QgsFeatureRequest().setFilterRect(bounding_box)
    filtered_features = layer.getFeatures(filter_request)

    result_list = []
    for feature in filtered_features:
        line = feature.geometry().asPolyline()
        # if point is on feature append in list
        if (is_point_on_line(point, line)):
            # skip features where point would be start or end point
            if ((point.compare(line[0], epsilon)) or (point.compare(line[-1], epsilon))) and not include_end_points:
                # prevention for resulting point trenches
                continue
            else:
                # append feature to list of overlapping features
                result_list.append(feature)

    return result_list
