# -*- coding: utf-8 -*-
# SPDX-FileCopyrightText: 2025 Deutsche Telekom Technik GmbH <f.vonstudsinske@telekom.de>
# SPDX-License-Identifier: GPL-3.0-only
"""Generate ordered, overlapping page rectangles along input lines."""

import math

from dataclasses import dataclass
from typing import List, Optional, Tuple

from qgis.core import QgsPointXY, QgsRectangle
from qgis.PyQt.QtCore import QObject, pyqtSignal

# tolerance for the segment parameter t, prevents tiny sections at the borders of covered areas
T_TOLERANCE = 1e-9


class PlotRectanglesFromLines(QObject):
    """ Creates rectangles along lines, following the order and the direction of the lines.

        The lines are processed in the given order (e.g. main roads first, then side roads).
        Each line is walked from its first to its last point and cut into consecutive sections.
        Each section is covered by one rectangle, so the rectangles of a line follow its direction.
        Several templates can be given (e.g. portrait and landscape); per section the template covering
        the longest part of the line is used.

        **Algorithm (walk along each line):**

        1. Parts of the line already covered by the inner area of an existing rectangle (rectangle minus the
           ``overlap / 2`` margin) are skipped, e.g. for lines with an overlapping course or a line running back
           on itself. A section starts at the first uncovered point.
        2. For each template, the line is followed as long as the bounding box of the section fits into the
           reduced plot area of the template (template size minus overlap). If the next vertex does not fit,
           the exact point on the segment where the limit is reached is calculated and the section ends there.
        3. The template with the longest covered line length is used; on equal length the first template
           in the list wins (e.g. at the end of a line, when several templates cover the rest).
        4. A rectangle with the full size of this template is centered on the bounding box of the section,
           so each side keeps a margin of at least ``overlap / 2`` of the rectangle size.
           Neighboring rectangles of a line therefore overlap around the cut point.
        5. The next section starts at the cut point; continue with step 1 until the end of the line.

        Resulting behavior:

        - Rectangles are ordered by line and, within a line, by the direction of the line.
        - Each line starts with a new rectangle; lines are not joined, even if they touch.
        - Parts already covered by rectangles (of previous lines or the same line) get no additional rectangles.
          A line completely covered by existing rectangles results in no rectangle.
        - Rectangles are axis-aligned (not rotated along the line).

        .. code-block:: python

            plot_rectangles = PlotRectanglesFromLines(lines, [landscape_rectangle, portrait_rectangle])
            plot_rectangles.progressChanged.connect(...)
            rectangles = plot_rectangles.run()
            used_templates = plot_rectangles.rectangle_template_indices

        :param lines: sorted list of lines, each line is a list of points; all points must be in the same
                      coordinate reference system as the templates. Empty lines are ignored,
                      a line with a single point results in one rectangle.
        :param templates: template rectangles; only their sizes (size of one plot) are used,
                          not their positions. The order defines the priority on equal line coverage.
        :param overlap: fraction of the rectangle size, range from 0 to 0.9 (0=no overlap)
        :param parent: optional QObject parent
    """

    # pyqtSignal(current step, max steps, text)
    progressChanged = pyqtSignal(int, int, str, name="progressChanged")
    # pyqtSignal(current step, max steps, text)
    subProgressChanged = pyqtSignal(int, int, str, name="subProgressChanged")

    def __init__(self, lines: List[List[QgsPointXY]], templates: List[QgsRectangle], overlap: float = 0.075,
                 parent: Optional[QObject] = None):
        """Initialize the line inputs, page templates, and overlap fraction."""

        super().__init__(parent)

        if not 0 <= overlap <= 0.9:
            raise ValueError(f"overlap must be in range 0 to 0.9, got {overlap}")

        if not templates:
            raise ValueError("at least one template rectangle is required")

        if any(template.width() <= 0 or template.height() <= 0 for template in templates):
            raise ValueError("template rectangles must have a width and height greater than 0")

        self.__lines = lines
        self.__templates = templates
        self.__overlap = overlap

        self.__rectangles: List[QgsRectangle] = []
        self.__rectangle_line_indices: List[int] = []
        self.__rectangle_template_indices: List[int] = []
        # inner areas (xmin, ymin, xmax, ymax) of the rectangles, used to skip covered line parts
        self.__covered_areas: List[Tuple[float, float, float, float]] = []

    def run(self) -> List[QgsRectangle]:
        """ Runs rectangle calculation and returns the rectangles.
            Already calculated rectangles will be cleared.
        """
        self.__rectangles.clear()
        self.__rectangle_line_indices.clear()
        self.__rectangle_template_indices.clear()
        self.__covered_areas.clear()

        self.progressChanged.emit(1, 1, "Berechne Rechtecke entlang der Linien")
        line_count = len(self.lines)
        for line_index, line in enumerate(self.lines):
            self.subProgressChanged.emit(line_index, line_count, "")
            self.__add_line(line_index, line)
        self.subProgressChanged.emit(line_count, line_count, "")

        return self.rectangles

    def __add_line(self, line_index: int, line: List[QgsPointXY]):
        """ Walks along the line and adds a rectangle per section with the best fitting template. """
        if not line:
            return

        segment_index = 0
        start = (line[0].x(), line[0].y())

        while True:
            segment_index, start, covered = self.__skip_covered(line, segment_index, start)
            if covered:
                break

            sections = [self.__walk(line, segment_index, start, template) for template in self.templates]
            # max() returns the first template on equal length
            template_index = max(range(len(sections)), key=lambda i: sections[i].length)
            section = sections[template_index]

            self.__add_rectangle(line_index, template_index, section.bbox)

            if section.finished:
                break

            segment_index = section.segment_index
            start = section.end

    def __skip_covered(self, line: List[QgsPointXY], segment_index: int,
                       start: Tuple[float, float]) -> Tuple[int, Tuple[float, float], bool]:
        """ Moves start along the line as long as it is inside the covered areas.
            Returns the new segment index, the new start and True, if the rest of the line is covered.
        """
        ax, ay = start
        for index in range(segment_index, len(line) - 1):
            bx, by = line[index + 1].x(), line[index + 1].y()
            dx, dy = bx - ax, by - ay

            # covered intervals of the segment parameter t (0 = start, 1 = end)
            intervals = [interval for area in self.__covered_areas
                         if (interval := self.__clip_segment(ax, ay, dx, dy, area)) is not None]
            t = 0.0
            extended = True
            while extended:
                extended = False
                for t0, t1 in intervals:
                    if t0 <= t + T_TOLERANCE and t1 > t:
                        t = t1
                        extended = True

            if t < 1.0 - T_TOLERANCE:
                return index, (ax + t * dx, ay + t * dy), False

            ax, ay = bx, by

        return len(line) - 1, (ax, ay), self.__is_covered(ax, ay)

    def __is_covered(self, x: float, y: float) -> bool:
        return any(xmin <= x <= xmax and ymin <= y <= ymax for xmin, ymin, xmax, ymax in self.__covered_areas)

    @staticmethod
    def __clip_segment(ax: float, ay: float, dx: float, dy: float,
                       area: Tuple[float, float, float, float]) -> Optional[Tuple[float, float]]:
        """ Returns the parameter interval (t0, t1) of the segment inside the area (Liang-Barsky) or None. """
        xmin, ymin, xmax, ymax = area
        t0, t1 = 0.0, 1.0
        for p, q in ((-dx, ax - xmin), (dx, xmax - ax), (-dy, ay - ymin), (dy, ymax - ay)):
            if p == 0:
                if q < 0:
                    return None
                continue
            r = q / p
            if p < 0:
                t0 = max(t0, r)
            else:
                t1 = min(t1, r)
            if t0 > t1:
                return None
        return t0, t1

    def __walk(self, line: List[QgsPointXY], segment_index: int, start: Tuple[float, float],
               template: QgsRectangle) -> '_Section':
        """ Follows the line from start (located on the segment segment_index) as long as the section
            fits into the reduced plot area of the template.
        """
        width_overlap = template.width() * (1 - self.overlap)
        height_overlap = template.height() * (1 - self.overlap)

        ax, ay = start
        # bounding box of the section: xmin, ymin, xmax, ymax
        bbox = [ax, ay, ax, ay]
        length = 0.0

        for index in range(segment_index, len(line) - 1):
            bx, by = line[index + 1].x(), line[index + 1].y()
            segment_length = math.hypot(bx - ax, by - ay)
            t = min(1.0,
                    self.__max_step(ax, bx - ax, bbox[0], bbox[2], width_overlap),
                    self.__max_step(ay, by - ay, bbox[1], bbox[3], height_overlap))

            if t < 1.0:
                cx, cy = ax + t * (bx - ax), ay + t * (by - ay)
                self.__extend(bbox, cx, cy)
                return _Section(bbox, length + t * segment_length, index, (cx, cy), False)

            self.__extend(bbox, bx, by)
            length += segment_length
            ax, ay = bx, by

        return _Section(bbox, length, len(line) - 1, (ax, ay), True)

    @staticmethod
    def __max_step(start: float, delta: float, bbox_min: float, bbox_max: float, size: float) -> float:
        """ Returns the largest fraction of delta, so the bounding box extended by the new value
            keeps the given size in this axis.
        """
        if delta > 0:
            return max(0.0, (bbox_min + size - start) / delta)
        if delta < 0:
            return max(0.0, (bbox_max - size - start) / delta)
        return math.inf

    @staticmethod
    def __extend(bbox: List[float], x: float, y: float):
        """Expand a bounding box to include the supplied point."""
        bbox[0] = min(bbox[0], x)
        bbox[1] = min(bbox[1], y)
        bbox[2] = max(bbox[2], x)
        bbox[3] = max(bbox[3], y)

    def __add_rectangle(self, line_index: int, template_index: int, bbox: List[float]):
        """Create a page rectangle and record its source line and template indices."""
        template = self.templates[template_index]
        center_x = (bbox[0] + bbox[2]) / 2
        center_y = (bbox[1] + bbox[3]) / 2
        half_width = template.width() / 2
        half_height = template.height() / 2
        self.__rectangles.append(QgsRectangle(center_x - half_width, center_y - half_height,
                                              center_x + half_width, center_y + half_height))
        self.__rectangle_line_indices.append(line_index)
        self.__rectangle_template_indices.append(template_index)

        inner_half_width = half_width * (1 - self.overlap)
        inner_half_height = half_height * (1 - self.overlap)
        self.__covered_areas.append((center_x - inner_half_width, center_y - inner_half_height,
                                     center_x + inner_half_width, center_y + inner_half_height))

    @property
    def lines(self) -> List[List[QgsPointXY]]:
        """Input lines in processing order."""
        return self.__lines

    @property
    def templates(self) -> List[QgsRectangle]:
        """Available page templates in tie-break priority order."""
        return self.__templates

    @property
    def overlap(self) -> float:
        """Fraction of each template reserved for overlap margins."""
        return self.__overlap

    @property
    def rectangles(self) -> List[QgsRectangle]:
        """Generated page rectangles in output order."""
        return self.__rectangles

    @property
    def rectangle_line_indices(self) -> List[int]:
        """ Index of the source line for each rectangle (same order as rectangles). """
        return self.__rectangle_line_indices

    @property
    def rectangle_template_indices(self) -> List[int]:
        """ Index of the used template for each rectangle (same order as rectangles). """
        return self.__rectangle_template_indices

    def __repr__(self):
        """Return a concise summary of the configured templates and overlap."""
        name = self.__class__.__name__
        sizes = [(template.width(), template.height()) for template in self.templates]
        return f"{name}(templates (width, height): {sizes}, overlap: {self.overlap})"


@dataclass
class _Section:
    bbox: List[float]  # xmin, ymin, xmax, ymax
    length: float  # covered line length
    segment_index: int  # segment of the end point
    end: Tuple[float, float]
    finished: bool  # end of the line reached
