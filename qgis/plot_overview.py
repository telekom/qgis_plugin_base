# -*- coding: utf-8 -*-
# SPDX-FileCopyrightText: 2025 Deutsche Telekom Technik GmbH <f.vonstudsinske@telekom.de>
# SPDX-License-Identifier: GPL-3.0-or-later

import json
import math

from qgis.core import (QgsVectorLayer, QgsGeometry, QgsFeature, QgsRectangle,
                       QgsFeatureRequest, QgsCoordinateReferenceSystem,
                       QgsWkbTypes)

from typing import List

from .geometry import transform_geometry, is_geometry_valid


class PlotOverviewRectangles:
    """ Creates rectangles containing all selected features with overlapping in percentage.

        :param layers:
        :param crs:
        :param rectangle:
        :param overlap: range from 0 to 0.9 (0=near to no overlap)
    """

    def __init__(self, layers: List[QgsVectorLayer], crs: QgsCoordinateReferenceSystem,
                 rectangle: QgsRectangle, overlap: float = 0.075):

        self.__layers = layers
        self.__crs = crs
        self.__rectangle = rectangle
        self.__overlap = overlap

        self.__width = self.rectangle.xMaximum() - self.rectangle.xMinimum()
        self.__height = self.rectangle.yMaximum() - self.rectangle.yMinimum()

        self.__width_overlap = self.width * (1 - overlap)
        self.__height_overlap = self.height * (1 - overlap)

        self.__positions: List[Position] = []
        self.__rectangles: List[QgsRectangle] = []

        self.run()

    def run(self):
        """ Runs rectangle calculation.
            Already calculated positions will be cleared.
        """
        self.positions.clear()

        for layer in self.layers:
            if not layer.selectedFeatureIds():
                continue

            request = QgsFeatureRequest().setNoAttributes()
            request = request.setFilterFids(layer.selectedFeatureIds())

            for feature in layer.getFeatures(request):
                self.add_feature(feature, layer.dataProvider().crs())

        self.calculate_rectangles()

    def calculate_rectangles(self):
        self.rectangles.clear()
        while self.positions:
            ppos = self.positions[:]

            # Kleinsten xmin-Wert finden
            xmin = None
            yxmin = None
            for p, _ in enumerate(self.positions):
                pos = self.positions[p]

                if xmin is None:
                    xmin = pos.xmin
                    yxmin = pos.ymin

                elif pos.xmin < xmin:
                    xmin = pos.xmin
                    yxmin = pos.ymin

            # Kleinsten ymin-Wert eines Objekts finden das noch komplett in die Plotbreite minus Überlappung passt
            ymin = None
            for p, _ in enumerate(self.positions):
                pos = self.positions[p]

                if abs(pos.xmin - xmin) <= self.width_overlap and abs(
                        pos.xmax - xmin) <= self.width_overlap:

                    if abs(pos.ymin - yxmin) <= self.height_overlap and abs(
                            pos.ymax - yxmin) <= self.height_overlap:

                        if ymin is None:
                            ymin = pos.ymin
                        elif pos.ymin < ymin:
                            ymin = pos.ymin

            # Alle Objekte finden die in dem Bereich liegen der durch xmin, ymin festgelegt wurde und in einer Liste
            # zusammenfassen und die wirklichen Ausmaße finden
            xmax = None
            ymax = None
            p_list = []
            for p, _ in enumerate(self.positions):
                pos = self.positions[p]
                if ymin is not None and xmin is not None:
                    if xmin <= pos.xmin and (xmin + self.width_overlap) >= pos.xmax:
                        if ymin <= pos.ymin <= (ymin + self.height_overlap):
                            p_list.append(p)
                            if xmax is None:
                                xmax = pos.xmax
                            elif xmax < pos.xmax:
                                xmax = pos.xmax

                            if ymax is None:
                                ymax = pos.ymax
                            elif ymax < pos.ymax:
                                ymax = pos.ymax

            # Falls sowohl xmin als auch ymin gefunden wurden, dann eine Map dieses Bereichs erstellen
            if xmin and ymin and xmax and ymax:
                # xpos = xmin
                # ypos = ymin
                xpos = xmin - (self.width - (xmax - xmin)) / 2
                ypos = ymin - (self.height - (ymax - ymin)) / 2
                _rect = QgsRectangle(xpos, ypos, xpos + self.width, ypos + self.height)
                rectangle = self.rectangle.scaled(1, _rect.center())
                self.rectangles.append(rectangle)

            # geplottete Objekte für den nächsten Durchlauf aus der Liste entfernen
            p_list.reverse()
            for p in p_list:
                del self.positions[p]

            if ppos == self.positions:
                break

    def add_feature(self, feature: QgsFeature, crs: QgsCoordinateReferenceSystem) -> List['Position']:
        geometry: QgsGeometry = feature.geometry()
        if not is_geometry_valid(geometry):
            return []

        transformed = transform_geometry(geometry, crs, self.crs)

        # convert polygon to line type
        if transformed.wkbType() in [QgsWkbTypes.Polygon, QgsWkbTypes.MultiPolygon]:
            if transformed.isMultipart():
                transformed = QgsGeometry.fromMultiPolylineXY(transformed.asMultiPolygon()[0])
            else:
                transformed = QgsGeometry.fromPolylineXY(transformed.asPolygon()[0])

        g = json.loads(transformed.asJson())
        if g['type'] == 'Point':
            self.positions.append(Position(
                x1=g['coordinates'][0],
                x2=g['coordinates'][0],
                y1=g['coordinates'][1],
                y2=g['coordinates'][1],
                width=0,
                height=0,
                xmin=g['coordinates'][0],
                ymin=g['coordinates'][1],
                xmax=g['coordinates'][0],
                ymax=g['coordinates'][1],
            ))
        elif g['type'] == 'LineString' or g['type'] == 'MultiLineString':
            if g['coordinates']:
                if g['type'] == 'LineString':
                    g['coordinates'] = [g['coordinates']]
                for gc in g['coordinates']:
                    xv = gc[0][0]
                    yv = gc[0][1]
                    max_len = self.height * self.overlap
                    for p in range(1, len(gc)):
                        dx = gc[p][0] - xv
                        dy = gc[p][1] - yv
                        line_length = math.sqrt(pow(dx, 2) + pow(dy, 2))
                        line_parts = int(line_length / max_len) + 1
                        dxp = dx / line_parts
                        dyp = dy / line_parts
                        for n in range(1, line_parts):
                            self.positions.append(Position(
                                x1=xv,
                                x2=xv + dxp,
                                y1=yv,
                                y2=yv + dyp,
                                width=abs(dxp),
                                height=abs(dyp),
                                xmin=xv if xv < xv + dxp else xv + dxp,
                                ymin=yv if yv < yv + dyp else yv + dyp,
                                xmax=xv if xv > xv + dxp else xv + dxp,
                                ymax=yv if yv > yv + dyp else yv + dyp
                            ))
                            xv += dxp
                            yv += dyp
                        self.positions.append(Position(
                            x1=xv,
                            x2=gc[p][0],
                            y1=yv,
                            y2=gc[p][1],
                            width=abs(gc[p][0] - xv),
                            height=abs(gc[p][1] - yv),
                            xmin=xv if xv < gc[p][0] else gc[p][0],
                            ymin=yv if yv < gc[p][1] else gc[p][1],
                            xmax=xv if xv > gc[p][0] else gc[p][0],
                            ymax=yv if yv > gc[p][1] else gc[p][1]
                        ))
                        xv = gc[p][0]
                        yv = gc[p][1]
        else:
            bb = transformed.boundingBox()
            self.positions.append(Position(
                x1=bb.xMinimum(),
                x2=bb.xMaximum(),
                y1=bb.yMinimum(),
                y2=bb.yMaximum(),
                width=abs(bb.xMaximum() - bb.xMinimum()),
                height=abs(bb.yMaximum() - bb.yMinimum()),
                xmin=bb.xMinimum(),
                ymin=bb.yMinimum(),
                xmax=bb.xMaximum(),
                ymax=bb.yMaximum()
            ))

    @property
    def layers(self) -> List[QgsVectorLayer]:
        return self.__layers

    @property
    def crs(self) -> QgsCoordinateReferenceSystem:
        return self.__crs

    @property
    def rectangle(self) -> QgsRectangle:
        return self.__rectangle

    @property
    def overlap(self) -> int:
        return self.__overlap

    @property
    def width(self) -> float:
        return self.__width

    @property
    def height(self) -> float:
        return self.__height

    @property
    def width_overlap(self) -> float:
        return self.__width_overlap

    @property
    def height_overlap(self) -> float:
        return self.__height_overlap

    @property
    def positions(self) -> List['Position']:
        return self.__positions

    @property
    def rectangles(self) -> List[QgsRectangle]:
        return self.__rectangles

    def __repr__(self):
        name = self.__class__.__name__
        return f"{name}(height: {self.height}, height_overlap: {self.height_overlap}, width: {self.width}, " \
               f"width_overlap: {self.width_overlap}, overlap: {self.overlap}, overlap: {self.overlap})"


class Position:

    def __init__(self, x1: float, x2: float, y1: float, y2: float, width: float,
                 height: float, xmin: float, ymin: float, xmax: float, ymax: float):
        self.x1 = x1
        self.x2 = x2
        self.y1 = y1
        self.y2 = y2
        self.width = width
        self.height = height
        self.xmin = xmin
        self.ymin = ymin
        self.xmax = xmax
        self.ymax = ymax

    def __repr__(self):
        name = self.__class__.__name__
        return f"{name}(x1={self.x1}, x2={self.x2}, y1={self.y1}, y2={self.y2}, width={self.width}, " \
               f"height={self.height}, xmin={self.xmin}, ymin={self.ymin}, xmax={self.xmax}, ymax={self.ymax})"
