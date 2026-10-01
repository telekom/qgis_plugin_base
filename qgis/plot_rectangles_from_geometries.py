# -*- coding: utf-8 -*-
# SPDX-FileCopyrightText: 2025 Deutsche Telekom Technik GmbH <f.vonstudsinske@telekom.de>
# SPDX-License-Identifier: GPL-3.0-only
"""Generate page rectangles covering a collection of geometries."""

import math

from bisect import bisect_right
from dataclasses import dataclass
from itertools import pairwise
from typing import List, Optional, Set, Tuple

from qgis.core import QgsGeometry, QgsRectangle, QgsWkbTypes
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
                            and pos.ymax - pos.ymin <= height_overlap
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
                # Prepared positions must fit at least one template. Keep a defensive
                # singleton fallback so a grouping edge case cannot silently drop one.
                template_index = next((i for i, template in enumerate(self.templates)
                                       if start.xmax - start.xmin <= template.width() * (1 - self.overlap)
                                       and start.ymax - start.ymin <= template.height() * (1 - self.overlap)), None)
                if template_index is None:
                    raise RuntimeError(f"No template can fit position {start}")
                best_candidate = (template_index, [start_index])

            template_index, group = best_candidate

            group_xmin = min(ordered[i].xmin for i in group)
            group_ymin = min(ordered[i].ymin for i in group)
            group_xmax = max(ordered[i].xmax for i in group)
            group_ymax = max(ordered[i].ymax for i in group)

            # Center the full-size page on the group's bounding box. Since the group
            # fits in the reduced usable area, the unused border remains around it.
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
        # Cells are half the smallest usable page dimensions, so an intersection's
        # bounding box fits a page with margin for rounding errors at cell boundaries.
        cell_width = min(template.width() * (1 - self.overlap) for template in self.templates) / 2
        cell_height = min(template.height() * (1 - self.overlap) for template in self.templates) / 2
        bb = geometry.boundingBox()

        engine = QgsGeometry.createGeometryEngine(geometry.constGet())
        engine.prepareGeometry()

        # Round up so the grid is large enough to span the full bounding box;
        # max(1, ...) also handles geometries with zero width or height.
        columns = max(1, math.ceil(bb.width() / cell_width))
        rows = max(1, math.ceil(bb.height() / cell_height))
        # Grid tuple: world-coordinate origin, cell dimensions, then grid dimensions.
        grid = (bb.xMinimum(), bb.yMinimum(), cell_width, cell_height, columns, rows)
        line_cells = self.__line_grid_cells(geometry, grid)
        cell_indices = (sorted(line_cells) if line_cells is not None else
                        ((column, row) for column in range(columns) for row in range(rows)))
        for column, row in cell_indices:
            x = bb.xMinimum() + column * cell_width
            y = bb.yMinimum() + row * cell_height
            cell = QgsGeometry.fromRect(QgsRectangle(x, y, x + cell_width, y + cell_height))
            if not engine.intersects(cell.constGet()):
                continue

            intersection = geometry.intersection(cell)
            if intersection.isNull() or intersection.isEmpty():
                continue

            self.__add_rectangle(intersection.boundingBox())

    @staticmethod
    def __line_grid_cells(geometry: QgsGeometry, grid: Tuple[float, float, float, float, int, int]
                          ) -> Optional[Set[Tuple[int, int]]]:
        """Return grid cells crossed by a linear geometry, or None for other geometry types."""
        if geometry.type() != QgsWkbTypes.LineGeometry:
            return None

        polylines = geometry.asMultiPolyline() if geometry.isMultipart() else [geometry.asPolyline()]
        if not polylines or any(not polyline for polyline in polylines):
            return None

        cells = set()
        for polyline in polylines:
            if len(polyline) == 1:
                cells.update(PlotRectanglesFromGeometries.__segment_grid_cells(polyline[0], polyline[0], grid))
            for start, end in pairwise(polyline):
                cells.update(PlotRectanglesFromGeometries.__segment_grid_cells(start, end, grid))

        return cells

    @staticmethod
    def __segment_grid_cells(start, end, grid: Tuple[float, float, float, float, int, int]
                             ) -> Set[Tuple[int, int]]:
        """Traverse one segment through the grid using a 2D digital differential analyzer."""
        # Convert world coordinates into grid coordinates, where one unit is one cell.
        # Clamp indices because a point on the bounding-box maximum belongs to the last cell.
        column = min(grid[4] - 1, max(0, math.floor((start.x() - grid[0]) / grid[2])))
        row = min(grid[5] - 1, max(0, math.floor((start.y() - grid[1]) / grid[3])))
        end_column = min(grid[4] - 1, max(0, math.floor((end.x() - grid[0]) / grid[2])))
        end_row = min(grid[5] - 1, max(0, math.floor((end.y() - grid[1]) / grid[3])))
        cells = {(column, row)}

        # Direction and distance of the segment in world coordinates.
        dx = end.x() - start.x()
        dy = end.y() - start.y()
        step_x = 1 if dx > 0 else -1 if dx < 0 else 0
        step_y = 1 if dy > 0 else -1 if dy < 0 else 0

        # Parameter change needed to cross one cell in each direction. For example,
        # delta_x is the fraction of the segment traversed between vertical grid lines.
        # A zero direction never crosses that axis, so infinity disables its crossings.
        delta_x = grid[2] / abs(dx) if dx else math.inf
        delta_y = grid[3] / abs(dy) if dy else math.inf

        # Segment parameter (0 at start, 1 at end) where the next cell boundary is met.
        # The boundary is the far edge when moving forward and the near edge when moving back.
        max_x = ((grid[0] + (column + 1) * grid[2] - start.x()) / dx if step_x > 0 else
                 (grid[0] + column * grid[2] - start.x()) / dx if step_x < 0 else math.inf)
        max_y = ((grid[1] + (row + 1) * grid[3] - start.y()) / dy if step_y > 0 else
                 (grid[1] + row * grid[3] - start.y()) / dy if step_y < 0 else math.inf)

        # Advance through whichever boundary is reached first. If both are reached
        # together, the segment passes through a corner and moves diagonally.
        while column != end_column or row != end_row:
            if max_x < max_y:
                column += step_x
                max_x += delta_x
            elif max_y < max_x:
                row += step_y
                max_y += delta_y
            else:
                column += step_x
                row += step_y
                max_x += delta_x
                max_y += delta_y
            cells.add((column, row))

        return cells

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
