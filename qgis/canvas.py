# -*- coding: utf-8 -*-
# SPDX-FileCopyrightText: 2025 Deutsche Telekom Technik GmbH <f.vonstudsinske@telekom.de>
# SPDX-License-Identifier: GPL-3.0-or-later

from qgis.core import (QgsPointXY, QgsFeature, QgsCoordinateReferenceSystem,
                       QgsRectangle, QgsGeometry, QgsProject)
from qgis.gui import QgsMapTool, QgsMapCanvas

from qgis.PyQt.QtCore import QPoint, QVariantAnimation

from typing import List, Optional

from .geometry import transform_geometry


def get_extent(target_crs: QgsCoordinateReferenceSystem,
               canvas: Optional[QgsMapCanvas] = None) -> QgsRectangle:
    """ returns extent in given target_crs from given canvas.

        :param target_crs: target crs
        :param canvas: canvas object, defaults to iface.mapCanvas()
    """
    if canvas is None:
        from qgis.utils import iface
        canvas = iface.mapCanvas()

    geometry = QgsGeometry.fromRect(canvas.extent())
    geometry = transform_geometry(geometry, QgsProject.instance().crs(), target_crs)
    return geometry.boundingBox()


def get_qpoint_xy(canvas: QgsMapCanvas, position_source) -> QgsPointXY:
    """ converts point-object into QgsPointXY.

        :param canvas: coordinate reference system for rectangle coordinates
        :param position_source: QgsFeature, QgsPoint
        :return: converted point
    """
    # wenn position_source = QgsFeature
    map_tool = QgsMapTool(canvas)

    qpoint_xy = None

    if isinstance(position_source, QgsFeature):
        geometry = position_source.geometry()
        if geometry.type() != 0:
            raise TypeError("Übergebenes Feature besitzt keine PunktGeometrie (evtl. ein Linien-Objekt?)")
        qpoint_xy = geometry.asPoint()
    # wenn position_source = QPoint (z.B. von einem Event wie Rechtsklick --> event.pos())
    if isinstance(position_source, QPoint):
        qpoint_xy = map_tool.toMapCoordinates(position_source)

    return qpoint_xy


def get_all_canvas_animations(canvas: QgsMapCanvas) -> List[QVariantAnimation]:
    """ Returns all active canvas animations  (e.g. flashFeatureIds, flashGeometries). """
    animations = canvas.findChildren(QVariantAnimation)
    return animations


def cancel_all_canvas_animations(canvas: QgsMapCanvas):
    """ Cancel all active animations in the canvas (e.g. flashFeatureIds, flashGeometries). """
    for animation in get_all_canvas_animations(canvas):
        # set the progress of the current animation the maximum progress/duration to finish it
        animation.setCurrentTime(animation.totalDuration())
