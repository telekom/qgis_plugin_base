# -*- coding: utf-8 -*-
# SPDX-FileCopyrightText: 2025 Deutsche Telekom Technik GmbH <f.vonstudsinske@telekom.de>
# SPDX-License-Identifier: GPL-3.0-or-later

from qgis.gui import QgsMapMouseEvent, QgsMapTool, QgsMapCanvas
from qgis.core import QgsMapLayer, QgsPointXY

from qgis.PyQt.QtCore import Qt, pyqtSignal


class MapClickTool(QgsMapTool):
    """ Create basic MapTool to catch Events.

        :param canvas:
        :type canvas: QgsMapCanvas

        :param reference_layer: Layer anhand dessen EPSG die Eventposition berechnet werden soll
                                -> `None`: Position anhand des EPSG des Projektes

        :param current_map_tool: previous/current map tool to restore later
    """
    aborted = pyqtSignal(name="aborted")
    finished = pyqtSignal(QgsPointXY, name="finished")
    canvasMoved = pyqtSignal(QgsMapMouseEvent, QgsPointXY, name="canvasMoved")

    def __init__(self, canvas: QgsMapCanvas = None, reference_layer: QgsMapLayer = None,
                 current_map_tool: QgsMapTool = None):
        self.canvas = canvas
        QgsMapTool.__init__(self, self.canvas)
        self._disabled = False

        # Aktionen die beim jeweiligen Event ausgeführt werden sollen
        self.reference_layer = reference_layer
        self.current_map_tool = current_map_tool

    def canvasReleaseEvent(self, event: QgsMapMouseEvent):
        """ wird getriggert beim Loslassen der Maus """

        if self._disabled:
            self.unload_tool()
            return

        if self.reference_layer is None:
            point = self.toMapCoordinates(self.canvas.mouseLastXY())
        else:
            point = self.toLayerCoordinates(self.reference_layer, event.pos())

        if event.button() == Qt.RightButton:
            # abort map tool
            self.aborted.emit()
            self.unload_tool()

        if event.button() == Qt.LeftButton:
            # map tool finished
            self.finished.emit(point)
            self.unload_tool()

    def canvasMoveEvent(self, event: QgsMapMouseEvent):
        """ wird getriggert beim Bewegen der Maus """

        if self._disabled:
            self.unload_tool()
            return

        if self.reference_layer is None:
            point = self.toMapCoordinates(self.canvas.mouseLastXY())
        else:
            point = self.toLayerCoordinates(self.reference_layer, event.pos())

        self.canvasMoved.emit(event, point)

    @classmethod
    def start_map_tool(cls, canvas: QgsMapCanvas,
                       reference_layer: QgsMapLayer = None) -> 'MapClickTool':
        """ Starts and sets new map tool

            :param canvas:
            :type canvas: QgsMapCanvas

            :param reference_layer: reference layer for clicked coordinates, defaults to None to use projects crs
            :type reference_layer: QgsMapLayer

            :return: created and set MapTool
            :rtype: MapTool
        """
        map_tool = cls(canvas, reference_layer, canvas.mapTool())
        canvas.setMapTool(map_tool)
        return map_tool

    def remove_all_drawings(self):
        ...

    @property
    def disabled(self):
        return self._disabled

    def unload_tool(self):
        self.canvas.unsetMapTool(self)
        if not self._disabled:
            self.canvas.setMapTool(self.current_map_tool)
        self._disabled = True
        self.remove_all_drawings()
