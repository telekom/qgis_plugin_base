# -*- coding: utf-8 -*-
# SPDX-FileCopyrightText: 2025 Deutsche Telekom Technik GmbH <f.vonstudsinske@telekom.de>
# SPDX-License-Identifier: GPL-3.0-or-later

from typing import List

from qgis.core import (QgsRectangle, QgsGeometry, QgsCoordinateReferenceSystem,
                       QgsVectorLayer)

from .geometry import transform_geometry


def get_extent_by_extents(extents: List[QgsRectangle]) -> QgsRectangle:
    """ Gets the highest extent of given rectangle-extents.

        :param extents: list of rectangles in same crs
        :return: rectangle
    """
    x_min = min(min_) if (min_ := [x.xMinimum() for x in extents]) else None
    x_max = max(max_) if (max_ := [x.xMaximum() for x in extents]) else None
    y_min = min(min_) if (min_ := [x.yMinimum() for x in extents]) else None
    y_max = max(max_) if (max_ := [x.yMaximum() for x in extents]) else None

    # exclude not correct found extends but allow 0 as value
    if (x_min is not None) and (x_max is not None) and (y_min is not None) and (y_max is not None):
        return QgsRectangle(x_min, y_min, x_max, y_max)
    else:
        # no extend found, return empty rectangle
        return QgsRectangle()


def polygon_to_rectangle(polygon_geometry: QgsGeometry) -> QgsRectangle:
    """ Converts simple geometry(polygon) to rectangle.
        All X/Y coordinates will be used, but expecting only 4 edges/points.
        Returns a rectangle with 0 coordinates if the input geometry is invalid

        :param polygon_geometry: Polygon geometry
        :return: converted rectangle
    """
    # get the outer ring of points from the polygon
    point_list = polygon_geometry.asPolygon()[0]

    x_axis = [p.x() for p in point_list]
    if not x_axis:
        x_axis = [0]
    x_min = min(x_axis)
    x_max = max(x_axis)

    y_axis = [p.y() for p in point_list]
    if not y_axis:
        y_axis = [0]
    y_min = min(y_axis)
    y_max = max(y_axis)

    return QgsRectangle(x_min, y_min, x_max, y_max)


def get_highest_extent(layers: List[QgsVectorLayer], source_crs: QgsCoordinateReferenceSystem) -> QgsRectangle:
    """ Calculates highest extent from joined extents from given `layers` list.
        Calculated extent's coordinates will be returned in expected `source_crs` system.

        :param layers: list of vector layers to get extents
        :param source_crs: coordinate reference system for rectangle coordinates
        :return: rectangle
    """

    layer_bounds = []
    for layer in layers:
        if not isinstance(layer, QgsVectorLayer):
            # nicht interessieren hier nur die Objekt zur Ausmaß bestimmung
            continue

        # force extent update
        layer.updateExtents(force=True)
        layer_extent = layer.extent()  # QgsRectangle im aktuellen dataProvider.crs
        geom = QgsGeometry.fromRect(layer_extent)
        if geom.isEmpty() or geom.isNull() or not geom.isGeosValid():
            # skip the invalid geometry
            continue

        # erstelle Rectangle für WGS 84
        new_geom_rect = transform_geometry(geom, layer.dataProvider().crs(), source_crs)

        r = polygon_to_rectangle(new_geom_rect)
        if r.xMinimum() == 0 and r.xMaximum() == 0 and r.yMinimum() == 0 and r.yMaximum() == 0:
            # empty
            continue

        layer_bounds.append(r)
    highest_extent = get_extent_by_extents(layer_bounds)

    return highest_extent
