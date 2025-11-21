# -*- coding: utf-8 -*-
# SPDX-FileCopyrightText: 2025 Deutsche Telekom Technik GmbH <f.vonstudsinske@telekom.de>
# SPDX-License-Identifier: GPL-3.0-or-later

from qgis.core import (QgsVectorLayer, QgsPointXY, QgsFeatureRequest, QgsRectangle,
                       QgsSpatialIndex, QgsFeature, QgsGeometry)

from typing import List, Optional, Tuple

from .geometry import (get_polyline, is_point_on_line, remove_duplicated_ranges,
                       get_point, transform_point, transform_geometry)
from .geometry_sort_line import sort_lines_features
from ..constants import EPSILON

def get_feature_ids_spatial_poly(origin_layer: QgsVectorLayer, polyline: List[QgsPointXY],
                                 request: QgsFeatureRequest = None, epsilon: float = EPSILON):
    """ Queries and orders feature-ids along polyline.
        Performance-Warning: Spatialindex will be used to order features

        :param origin_layer: layer where to find and order features
        :param polyline: layer where to find and order features
        :param request: request, defaults to None
        :param epsilon: tolerance for comparing points, defaults to EPSILON

        :return: returns ordered feature-id list
    """

    feature_ids = []  # Liste von Fids in der Reihenfolge der polyline
    if not isinstance(request, QgsFeatureRequest):
        # Ausmaße ermitteln der Polylinie
        max_x = max([p.x() for p in polyline])
        max_y = max([p.y() for p in polyline])
        min_x = min([p.x() for p in polyline])
        min_y = min([p.y() for p in polyline])

        rect = QgsRectangle(min_x, min_y, max_x, max_y)
        # rect.scale(1.1)

        # Feature auf Basis der Ausmaße abfragen
        request = QgsFeatureRequest().setFilterRect(rect)
    request = request.setNoAttributes()

    origin_dic = {}
    point_dic = {}  # Referenz-Dict von neuem Punkt zu Linienfeature-ID
    spatial = QgsSpatialIndex()  # enthält alle Knotenpunkte jedes Features

    nid = 1
    for f in origin_layer.getFeatures(request):

        # Multi Linien Geometrie kann nicht ausgewertet werden, nehme immer erstes Segment
        seg = get_polyline(f.geometry())

        # Original Referenz
        origin_dic[f.id()] = seg

        # Jeden Knotenpunkt in ein neues Dict schreiben und in spatial index übernehmen
        for p in seg:
            nf = QgsFeature(nid)
            nf.setGeometry(QgsGeometry.fromPointXY(p))
            point_dic[nid] = f.id()
            spatial.addFeature(nf)
            nid += 1

    for index in range(len(polyline)):
        if index + 1 > len(polyline) - 1:
            break  # Ende erreicht

        start_point = polyline[index]
        end_point = polyline[index + 1]

        ids_end = spatial.nearestNeighbor(end_point, 10)

        feature_ids_end = [point_dic[i] for i in ids_end]

        for p_id_start in spatial.nearestNeighbor(start_point, 10):

            feature_id_start = point_dic[p_id_start]
            if feature_id_start in feature_ids:
                # bereits ermittelt
                continue

            if feature_id_start not in feature_ids_end:
                # start & ende enthält das nicht
                continue

            line_start = origin_dic[feature_id_start]
            s_0 = is_point_on_line(start_point, line_start, epsilon)
            s_1 = is_point_on_line(end_point, line_start, epsilon)

            if s_0 and s_1:
                # Aktueller und nächster Punkt liegen drauf
                feature_ids.append(feature_id_start)
                break

    return feature_ids


