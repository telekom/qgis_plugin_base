# -*- coding: utf-8 -*-
# SPDX-FileCopyrightText: 2025 Deutsche Telekom Technik GmbH <f.vonstudsinske@telekom.de>
# SPDX-License-Identifier: GPL-3.0-only

import processing

from enum import auto

from qgis.PyQt.QtCore import QObject
from qgis.core import (QgsVectorLayer, QgsProcessingException, QgsPointXY, QgsWkbTypes, QgsTracer,
                       QgsSpatialIndexKDBush, QgsFeatureRequest, QgsFeature, QgsGeometry, QgsFeatureSink)
from qgis.analysis import (QgsVectorLayerDirector, QgsNetworkDistanceStrategy, QgsNetworkStrategy,
                           QgsGraphBuilder, QgsGraphAnalyzer)

from typing import Optional, List, Dict, Callable, Any

from .geometry import remove_duplicated_points, get_transform, get_polyline, is_point_on_line
from ..constants import EPSILON
from ..enum_ import Enum


class PathFinderMethods(Enum):
    """ Methods in a default order for the PathFinderV2. """

    ProcessingDijkstra = auto()
    """ Uses the processing algorithm 'native:shortestpathpointtopoint' """

    Dijkstra = auto()
    """ Use the 'QgsGraphAnalyzer.dijkstra' method """

    ShortestTree = auto()
    """ Use the 'QgsGraphAnalyzer.shortestTree' method """

    Tracer = auto()
    """ Use the implementation from the QgsTracer class with 'QgsTracer.findShortestPath()'. """


class PathFinderFidRouteModes(Enum):
    STRICT = auto()
    """ "strict" that the found fid route must start and end with the given points. """

    CONTAINS = auto()
    """ "contains" is less strict to get fids with some overlapping points, 
        but not fully included in the path.
    """


