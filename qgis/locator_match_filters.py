# -*- coding: utf-8 -*-
# SPDX-FileCopyrightText: 2025 Deutsche Telekom Technik GmbH <f.vonstudsinske@telekom.de>
# SPDX-License-Identifier: GPL-3.0-only

from typing import Optional, List, Union

from qgis.core import (QgsVectorLayer, QgsFeatureRequest,
                       QgsPointLocator, QgsPointXY, QgsSpatialIndex,
                       QgsSpatialIndexKDBush, QgsWkbTypes,
                       QgsProject, QgsCoordinateReferenceSystem,
                       QgsRectangle)

from .geometry import get_polyline, is_point_on_line, transform_point


class BaseMatchFilter(QgsPointLocator.MatchFilter):
    """ Base class for match filters used in :ref:``"""

    def __init__(self):

        super().__init__()
        self._errors = []

    def get_last_error(self) -> Optional[str]:
        if not self._errors:
            return None

        return self._errors[-1]

    def get_errors(self) -> List[str]:
        return self._errors


class LayerMatchFilter(BaseMatchFilter):
    """ Match Filter class to match snapped points from given layer list.
        Be careful, when using overlaying layers.
        QGIS does not match a list of vector layers, QGIS matches the first found vector layer with topological points/vertices.

        :param layers: List of vector layers, where to match on
    """

    def __init__(self, layers: List[QgsVectorLayer]):

        if not layers:
            raise ValueError("list of vector layers should not be emoty/False")

        self.__layers = layers
        self.__names = [l.name() for l in self.__layers
                        if l.name()]
        self.__names = list(sorted(set(self.__names)))

        super().__init__()

    def acceptMatch(self, match: QgsPointLocator.Match) -> bool:

        if match.layer() is None:
            # no layer matched
            self._errors.append("Koordinate auf keinem Layer gefangen.")
            return False

        if match.layer() not in self.__layers:
            names = ", ".join(self.__names)
            self._errors.append(f"Gefangene Koordinate wurde auf unerwarteten Layer '{match.layer().name()}' "
                                f"gefangen. Erwarte aber Layer: {names}")
            return False

        return True


class SpatialMatchFilter(BaseMatchFilter):
    """ Match filter to match if matched point is in a spatial index.

        Compatible with spatial index types:

            - QgsSpatialIndex (spatial index with boundingbox, full geometry or points)
            - QgsSpatialIndexKDBush (only and optimized for points, single type)

        Expects a snapped match on the given spatial index.

        :param spatial: created spatial index
        :param crs: coordinate reference system for coordinates for the spatial index
        :param distance: radius/distance to identify a snapped point
    """

    def __init__(self, spatial: Union[QgsSpatialIndex, QgsSpatialIndexKDBush],
                 crs: QgsCoordinateReferenceSystem,
                 distance: float = 1e-6,
                 name: Optional[str] = None):

        super().__init__()
        self.__crs = crs
        self.__spatial = spatial
        self.__distance = distance
        self.__name = name

    def __accept_spatial_index(self, match: QgsPointLocator.Match):
        # get (transformed) point
        point = self.__get_matched_point(match)
        # get nearest fid, list is empty, if nothing there
        fids = self.__spatial.nearestNeighbor(
            point, 1, self.__distance)
        return bool(fids)

    def __accept_spatial_index_kd_bush(self, match: QgsPointLocator.Match):
        # get (transformed) point
        point = self.__get_matched_point(match)
        # get nearest bush data, list is empty, if nothing there
        kd_bush_datas = self.__spatial.within(point, self.__distance)
        return bool(kd_bush_datas)

    def __get_matched_point(self, match: QgsPointLocator.Match) -> QgsPointXY:
        point = match.point()
        if QgsProject.instance().crs() != self.__crs:
            # transform geometry from layer to spatial crs
            # if projection crs is different to spatial crs
            point = transform_point(
                point, QgsProject.instance().crs(), self.__crs)
        return point

    def acceptMatch(self, match: QgsPointLocator.Match) -> bool:

        if match.layer() is None:
            # no layer matched
            if self.__name:
                self._errors.append(f"{self.__name}: Koordinate auf keinem Layer gefangen.")
            else:
                self._errors.append("Koordinate auf keinem Layer gefangen.")
            return False

        ok = False
        # spatial match validation
        if isinstance(self.__spatial, QgsSpatialIndex):
            ok = self.__accept_spatial_index(match)
        if isinstance(self.__spatial, QgsSpatialIndexKDBush):
            ok = self.__accept_spatial_index_kd_bush(match)

        if not ok:
            if self.__name:
                self._errors.append(
                    f"{self.__name}: Gewählte Koordinate nicht in zulässiger Punktliste zum Einrasten vorhanden")
            else:
                self._errors.append(
                    "Gewählte Koordinate nicht in zulässiger Punktliste zum Einrasten vorhanden")

        return ok


class GeometrySpatialMatchFilter(BaseMatchFilter):
    """ Match filter based on spatial index with store-flag for geometries.

        :param layer: vector layer
        :param distance: radius/distance to identify a snapped point
    """

    def __init__(self, layer: QgsVectorLayer,
                 distance: float = 1e-6,
                 name: Optional[str] = None):

        super().__init__()
        self.__layer = layer
        self.__spatial = QgsSpatialIndex(layer)
        self.__distance = distance
        self.__crs = self.__layer.dataProvider().crs()
        self.__name = name

        if self.__layer.wkbType() != QgsWkbTypes.LineString:
            raise ValueError(f"given vector layer is not a line string layer")

    def __accept_spatial_index(self, match: QgsPointLocator.Match):
        # get (transformed) point
        point = self.__get_matched_point(match)
        # get nearest fid, list is empty, if nothing there
        rect = QgsRectangle().fromCenterAndSize(point, self.__distance, self.__distance)
        fids = self.__spatial.intersects(rect)

        if not fids:
            # no fids with spatial intersection found
            return False

        # create feature request to fetch all intersecting fids with its bbox
        request = QgsFeatureRequest().setFilterFids(fids)
        request = request.setSubsetOfAttributes(["fid"], self.__layer.dataProvider().fields())

        # test each found feature's geometry with matched/snapped point for intersection
        for feature in self.__layer.getFeatures(request):
            geometry = feature.geometry()

            if is_point_on_line(point, get_polyline(geometry), epsilon=self.__distance):
                return True

        return False

    def __get_matched_point(self, match: QgsPointLocator.Match) -> QgsPointXY:
        point = match.point()
        if QgsProject.instance().crs() != self.__crs:
            # transform geometry from layer to spatial crs
            # if projection crs is different to spatial crs
            point = transform_point(
                point, QgsProject.instance().crs(), self.__crs)
        return point

    def acceptMatch(self, match: QgsPointLocator.Match) -> bool:

        if match.layer() is None:
            # no layer matched
            if self.__name:
                self._errors.append(f"{self.__name}: Koordinate auf keinem Layer gefangen.")
            else:
                self._errors.append("Koordinate auf keinem Layer gefangen.")
            return False

        ok = self.__accept_spatial_index(match)

        if not ok:
            if self.__name:
                self._errors.append(
                    f"{self.__name}: Gewählte Koordinate nicht in zulässiger Punktliste zum Einrasten vorhanden")
            else:
                self._errors.append(
                    "Gewählte Koordinate nicht in zulässiger Punktliste zum Einrasten vorhanden")

        return ok
