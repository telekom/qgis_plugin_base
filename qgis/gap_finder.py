# -*- coding: utf-8 -*-
# SPDX-FileCopyrightText: 2025 Deutsche Telekom Technik GmbH <f.vonstudsinske@telekom.de>
# SPDX-License-Identifier: GPL-3.0-or-later

from enum import Enum, auto
from pathlib import Path
from typing import Optional, List, Set, Tuple

from qgis.core import (QgsVectorLayer, QgsField, QgsSpatialIndex, QgsFeature,
                       QgsGeometry, QgsPointXY, QgsRectangle, NULL)
from qgis.PyQt.QtCore import QVariant, QObject, pyqtSignal

from .geometry import get_polyline, is_point_on_line

from .spatial_line_ends_to_point_v2 import LineEndsToPointSpatialIndexV2

from ..constants import EPSILON


class CheckTypes(Enum):
    LineEnds = auto()
    """ Check only line ends, if they are snapped within the given distance and constants.EPSILON """

    RequiresSegmentSplit = auto()
    """ Use this type when the line geometries must be cut at the checked coordinate, 
        not snapped on the segment. 
    """

    OnSegmentSnapped = auto()
    """ Compare line ends, if they are on segments.
        Use this type when the checked coordinate must be snapped on the line geometries.
        Uses always the constants.EPSILON value for the final comparison.
        In the given distance the search will be performed and found geometries must be snapped on segment or vertex.
    """

    OverlappingParts = auto()
    """ Check possible overlapping points. Compare always with constants.EPSILON """

    PointWktEquals = auto()
    """ Similar to `LineEnds`, but with zero epsilon and coordinates must be explicit equal.
        Will only be used, if given in arguments and `LineEnds` check returns True.
    """

    _Error = auto()
    """ Error occurred in a validation, see for more in the feature details. """