def get_feature_ids_containing(origin_layer: QgsVectorLayer, polyline: List[QgsPointXY],
                               request: QgsFeatureRequest = None, epsilon: float = EPSILON):
    """ Queries and orders feature-ids along polyline.
        Performance-Warning: Spatialindex will be used to order features

        :param origin_layer: layer where to find and order features
        :param polyline: layer where to find and order features
        :param request: request, defaults to None
        :param epsilon: tolerance for comparing points, defaults to EPSILON

        :return: returns ordered feature-id list
    """
    # prevent recursive import
    from .spatial_line_ends_to_point_v2 import LineEndsToPointSpatialIndexV2

    feature_ids = []  # Liste von Fids in der Reihenfolge der polyline
    if not isinstance(request, QgsFeatureRequest):
        # Ausmaße ermitteln der Polylinie
        max_x = max([p.x() for p in polyline])
        max_y = max([p.y() for p in polyline])
        min_x = min([p.x() for p in polyline])
        min_y = min([p.y() for p in polyline])

        rect = QgsRectangle(min_x, min_y, max_x, max_y)
        # rect.scale(1.1)

        # Feature auf Basis der Ausmaße abfragen
        request = QgsFeatureRequest().setFilterRect(rect)
    request = request.setNoAttributes()

    spatial = LineEndsToPointSpatialIndexV2([])
    spatial.init(origin_layer.getFeatures(request))

    def get_fid(a, b):
        ids_a = spatial.get_nearest_source_fids(a)
        ids_b = spatial.get_nearest_source_fids(b)

        ids = [i for i in ids_a if i in ids_b]
        for i in ids:
            poly = get_polyline(spatial.get_source_geometry(i))
            if is_point_on_line(a, poly, epsilon) and is_point_on_line(b, poly, epsilon):
                return i

        return None

    for index in range(len(polyline) - 1):

        start_point = polyline[index]
        end_point = polyline[index + 1]
        fid = get_fid(start_point, end_point)
        if fid is not None and fid not in feature_ids:
            feature_ids.append(fid)

    return feature_ids


def get_intersecting_features(geometry: QgsGeometry, layer: QgsVectorLayer) -> List[QgsFeature]:
    """ Returns a list from with intersecting features to given geometry

        :param geometry: geometry's coordinates must be in layers crs
        :param layer: layer where to find feature
    """
    request = QgsFeatureRequest().setFlags(QgsFeatureRequest.ExactIntersect)
    request = request.setFilterRect(QgsRectangle(geometry.boundingBox()))
    features = []
    for f in layer.getFeatures(request):
        if f.geometry().intersection(geometry):
            features.append(f)
    return features


def get_touching_features(geometry: QgsGeometry, layer: QgsVectorLayer) -> List[QgsFeature]:
    """ Returns a list of touching features.
        E.g. polyline start/end touches another feature's geometry.

        :param geometry: geometry's coordinates must be in layers crs
        :param layer: layer where to find feature
    """
    # create a feature request with a scaled boundingBox from 'geometry'
    # features must exactly intersect with the bbox
    request = QgsFeatureRequest().setFlags(QgsFeatureRequest.ExactIntersect)
    rect = geometry.boundingBox()
    rect = rect.scaled(1.2)
    request = request.setFilterRect(rect)

    # collect the touching features from the given feature request
    features = []
    for feature in layer.getFeatures(request):
        if geometry.touches(feature.geometry()):
            features.append(feature)

    return features


def get_fids_from_poly_line(layer: QgsVectorLayer, poly_line: List[QgsPointXY],
                            epsilon: float = EPSILON) -> List[int]:
    """ Returns a sorted feature list with given layer and poly_line.
        Duplicated ranges between points will be skipped.
        A possible line is matched, when current vertex index and next vertex are sharing the same line feature id.

        Point at vertex 10 and point at vertex 11 are on line feature with fid 10.
        Then feature with id 10 will be added.

        No connection test made here.

        Example:
            polyline = [1, 2, 3, 4, 10, 11, 4, 5, 6, 6, 7, 9, 7]
            out = [1, 2, 3, 4, 5, 6, 7]
            duplicates and spaces between duplicates ignored

        :param layer: vector layer (single geometry type)
        :param poly_line: list of points, likely in dijkstra
        :param epsilon: epsilon for internal spatial index `LineEndsToPointSpatialIndexV2`
    """
    from .spatial_line_ends_to_point_v2 import LineEndsToPointSpatialIndexV2

    poly_line = remove_duplicated_ranges(poly_line)
    bbox = QgsGeometry.fromPolylineXY(poly_line).boundingBox().scaled(1.05)
    req = QgsFeatureRequest().setFilterRect(bbox)
    spatial = LineEndsToPointSpatialIndexV2([])
    spatial.init(layer.getFeatures(req))
    fids = []

    for i in range(len(poly_line) - 1):
        current = poly_line[i]
        next_ = poly_line[i + 1]

        current_s_fids = set(spatial.get_nearest_source_fids(current, maxDistance=epsilon))
        next_s_fids = set(spatial.get_nearest_source_fids(next_, maxDistance=epsilon))

        # only one intersection allowed
        inter = current_s_fids.intersection(next_s_fids)
        if len(inter) == 1:
            fid = next(iter(inter))
            if fid in fids:
                continue

            fids.append(fid)

    return fids


