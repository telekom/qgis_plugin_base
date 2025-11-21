# -*- coding: utf-8 -*-
# SPDX-FileCopyrightText: 2025 Deutsche Telekom Technik GmbH <f.vonstudsinske@telekom.de>
# SPDX-License-Identifier: GPL-3.0-or-later

from typing import Optional

from qgis.PyQt.QtCore import Qt, pyqtSignal
from qgis.PyQt.QtGui import QColor, QMouseEvent
from qgis.core import (QgsVectorLayer, Qgis, QgsRectangle,
                       QgsPointXY, QgsGeometry, QgsProject,
                       QgsApplication, QgsWkbTypes)
from qgis.gui import QgisInterface, QgsMapCanvas, QgsMapTool, QgsRubberBand

from .plot_layer import PlotLayer, PlotPage
from .plot_layout import PlotLayout
from .geometry import transform_geometry


class PlotPageMapTool(QgsMapTool):
    """ Map Tool to add new Pages to PlotLayer.
        Item_map and target_crs and scale working together to calculate correct page size in given crs.

        :param iface: qgis interface with map canvas
        :param previous_map_tool: tool to restore
        :param layout: layout for this new page
        :param scale: map scale to use
        :param plot_layer: PlotLayer
        :param drawings: drawings
    """
    pageAdded = pyqtSignal(PlotPage, name="pageAdded")
    finished = pyqtSignal(name="finished")

    def __init__(self, iface: QgisInterface,
                 previous_map_tool: QgsMapTool,
                 layout: PlotLayout,
                 scale: int,
                 plot_layer: PlotLayer,
                 drawings: Optional[list] = None):
        self.canvas: QgsMapCanvas = iface.mapCanvas()
        QgsMapTool.__init__(self, self.canvas)

        self.layout = layout
        self.iface = iface
        self.item_map = self.layout.item_map
        self.previous_map_tool = previous_map_tool
        self.plot_layer = plot_layer
        layer = self.plot_layer.layer_pages
        self.crs = layer.dataProvider().crs()
        del layer
        self.layer = QgsVectorLayer(f"Point?crs={self.crs.authid()}", "dummy", "memory")

        if drawings is None:
            drawings = []

        self.drawings = drawings
        self.canvas_item: QgsRubberBand = None
        self.scale = scale

        self.item_map.setScale(scale)
        self.item_map.setCrs(self.crs)

        self.iface.messageBar().pushMessage(
            self.tr_('Hint'),
            self.tr_("Left mouse button click on canvas to add new pages. Right mouse button click to finish/cancel map tool."),
            level=Qgis.Info,
            duration=10
        )

    @classmethod
    def tr_(cls, text: str):
        result = QgsApplication.translate("QgsApplication", text)
        return result

    def canvasMoveEvent(self, event):
        """
        QgsMapTool Funktion. Verschiebt ein Rechteck mit
        auf der Karte, wo sich die Maus so lang bewegt.
        """
        center: QgsPointXY = self.toLayerCoordinates(self.layer,
                                                     self.toMapCoordinates(event.pos()))
        if self.canvas_item is None:
            self.canvas_item = QgsRubberBand(self.iface.mapCanvas(), QgsWkbTypes.PolygonGeometry)
            self.drawings.append(self.canvas_item)

        rectangle: QgsRectangle = self.layout.get_parent().get_layout_extent(self.layout.path,
                                                                             center,
                                                                             self.scale)

        # Setze Geometrie
        self.canvas_item.reset()
        geometry = QgsGeometry.fromRect(rectangle)
        geometry = transform_geometry(geometry, self.crs, QgsProject.instance().crs())
        self.canvas_item.setToGeometry(geometry, None)  # Bewegt sich mit Maus mit
        self.canvas_item.setColor(QColor(123, 50, 75, 128))
        self.canvas_item.setWidth(9)
        self.canvas_item.updateCanvas()

    def canvasReleaseEvent(self, event: QMouseEvent):
        btn = event.button()
        if btn != Qt.LeftButton:
            self.iface.mapCanvas().setMapTool(self.previous_map_tool)
            self.iface.mapCanvas().unsetMapTool(self)
            self.iface.messageBar().pushMessage(
                self.tr_('Hint'),
                self.tr_('Finished'),
                level=Qgis.Info,
                duration=5
            )
            if self.canvas_item:
                self.iface.mapCanvas().scene().removeItem(self.canvas_item)
            self.finished.emit()
            return

        # holt die Koordinaten der Maus aus dem PlotLayer
        center: QgsPointXY = self.toLayerCoordinates(self.layer, event.pos())
        rectangle: QgsRectangle = self.layout.get_parent().get_layout_extent(self.layout.path,
                                                                             center,
                                                                             self.scale)
        rect_geom = QgsGeometry.fromRect(rectangle)

        page = self.plot_layer.add_page(self.layout, rect_geom, self.scale)

        self.pageAdded.emit(page)
