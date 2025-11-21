# -*- coding: utf-8 -*-
# SPDX-FileCopyrightText: 2025 Deutsche Telekom Technik GmbH <f.vonstudsinske@telekom.de>
# SPDX-License-Identifier: GPL-3.0-or-later

import processing

from qgis.core import (QgsFeatureRequest, QgsProject, QgsVectorLayer,
                       QgsPointXY, QgsDistanceArea, QgsTracer)
from qgis.analysis import (QgsVectorLayerDirector, QgsNetworkDistanceStrategy,
                           QgsGraphBuilder, QgsGraphAnalyzer)

from qgis.PyQt.QtCore import QVariant
from qgis.PyQt.QtWidgets import QProgressBar

from typing import List, Tuple, Optional

from .geometry_sort_line import sort_lines_features
from .layer_features import get_feature_ids_spatial_poly, get_feature_ids_containing
from .geometry import (get_transform, get_polyline, is_point_in_polylist,
                       remove_duplicated_points)
from ..constants import EPSILON, EPSILON_METRES


class PathFinderMethods:
    """
        FIRST_MATCH: Tests path finding step by step and use first result without error.

        PROCESSING: Use qgis processing module shortestpathpointtopoint (only on cut lines).

        DIJKSTRA: Use classic dijkstra vector director (only on cut lines).

        SHORTEST_PATH: Use shortest tree algorithm (only on cut lines).

        TRACER: Use QgsTracer class (on all vertices, no line end needed).
                Warning: This can cause unexpected behaviour,
                         when you don't want to get paths starting/ending on a vertex and not on an end-/startpoint.
    """

    #
    FIRST_MATCH = 0
    PROCESSING = 1
    DIJKSTRA = 2
    SHORTEST_PATH = 3
    TRACER = 4


