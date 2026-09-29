# -*- coding: utf-8 -*-
# SPDX-FileCopyrightText: 2025 Deutsche Telekom Technik GmbH <f.vonstudsinske@telekom.de>
# SPDX-License-Identifier: GPL-3.0-only
"""Generate page rectangles covering a collection of geometries."""

import math

from bisect import bisect_right
from dataclasses import dataclass
from typing import List, Optional

from qgis.core import QgsGeometry, QgsRectangle
from qgis.PyQt.QtCore import QObject, pyqtSignal

from .geometry import is_geometry_valid


class PlotRectanglesFromGeometries(QObject):
    """ Creates rectangles containing all given geometries with an overlap as a fraction of template size.

        Geometries fitting into the reduced plot area (plot size minus overlap) are kept in one rectangle.
        Otherwise each part of a multipart geometry is handled separately; parts still too big are split with
        a grid, so they are contained in the union of the rectangles.
        Null, empty or invalid geometries are ignored.

        **Algorithm (greedy sweep, left to right):**

        The geometries are converted into bounding boxes (positions), each fitting into the reduced plot area
        (``width_overlap`` x ``height_overlap``). The positions are sorted by ``xmin``. Then per rectangle:

        1. Horizontal: the leftmost unassigned position is the start. Only the vertical strip
           ``[xmin, xmin + width_overlap]`` is searched.
        2. Vertical: within the strip, the lowest ``ymin`` of the positions lying within ``height_overlap``
           above/below the start defines the bottom of the area.
        3. All positions completely inside ``[xmin, xmin + width_overlap] x [ymin, ymin + height_overlap]``
           form a group.
        4. The template covering the most positions is selected; on equal coverage the first template wins.
           A rectangle with its full size is centered on the extent of the group, so each side keeps
           a margin of at least ``overlap / 2`` of the rectangle size.
        5. The grouped positions are marked as assigned; continue with step 1.

        Resulting behavior:

        - Rectangles follow the data (no fixed grid): strips go from left to right, rectangles within a strip
          mostly from bottom to top. Empty areas are skipped, so no rectangles are created there.
        - ``overlap`` guarantees a minimum margin around the content; the actual overlap between neighboring
          rectangles depends on the data and may be larger or smaller.
        - Greedy approach: decisions are not revised, so the minimum number of rectangles is not guaranteed.

        .. code-block:: python

            plot_rectangles = PlotRectanglesFromGeometries(geometries, [landscape_rectangle, portrait_rectangle])
            plot_rectangles.progressChanged.connect(...)
            rectangles = plot_rectangles.run()
            used_templates = plot_rectangles.rectangle_template_indices

        :param geometries: geometries to cover; all geometries must be in the same
                           coordinate reference system as the rectangle
        :param templates: template rectangles; only their sizes (size of one plot) are used, not their positions.
                          The order defines priority when templates cover the same number of positions.
        :param overlap: fraction of the template size, range from 0 to 0.9 (0=no overlap)
        :param parent: optional QObject parent
    """

    # pyqtSignal(current step, max steps, text)
    progressChanged = pyqtSignal(int, int, str, name="progressChanged")
    # pyqtSignal(current step, max steps, text)
    subProgressChanged = pyqtSignal(int, int, str, name="subProgressChanged")

    def __init__(self, geometries: List[QgsGeometry], templates: List[QgsRectangle], overlap: float = 0.075,
                 parent: Optional[QObject] = None):
        """Initialize the input geometries, page templates, and overlap fraction."""

        super().__init__(parent)

        if not 0 <= overlap <= 0.9:
            raise ValueError(f"overlap must be in range 0 to 0.9, got {overlap}")

        if not templates:
            raise ValueError("at least one template rectangle is required")

        if any(template.width() <= 0 or template.height() <= 0 for template in templates):
            raise ValueError("template rectangles must have a width and height greater than 0")

        self.__geometries = geometries
        self.__templates = templates
        self.__overlap = overlap

        self.__positions: List[_Position] = []
        self.__rectangles: List[QgsRectangle] = []
        self.__rectangle_template_indices: List[int] = []

    def run(self) -> List[QgsRectangle]:
        """ Runs rectangle calculation and returns the rectangles.
            Already calculated positions and rectangles will be cleared.
        """
        self.positions.clear()
        self.__rectangles.clear()
        self.__rectangle_template_indices.clear()

        self.progressChanged.emit(1, 2, "Vorbereitung der Geometrien")
        geometry_count = len(self.geometries)
        for i, geometry in enumerate(self.geometries):
            self.subProgressChanged.emit(i, geometry_count, "")
            self.add_geometry(geometry)
        self.subProgressChanged.emit(geometry_count, geometry_count, "")

        self.progressChanged.emit(2, 2, "Berechne Rechtecke")
        self.__calculate_rectangles()

        return self.rectangles

    def __calculate_rectangles(self):
        """Group prepared positions and create rectangles using the best-fitting template."""
        self.__rectangles.clear()
        self.__rectangle_template_indices.clear()

        # sorted by xmin, so only the strip [xmin, xmin + width_overlap] has to be searched
        ordered = sorted(self.positions, key=lambda pos: pos.xmin)
        xmins = [pos.xmin for pos in ordered]
        alive = [True] * len(ordered)
        position_count = len(ordered)
        removed_count = 0
        start_index = 0

        while start_index < position_count:
            if not alive[start_index]:
                start_index += 1
                continue

            self.subProgressChanged.emit(removed_count, position_count, "")

            # smallest xmin of all positions
            start = ordered[start_index]
            xmin = start.xmin
            best_candidate = None
            for template_index, template in enumerate(self.templates):
                width_overlap = template.width() * (1 - self.overlap)
                height_overlap = template.height() * (1 - self.overlap)
                strip = [i for i in range(start_index, bisect_right(xmins, xmin + width_overlap)) if alive[i]]

                # Find the lowest valid group origin for this template.
                ymin = None
                for i in strip:
                    pos = ordered[i]
                    if (pos.xmax - xmin <= width_overlap
                            and abs(pos.ymin - start.ymin) <= height_overlap
                            and abs(pos.ymax - start.ymin) <= height_overlap
                            and (ymin is None or pos.ymin < ymin)):
                        ymin = pos.ymin

                if ymin is None:
                    continue

                group = [i for i in strip
                         if ordered[i].xmax <= xmin + width_overlap
                         and ymin <= ordered[i].ymin and ordered[i].ymax <= ymin + height_overlap]
                if group and (best_candidate is None or len(group) > len(best_candidate[1])):
                    best_candidate = (template_index, group)

            if best_candidate is None:
                break

            template_index, group = best_candidate

            group_xmin = min(ordered[i].xmin for i in group)
            group_ymin = min(ordered[i].ymin for i in group)
            group_xmax = max(ordered[i].xmax for i in group)
            group_ymax = max(ordered[i].ymax for i in group)

            center_x = (group_xmin + group_xmax) / 2
            center_y = (group_ymin + group_ymax) / 2
            template = self.templates[template_index]
            half_width = template.width() / 2
            half_height = template.height() / 2
            self.__rectangles.append(QgsRectangle(center_x - half_width, center_y - half_height,
                                                  center_x + half_width, center_y + half_height))
            self.__rectangle_template_indices.append(template_index)

            for i in group:
                alive[i] = False
            removed_count += len(group)

        self.positions[:] = [pos for i, pos in enumerate(ordered) if alive[i]]
        self.subProgressChanged.emit(position_count, position_count, "")

    def add_geometry(self, geometry: QgsGeometry):
        """ Adds the positions of the geometry. Null, empty or invalid geometries are ignored. """
        if geometry is None or geometry.isNull() or geometry.isEmpty() or not is_geometry_valid(geometry):
            return

        if self.__fits(geometry.boundingBox()):
            self.__add_rectangle(geometry.boundingBox())
            return

        for part in geometry.asGeometryCollection():
            bb = part.boundingBox()
            if self.__fits(bb):
                self.__add_rectangle(bb)
            else:
                self.__add_grid_cells(part)

    def __fits(self, bb: QgsRectangle) -> bool:
        """Return whether a bounding box fits within any template's usable area."""
        return any(bb.width() <= template.width() * (1 - self.overlap)
                   and bb.height() <= template.height() * (1 - self.overlap)
                   for template in self.templates)

    def __add_grid_cells(self, geometry: QgsGeometry):
        """ Splits the geometry into grid cells, each fitting into the reduced plot area. """
        # half size leaves a margin for floating point deviations of the intersection
        cell_width = min(template.width() * (1 - self.overlap) for template in self.templates) / 2
        cell_height = min(template.height() * (1 - self.overlap) for template in self.templates) / 2
        bb = geometry.boundingBox()

        engine = QgsGeometry.createGeometryEngine(geometry.constGet())
        engine.prepareGeometry()

        columns = max(1, math.ceil(bb.width() / cell_width))
        rows = max(1, math.ceil(bb.height() / cell_height))
        for column in range(columns):
            for row in range(rows):
                x = bb.xMinimum() + column * cell_width
                y = bb.yMinimum() + row * cell_height
                cell = QgsGeometry.fromRect(QgsRectangle(x, y, x + cell_width, y + cell_height))
                if not engine.intersects(cell.constGet()):
                    continue

                intersection = geometry.intersection(cell)
                if intersection.isNull() or intersection.isEmpty():
                    continue

                self.__add_rectangle(intersection.boundingBox())

    def __add_rectangle(self, bb: QgsRectangle):
        """Add a geometry bounding box to the intermediate positions."""
        self.positions.append(_Position(bb.xMinimum(), bb.yMinimum(), bb.xMaximum(), bb.yMaximum()))

    @property
    def geometries(self) -> List[QgsGeometry]:
        """Input geometries to cover."""
        return self.__geometries

    @property
    def templates(self) -> List[QgsRectangle]:
        """Available page templates in tie-break priority order."""
        return self.__templates

    @property
    def overlap(self) -> float:
        """Fraction of each template reserved for overlap margins."""
        return self.__overlap

    @property
    def positions(self) -> List['_Position']:
        """Intermediate bounding boxes generated from input geometries."""
        return self.__positions

    @property
    def rectangles(self) -> List[QgsRectangle]:
        """Generated page rectangles in output order."""
        return self.__rectangles

    @property
    def rectangle_template_indices(self) -> List[int]:
        """ Index of the selected template for each rectangle, in rectangle order. """
        return self.__rectangle_template_indices


@dataclass
class Rectangle:
    """Pair a template name with its page rectangle."""

    name: str
    """Name of the layout template."""
    rectangle: QgsRectangle
    """Rectangle dimensions and extent for the template."""


@dataclass
class _Position:
    xmin: float
    ymin: float
    xmax: float
    ymax: float