class GapFinder(QObject):
    """ Class to find gaps in given features/layer and create a point layer

        Example from Python Console with Plan[Goo] V2:

            .. code-block:: python

                from <plugin>.submodules.core.qgis.tools.gap_finder import GapFinder
                from <plugin>.submodules.core.qgis.canvas.functions import get_extent

                layer = iface.activeLayer()
                current_extent = QgsFeatureRequest().setFilterRect(
                    get_extent(layer.dataProvider().crs()))

                # reduce layer to current zoomed canvas extent
                # layer = layer.materialize(current_extent)

                # size depends on crs (degree or meters)
                gap_size = 0.1

                gap = GapFinder(layer, [CheckTypes.LineEnds], epsilon=gap_size)
                if gap.debug_layer:
                    gap.debug_layer.setName(gap.debug_layer.name() + " - LineEnds")
                    QgsProject.instance().addMapLayer(gap.debug_layer)
                    iface.messageBar().pushWarning(
                        "Lückensuche", f"{gap.debug_layer.featureCount()} Lücke(n) gefunden (LineEnds).")
                else:
                    iface.messageBar().pushSuccess("Lückensuche", "Scheint alles i.o. zu sein")

                gap = GapFinder(layer, [CheckTypes.Segment], epsilon=gap_size)
                if gap.debug_layer:
                    gap.debug_layer.setName(gap.debug_layer.name() + " - Segment")
                    QgsProject.instance().addMapLayer(gap.debug_layer)
                    iface.messageBar().pushWarning(
                        "Lückensuche", f"{gap.debug_layer.featureCount()} Lücke(n) gefunden (Segment).")
                else:
                    iface.messageBar().pushSuccess("Lückensuche", "Scheint alles i.o. zu sein")

                gap = GapFinder(layer, [CheckTypes.OverlappingParts], epsilon=gap_size)
                if gap.debug_layer:
                    gap.debug_layer.setName(gap.debug_layer.name() + " - OverlappingParts")
                    QgsProject.instance().addMapLayer(gap.debug_layer)
                    iface.messageBar().pushWarning(
                        "Lückensuche", f"{gap.debug_layer.featureCount()} Lücke(n) gefunden (OverlappingParts).")
                else:
                    iface.messageBar().pushSuccess("Lückensuche", "Scheint alles i.o. zu sein (OverlappingParts)")
    """
    progressChanged = pyqtSignal(int, int, str, name="progressChanged")
    subProgressChanged = pyqtSignal(int, int, str, name="subProgressChanged")

    def __init__(self, layer: QgsVectorLayer, modes: List[CheckTypes],
                 distance: float = EPSILON * 2, parent: Optional[QObject] = None):
        super().__init__(parent)

        self.modes = modes
        self.__current_main_step = 0

        # setup some stuff
        self.spatial_line_end = LineEndsToPointSpatialIndexV2([0, -1])
        self.spatial_line_end.init(layer)

        if CheckTypes.OnSegmentSnapped in self.modes:
            # create a spatial index with the cached geometries
            self.__spatial_index_snapped_segment: Optional[QgsSpatialIndex] = QgsSpatialIndex(
                layer, flags=QgsSpatialIndex.FlagStoreFeatureGeometries)
        else:
            self.__spatial_index_snapped_segment: Optional[QgsSpatialIndex] = None

        self.layer = layer
        self.distance = distance
        self._handled_point_fids = []
        self._handled_point_fids_segment = set()

        # result layer with point features where maybe is a gap
        self.debug_layer: Optional[QgsVectorLayer] = None
        self.points: Set[Tuple[QgsPointXY, CheckTypes, Optional[str]]] = set()
        self.overlapping_points = []

    def run(self):

        self.__current_main_step += 1
        self.progressChanged.emit(
            self.__current_main_step, len(self.modes) - 1, "Prüfe auf Linienenden/Segmente")
        point_count = len(self.spatial_line_end.get_mapped_points())
        for i, (point_fid, point) in enumerate(self.spatial_line_end.get_mapped_points().items()):
            self.subProgressChanged.emit(i, point_count, "")

            if CheckTypes.LineEnds in self.modes or CheckTypes.PointWktEquals in self.modes:
                self.__check_line_ends(point)

            if CheckTypes.RequiresSegmentSplit in self.modes:
                self.__check_segment(point, point_fid)

            if CheckTypes.OnSegmentSnapped in self.modes:
                self.__check_spatial_index_segment(point, self.spatial_line_end.get_source_fid(point_fid))

        if CheckTypes.OverlappingParts in self.modes:
            self.__current_main_step += 1
            self.progressChanged.emit(
                self.__current_main_step, len(self.modes) - 1, "Prüfe auf überlappende Knotenpunkte")
            self.__check_overlapping_parts()

        if self.points or self.overlapping_points:
            self.setup_layer()

    def setup_layer(self):
        self.debug_layer = QgsVectorLayer(f"Point?crs={self.layer.dataProvider().crs().authid()}",
                                          "vertices",
                                          "memory")
        qml_file = str(Path(__file__).parent / "qml" / "path_finder_gaps.qml")
        self.debug_layer.loadNamedStyle(qml_file)
        self.debug_layer.dataProvider().addAttributes(
            [
                QgsField("mode", QVariant.String),
                QgsField("source_fid", QVariant.LongLong, comment="Source fid from OverlappingParts"),
                QgsField("details", QVariant.String, comment="Optional more details")
            ]
        )
        self.debug_layer.updateFields()
        features = []

        # add points from Segment and LineEnds/PointWktEquals check to the debug layer
        for point, mode, details in self.points:
            f = QgsFeature(self.debug_layer.fields())
            f.setGeometry(QgsGeometry.fromPointXY(point))
            f['mode'] = mode.name
            f['details'] = details if details else NULL
            features.append(f)

        # add overlapping points from line layer to the debug layer
        for point, source_fid in self.overlapping_points:
            f = QgsFeature(self.debug_layer.fields())
            f.setGeometry(QgsGeometry.fromPointXY(point))
            f['source_fid'] = source_fid
            f['mode'] = CheckTypes.OverlappingParts.name
            features.append(f)

        ok, _ = self.debug_layer.dataProvider().addFeatures(features)

    def __check_spatial_index_segment(self, point: QgsPointXY, source_fid: int):
        """ Performs a spatial check with the given point, if the point is snapped on a segment
        or equal to other vertices from different geometries than from the given source_fid.

            :param point: point to test
            :param source_fid: Source fid (first/last vertex from line to validate and to ignore)
        """

        # get the neighbor fids from the spatial index
        rect = QgsRectangle.fromCenterAndSize(point, self.distance, self.distance)
        nearest_line_fids = self.__spatial_index_snapped_segment.intersects(rect)
        if source_fid in nearest_line_fids:
            # remove the source fid from the neighbor list
            nearest_line_fids.remove(source_fid)

        errors = set()

        for geometry in map(self.layer.getGeometry, nearest_line_fids):
            sqrt_distance, closest_point, after_vertex, _ = geometry.closestSegmentWithContext(point)
            if sqrt_distance < 0:
                # noinspection PyProtectedMember
                # negative on error
                errors |= {(point, CheckTypes._Error,
                                 f"Validation for check type '{CheckTypes.OnSegmentSnapped.name}' failed "
                                 f"for coordinate {point.asWkt()}")}
                continue

            if closest_point.distance(point) > self.distance:
                # ignore, to far away
                # not expected to be the case, because only features/geometries are in check
                #   based on the geometry distance, not the bbox (flag)
                continue

            if not is_point_on_line(point, geometry.asPolyline(), epsilon=EPSILON):
                errors |= {(point, CheckTypes.OnSegmentSnapped, f"Entfernung: {sqrt_distance}")}
            else:
                # at least one VALID point found, do nothing
                return

        # not returned yet, add the found errors
        self.points |= errors

    def __check_segment(self, point: QgsPointXY, point_fid: int):
        """ Performs a spatial test to find points from line ends/starts wich are on a segment or vertex.

            :param point: point to test
            :param point_fid: point fid from self.spatial_line_end
        """
        # FIXME Ändern auf, dass geprüft wird, dass ein Segment hier geteilt werden sollte.
        spatial_segment = QgsSpatialIndex(self.layer)
        neighbor = spatial_segment.intersects(QgsRectangle.fromCenterAndSize(
            point, self.distance * 2, self.distance * 2))
        source_fid = self.spatial_line_end.get_source_fid(point_fid)
        for nid in neighbor:
            if nid == source_fid:
                # source fid equals neighbor fid
                continue

            geometry = self.spatial_line_end.get_source_geometry(nid)
            if geometry is None:
                # geometry not loaded
                continue

            poly = get_polyline(geometry)

            if poly[0].compare(point, self.distance):
                # test point equals start/end point
                continue

            if poly[-1].compare(point, self.distance):
                # test point equals start/end point
                continue

            if not is_point_on_line(point, poly, self.distance):
                # test point not on segment on this neighbor line
                continue

            sqrt_distance, closest_point, after_vertex, _ = geometry.closestSegmentWithContext(point)
            if sqrt_distance < 0:
                # negative on error
                continue

            if closest_point.distance(point) > self.distance:
                continue

            # add it
            self.points |= {(point, CheckTypes.RequiresSegmentSplit, None)}

    def __check_line_ends(self, point: QgsPointXY):
        """ Performs a spatial test on self.spatial_line_end to find not snapped line ends/starts.

            :param point: point to test
        """

        # test for start/end point
        # from rectangle intersection, similar to a radius check
        neighbor = self.spatial_line_end.intersects(QgsRectangle.fromCenterAndSize(point,
                                                                                   self.distance * 2,
                                                                                   self.distance * 2))
        errors = set()

        for point_fid in neighbor:
            if point_fid in self._handled_point_fids:
                # prevent from performance issues
                continue

            # compare test point with spatial point
            source_point = self.spatial_line_end.get_point_from_point_fid(point_fid)
            distance = source_point.distance(point)

            point_wkt = point.asWkt()
            source_point_wkt = source_point.asWkt()

            if source_point.distance(point) > self.distance:
                # point distance is larger than the check distance, do not check
                # break here, because the nearestNeighbor list is sorted by distance
                break

            if CheckTypes.LineEnds in self.modes and not point.compare(source_point, EPSILON):
                errors |= {(point, CheckTypes.LineEnds, f"A: {point_wkt}\nB: {source_point_wkt}")}
                errors |= {(source_point, CheckTypes.LineEnds, f"A: {point_wkt}\nB: {source_point_wkt}")}
                # break, invalid coordinate found
                break

            elif (CheckTypes.PointWktEquals in self.modes
                    and point_wkt != source_point_wkt
                    and point.compare(source_point, EPSILON)):

                # get wkt coordinates
                p0 = point_wkt.replace("POINT(", "").replace(")", "")
                p1 = source_point_wkt.replace("POINT(", "").replace(")",
                                                                        "")
                errors |= {(point, CheckTypes.PointWktEquals,
                            f"Außerste Genauigkeit gefragt:\n"
                            f"{p0}\n{p1}\n{distance=}")}

                # break, invalid coordinate found
                break

        self._handled_point_fids.extend(neighbor)
        self.points |= errors

    def __check_overlapping_parts(self):

        def _get_id(f) -> int:
            # returns preferred fid attribute, fallback to feature's id itself
            if f.fields().indexFromName("fid") != -1:
                return f['fid']

            return f.id()

        # create map
        poly_line_map = {
            _get_id(feature): get_polyline(feature.geometry())
            for feature in self.layer.getFeatures()
        }
        feature_count = len(poly_line_map)
        for i, (source_fid, poly_line) in enumerate(poly_line_map.items()):
            self.subProgressChanged.emit(i, feature_count, "")

            for fid_iter, poly_line_iter in poly_line_map.items():
                if source_fid == fid_iter:
                    # do not check same line
                    continue

                for point in poly_line[1:-1]:

                    if point.compare(poly_line_iter[0], self.distance) or point.compare(poly_line_iter[-1],
                                                                                        self.distance):
                        # equal to first or last vertex in compare line
                        continue

                    if is_point_on_line(point, poly_line_iter):
                        self.overlapping_points.append((point, source_fid))