class PathFinder:
    """

        .. code-block:: python
            :linenos:

            from <plugin>.submodules.core.qgis.tools.path_finder import PathFinder
            from <plugin>.submodules.core.qgis.spatial.functions import get_feature_ids_containing

            # choose your layer
            line_layer = QgsProject.instance().mapLayersByName("line_layer")[0]

            # define your points
            start = QgsPointXY(898443.0870717462, 7082558.636087883)
            end = QgsPointXY(898572.6998322988, 7082658.119421324)

            # find the path with tracer
            poly = PathFinder.get_polyline_tracer(
                line_layer,
                start,
                end)

            # find underlying features and select them
            fids = get_feature_ids_containing(line_layer, poly)
            line_layer.selectByIds(fids)

            # add found poly line to project as memory layer
            layer = QgsVectorLayer("LineString?crs=epsg:3857", "test", "memory")
            f = QgsFeature()
            f.setGeometry(QgsGeometry.fromPolylineXY(poly))
            QgsProject.instance().addMapLayer(layer)

    """

    def __init__(self):
        pass

    @classmethod
    def get_feature_route(cls, layer: QgsVectorLayer, points: List[QgsPointXY],
                          progressbar: Optional[QProgressBar] = None,
                          sub_layer=None, method: int = PathFinderMethods.FIRST_MATCH,
                          epsilon: float = EPSILON) -> List[int]:
        """ get ordered feature-id path between points

            :param layer: vector layer (single line geometry) recommended
            :param points: point list where to find the path over
            :param progressbar: expected at 0 QProgressBar (like), at 1 free progress space, defaults to [None, None]
            :param sub_layer: None or vector layer, defaults to None
            :param method: path find method (PathFinderMethods)
            :param epsilon: Epsilon/Tolerance to remove duplicated coordinates,
                            allow small inaccuracies to the feature sorting
                            and the spatial-based feature query.
                            Provide a useful value relating the CRS from the given layer/sub layer.

            :return: sorted list of features ordered form start to end

            .. code-block:: python
                :linenos:

                feature_id_route = PathFinder.get_feature_route(source_layer,
                                                              [start_point_xy, end_point_xy],
                                                              sub_layer=reduced_sub_layer)
        """
        if progressbar is not None:
            progressbar.setValue(0)
            progressbar.setMaximum(len(points) - 1)

        route_layer = layer if sub_layer is None else sub_layer
        # hop over each point pair and get poly line
        # collect the poly lines and create new huge new poly line
        poly_line = []
        for i in range(len(points) - 1):

            if progressbar is not None:
                progressbar.setValue(progressbar.value() + 1)

            start_point = points[i]
            to_point = points[i + 1]
            poly = cls.get_polyline(route_layer, start_point, to_point, method)
            if not poly:
                return []

            poly_line.extend(poly[:-1])
        poly_line.append(points[-1])

        # remove duplicates
        poly_line = remove_duplicated_points(poly_line, epsilon=epsilon)

        # get fids from new poly line and sort it
        route_fids = get_feature_ids_spatial_poly(layer, poly_line, epsilon=epsilon)

        if not route_fids:
            return []

        try:
            features = [layer.getFeature(fid) for fid in route_fids]

            return_fids = sort_lines_features(features, epsilon=epsilon)
            if is_point_in_polylist(points[-1], get_polyline(return_fids[0].geometry())):
                # last point from given points equals to first feature -> reverse
                return_fids = [f.id() for f in reversed(return_fids)]
            else:
                return_fids = [f.id() for f in return_fids]

        except AttributeError:
            # whoops
            return_fids = []

        return return_fids

    @classmethod
    def get_containing_feature_route(cls, layer: QgsVectorLayer, points: List[QgsPointXY],
                                     progressbar: Optional[QProgressBar] = None,
                                     sub_layer=None, method: int = PathFinderMethods.FIRST_MATCH,
                                     epsilon: float = EPSILON) -> List[int]:
        """ get ordered feature-id path between points.
            found poly line must only be on the found features.

            :param layer: vector layer (single line geometry) recommended
            :param points: point list where to find the path over
            :param progressbar: expected at 0 QProgressBar (like), at 1 free progress space, defaults to [None, None]
            :param sub_layer: None or vector layer, defaults to None
            :param method: path find method
            :param epsilon: Epsilon/Tolerance to allow small inaccuracies to the feature sorting
                            and the spatial-based feature query.
                            Provide a useful value relating the CRS from the given layer/sub layer.

            :return: sorted list of features ordered form start to end

            .. code-block:: python
                :linenos:

                feature_id_route = PathFinder.get_feature_route(source_layer,
                                                              [start_point_xy, end_point_xy],
                                                              sub_layer=reduced_sub_layer)
        """
        if progressbar is not None:
            progressbar.setValue(0)
            progressbar.setMaximum(len(points) - 1)

        route_layer = layer if sub_layer is None else sub_layer
        # hop over each point pair and get poly line
        # collect the poly lines and create new huge new poly line
        poly_line = []
        for i in range(len(points) - 1):

            if progressbar is not None:
                progressbar.setValue(progressbar.value() + 1)

            start_point = points[i]
            to_point = points[i + 1]
            poly = cls.get_polyline(route_layer, start_point, to_point, method)
            if not poly:
                return []

            poly_line.extend(poly[:-1])
        poly_line.append(points[-1])

        # remove duplicates
        # epsilon always 0
        poly_line = remove_duplicated_points(poly_line, epsilon=0.0)

        # get fids from new poly line and sort it
        route_fids = get_feature_ids_containing(layer, poly_line, epsilon=epsilon)
        if not route_fids:
            return route_fids

        try:
            return_fids = sort_lines_features([layer.getFeature(fid) for fid in route_fids], epsilon=epsilon)
            if is_point_in_polylist(points[-1], get_polyline(return_fids[0].geometry())):
                # last point from given points equals to first feature -> reverse
                route_fids = [f.id() for f in reversed(return_fids)]
            else:
                route_fids = [f.id() for f in return_fids]

        except AttributeError as e:
            # whoops
            route_fids = []

        return route_fids

    @classmethod
    def get_fid_route(cls, origin_layer: QgsVectorLayer, start: QgsPointXY, end: QgsPointXY, sub_layer: Optional[QgsVectorLayer] = None,
                      check_gaps=False, last_pt_tolerance=EPSILON_METRES,
                      method: int = PathFinderMethods.FIRST_MATCH,
                      epsilon: float = EPSILON) -> Tuple[List[int], List[QgsPointXY]]:
        """ finds feature-id sorted by path and return them

            :param origin_layer: vector layer (line geometry) to find features on
            :param start: start point
            :param end: end point
            :param sub_layer: vector layer (line geometry) to route on, defaults to None
            :param check_gaps: check for gaps on route, defaults to False
            :param last_pt_tolerance: last point tolerance in metres
            :param method: find method
            :param epsilon: Epsilon/Tolerance, to allow small inaccuracies to the spatial-based feature query.
                            Provide a useful value relating the CRS from the given layer/sub layer.

            :return: Returns the ordered list of feature id at 0 and polyline path at 1.

            .. code-block:: python
                :linenos:

                feature_id_route = PathFinder.get_fid_route(source_layer, start_point_xy,
                                                          end_point_xy, reduced_sub_layer)
        """

        route_layer = origin_layer if sub_layer is None else sub_layer
        points = cls.get_polyline(route_layer, start, end, method)
        if not points:
            return [], []

        # Nun zu den Punkten auf der Route die passenden Features ermitteln...
        feat_ids = get_feature_ids_spatial_poly(origin_layer, points, epsilon=epsilon)

        if check_gaps:
            feat_ids = cls.check_route_gaps(origin_layer, start, end, feat_ids, -1, last_pt_tolerance)[1]

        return feat_ids, points

    @classmethod
    def get_containing_fid_route(cls, origin_layer: QgsVectorLayer, start: QgsPointXY, end: QgsPointXY, sub_layer,
                                 check_gaps=False, last_pt_tolerance=EPSILON_METRES,
                                 method: int = PathFinderMethods.FIRST_MATCH,
                                 epsilon: float = EPSILON) -> Tuple[List[int], List[QgsPointXY]]:
        """ finds feature-id sorted by path and return them

            :param origin_layer: vector layer (line geometry) to find features on
            :param start: start point
            :param end: end point
            :param sub_layer: vector layer (line geometry) to route on, defaults to None
            :param check_gaps: check for gaps on route, defaults to False
            :param last_pt_tolerance: last point tolerance in metres
            :param method: find method
            :param epsilon: Epsilon/Tolerance, to allow small inaccuracies to the spatial-based feature query.
                            Provide a useful value relating the CRS from the given layer/sub layer.

            :return: Returns the ordered list of feature id at 0 and polyline path at 1.

            .. code-block:: python
                :linenos:

                feature_id_route = PathFinder.get_fid_route(source_layer, start_point_xy,
                                                          end_point_xy, reduced_sub_layer)
        """

        route_layer = origin_layer if sub_layer is None else sub_layer
        points = cls.get_polyline(route_layer, start, end, method)
        if not points:
            return [], []

        # Nun zu den Punkten auf der Route die passenden Features ermitteln...
        feat_ids = get_feature_ids_containing(origin_layer, points, epsilon=epsilon)

        if check_gaps:
            feat_ids = cls.check_route_gaps(origin_layer, start, end, feat_ids, -1, last_pt_tolerance)[1]

        return feat_ids, points

    @classmethod
    def get_polyline(cls, network_layer: QgsVectorLayer, start: QgsPointXY,
                     end: QgsPointXY, method: int = PathFinderMethods.FIRST_MATCH) -> List[QgsPointXY]:
        """ gets polyline list of QgsPointXY's from start to end point.
            You can choose between three methods:
                0 for prioritizing processing and then dijkstra director,
                1 for using only processing method (slow, high accuracy)
                2 for using only old dijkstra director (fast, medium accuracy)
                3 for using only sourceTree (fast, unknown accuracy)
                4 for using QgsTracer class with shortestPath

            Please use option values from PathFinderMethods class

            :param network_layer: vector layer (LineGeometry)
            :param start: start point on path
            :param end: endpoint on path
            :param method: path find method

            :return: Returns list of QgsPointXY ordered form start to end
        """
        if not isinstance(network_layer, QgsVectorLayer):
            raise TypeError
        if not isinstance(start, QgsPointXY):
            raise TypeError
        if not isinstance(end, QgsPointXY):
            raise TypeError
        polyline = []

        if method in [PathFinderMethods.FIRST_MATCH, PathFinderMethods.PROCESSING] and not polyline:
            polyline = cls.get_polyline_processing(network_layer, start, end)
            if len(polyline) < 2:
                polyline = []

        if method in [PathFinderMethods.FIRST_MATCH, PathFinderMethods.DIJKSTRA] and not polyline:
            polyline = cls.get_polyline_director(network_layer, start, end)
            if len(polyline) < 2:
                polyline = []

        if method in [PathFinderMethods.FIRST_MATCH, PathFinderMethods.SHORTEST_PATH] and not polyline:
            polyline = cls.get_polyline_shortest_tree(network_layer, start, end)
            if len(polyline) < 2:
                polyline = []

        if method in [PathFinderMethods.FIRST_MATCH, PathFinderMethods.TRACER] and not polyline:
            polyline = cls.get_polyline_tracer(network_layer, start, end)
            if len(polyline) < 2:
                polyline = []

        if polyline:

            if polyline[0].distance(start) <= EPSILON:
                # Startpunkt kann ersetzt werden
                polyline[0] = start
                if polyline[1].distance(start) <= EPSILON:
                    polyline.pop(1)
            else:
                polyline.insert(0, start)

            if polyline[-1].distance(end) <= EPSILON:
                # Endpunkt kann ersetzt werden
                polyline[-1] = end
            else:
                polyline.append(end)

        return polyline

    @classmethod
    def get_polyline_director(cls, network_layer: QgsVectorLayer,
                              start: QgsPointXY, end: QgsPointXY) -> List[QgsPointXY]:
        """ gets polyline list of QgsPointXY's from start to end point
            by using qgis QgsVectorLayerDirector the python way.

            :param network_layer: vector layer (LineGeometry)
            :param start: start point on path
            :param end: endpoint on path

            :return: Returns list of QgsPointXY ordered form start to end
        """
        # https://docs.qgis.org/3.4/de/docs/pyqgis_developer_cookbook/network_analysis.html
        director = QgsVectorLayerDirector(
            network_layer,  # feature source representing network
            -1,  # field containing direction value
            '',  # value for direct one-way road
            '',  # value for reversed one-way road
            '',  # value for two-way (bidirectional) road
            QgsVectorLayerDirector.DirectionBoth
        )
        strategy = QgsNetworkDistanceStrategy()  # Strategy ohne weitere Eigenschaften
        director.addStrategy(strategy)
        graph_builder = QgsGraphBuilder(network_layer.sourceCrs())
        graph_points = director.makeGraph(graph_builder, [start, end])

        start = graph_points[0]
        end = graph_points[1]

        graph = graph_builder.graph()

        vertex_start_id = graph.findVertex(start)
        vertex_end_id = graph.findVertex(end)
        vertex_current_id = vertex_end_id  # dijkstra-Methode geht rückwärts

        (tree, costs) = QgsGraphAnalyzer.dijkstra(graph, vertex_start_id, 0)

        if tree[vertex_end_id] == -1:
            return []

        points = []  # [graph.vertex(vertex_end_id).point()]
        while vertex_current_id != vertex_start_id:
            vertex_current_id = graph.edge(tree[vertex_current_id]).fromVertex()
            points.append(graph.vertex(vertex_current_id).point())

        # Punkte nochmal prüfen, ob diese iwo drauf liegen, und nach ersten Treffen von Start->Ende beenden
        new_points = []
        for point in points:
            new_points.append(point)
            # Linie endet/startet jetzt, danach folgende Punkte werden ignoriert (ZickZack?)
            if point.distance(start) <= EPSILON:
                break

        # Route umdrehen, damit die Laufrichtung wieder richtig ist, dijkstra routet rückwärts
        new_points.reverse()
        return new_points

    @classmethod
    def get_polyline_processing(cls, network_layer: QgsVectorLayer,
                                start: QgsPointXY, end: QgsPointXY) -> List[QgsPointXY]:
        """ gets polyline list of QgsPointXY's from start to end point
            by using qgis processing plugin.

            :param network_layer: vector layer (LineGeometry)
            :param start: start point on path
            :param end: endpoint on path

            :return: Returns list of QgsPointXY ordered form start to end
        """
        params = {'DEFAULT_DIRECTION': QgsVectorLayerDirector.DirectionBoth,
                  'DEFAULT_SPEED': 50,
                  'DIRECTION_FIELD': None,
                  'START_POINT': f"{round(start.x(), 6)}, {round(start.y(), 6)} "
                                 f"[{network_layer.dataProvider().crs().authid()}]",
                  'END_POINT': f"{round(end.x(), 6)}, {round(end.y(), 6)} ["
                               f"{network_layer.dataProvider().crs().authid()}]",
                  'INPUT': network_layer,
                  'OUTPUT': 'TEMPORARY_OUTPUT',
                  'SPEED_FIELD': None,
                  'STRATEGY': 0,
                  'TOLERANCE': 0,
                  'VALUE_BACKWARD': '',
                  'VALUE_BOTH': '',
                  'VALUE_FORWARD': ''}

        try:
            output_layer = processing.run("native:shortestpathpointtopoint", params)['OUTPUT']

            f = output_layer.getFeature(1)
            if not f.isValid():
                req = QgsFeatureRequest()
                req = req.setNoAttributes()
                f = next(output_layer.getFeatures(req))

            polyline = get_polyline(f.geometry())

            points = []
            for p in polyline:
                if p not in points:
                    points.append(p)

            if points[0].compare(end):
                # falsch herum gerechnet, einmal Liste drehen
                polyline.reverse()

            return points

        except KeyError as e:
            return []

        except Exception as e:
            return []

    @classmethod
    def get_polyline_tracer(cls, network_layer, start_point, end_point):
        """ gets polyline list of QgsPointXY's from start to end point
            by using qgis QgsTracer class.

            This method expects

            :param network_layer: vector layer (LineGeometry)
            :type network_layer: QgsVectorLayer

            :param start_point: start point on path
            :param end_point: end point on path
        """
        tracer = QgsTracer()
        tracer.setLayers([network_layer])

        transform = get_transform(network_layer.crs(), network_layer.crs())
        tracer.setDestinationCrs(network_layer.crs(), transform.context())

        return tracer.findShortestPath(start_point, end_point)[0]

    @classmethod
    def get_polyline_shortest_tree(cls, network_layer, start_point, end_point):
        """ gets polyline list of QgsPointXY's from start to end point
            by using qgis QgsVectorLayerDirector the python way.

            :param network_layer: vector layer (LineGeometry)
            :type network_layer: QgsVectorLayer

            :param start_point: start point on path
            :param end_point: end point on path
        """

        builder = QgsGraphBuilder(network_layer.sourceCrs())
        director = QgsVectorLayerDirector(
            network_layer,  # feature source representing network
            -1,  # field containing direction value
            '',  # value for direct one-way road
            '',  # value for reversed one-way road
            '',  # value for two-way (bidirectional) road
            QgsVectorLayerDirector.DirectionBoth
        )

        points = director.makeGraph(builder, [start_point, end_point])
        tied_start_point, tied_stop_point = points

        graph = builder.graph()
        point_idx_start = graph.findVertex(tied_start_point)
        tree = QgsGraphAnalyzer.shortestTree(graph, point_idx_start, 0)
        point_idx_start = tree.findVertex(tied_start_point)
        point_idx_end = tree.findVertex(tied_stop_point)
        # no Route found
        if point_idx_end == -1:
            return []

        # Add last point
        route = [tree.vertex(point_idx_end).point()]

        # Iterate the graph
        while point_idx_end != point_idx_start:
            edge_ids = tree.vertex(point_idx_end).incomingEdges()
            if len(edge_ids) == 0:
                break
            edge = tree.edge(edge_ids[0])
            route.insert(0, tree.vertex(edge.fromVertex()).point())
            point_idx_end = edge.fromVertex()

        return route

    @classmethod
    def check_route_gaps(cls, layer: QgsVectorLayer, start_point: QgsPointXY,
                             end_point: QgsPointXY, route: Optional[List[int]] = None,
                             vertex_tolerance: float = EPSILON,
                             last_pt_tolerance: float = EPSILON_METRES):
        """ checks, whether the route can be ordered from start point to endpoint on given layer.
            It can consider using vertex tolerance for route points and last point-check.
            It orders route-list and returns it

            :param layer: vector layer with line geometries
            :param start_point: first point on route
            :param end_point: last point on route
            :param route: feature id list starting with first feature
            :param vertex_tolerance: point tolerance to find connected segment
            :param last_pt_tolerance: last point tolerance in metres
        """
        if not route:
            return False, route, True

        obj_distance = QgsDistanceArea()
        crs = layer.dataProvider().crs()
        obj_distance.setSourceCrs(crs,
                                  QgsProject.instance().transformContext())
        obj_distance.setEllipsoid(crs.ellipsoidAcronym())

        features = [layer.getFeature(fid) for fid in route]

        get_dist = lambda a, b: obj_distance.measureLine(a, b)
        is_dist_ok = lambda d: d <= vertex_tolerance or vertex_tolerance == -1
        found = []
        index = 0
        spaces_found = False

        def order_line(search_point):
            nearest = []  # [dist, fid, poly index]
            if get_dist(search_point, end_point) == 0:
                return
            for f in features:
                if f.id() in found:
                    continue  # Bereits gefunden

                line = get_polyline(f.geometry())
                d_a = get_dist(search_point, line[0])
                d_b = get_dist(search_point, line[-1])
                if is_dist_ok(d_a):  # Linie richtig gemalt
                    nearest.append([d_a, f.id(), -1])
                if is_dist_ok(d_b):  # spiegel verkehrt gemalt
                    nearest.append([d_b, f.id(), 0])

            nearest.sort(key=lambda x: x[0])
            if nearest:
                this_dist, fid, poly_index = nearest[0]
                if this_dist > 0:
                    spaces_found = True
                found.append(fid)
                feat = layer.getFeature(fid)
                point = get_polyline(feat.geometry())[poly_index]
                order_line(point)

        order_line(start_point)  # Gehe von Start -> Ende durch
        # Prüfe nun Ende
        route_found = len(found) == len(route)
        if found:  # Es muss natürlich was da sein...
            last_line = get_polyline(layer.getFeature(found[-1]).geometry())
            if get_dist(end_point, last_line[0]) > last_pt_tolerance \
                and get_dist(end_point, last_line[-1]) > last_pt_tolerance:
                route_found = False  # grenzt doch nicht an...
                spaces_found = True  # grenzt doch nicht an...

        return route_found, found, spaces_found  # Wenn Länge gleich, dann i.O.
