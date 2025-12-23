# -*- coding: utf-8 -*-
# SPDX-FileCopyrightText: 2025 Deutsche Telekom Technik GmbH <f.vonstudsinske@telekom.de>
# SPDX-License-Identifier: GPL-3.0-only

from typing import Optional, List, Tuple, Union, Dict

from qgis.PyQt.QtCore import QVariant

from qgis.core import (QgsVectorLayer, QgsFeatureRequest,
                       QgsPointXY, QgsSpatialIndex,
                       QgsFeatureIterator, QgsFeature,
                       QgsFields, QgsField, QgsGeometry,
                       QgsPoint, QgsCoordinateReferenceSystem,
                       QgsFeedback)

from .geometry import get_multi_polyline, is_line_geometry_valid
from ..constants import EPSILON, TO_STRING_PREC
from ..enum_ import Enum


# QObject is not inheritable here (fighting with the QgsSpatialIndex)
class LineEndsToPointSpatialIndexV2(QgsSpatialIndex):
    """ layer geometries must be single type.
        Non-existing vertices will be ignored.
        Only features with valid geometry will be loaded (see. is_geometry_valid)
        Possible to track the progress of the spatial index creation with QgsFeedback

        Fore more information see `QgsSpatialIndex` in pyqgis doc.

        .. code-block:: python
            :linenos:

            # simple usage
            spatial = LineEndsToPointSpatialIndexV2([])
            spatial_index.init(line_layer)
            nearest_point_fid = spatial.nearestNeighbor(QgsPointXY(1,1), 1)[0]
            nearest_point_xy = spatial.get_point_from_point_fid(nearest_point_fid)

        .. code-block:: python
            :linenos:

            # usage with a debug layer
            spatial_index = LineEndsToPointSpatialIndexV2([],
                                                        create_debug_layer=True)

            # with a feedback (usuable for progress bars)
            def show_feedback_processed_count(processed_count: int):
                # helper inner function to show connect preparation with progress ui
                print("show_feedback_processed_count", processed_count, "/", self.__spatial.expected_feature_count)
            feedback = QgsFeedback()
            feedback.processedCountChanged.connect(show_feedback_processed_count)

            spatial_index.init(iface.activeLayer(), feedback=feedback)
            if spatial_index.debug_layer:
                QgsProject.instance().addMapLayer(spatial_index.debug_layer)

        :param vertices: vertices from geometry or per segment, per default loads all vertices
        :param vertex_type: vertex type, per segment in geometry or per vertex index from whole geometry?
        :param create_debug_layer: create a debug layer?
        :param keep_attributes: keep attributes from features in mapping dict

    """

    class VertexOptions(Enum):
        """ defines, how the vertex will be loaded into the spatial index """
        PER_SEGMENT = 0  # default, adds point from each polyline (multipolyline -> each polyline in it)
        PER_GEOMETRY_VERTEX = 1  # whole geometry vertex index

    PER_SEGMENT = VertexOptions.PER_SEGMENT
    PER_GEOMETRY_VERTEX = VertexOptions.PER_GEOMETRY_VERTEX

    def __init__(self, vertices: Optional[List[int]] = None, vertex_type: VertexOptions = PER_SEGMENT,
                 create_debug_layer: bool = False, keep_attributes: bool = False):

        if vertices is None:
            vertices = []

        if vertex_type not in self.VertexOptions:
            raise ValueError(f"unknown vertex_type of '{vertex_type}'")

        # super init
        super(LineEndsToPointSpatialIndexV2, self).__init__()

        self._vertices = vertices
        self.__init_called: bool = False
        self.__keep_attributes: bool = keep_attributes
        self.__create_debug_layer: bool = create_debug_layer
        self._only_ends = 0 in vertices and -1 in vertices  # geometry ends available
        self._feature_count = 0  # counter and id of each spatial feature
        self.__expected_feature_count = 0
        self._mapping_point_to_original_fid = {}
        self._mapping_feature_geometries: Dict[int, QgsGeometry] = {}
        self._mapping_features: Dict[int, QgsFeature] = {}
        self._mapping_point_to_vertex = {}  # point fid to vertex index from polyline
        self._mapping_feature_fid_to_point_id_map = {}
        self._mapping_point_to_temp_feature = {}  # point fid with temp feature
        self._mapping_feature_fid_to_vertex_map = {}  # maps layer feature id to used vertex map
        self._mapping_point = {}
        self._mapping_point_connection_count: Dict[str, int] = {}  # {point toString, count of points at this coordinate)
        self._mapping_xy_to_point_ids: Dict[str, List[int]] = {}  # {point toString, [list of point ids])
        self.not_loaded_ids = []
        self._vertex_type: LineEndsToPointSpatialIndexV2.VertexOptions = vertex_type

        self.fields = QgsFields()
        self.fields.append(QgsField("fid", QVariant.Int))
        self.fields.append(QgsField("vertex", QVariant.Int))

    def init(self, source: Union[QgsVectorLayer, QgsFeatureIterator, List[QgsFeature]],
             crs: Optional[QgsCoordinateReferenceSystem] = None, feedback: Optional[QgsFeedback] = None):
        """ initialize the spatial index (may take a while)

            :param source: source features from layer or iterable with features
            :param crs: needed, if given layer is not a vector layer and for the debug layer
            :param feedback: Optional QgsFeedback to track the current progress
        """
        if self.__init_called:
            raise RuntimeError("init can not be called twice")
        self.__init_called = True

        if isinstance(source, QgsVectorLayer):
            # using all features from layer
            if self.__keep_attributes:
                request = QgsFeatureRequest()
            else:
                request = QgsFeatureRequest().setNoAttributes()
            iterator = source.getFeatures(request)
            features = list(iterator)
            use_crs = source.dataProvider().crs()
        elif isinstance(source, (QgsFeatureIterator, list)):
            # using iterator -> transform to list
            features = list(source) if isinstance(source, QgsFeatureIterator) else source
            if self.__create_debug_layer and not isinstance(crs, QgsCoordinateReferenceSystem):
                raise TypeError("crs QgsCoordinateReferenceSystem must be given")
            use_crs = crs
        else:
            raise TypeError("layer must be vector layer or feature iterator")

        if self.__create_debug_layer:
            self.debug_layer = QgsVectorLayer(f"point?crs={use_crs.authid()}",
                                              f"LineEndsToPointSpatialIndexV2 {self._vertex_type}",
                                              "memory")
            self.debug_layer.dataProvider().addAttributes(self.fields.toList())
            self.debug_layer.updateFields()
        else:
            self.debug_layer = None

        # loading features into this spatial index
        self.__expected_feature_count = len(features)
        for i, feature in enumerate(features):

            if feedback is not None:
                feedback.setProcessedCount(i + 1)
                feedback.setProgress(i + 1 / self.expected_feature_count)

            if not isinstance(feature, QgsFeature):
                raise ValueError(f"object at {i} is not a QgsFeature, got {feature}")

            if not is_line_geometry_valid(feature.geometry()):
                self.not_loaded_ids.append(feature.id())
                continue

            if self.add_line_feature(feature):
                self._mapping_features[feature.id()] = feature

        if isinstance(self.debug_layer, QgsVectorLayer):
            self.debug_layer.dataProvider().addFeatures(self._mapping_point_to_temp_feature.values())

    def add_line_feature(self, feature: QgsFeature):
        """ Adds features line geometry to this index.
            Geometrytype can be LineString or MultiLineString.
            Depending on `vertex_type` the vertices will be loaded per segment or per geometry.

            :param feature: QgsFeature to add
        """
        geometry = feature.geometry()
        self._mapping_feature_geometries[feature.id()] = geometry

        if self._vertex_type == self.PER_SEGMENT:

            mapped_point = {}
            mapped_point_id = {}
            for segment in get_multi_polyline(geometry):

                if not self._vertices:
                    # add all points into this index
                    use_vertex_count = list(range(len(segment)))
                else:
                    use_vertex_count = self._vertices

                for vertex in use_vertex_count:

                    try:
                        point = segment[vertex]
                    except IndexError:
                        # vertex does not exists here, ignore it
                        continue

                    id_, point = self._add_simple_vertex(feature, vertex, point)
                    mapped_point[vertex] = point
                    mapped_point_id[vertex] = id_

            self._mapping_feature_fid_to_vertex_map[feature.id()] = mapped_point
            self._mapping_feature_fid_to_point_id_map[feature.id()] = mapped_point_id

        elif self._vertex_type == self.PER_GEOMETRY_VERTEX:
            self._add_geometry_vertices(feature, geometry)

        return True

    def _add_simple_vertex(self, feature: QgsFeature, vertex: int,
                           point: Union[QgsPoint, QgsPointXY]) -> Tuple[int, QgsPointXY]:
        """ will be called, when vertex_type `PER_SEGMENT` is active

            :param feature: feature from source
            :param vertex: vertex from new point
            :param point: point to add

            :return: returns point fid in this spatial index and added point
        """

        # internal feature counter
        self._feature_count += 1
        point = QgsPointXY(point)

        # new spatial feature with dummy fields
        spatial_feature = QgsFeature(self.fields)
        spatial_feature.setId(self._feature_count)
        spatial_feature['fid'] = feature.id()
        spatial_feature['vertex'] = vertex
        spatial_feature.setGeometry(QgsGeometry.fromPointXY(point))

        # some mappings to handle them with new methods
        self._mapping_point_to_vertex[self._feature_count] = vertex
        self._mapping_point_to_temp_feature[self._feature_count] = spatial_feature

        self._mapping_point_to_original_fid[self._feature_count] = feature.id()
        self._mapping_point[self._feature_count] = point

        # count points at coordinate
        key = point.toString(TO_STRING_PREC)
        self._mapping_point_connection_count.setdefault(key, 0)
        self._mapping_point_connection_count[key] += 1

        # save a reference to the coordinates and the connected points
        self._mapping_xy_to_point_ids.setdefault(key, [])
        self._mapping_xy_to_point_ids[key].append(self._feature_count)

        # add feature to spatial index
        self.addFeature(spatial_feature)

        return self._feature_count, point

    def _add_geometry_vertices(self, feature: QgsFeature, geometry: QgsGeometry):
        """ will be called, when vertex_type `PER_GEOMETRY_VERTEX` is active
            Similar to `_add_simple_vertex`, but the vertex will be used on QgsGeometry.vertexAt.

            It is important to know, how it works with LineString and MultiLineStrings.

            :param feature: feature from source
            :param geometry: geometry to add
        """

        if not self._vertices:
            # add all vertices to this spatial index
            mapped_point = {}
            mapped_point_id = {}

            for index, vertex in enumerate(geometry.vertices()):
                id_, point = self._add_simple_vertex(feature, index, vertex)
                mapped_point[index] = point
                mapped_point_id[index] = index

            self._mapping_feature_fid_to_vertex_map[feature.id()] = mapped_point
            self._mapping_feature_fid_to_point_id_map[feature.id()] = mapped_point_id
        else:
            # a list of poly line geometries
            collection = geometry.asGeometryCollection()
            points = []
            for segment in collection:
                points.extend(segment.asPolyline())

            mapped_point = {}
            mapped_point_id = {}

            for vertex in self._vertices:

                try:
                    point = points[vertex]
                except IndexError:
                    # vertex does not exists here, ignore it
                    continue

                id_, point = self._add_simple_vertex(feature, vertex, point)
                mapped_point[vertex] = point
                mapped_point_id[vertex] = vertex

            self._mapping_feature_fid_to_vertex_map[feature.id()] = mapped_point
            self._mapping_feature_fid_to_point_id_map[feature.id()] = mapped_point_id

    def get_other_side(self, point_fid: int) -> int:
        """ returns point fid (temp feat from spatial index) from the other side.
            Only works, when available vertices are 0 and -1

            :param point_fid: internal point fid
        """
        try:
            fid = self._mapping_point_to_original_fid[point_fid]
            vertex = self._mapping_point_to_vertex[point_fid]
        except KeyError:
            raise KeyError(f"{point_fid} not in spatial index")

        if vertex not in [0, -1]:
            raise ValueError(f"vertex {vertex} from point {point_fid} is invalid, must be 0 or -1")

        if vertex == 0:
            # returns other side point fid
            try:
                return self._mapping_feature_fid_to_point_id_map[fid][-1]
            except KeyError:
                raise KeyError(f"no index -1 in vertex map for feature {fid}")

        if vertex == -1:
            # returns other side point fid
            try:
                return self._mapping_feature_fid_to_point_id_map[fid][0]
            except KeyError:
                raise KeyError(f"no index 0 in vertex map for feature {fid}")

        raise KeyError(f"vertex {vertex} is not valid for this function")

    def get_other_side_point(self, point_fid: int) -> QgsPointXY:
        """ return QgsPointXY from other line side with given end point fid from this spatial index.
            Only works, when available vertices are 0 and -1

            :param point_fid: internal point fid
        """
        other_fid = self.get_other_side(point_fid)
        return self.get_point_from_point_fid(other_fid)

    def get_point_from_point_fid(self, point_fid: int) -> QgsPointXY:
        """ returns coordinate from point fid from this spatial index

            :param point_fid: internal point fid
        """
        return self._mapping_point[point_fid]

    def get_mapped_points(self):
        """ returns all mapped points with its id
        """
        return self._mapping_point

    def get_mapped_point_counts(self) -> Dict[str, int]:
        """ Returns all mapped points with its count.
            The point will be added as a string (QgsPointXY.toString(TO_STRING_PREC))
        """
        return self._mapping_point_connection_count

    def get_mapped_xy_to_point_ids(self) -> Dict[str, List[int]]:
        """ Returns all added points with its point ids.
            The point will be added as a string (QgsPointXY.toString(TO_STRING_PREC))
        """
        return self._mapping_xy_to_point_ids

    def get_source_fid(self, point_fid: int) -> int:
        """ returns feature id from source with given id from this index.nearestNeighbor

            :param point_fid: internal point fid
        """
        return self._mapping_point_to_original_fid[point_fid]

    def get_source_fids(self, point_fids: List[int]) -> List[int]:
        """ Returns all feature ids from source with ids from index.nearestNeighbor
            Warning: duplicates in ids possible, when line has duplicated points in index

            :param point_fids: internal point fids
        """
        return list(map(self.get_source_fid, point_fids))

    def get_source_feature(self, source_fid: int) -> Optional[QgsFeature]:
        """ returns feature from source with given id from this index.get_nearest_source_fid

            :param source_fid: source fid
        """

        if source_fid not in self._mapping_features or source_fid in self.not_loaded_ids:
            # e.g. invalid line geometry on source feature
            return None

        return self._mapping_features[source_fid]

    def get_source_geometry(self, source_fid: int) -> Optional[QgsGeometry]:
        """ returns geometry from source with given id from this index.get_nearest_source_fid

            :param source_fid: source fid
        """

        if source_fid not in self._mapping_features or source_fid in self.not_loaded_ids:
            # e.g. invalid line geometry on source feature
            return None

        return self._mapping_features[source_fid].geometry()

    def get_source_features(self, source_fids: List[int]) -> List[QgsFeature]:
        """ Returns all features from source with ids from index.get_nearest_source_fid
            Warning: duplicates in ids possible, when line has duplicated points in index

            :param source_fids: source fids
        """
        return list(map(self.get_source_feature, source_fids))

    def get_nearest_source_fids(self, point: QgsPointXY, *args, **kwargs) -> List[int]:
        """ Arguments like the original `QgsSpatialIndex.nearestNeighbor` method.

            :param point: point
            :param neighbor: max neighbor count
            :param distance: distance to search
        """
        fids = []
        for nid in self.nearestNeighbor(point, *args, **kwargs):
            source_fid = self.get_source_fid(nid)
            if source_fid not in fids:
                fids.append(source_fid)

        return fids

    def get_intersecting_source_fids(self, point: QgsPointXY, *args, epsilon: float = EPSILON, **kwargs) -> List[int]:
        """ Arguments like the original `QgsSpatialIndex.nearestNeighbor` method.

            :param point: point
            :param neighbor: max neighbor count
            :param distance: distance to search
            :param epsilon: epsilon for intersection
        """
        fids = []
        for nid in self.nearestNeighbor(point, *args, **kwargs):

            # no intersected point found in this loop, break it?
            if not self.get_point_from_point_fid(nid).compare(point, epsilon):
                continue

            source_fid = self.get_source_fid(nid)
            if source_fid not in fids:
                # prevent double fids
                fids.append(source_fid)

        return fids

    def get_intersecting_source_features(self, point: QgsPointXY, *args, epsilon: float = EPSILON, **kwargs) -> List[QgsFeature]:
        """ Arguments like the original `QgsSpatialIndex.nearestNeighbor` method.

            :param point: point
            :param neighbor: max neighbor count
            :param distance: distance to search
            :param epsilon: epsilon for intersection
        """
        fids = self.get_intersecting_source_fids(point, *args, epsilon=epsilon, **kwargs)
        return self.get_source_features(fids)

    def is_point_in_index(self, point: QgsPointXY, max_neighbor: int = 1, epsilon: float = EPSILON) -> bool:
        """ Checks, if point is in this spatial index with given tolerance as epsilon.

            :param point: point
            :param max_neighbor: max neighbor count
            :param epsilon: epsilon to check distance to found nearest neighbor

            :return: True, if point is here
        """

        for nid in self.nearestNeighbor(point, max_neighbor):
            if self.get_point_from_point_fid(nid).compare(point, epsilon):
                return True

        return False

    def get_source_count(self) -> int:
        """ returns count of loaded and stored features """
        return len(self._mapping_features)

    def get_point_count(self) -> int:
        """ returns count of loaded points """
        return len(self._mapping_point)

    def get_connected_lines(self, epsilon: float = EPSILON) -> Dict[QgsPointXY, List[QgsFeature]]:
        """ Returns a Dict of connected line features based on point and given epsilon.
            It is similar to get connected edges for the Dijkstra algorithm.
        """

        point_to_features: Dict[QgsPointXY, List[QgsFeature]] = {}

        def point_handled(p: QgsPointXY):
            # checks, if given point has been already added/calculated
            for handled_point in point_to_features:
                if handled_point.compare(p, epsilon):
                    return True

            return False

        # load connected points from loaded vertices in this spatial
        for point in self._mapping_point.values():
            if point_handled(point):
                continue

            # get intersecting features at this coordinate
            features = self.get_intersecting_source_features(point, epsilon=epsilon)
            point_to_features[point] = features

        return point_to_features

    @property
    def expected_feature_count(self):
        return self.__expected_feature_count

    # deprecated
    get_point_from_index_id = get_point_from_point_fid
