# -*- coding: utf-8 -*-
# SPDX-FileCopyrightText: 2025 Deutsche Telekom Technik GmbH <f.vonstudsinske@telekom.de>
# SPDX-License-Identifier: GPL-3.0-only

from typing import Optional, List

from qgis.core import (QgsVectorLayer, QgsGeometry,
                       QgsFeature, QgsWkbTypes,
                       Qgis, QgsPoint, QgsProject,
                       QgsPointXY, QgsPointLocator)
from qgis.gui import (QgsMapToolDigitizeFeature, QgsMapCanvas,
                      QgsAdvancedDigitizingDockWidget,
                      QgsMapMouseEvent, QgisInterface,
                      QgsMapTool)
from qgis.PyQt.QtCore import Qt, pyqtSignal

from .locator_match_filters import BaseMatchFilter
from .geometry import is_point_in_polylist


class MapToolDigitizeFeature(QgsMapToolDigitizeFeature):

    """ Canvas Map Tool to digitize new geometry on given vector layer in
        expected coordinate reference system.
            - no additional coordinate transformation needed, base class do this

        Maybe you have to store the tool object somewhere (e.g. in a UI on self), to let it survive.
        Garbage Collector is still in range and hungry!
        When you have set the created tooltip e.g. on self, you should remove it before set the new one

        Code Block, Console, MapToolDigitizeFeature with Spatial Index
        ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

        .. code-block:: python

            # import from here
            import importlib
            from <plugin>.submodules.core.qgis.canvas import maptool_digitize_geometry
            MapToolDigitizeFeature = importlib.reload(maptool_digitize_geometry).MapToolDigitizeFeature

            # test with SpatialMatchFilter and only snapping on points
            layer = QgsProject.instance().mapLayersByName("Testvergleich-1")[0]
            spatial = QgsSpatialIndex(layer)
            spatial_crs = layer.dataProvider().crs()

            _tool = MapToolDigitizeFeature.start_from_layer(
                iface.activeLayer(),
                iface,
                match_filters=[SpatialMatchFilter(spatial, spatial_crs)])
            _tool.drawingFinished.connect(lambda *args: print("drawingFinished", args))
            _tool.digitizingFinished.connect(lambda *args: print("digitizingFinished", args))


        Code Block, Console, MapToolDigitizeFeature with LayerMatchFilter
        ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

        .. code-block:: python

            # import from here
            import importlib
            from <plugin>.submodules.core.qgis.canvas import maptool_digitize_geometry
            MapToolDigitizeFeature = importlib.reload(maptool_digitize_geometry).MapToolDigitizeFeature

            # test with LayerMatchFilter and simple line drawing
            _tool = MapToolDigitizeFeature.start_from_layer(
                iface.activeLayer(),
                iface,
                match_filters=[LayerMatchFilter([iface.activeLayer()])])
            _tool.drawingFinished.connect(lambda *args: print("drawingFinished", args))
            _tool.digitizingFinished.connect(lambda *args: print("digitizingFinished", args))

        :param canvas: default argument, map canvas
        :param cad_dockwidget: CAD dockwidet form QgisInterface
        :param capture: geometry capture type
        :param layer: layer to draw on (must be in edit mode), overwrites default `mapCanvas().currentLayer()`
        :param previous_layer_id: Layer id to restore previous layer on mapCanvas, before `start_map_tool`
        :param match_filters: List of match filters, to validate clicked coordinates.
                             Can overwrite `force_snap` argument.
                             If one match filter accepts the matched point,
                             than this point is matchen (or check).
        :param force_snap: Internal force snap, if clicked coordinated has to be snapped on an unspecified layer.
        :param warn_disabled_snapping: Auto warn on tool creation, if QGIS internal snapping utils are disabled.
        :param ignore_duplicated_points: ignore already added points
        :param previous_tool: on deactivate restore this map tool
        :param auto_deactivate: Auto deactivate maptool on drawingFinished signal

        :signal drawingFinished: Emits only drawn geometry (uses feature from `digitizingFinished` signal).
                                    - auto emit on point capture type, when a point coordinate has been accepted
                                    - line capture only valid with minimum two vertices, otherwise cancellation on right click
                                    - polygon only valid with at least three vertices, otherwise cancellation on right click
        :signal aborted: if maptool has been canceled
        :signal digitizingCompleted: base implementation, if feature has been digitized
        :signal digitizingFinished: base implementation, if map tool changed/ended

    """

    aborted = pyqtSignal(name="aborted")
    drawingFinished = pyqtSignal(QgsGeometry, name="drawingFinished")

    def __init__(self, canvas: QgsMapCanvas,
                 cad_dockwidget: QgsAdvancedDigitizingDockWidget,
                 capture: QgsMapToolDigitizeFeature.CaptureMode,
                 layer: QgsVectorLayer,
                 previous_layer_id: Optional[str] = None,
                 match_filters: Optional[List[BaseMatchFilter]] = None,
                 force_snap: bool = False,
                 warn_disabled_snapping: bool = True,
                 ignore_duplicated_points: bool = True,
                 previous_tool: Optional[QgsMapTool] = None,
                 auto_deactivate: bool = True,
                 **kwargs):

        # super init
        super().__init__(canvas, cad_dockwidget, capture)
        self.canvas().setCurrentLayer(layer)
        self.setLayer(layer)

        self.__layer = layer
        self.__previous_layer_id = previous_layer_id
        self.__origin_layer = kwargs["origin_layer"]

        self.__force_snap = force_snap
        self.__ignore_duplicated_points = ignore_duplicated_points

        # use the given match filter
        if match_filters is None:
            match_filters = []
        self.__match_filters = match_filters
        self.previous_tool = previous_tool
        self.__deactivated = False
        self.__auto_deactivate = auto_deactivate
        self.drawings = []

        # test snapping config from canvas
        config = self.canvas().snappingUtils().config()
        if warn_disabled_snapping:
            if not config.typeFlag():
                # no snapping type (vertex, segment, centroid etc.) set
                self.canvas().messageEmitted.emit(
                    "Kartenwerkzeug",
                    "Das Einrastwerkzeug ist nicht korrekt eingestellt. Einrasten nicht möglich.",
                    Qgis.MessageLevel.Info)

            if not config.enabled():
                self.canvas().messageEmitted.emit(
                    "Kartenwerkzeug",
                    "Das Einrastwerkzeug ist nicht aktiviert. Einrasten nicht möglich.",
                    Qgis.MessageLevel.Info)

        if not QgsProject.instance().crs().isValid():
            self.canvas().messageEmitted.emit(
                "Kartenwerkzeug",
                "Das Koordinatenbezugssystem für das aktuelle QGIS-Projekt ist ungültig/nicht gesetzt.",
                Qgis.MessageLevel.Critical)


        # connect internal signal to emit only drawn feature-geometries
        self.digitizingCompleted.connect(self._digitizing_completed)
        # connect abort to parent class signal for deactivating tool
        super(QgsMapToolDigitizeFeature, self).deactivated.connect(lambda *_: self.aborted.emit())

    def _digitizing_completed(self, feature: QgsFeature):
        """ Connected to signal `digitizingCompleted`.
            Possible auto restore/deactivate of this tool.

        """
        if not feature.isValid():
            raise ValueError("digitized feature is not valid")
        self.drawingFinished.emit(feature.geometry())

        if self.__auto_deactivate:
            self.deactivate()

    def deactivate(self):
        """ Re-implemented method.

            Additional functionality: Restore previous tool.
        """

        for drawing in self.drawings:
            if drawing:
                self.canvas().scene().removeItem(drawing)
        else:
            self.drawings.clear()

        prev_state = self.deactivated

        self.__deactivated = True

        if not prev_state:
            # run only on first run
            super().deactivate()
            self.canvas().unsetMapTool(self)
        else:
            # prevent recursion calls
            return

        if current_layer := self.canvas().currentLayer():
            id_ = current_layer.id()
            layer = QgsProject.instance().mapLayer(id_)
            if layer is not current_layer:
                # remove no available layer from canvas
                #   should prevent QGIS crashes, when object is not available
                self.canvas().setCurrentLayer(None)

        # clear rubber bands
        self.deleteTempRubberBand()
        rubber_band = self.takeRubberBand()
        if rubber_band:
            self.canvas().scene().removeItem(rubber_band)

        # restore previous active layer on mapCanvas
        # only if in this call this tool has been deactivated
        if self.previous_layer_id and not prev_state:
            # restore main/root layer, before this tool with possible memorized layer was created
            previous_layer = QgsProject.instance().mapLayer(self.previous_layer_id)
            if previous_layer is not None:
                # activate previous layer on QgsMapCanvas (default here is iface.mapCanvas())
                self.canvas().setCurrentLayer(previous_layer)

        if self.previous_tool is not None:
            self.canvas().setMapTool(self.previous_tool)

            # set the previous tool to None, to prevent recursive calls which will end in QGIS CRASH
            self.previous_tool = None

    def keyReleaseEvent(self, event):
        """ Special/Unexpected behaviour from QGIS here!
            The original C++ method is still called.

            Overwrites ESC-Key to cancel the tool and restore previous tool.

        """

        pressed_key = event.key()
        # escape button is pressed, drawing tool is unloaded, temporary drawings are removed
        if pressed_key == Qt.Key_Escape:
            event.ignore()
            self.deactivate()

    # FIXME dieses Attribute überschreibt ein vererbtes Signal von QgsMapTool!
    #  WORKAROUND super(QgsMapToolDigitizeFeature, self.__tool).deactivated.connect(lambda: self.__digitization_aborted())
    @property
    def deactivated(self) -> bool:
        """ tool deactivated? """
        return self.__deactivated

    @property
    def auto_deactivate(self) -> bool:
        """ tool to be auto deactivated? """
        return self.__auto_deactivate

    def cadCanvasReleaseEvent(self, event: QgsMapMouseEvent):
        # https://github.com/qgis/QGIS/blob/42f4e1c80ebe7805d06abdd3994d01c0e5c56238/src/gui/qgsmaptoolcapture.cpp#L1233
        if self.deactivated:
            # tool already deactivated ...
            event.ignore()
            self.deactivate()
            self.previous_tool = None
            return

        if event.button() != Qt.LeftButton:
            # cancel tool with right click, if point list is empty or has a length of one
            if len(self.points()) <= 1 and event.button() == Qt.RightButton:
                # cancel tool
                self.deactivate()
                event.ignore()
                return

            # go to super
            super().cadCanvasReleaseEvent(event)
            return

        # get the (snapped/clicked) point, if possible
        # if possible, point's coordinates will be transformed to the self.layer.crs()
        match = event.mapPointMatch()
        point = self.get_clicked_point_xy(event)
        if point is None:
            event.ignore()
            return

        # default pre check
        if self.__force_snap or self.match_filters:
            # Individual handling with expected snapping
            if errors := self.get_match_filter_errors(match):
                errors = "; ".join(errors)
                if errors:
                    errors = " >> " + errors
                self.canvas().messageEmitted.emit(
                    "Kartenwerkzeug",
                    "Gewählte Koordinate auf Grund von zusätzlichen Filtern nicht zugelassen." + errors,
                    Qgis.MessageLevel.Warning)
                event.ignore()
                return

            # check if is matched
            if self.__force_snap and not match.isValid():
                # not snapped, but snapping expected
                event.ignore()
                self.canvas().messageEmitted.emit(
                    "Kartenwerkzeug",
                    "Gewählte Koordinate wurde nicht eingerastet.",
                    Qgis.MessageLevel.Warning)
                return

            if point.isEmpty():
                event.ignore()
                self.canvas().messageEmitted.emit(
                    "Kartenwerkzeug",
                    "Gewählte Koordinate ist leer",
                    Qgis.MessageLevel.Warning)
                return

            if self.__ignore_duplicated_points and is_point_in_polylist(QgsPointXY(point), self.points()):
                event.ignore()
                self.canvas().messageEmitted.emit(
                    "Kartenwerkzeug",
                    "Koordinate bereits geladen.",
                    Qgis.MessageLevel.Warning)
                return

            # okay, let's QGIS do his stuff to add point to map tool
            super().cadCanvasReleaseEvent(event)

        else:
            # default handling
            super().cadCanvasReleaseEvent(event)
            return

    def get_clicked_point_xy(self, event: QgsMapMouseEvent) -> Optional[QgsPointXY]:
        """ Returns the clicked point (transformed coordinates to self.layer()).
            In case of error returns None.
        """

        point = QgsPoint()
        match = event.mapPointMatch()

        # if understanding is correct
        # 0/1 are valid fetches, 2 in case of any error
        # error types are unknown
        #   vertex not found (e.g. on a segment)
        #   feature from match not fetchable
        #   invalid sorce layer
        # https://github.com/qgis/QGIS/blob/42f4e1c80ebe7805d06abdd3994d01c0e5c56238/src/gui/qgsmaptoolcapture.cpp#L605
        res = self.fetchLayerPoint(match, point)

        if res == 1:
            # transform in case of crs mismatch
            # see c++ code
            point = self.canvas().mapSettings().mapToLayerCoordinates(
                self.layer(),
                event.mapPoint())

        if (res == 2 and self.layer() and self.layer().isValid()
                and not event.mapPoint().isEmpty()):
            # QGIS 3.34.6
            # layer is "true", valid and point is not empty
            point = self.canvas().mapSettings().mapToLayerCoordinates(
                self.layer(),
                event.mapPoint())

        # possible convert QgsPoint to QgsPointXY
        point_xy = QgsPointXY(point)

        return point_xy

    @property
    def previous_layer_id(self) -> Optional[str]:
        return self.__previous_layer_id

    @property
    def origin_layer(self) -> QgsVectorLayer:
        return self.__origin_layer

    def get_previous_layer(self) -> Optional[QgsVectorLayer]:
        if not self.previous_layer_id:
            return None

        return QgsProject.instance().mapLayer(self.previous_layer_id)

    def layer(self):
        # overwritted method to not use active canvas layer (iface.activeLayer())
        # use individual layer instead
        return self.__layer

    @classmethod
    def start_from_layer(cls, layer: QgsVectorLayer, iface: QgisInterface,
                         **kwargs):
        """ Create and activate a map tool to digitize a geometry.

            :param layer: Vector layer to digitize a feature for. CaptureMode will be identified from layers geometry type
            :param iface: QgisInterface
            :param kwargs: See for more arguments in class description.
        """
        geometry_type = layer.geometryType()

        wkb_type = layer.wkbType()
        wkb_name = QgsWkbTypes.displayString(wkb_type)

        # create a memory layer to draw on
        memory_layer = QgsVectorLayer(f"{wkb_name}?crs={layer.dataProvider().crs().authid()}", layer.name() + " - Zeichenlayer", "memory")
        memory_layer.startEditing()  # start edit mode to prevent errors
        previous_layer_id = layer.id()  # restore main layer on iface.activeLayer()

        # get valud capture type for geometry
        if geometry_type in [QgsWkbTypes.LineGeometry]:
            capture = QgsMapToolDigitizeFeature.CaptureLine

        elif geometry_type in [QgsWkbTypes.PointGeometry]:
            capture = QgsMapToolDigitizeFeature.CapturePoint

        elif geometry_type in [QgsWkbTypes.PolygonGeometry]:
            capture = QgsMapToolDigitizeFeature.CapturePolygon
        else:
            raise ValueError("unknown geometry type, no capture-type found")

        # overwrite previous_layer_id to restore map layer
        # only overwrite, if not set yet by given kwargs
        if kwargs.get("previous_layer_id", None) is None:
            kwargs["previous_layer_id"] = previous_layer_id

        kwargs["origin_layer"] = layer

        # activate map tool
        tool = cls(iface.mapCanvas(), iface.cadDockWidget(),
                   capture, memory_layer,
                   **kwargs)
        tool.previous_tool = iface.mapCanvas().mapTool()  # save current map tool to restore later
        if hasattr(tool, "setToolName"):  # since QGIS 3.20
            tool.setToolName(memory_layer.name())
        iface.mapCanvas().setMapTool(tool)

        return tool

    def get_match_filter_errors(self, match: QgsPointLocator.Match) -> List[str]:
        """ Returns a list of errors, when individual BaseMatchFilters cannot accept the match """
        errors = []
        for filter_ in self.match_filters:
            if not filter_.acceptMatch(match):
                # get error data from current match
                # get optional error from match filter
                if isinstance(filter_, BaseMatchFilter):
                    # individual solution
                    error = filter_.get_last_error()
                    errors.append(error)

            else:
                # no error found in iteration,
                # only one from match filter list must accept the point and skip all other filters

                # one match is accepted, clear the error list
                errors.clear()
                break

        return errors

    @property
    def force_snap(self) -> bool:
        return self.__force_snap

    @property
    def ignore_duplicated_points(self) -> bool:
        return self.__ignore_duplicated_points

    @property
    def match_filters(self) -> List[BaseMatchFilter]:
        return self.__match_filters