class PathFinderV2(QObject):

    def __init__(self, network_layer: QgsVectorLayer, *,
                 vector_layer_director_params: Optional[dict] = None,
                 vector_layer_director_dijkstra_strategy: QgsNetworkStrategy = None,
                 epsilon: float = EPSILON,
                 vector_layer_director_graph_points: Optional[List[QgsPointXY]] = None,
                 processing_dijkstra_params: Optional[Dict[str, Any]] = None,
                 parent: Optional[QObject] = None):
        """ The Path Finder helps to find the shortest/fastest path on a line layer (LineString, not multipart).
            The Path Finder can find the route with different methods from QGIS
            and can find the underlying feature ids from the found polyline list based on equality and intersection.

            This class is reusable as an object, until the used network layer has been changed with geometry data.

            :param network_layer: Layer to find the route on (must be a layer from geometry type LineString).
            :param vector_layer_director_params: Additional arguments parsed as kwargs to the QgsVectorLayerDirector.
                                                 The kwarg 'source' will be overwritten with the network_layer.
            :param vector_layer_director_dijkstra_strategy: Strategy for the Dijkstra method
                                                            with the QgsVectorLayerDirector.
                                                            Defaults to QgsNetworkDistanceStrategy()
            :param epsilon: Epsilon value for point comparison.
            :param vector_layer_director_graph_points: All points that should be tied in the graph.
                                                       Case 1: Find the route only for one given start and end,
                                                               then provide a list with only this to points.
                                                       Case 2: Reusing the Path Finder a list of many points,
                                                               that should be used in the following
                                                               path finding progress.
           :param processing_dijkstra_params: Additional processing algorithm arguments.
                                              Defaults to internal preset values.

        """
        super().__init__(parent)

        # pre-check some basic data
        wkb_type = network_layer.wkbType()
        if wkb_type != QgsWkbTypes.LineString:
            raise ValueError(f"The given network_layer ('{network_layer.id()}') "
                             f"is not from type {QgsWkbTypes.displayString(QgsWkbTypes.LineString)}, "
                             f"but got {QgsWkbTypes.displayString(wkb_type)}")

        # set default variables
        self.__network_layer = network_layer
        if vector_layer_director_params is None:
            vector_layer_director_params = {
                'source': self.__network_layer,  # feature source representing network
                'directionFieldId': -1,  # field containing direction value
                'directDirectionValue': "",  # value for direct one-way road
                'reverseDirectionValue': "",  # value for reversed one-way road
                'bothDirectionValue': "",  # value for two-way (bidirectional) road
                'defaultDirection': QgsVectorLayerDirector.DirectionBoth  # value for two-way (bidirectional) road
            }
        else:
            # overwrite/add the key for the layer
            vector_layer_director_params['source'] = self.__network_layer
        self.__vector_layer_director_params = vector_layer_director_params
        if vector_layer_director_dijkstra_strategy is None:
            # default strategy to use
            vector_layer_director_dijkstra_strategy = QgsNetworkDistanceStrategy()
        self.__vector_layer_director_dijkstra_strategy = vector_layer_director_dijkstra_strategy
        self.__vector_layer_director_dijkstra: Optional[QgsVectorLayerDirector] = None
        self.__vector_layer_director_shortest: Optional[QgsVectorLayerDirector] = None
        self.__vector_layer_director_graph_points: List[QgsPointXY] = vector_layer_director_graph_points or []
        self.__tracer: Optional[QgsTracer] = None
        self.__graph_builder_dijkstra = QgsGraphBuilder(self.__network_layer.sourceCrs())
        self.__graph_builder_shortest = QgsGraphBuilder(self.__network_layer.sourceCrs())
        self.__epsilon = epsilon
        if processing_dijkstra_params is None:
            # values for START_POINT and END_POINT will be set later
            self.__processing_dijkstra_params = {
                'DEFAULT_DIRECTION': QgsVectorLayerDirector.DirectionBoth,
                'DEFAULT_SPEED': 50,
                'DIRECTION_FIELD': None,
                'INPUT': self.__network_layer,
                'OUTPUT': 'TEMPORARY_OUTPUT',
                'SPEED_FIELD': None,
                # strategy from the QGIS ui: 0=shortest "Kürzester", 1=fastest "Schnellster"
                'STRATEGY': 0,
                'TOLERANCE': 0,
                'VALUE_BACKWARD': '',
                'VALUE_BOTH': '',
                'VALUE_FORWARD': ''}
        else:
            self.__processing_dijkstra_params = processing_dijkstra_params
        # layer id: spatial index
        self.__spatial_indices_fid_routes: Dict[str, QgsSpatialIndexKDBush] = {}
        # layer id: {mem fid: layer fid}
        self.__mem_feature_id_to_layer_fid_id: Dict[str, Dict[int, int]] = {}
        # layer id: {layer fid: poly line]
        self.__layer_fid_to_polyline: Dict[str, Dict[int, List[QgsPointXY]]] = {}

    def __get_layer_director_dijkstra(self) -> QgsVectorLayerDirector:
        """ Returns the QgsVectorLayerDirector for the internal Dijkstra solution.
            The director will be set to self to become reusable in this object.
            The initial creation of the director may take a moment.

            This director is reusable in the method PathFinderMethods.Dijkstra.
        """
        if self.__vector_layer_director_dijkstra is not None:
            # already set, return it
            return self.__vector_layer_director_dijkstra

        # create the director and parsing the vector layer params
        director = QgsVectorLayerDirector(**self.__vector_layer_director_params)
        director.addStrategy(self.__vector_layer_director_dijkstra_strategy)
        # create the graph with all points to get tied
        director.makeGraph(self.__graph_builder_dijkstra, self.__vector_layer_director_graph_points)

        # make the director reusable on self
        self.__vector_layer_director_dijkstra = director

        return self.__vector_layer_director_dijkstra

    def __get_layer_director_shortest(self) -> QgsVectorLayerDirector:
        """ Returns the QgsVectorLayerDirector for the internal shortest tree solution.
            The director will be set to self to become reusable in this object.
            The initial creation of the director may take a moment.

            The created directory does not have a strategy.

            This director is reusable in the method PathFinderMethods.ShortestTree.
        """
        if self.__vector_layer_director_shortest is not None:
            # already set, return it
            return self.__vector_layer_director_shortest

        # create the director and parsing the vector layer params
        director = QgsVectorLayerDirector(**self.__vector_layer_director_params)
        # create the graph with all points to get tied
        director.makeGraph(self.__graph_builder_shortest, self.__vector_layer_director_graph_points)

        # make the director reusable on self
        self.__vector_layer_director_shortest = director

        return self.__vector_layer_director_shortest

    def __get_tracer(self) -> QgsTracer:
        """ Returns the QgsTracer with preset values.
            The tracer is reusable in the method PathFinderMethods.Tracer.
        """
        if self.__tracer is not None:
            # already created the tracer, return it
            return self.__tracer

        # create the tracer
        self.__tracer = QgsTracer()
        # set the network layer to route on
        self.__tracer.setLayers([self.__network_layer])
        # set transform information
        crs = self.__network_layer.dataProvider().crs()
        transform = get_transform(crs, crs)
        self.__tracer.setDestinationCrs(crs, transform.context())
        # self.__tracer.setAddPointsOnIntersectionsEnabled(True)

        # build the graph
        self.__tracer.init()

        return self.__tracer

    def get_poly_line(self, start_point: QgsPointXY, end_point: QgsPointXY,
                      methods: Optional[List[PathFinderMethods]] = None) -> List[QgsPointXY]:
        """ Returns the found route of points as a poly line.
            In case of no route or an error, the returned list is empty.
            The first (index 0) point in the return list is 'start_point' and the last (index -1) is 'end_point'.

            :param start_point: Start point for the route
            :param end_point: Destination point for the route
            :param methods: Ordered/Prioritized methods to calculate the poly line.
                            First match results into the found route.
        """
        if methods is None:
            methods = PathFinderMethods.members().values()

        elif not methods:
            raise ValueError("no methods defined")

        method_mapping: Dict[PathFinderMethods, Callable[[QgsPointXY, QgsPointXY], List[QgsPointXY]]] = {
            PathFinderMethods.Dijkstra: self.get_poly_line_director_dijkstra,
            PathFinderMethods.ProcessingDijkstra: self.get_poly_line_processing_dijkstra,
            PathFinderMethods.Tracer: self.get_poly_line_tracer,
            PathFinderMethods.ShortestTree: self.get_poly_line_shortest_tree,
        }

        # for the given order (priority) the method will be used to find the route
        for method_enum in methods:
            # get the callable method
            method = method_mapping[method_enum]
            if poly_line := method(start_point, end_point):
                # the poly line is not empty, return the result
                return poly_line  # self.__get_fixed_poly_line(start_point, end_point, poly_line)

        return []

    def __get_fixed_poly_line(self, start_point: QgsPointXY, end_point: QgsPointXY,
                              poly_line: List[QgsPointXY]) -> List[QgsPointXY]:
        """ Fixes the found poly_line, to add the missing start vertex, add the missing end vertex
            or update the vertex to fix inaccuracies with the coordinates.

            :param start_point: Start point for the route.
            :param end_point: Destination point for the route.
            :param poly_line: Polyline to fix.
        """
        poly_line = poly_line.copy()

        if poly_line[0].compare(start_point, self.__epsilon):
            # replace the first vertex, to be sure, that they are no inaccuracies with the coordinates
            poly_line[0] = start_point
            if poly_line[1].compare(start_point, self.__epsilon):
                # remove the second item in the list (prevent duplicated points)
                poly_line.pop(1)
        else:
            # missing start point (usually not the case, but just to be sure)
            poly_line.insert(0, start_point)

        if poly_line[-1].compare(end_point, self.__epsilon):
            # replace the last vertex, to be sure, that they are no inaccuracies with the coordinates
            poly_line[-1] = end_point
        else:
            # missing end point, depends on the used method from PathFinderMethods it might be the case ...
            poly_line.append(end_point)

        return poly_line

    def get_poly_line_director_dijkstra(self, start_point: QgsPointXY, end_point: QgsPointXY) -> List[QgsPointXY]:
        """ Returns the found route of points as a poly line.
            Uses the python based Dijkstra implementation from PyQGIS.

            This implementation orientated at PyQGIS Cookbook and C++ implementation.

            Reuses the created graph if present, otherwise create it.

            :param start_point: Start point for the route. The provided point should be included
                                in the vector_layer_director_graph_points argument list.
            :param end_point: Destination point for the route. The provided point should be included
                              in the vector_layer_director_graph_points argument list.
        """

        # create the director and graph, if not exists
        self.__get_layer_director_dijkstra()
        graph = self.__graph_builder_dijkstra.graph()

        # get the required start and end vertex ids
        vertex_start_id = graph.findVertex(start_point)
        vertex_end_id = graph.findVertex(end_point)
        # the Dijkstra goes backwards, current id is the end vertex id
        vertex_current_id = vertex_end_id

        # pre checks, if the vertex id in the graph is -1 (not exists)
        #   EPSILON based comparison not performed in c++ QgsGraph.findVertex, uses == operator
        if vertex_start_id == -1 or vertex_end_id == -1:
            return []

        # get the tree
        (tree, costs) = QgsGraphAnalyzer.dijkstra(graph, vertex_start_id, 0)

        if tree[vertex_end_id] == -1:
            # no route found
            return []

        # the end vertex/point is not always included
        points = [graph.vertex(vertex_end_id).point()]
        while vertex_current_id != vertex_start_id:
            vertex_current_id = graph.edge(tree[vertex_current_id]).fromVertex()
            points.append(graph.vertex(vertex_current_id).point())

        # Post check, to prepare a list with only the first match between start and the end point
        new_points = []
        for point in points:
            new_points.append(point)
            # poly line ends here (starts here), all other remaining points will be ignored
            if point.compare(start_point, self.__epsilon):
                break

        # reverse the point list, because Dijkstra goes backwards, not forward here
        new_points.reverse()
        return new_points

    def get_poly_line_processing_dijkstra(self, start_point: QgsPointXY, end_point: QgsPointXY):
        """ Returns the found route of points as a poly line.
            Uses the C++ Dijkstra implementation from QGIS with the processing plugin.
            The algorithm name is 'native:shortestpathpointtopoint'.

            No reuse of created graphs in the background.

            :param start_point: Start point for the route. The provided point should be included
                                in the vector_layer_director_graph_points argument list.
            :param end_point: Destination point for the route. The provided point should be included
                              in the vector_layer_director_graph_points argument list.
        """

        # prepare the algorithm arguments
        params = self.__processing_dijkstra_params.copy()
        auth_id = self.__network_layer.dataProvider().crs().authid()
        params['START_POINT'] = f"{round(start_point.x(), 6)}, {round(start_point.y(), 6)} [{auth_id}]"
        params['END_POINT'] = f"{round(end_point.x(), 6)}, {round(end_point.y(), 6)} [{auth_id}]"

        # try&except to catch possible algorithm errors
        try:
            # run the algorithm and get the output layer
            output_layer = processing.run("native:shortestpathpointtopoint", params)['OUTPUT']

            # get the first found feature
            feature = next(output_layer.getFeatures())

        except (KeyError, StopIteration):
            # StopIteration maybe in case of an empty output_layer
            # KeyError, when OUTPUT not found
            return []

        except QgsProcessingException:
            # no route found or invalid data, from the processing algorithm itself
            return []

        else:
            # algorithm succeed
            poly_line = feature.geometry().asPolyline()

            # remove duplicated points
            poly_line = remove_duplicated_points(poly_line, epsilon=0.0)

            if poly_line[0].compare(end_point, self.__epsilon):
                # poly_line is not rotated correctly
                poly_line.reverse()

            return poly_line

    def get_poly_line_shortest_tree(self, start_point: QgsPointXY, end_point: QgsPointXY) -> List[QgsPointXY]:
        """ Returns the found route of points as a poly line.
            Uses the python based shortest tree implementation from PyQGIS.

            This implementation orientated at PyQGIS Cookbook and C++ implementation.

            Reuses the created graph if present, otherwise create it.

            :param start_point: Start point for the route. The provided point should be included
                                in the vector_layer_director_graph_points argument list.
            :param end_point: Destination point for the route. The provided point should be included
                              in the vector_layer_director_graph_points argument list.
        """

        # prepare the director and get the graph
        self.__get_layer_director_shortest()
        graph = self.__graph_builder_shortest.graph()

        # get the vertex ids in the graph
        point_idx_start = graph.findVertex(start_point)

        # no route/start point found, vertex id is -1
        # prevent crash, when it is -1
        if point_idx_start == -1:
            return []

        tree = QgsGraphAnalyzer.shortestTree(graph, point_idx_start, 0)
        point_idx_end = tree.findVertex(end_point)

        # no route found, vertex id is -1
        # prevent crash, when it is -1
        if point_idx_end == -1:
            return []

        # add the end point per default into the list
        points = [tree.vertex(point_idx_end).point()]

        # Iterate the graph
        while point_idx_end != point_idx_start:
            # get the edge ids
            edge_ids = tree.vertex(point_idx_end).incomingEdges()
            if len(edge_ids) == 0:
                # no more edge ids, break here
                break
            # get the first edge from the found edges and use it
            edge = tree.edge(edge_ids[0])
            points.insert(0, tree.vertex(edge.fromVertex()).point())
            point_idx_end = edge.fromVertex()

        return points

    def get_poly_line_tracer(self, start_point: QgsPointXY, end_point: QgsPointXY) -> List[QgsPointXY]:
        """ Returns the found route of points as a poly line.
            Uses the QgsTracer.

            Reuses the created tracer if present, otherwise create it.

            :param start_point: Start point for the route. The provided point should be included
                                in the vector_layer_director_graph_points argument list.
            :param end_point: Destination point for the route. The provided point should be included
                              in the vector_layer_director_graph_points argument list.
        """
        # get the tracer
        tracer = self.__get_tracer()
        # find the shortest path
        points, _ = tracer.findShortestPath(start_point, end_point)

        return points

    def get_fid_route(self, start_point: QgsPointXY, end_point: QgsPointXY,
                      origin_layer: Optional[QgsVectorLayer] = None,
                      methods: Optional[List[PathFinderMethods]] = None,
                      *,
                      mode: PathFinderFidRouteModes = PathFinderFidRouteModes.STRICT) -> List[int]:
        """ Returns a sorted feature id list based on the found path with the start and end point.
            The start_point and the end_point must be equal to the first
            or last vertex in the first or last poly line from the fid list.

            :param start_point: Start point for the route.
            :param end_point: Destination point for the route.
            :param origin_layer: Optional layer to get the feature ids from. Defaults to the network_layer.
                                 The CRS must be equal to the network layer.
            :param methods: Ordered/Prioritized methods to calculate the poly line.
                            First match results into the found route.
            :param mode: Mode for coordinates comparison
        """
        # get the polyline path from the network layer
        if not (poly_line := self.get_poly_line(start_point, end_point, methods)):
            return []

        # layer to use
        layer = origin_layer or self.__network_layer
        # get the spatial index to use
        spatial_index: QgsSpatialIndexKDBush = self.__get_fid_route_spatial_index(layer)

        fid_to_polyline = self.__layer_fid_to_polyline[layer.id()]
        mem_feature_id_to_layer_fid_id = self.__mem_feature_id_to_layer_fid_id[layer.id()]

        # sorted feature id list from start to end
        feature_ids: List[int] = []
        len_poly_line = len(poly_line)

        for index in range(len_poly_line):
            if index + 1 > len_poly_line - 1:
                # finished
                break

            current_point = poly_line[index]
            next_point = poly_line[index + 1]

            # get the layer fids from the next point
            next_feature_ids = [
                mem_feature_id_to_layer_fid_id[next_spatial_data.id]
                for next_spatial_data in spatial_index.within(next_point, self.__epsilon)]

            for current_spatial_data in spatial_index.within(current_point, self.__epsilon):
                # get the layer fid from the current iteration
                current_fid = mem_feature_id_to_layer_fid_id[current_spatial_data.id]

                if current_fid in feature_ids:
                    # fid already found
                    continue

                if current_fid not in next_feature_ids:
                    # fid not available in current and next
                    continue

                # get the source poly line from the layer and fid
                current_poly_line = fid_to_polyline[current_fid]

                # current and next point are on the current poly line, then use this feature id
                # minimum two matches
                if (is_point_on_line(current_point, current_poly_line, self.__epsilon)
                        and is_point_on_line(next_point, current_poly_line, self.__epsilon)):
                    feature_ids.append(current_fid)
                    break

        if mode == PathFinderFidRouteModes.STRICT:
            # small post check, if the start is correctly available in the first poly line
            start_poly_line = fid_to_polyline[feature_ids[0]]
            if (not start_poly_line[0].compare(start_point, self.__epsilon)
                    and not start_poly_line[-1].compare(start_point, self.__epsilon)):
                # poly line from the first fid does not start/end with the given end_point
                return []

            # small post check, if the end is correctly available in the last poly line
            end_poly_line = fid_to_polyline[feature_ids[-1]]
            if (not end_poly_line[0].compare(end_point, self.__epsilon)
                    and not end_poly_line[-1].compare(end_point, self.__epsilon)):
                # poly line from the last fid does not start/end with the given end_point
                return []

        return feature_ids

    def __get_fid_route_spatial_index(self, layer: QgsVectorLayer) -> QgsSpatialIndexKDBush:
        """ Returns the existing spatial index for this layer or create a new one. """
        layer_id = layer.id()
        if layer_id in self.__spatial_indices_fid_routes:
            # spatial index for this layer already created
            return self.__spatial_indices_fid_routes[layer_id]

        # request without any attributes, use only the geometries
        request = QgsFeatureRequest().setNoAttributes()

        # create the memory layer for the spatial index
        mem_feature_id = 1
        mem_layer_uri = f"Point?crs={self.__network_layer.dataProvider().crs().authid()}"
        mem_layer = QgsVectorLayer(mem_layer_uri, "memory", "memory")
        self.__layer_fid_to_polyline[layer_id] = layer_fid_to_polyline = {}
        self.__mem_feature_id_to_layer_fid_id[layer_id] = mem_feature_id_to_layer_fid_id= {}

        for feature in layer.getFeatures(request):

            # feature id
            layer_fid = feature.id()
            # get the feature's geometry
            geometry = feature.geometry()
            if geometry.isEmpty() or geometry.isNull():
                # skip this feature
                continue

            # get the poly line
            poly_line = get_polyline(geometry)
            layer_fid_to_polyline[layer_fid] = poly_line

            # add per vertex a point feature
            for point in poly_line:
                # create the feature for the memory layer
                mem_feature = QgsFeature(mem_feature_id)
                mem_feature.setGeometry(QgsGeometry.fromPointXY(point))
                mem_feature_id_to_layer_fid_id[mem_feature_id] = layer_fid
                mem_layer.dataProvider().addFeature(mem_feature, QgsFeatureSink.FastInsert)

                mem_feature_id += 1

        if mem_layer.featureCount() < 1:
            raise ValueError(f"the memory layer is empty, no features available. "
                             f"The source layer's id is '{layer_id}'")

        # create the spatial index
        spatial = QgsSpatialIndexKDBush(mem_layer)

        # store the spatial index
        self.__spatial_indices_fid_routes[layer_id] = spatial

        return spatial
