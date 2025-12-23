# -*- coding: utf-8 -*-
# SPDX-FileCopyrightText: 2025 Deutsche Telekom Technik GmbH <f.vonstudsinske@telekom.de>
# SPDX-License-Identifier: GPL-3.0-only

from qgis.gui import QgsMapTool, QgsVertexMarker, QgsRubberBand, QgsMapCanvas
from qgis.core import QgsGeometry, QgsVectorLayer, QgsPointXY, QgsWkbTypes

from qgis.PyQt.QtGui import QColor, QFont
from qgis.PyQt.QtCore import Qt, QPointF

from typing import Optional, Union

from .canvas_item import TextItemWithStroke


class DrawTool:
    """ Zur Erstellung einfacher Grafiken und Markierungen auf der Karte.

        Example Usage:

            .. code-block:: python

                # initialize the draw object
                tool = DrawTool(iface.mapCanvas())
                # create point on canvas
                point = tool.create_vpoint(pointxy,
                                           reference_layer,  # needed to convert point to canvas point
                                           QColor(255, 120, 0, 70),
                                           QgsVertexMarker.ICON_CIRCLE,
                                           15,
                                           15)
                # add text to canvas (no scaling)
                tool.add_text("Von", point.pos(), font)

        :param canvas: canvas to draw markers on
        :param reference_list: reference/mutable list to store some data
        :param color: color from Qt, defaults to QColor(0, 250, 0, 100)
        :param size: size, defaults to 10
        :param width: width, defaults to 7
    """

    def __init__(self, canvas: QgsMapCanvas, reference_list: Optional[list] = None,  
                 color: QColor = QColor(0, 250, 0, 100), 
                 size: int = 10, width: int = 7):

        self.canvas = canvas
        self.QgsMapTool = QgsMapTool(self.canvas)
        self.width = width
        self.size = size
        self.color = color

        self.all_drawings = [] if reference_list is None else reference_list

    def add_text(self, text: str, point: Union[QPointF, QgsVertexMarker], font: Optional[QFont] = None,
                 stroke_color: QColor = None, stroke_width: float = 1.0):
        """ Adds text to current canvas scene at given point.

            Hint:

                Added text needs point position relative to current canvas, not to an QgsPointXY.
                You can add text at VertexMarkers location mit `QgsVertexMarker().pos()`.
                On canvas moving, you have to reload the text

            :param text: text to display
            :param point: point position
            :param font: optional font, defaults to default font settings
            :param stroke_color: optional background color

        """
        if font is None:
            font = QFont()

        if isinstance(point, QgsVertexMarker):
            point = point.pos()

        if stroke_color:
            item = TextItemWithStroke(text=text, font=font, stroke_color=stroke_color, stroke_width=stroke_width)
            self.canvas.scene().addItem(item)

        else:
            item = self.canvas.scene().addText(text, font)

        item.setPos(point)
        self.all_drawings.append(item)

    def set_color(self, red: int, green: int, blue: int, transparency: int):
        """ Ändere die Farbe des Zeichentools

            :param red: 0 - 255
            :type red: int

            :param green: 0 - 255
            :type green: int

            :param blue: 0 - 255
            :type blue: int

            :param transparency: 0 - 255
            :type transparency: int
        """
        self.color = QColor(red, green, blue, transparency)

    def set_size(self, size: int):
        """ Ändere die Größe des Zeichentools

            :param size: size
            :type size: int
        """
        self.size = size

    def set_width(self, width: int):
        """ Ändere die Breite des Zeichentools

            :param width: width
            :type width: int
        """
        self.width = width

    def create_vpoint(self, point, source_layer: QgsVectorLayer,
                      color: QColor = None, icon_type: QgsVertexMarker.IconType = None,
                      size: Optional[int] = None, width: Optional[int] = None, 
                      fill_color: QColor = None):
        """ Erstellt ein oder mehrere Punktgrafiken (QgsVertexMarker)

            :param point: QgsPoint or QgsPointXY or QgsGeometry or list of points
            :param source_layer: converts point types to correct crs
            :param color: color, defaults to None
            :param icon_type: icon_type, defaults to None
            :param size: size, defaults to None
            :param width: width, defaults to None
            :param fill_color: fill color, defaults to None
            :return: QgsVertexMarker or List[QgsVertexMarker]

            :raises ValueError: Übergebener `point` ist nicht gültig
        """
        if color is None:
            color = self.color
        if size is None:
            size = self.size
        if width is None:
            width = self.width
        if icon_type is None:
            icon_type = QgsVertexMarker.ICON_CIRCLE

        if isinstance(point, list):
            v_points = []
            for geo in point:
                qpointxy_map = self.QgsMapTool.toMapCoordinates(source_layer, geo)
                v_point = QgsVertexMarker(self.canvas)
                v_point.setCenter(qpointxy_map)
                v_point.setColor(color)
                v_point.setIconSize(size)
                v_point.setIconType(icon_type)
                v_point.setPenWidth(width)
                if fill_color:
                    v_point.setFillColor(fill_color)
                v_points.append(v_point)
                self.all_drawings.append(v_point)
            return v_points

        elif isinstance(point, QgsPointXY):
            v_point = QgsVertexMarker(self.canvas)
            qpointxy_map = self.QgsMapTool.toMapCoordinates(source_layer, point)
            # qpoint = self.QgsMapTool.toCanvasCoordinates(qpointxy_map)
            # print(qpoint)
            # point = self.QgsMapTool.toMapCoordinates(qpoint)
            v_point.setCenter(qpointxy_map)
            v_point.setColor(color)
            v_point.setIconSize(size)
            v_point.setIconType(icon_type)
            v_point.setPenWidth(width)
            if fill_color:
                v_point.setFillColor(fill_color)
            self.all_drawings.append(v_point)
            return v_point

        elif isinstance(point, QgsGeometry):
            qpointxy = point.asPoint()
            v_point = QgsVertexMarker(self.canvas)
            qpointxy_map = self.QgsMapTool.toMapCoordinates(source_layer, qpointxy)
            # qpoint = self.QgsMapTool.toCanvasCoordinates(qpointxy_map)
            # print(qpoint)
            # point = self.QgsMapTool.toMapCoordinates(qpoint)
            v_point.setCenter(qpointxy_map)
            v_point.setColor(color)
            v_point.setIconSize(size)
            v_point.setIconType(icon_type)
            v_point.setPenWidth(width)
            if fill_color:
                v_point.setFillColor(fill_color)
            self.all_drawings.append(v_point)
            return v_point

        else:
            raise ValueError("Übergebener Punkt ist nicht gültig")

    def create_rubber_band(self, geometry, source_layer: QgsVectorLayer, line_type: Qt.PenStyle = Qt.DashLine,
                           color: QColor = None, width: Optional[int] = None, drawn: bool = False) -> QgsRubberBand:
        """ Erstellt eine oder Liniengrafik (QgsRubberBand)

            :param geometry: QgsGeometry or List[QgsGeometry]
            :param source_layer:
            :param line_type: Aussehen der Linie (Gestrichelt, Durchgängig, ...), defaults to
            :param color:
            :param width:
            :param drawn:

            :return: created QgsRubberBand
        """
        if color is None:
            color = self.color
        if width is None:
            width = self.width

        if isinstance(geometry, list):
            qpointsxy = []
            for point in geometry:
                qpointsxy.append(self.QgsMapTool.toMapCoordinates(source_layer, point))
            geometry = QgsGeometry.fromPolylineXY(qpointsxy)

        else:
            qpointsxy = []
            points = geometry.asPolyline()
            for point in points:
                qpointsxy.append(self.QgsMapTool.toMapCoordinates(source_layer, point))
            geometry = QgsGeometry.fromPolylineXY(qpointsxy)

        rubber_band = QgsRubberBand(self.canvas, QgsWkbTypes.LineGeometry)
        rubber_band.setToGeometry(geometry, None)
        rubber_band.setColor(color)
        rubber_band.setWidth(width)
        rubber_band.setLineStyle(line_type)
        self.all_drawings.append(rubber_band)
        return rubber_band

    def create_geometry(self, geometry, source_layer: QgsVectorLayer,
                        color: QColor = None, width: Optional[int] = None, drawn: bool = False,
                        line_type: Qt.PenStyle = Qt.SolidLine) -> QgsRubberBand:
        """ Creates new rubberband on map canvas for given geometry from given layer.

            :param geometry: QgsGeometry
            :param source_layer: Layer for geometry
            :param color:
            :param width:
            :param drawn:
            :param line_type:

            :return: created QgsRubberBand
        """
        if color is None:
            color = self.color
        if width is None:
            width = self.width
            
        canvas_item = QgsRubberBand(self.canvas, source_layer.geometryType())

        canvas_item.setToGeometry(geometry, source_layer)  # Bewegt sich mit Maus mit
        canvas_item.setColor(color)
        canvas_item.setWidth(width)
        canvas_item.setLineStyle(line_type)
        canvas_item.updateCanvas()
        self.all_drawings.append(canvas_item)
        return canvas_item

    def remove_all_drawings(self):
        """ entfernt alle Zeichnungen """
        for drawing in self.all_drawings:
            self.canvas.scene().removeItem(drawing)
        self.all_drawings.clear()

    def remove_last_drawings(self, quantity: int = 1):
        """ entfernt die letzten `quantity` Zeichnungen

            :param quantity: Anzahl der zu entfernenden letzten Zeichnungen
            :type quantity: int
        """
        for i in range(quantity):
            try:
                self.canvas.scene().removeItem(self.all_drawings[-1])
                self.all_drawings.pop(-1)
            except IndexError:
                pass
