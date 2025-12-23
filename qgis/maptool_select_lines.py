# -*- coding: utf-8 -*-
# SPDX-FileCopyrightText: 2025 Deutsche Telekom Technik GmbH <f.vonstudsinske@telekom.de>
# SPDX-License-Identifier: GPL-3.0-only

from qgis.core import QgsGeometry, QgsFeatureRequest
from qgis.PyQt.QtCore import pyqtSignal

from .maptool_digitize_geometry import MapToolDigitizeFeature
from .path_finder import PathFinder
from .gap_finder import GapFinder, CheckTypes
from ..constants import EPSILON, EPSILON_GEOGRAPHIC


class MapToolPathFinderMethod:
    Explicit = 0
    Containing = 1


class MapToolPathFinder(MapToolDigitizeFeature):
    """ Create a MapTool to find feature-id path on given linestring layer.

        .. code-block:: python

            # import from here
            import importlib
            from <plugin>.submodules.core.qgis.canvas import maptool_select_lines
            MapToolPathFinder = importlib.reload(maptool_select_lines).MapToolPathFinder

            _tool = MapToolPathFinder.start_from_layer(
                    iface.activeLayer(),
                    iface,
                    force_snap=True,
                    match_filters=[])
            _tool.drawingFinished.connect(lambda *args: print("drawingFinished", args))
            _tool.digitizingFinished.connect(lambda *args: print("digitizingFinished", args))
            _tool.routeNotFound.connect(lambda *args: print("routeNotFound", args))
            _tool.routeFound.connect(lambda *args: print("routeFound", args))

        :param method: Method for PathFinder MapToolPathFinderMethod (hidden kwarg)
        :param create_sub_layer_factor: Float factor to create sub layer for routing (hidden kwarg)
    """
    # optional gap layer with possible gabs in point area
    routeNotFound = pyqtSignal(GapFinder, name="routeNotFound")
    # route found with list of feature ids (sorted from start to end)
    routeFound = pyqtSignal(list, name="routeFound")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._method = kwargs.get('method', MapToolPathFinderMethod.Explicit)
        self._create_sub_layer_factor = kwargs.get('create_sub_layer_factor', 4.0)
        self.drawingFinished.connect(self.find_route)

    def find_route(self, geometry: QgsGeometry):
        """ drawing finished, now try to find route.
            Emits signal routeFound or routeNotFound.
        """
        sub_layer = None

        if geometry.isMultipart():
            # get the segment with vertices from the drawn line
            points = geometry.asMultiPolyline()[0]
        else:
            # single type
            points = geometry.asPolyline()

        if self.layer().dataProvider().crs().isGeographic():
            # e.g. EPSG:4326
            epsilon = EPSILON_GEOGRAPHIC
        else:
            # e.g. EPSG:25832, EPSG:3857
            epsilon = EPSILON

        if self._create_sub_layer_factor:
            bbox = geometry.boundingBox()
            bbox = bbox.scaled(self._create_sub_layer_factor)
            sub_layer = self.origin_layer.materialize(QgsFeatureRequest().setFilterRect(bbox))

        if self._method == MapToolPathFinderMethod.Explicit:
            route = PathFinder.get_feature_route(self.origin_layer, points, sub_layer=sub_layer, epsilon=epsilon)
        elif self._method == MapToolPathFinderMethod.Containing:
            route = PathFinder.get_containing_feature_route(self.origin_layer, points, sub_layer=sub_layer, epsilon=epsilon)
        else:
            raise ValueError(f"{self._method} method unknown")

        if route:
            self.routeFound.emit(route)
        else:
            request = QgsFeatureRequest().setFilterRect(
                geometry.boundingBox().scaled(2.0))
            gap = GapFinder(self.origin_layer.materialize(request),
                            modes=[CheckTypes.LineEnds, CheckTypes.RequiresSegmentSplit, CheckTypes.OverlappingParts])
            gap.run()
            self.routeNotFound.emit(gap)