def get_feature_ids_poly(origin_layer: QgsVectorLayer, polyline: List[QgsPointXY],
                         epsilon: float = EPSILON) -> List[int]:
    """ requires origin_layer with only line-features under polyline

        :param origin_layer: vector layer (LineGeometry)
        :type origin_layer: QgsVectorLayer

        :param polyline: list of points
        :type polyline: List[QgsPointXY]

        :param epsilon: tolerance for comparing points, defaults to EPSILON
        :type epsilon: float

        :return: returns ordered feature-id list
        :rtype: List[int]
    """

    try:
        req = QgsFeatureRequest().setNoAttributes()
        feature_ids = sort_lines_features(origin_layer.getFeatures(req), epsilon)
        if feature_ids:
            first_feature = origin_layer.getFeature(feature_ids[0].id())
            poly = get_polyline((first_feature.geometry()))

            if not poly[0].compare(polyline[0], epsilon) and not poly[-1].compare(polyline[0], epsilon):
                # first feature-geometry points are not the points from polyline
                feature_ids.reverse()

        else:
            raise AttributeError

    except AttributeError:
        feature_ids = get_feature_ids_spatial_poly(origin_layer, polyline)

    return feature_ids


def get_points_from_help_line(geometry: QgsGeometry, main_line_layer: QgsVectorLayer,
                              reference_line_layer: QgsVectorLayer,
                              epsilon: float = EPSILON) -> Optional[Tuple[Tuple[int, QgsPointXY],
                                                                                      Tuple[int, QgsPointXY]]]:
    """ Finds intersection points from geometry in main and reference layer.
        The first found intersection point per layer will be used.
        Returned coordinates will be in main line layer crs.

        :param geometry: geometry, coordinates must be in same crs like main layer
        :param main_line_layer: main layer
        :param reference_line_layer: reference layer
        :param epsilon: epsilon/tolerance

        :returns: main layer intersection point and reference intersection point,
                  defaults to None

    """

    # fall back
    fall_back_match_main = None
    fall_back_match_reference = None

    # main intersection
    main_point = None
    main_feature = None

    for main_feature in get_intersecting_features(geometry, main_line_layer):
        inter = geometry.intersection(main_feature.geometry())

        # is this a valid intersection?
        if not inter.isEmpty() and not inter.isNull() and inter.isGeosValid():
            main_point = get_point(inter)
            poly = get_polyline(main_feature.geometry())
            if main_point.compare(poly[0], epsilon) or main_point.compare(poly[-1], epsilon):
                # save backup
                fall_back_match_main = (main_feature, main_point)
                # already okay
                main_point = None
                continue

            break

    # reference intersection
    reference_geometry = transform_geometry(geometry,
                                            main_line_layer.dataProvider().crs(),
                                            reference_line_layer.dataProvider().crs())
    reference_point = None
    reference_feature = None

    for reference_feature in get_intersecting_features(reference_geometry,
                                                       reference_line_layer):
        inter = reference_geometry.intersection(reference_feature.geometry())

        # is this a valid intersection?
        if not inter.isEmpty() and not inter.isNull() and inter.isGeosValid():
            reference_point = get_point(inter)

            poly = get_polyline(reference_feature.geometry())
            if reference_point.compare(poly[0], epsilon) or reference_point.compare(poly[-1], epsilon):
                # save backup
                fall_back_match_reference = (reference_feature, reference_point)
                # already okay
                reference_point = None
                continue
            break

    # test for fall back, if only intersection on poly line end/start point and not somewhere along the poly line
    if main_point is None and fall_back_match_main is not None:
        main_feature, main_point = fall_back_match_main
    if reference_point is None and fall_back_match_reference is not None:
        reference_feature, reference_point = fall_back_match_reference

    # both points found
    if reference_point and main_point:

        # transform point to main layer crs
        reference_point = transform_point(reference_point,
                                          reference_line_layer.dataProvider().crs(),
                                          main_line_layer.dataProvider().crs())

        return (main_feature.id(), main_point), \
               (reference_feature.id(), reference_point)

    # minimum one point not found
    return None