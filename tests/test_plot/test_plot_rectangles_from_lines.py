# -*- coding: utf-8 -*-
# SPDX-FileCopyrightText: 2025 Deutsche Telekom Technik GmbH <f.vonstudsinske@telekom.de>
# SPDX-License-Identifier: GPL-3.0-only

import math
import pytest

from qgis.core import QgsGeometry, QgsPointXY, QgsRectangle

from ..fixtures import plugin_qgis_new_project

PLOT_RECTANGLE = QgsRectangle(0, 0, 100, 50)
TEMPLATES = [PLOT_RECTANGLE]
LANDSCAPE = QgsRectangle(0, 0, 100, 50)
PORTRAIT = QgsRectangle(0, 0, 50, 100)


def _line(*coordinates):
    return [QgsPointXY(x, y) for x, y in coordinates]


TEST_LINES = [
    _line((0, 0), (1000, 0)),
    _line((0, 0), (1000, 0), (1000, 800), (200, 400)),
    _line((500, 500), (-300, -300), (400, 900)),
    _line((10, 10), (30, 20), (40, 15)),
    _line((2000, 2000), (2000, 2000), (2050, 2010)),
]


def _union(rectangles):
    return QgsGeometry.unaryUnion([QgsGeometry.fromRect(rectangle) for rectangle in rectangles])


def _line_geometry(line):
    return QgsGeometry.fromPointXY(line[0]) if len(line) == 1 else QgsGeometry.fromPolylineXY(line)


def _rectangles_of_line(plot, line_index):
    return [rectangle for rectangle, index in zip(plot.rectangles, plot.rectangle_line_indices) if index == line_index]


@pytest.mark.parametrize('overlap', [0.075, 0.3, 0.9])
def test_all_lines_contained(plugin_qgis_new_project, overlap):
    from ...qgis.plot_rectangles_from_lines import PlotRectanglesFromLines

    plot = PlotRectanglesFromLines(TEST_LINES, TEMPLATES, overlap=overlap)
    plot.run()

    # covered parts of a line may be in rectangles of other lines
    union = _union(plot.rectangles)
    for line_index, line in enumerate(TEST_LINES):
        assert union.contains(_line_geometry(line)), f"line {line_index} not contained"

    for rectangle in plot.rectangles:
        assert rectangle.width() == pytest.approx(PLOT_RECTANGLE.width())
        assert rectangle.height() == pytest.approx(PLOT_RECTANGLE.height())


@pytest.mark.parametrize('overlap', [0.0, 0.075, 0.3, 0.9])
def test_consecutive_rectangles_overlap(plugin_qgis_new_project, overlap):
    from ...qgis.plot_rectangles_from_lines import PlotRectanglesFromLines

    # single lines without self-crossing only, skipped covered parts would leave gaps
    for line in [line for i, line in enumerate(TEST_LINES) if i != 2]:
        rectangles = PlotRectanglesFromLines([line], TEMPLATES, overlap=overlap).run()
        for previous, current in zip(rectangles, rectangles[1:]):
            assert previous.intersects(current)


@pytest.mark.parametrize('duplicate', [
    _line((0, 0), (1000, 0)),
    _line((1000, 0), (0, 0)),
    _line((200, 0), (700, 0)),
    _line((0, 0), (500, 0), (0, 0), (1000, 0)),
])
def test_covered_lines_create_no_rectangles(plugin_qgis_new_project, duplicate):
    from ...qgis.plot_rectangles_from_lines import PlotRectanglesFromLines

    line = _line((0, 0), (1000, 0))
    single_count = len(PlotRectanglesFromLines([line], TEMPLATES).run())

    plot = PlotRectanglesFromLines([line, duplicate], TEMPLATES)
    rectangles = plot.run()

    assert len(rectangles) == single_count
    assert set(plot.rectangle_line_indices) == {0}


def test_self_overlapping_line(plugin_qgis_new_project):
    from ...qgis.plot_rectangles_from_lines import PlotRectanglesFromLines

    line = _line((0, 0), (1000, 0))
    back_and_forth = _line((0, 0), (1000, 0), (0, 0), (1000, 0))

    single_count = len(PlotRectanglesFromLines([line], TEMPLATES).run())
    rectangles = PlotRectanglesFromLines([back_and_forth], TEMPLATES).run()

    assert len(rectangles) == single_count


def test_partially_covered_line(plugin_qgis_new_project):
    from ...qgis.plot_rectangles_from_lines import PlotRectanglesFromLines

    main_road = _line((0, 0), (1000, 0))
    # runs 500 along the main road, then 500 to the north
    side_road = _line((0, 0), (500, 0), (500, 500))

    main_count = len(PlotRectanglesFromLines([main_road], TEMPLATES).run())
    north_count = len(PlotRectanglesFromLines([_line((500, 0), (500, 500))], TEMPLATES).run())

    plot = PlotRectanglesFromLines([main_road, side_road], TEMPLATES)
    rectangles = plot.run()

    side_rectangles = _rectangles_of_line(plot, 1)
    assert len(side_rectangles) <= north_count
    assert len(rectangles) == main_count + len(side_rectangles)
    assert _union(rectangles).contains(_line_geometry(side_road))
    # no rectangle of the side road is centered on the main road
    assert all(rectangle.center().y() > 0 for rectangle in side_rectangles)


def test_covered_point_creates_no_rectangle(plugin_qgis_new_project):
    from ...qgis.plot_rectangles_from_lines import PlotRectanglesFromLines

    plot = PlotRectanglesFromLines([_line((0, 0), (1000, 0)), [QgsPointXY(300, 0)]], TEMPLATES)
    plot.run()

    assert set(plot.rectangle_line_indices) == {0}


def test_straight_line_count(plugin_qgis_new_project):
    from ...qgis.plot_rectangles_from_lines import PlotRectanglesFromLines

    overlap = 0.075
    rectangles = PlotRectanglesFromLines([_line((0, 0), (1000, 0))], TEMPLATES, overlap=overlap).run()

    assert len(rectangles) == math.ceil(1000 / (PLOT_RECTANGLE.width() * (1 - overlap)))


@pytest.mark.parametrize('line, axis, direction', [
    (_line((0, 0), (1000, 0)), 'x', 1),
    (_line((1000, 0), (0, 0)), 'x', -1),
    (_line((0, 0), (0, 1000)), 'y', 1),
    (_line((0, 1000), (0, 0)), 'y', -1),
])
def test_rectangles_follow_line_direction(plugin_qgis_new_project, line, axis, direction):
    from ...qgis.plot_rectangles_from_lines import PlotRectanglesFromLines

    rectangles = PlotRectanglesFromLines([line], TEMPLATES).run()
    centers = [rectangle.center().x() if axis == 'x' else rectangle.center().y() for rectangle in rectangles]

    assert len(centers) > 1
    assert all((b - a) * direction > 0 for a, b in zip(centers, centers[1:]))


def test_rectangles_follow_line_vertices(plugin_qgis_new_project):
    from ...qgis.plot_rectangles_from_lines import PlotRectanglesFromLines

    # U-turn: east, north, west
    line = _line((0, 0), (500, 0), (500, 300), (0, 300))
    rectangles = PlotRectanglesFromLines([line], TEMPLATES).run()

    assert QgsGeometry.fromRect(rectangles[0]).contains(QgsGeometry.fromPointXY(line[0]))
    assert QgsGeometry.fromRect(rectangles[-1]).contains(QgsGeometry.fromPointXY(line[-1]))

    # first index of a rectangle containing each vertex must be increasing
    first_indices = [next(i for i, rectangle in enumerate(rectangles)
                          if QgsGeometry.fromRect(rectangle).contains(QgsGeometry.fromPointXY(point)))
                     for point in line]
    assert first_indices == sorted(first_indices)


def test_rectangles_in_line_order(plugin_qgis_new_project):
    from ...qgis.plot_rectangles_from_lines import PlotRectanglesFromLines

    main_road = _line((0, 0), (600, 0))
    side_road = _line((300, 0), (300, 400))
    plot = PlotRectanglesFromLines([main_road, side_road], TEMPLATES)
    rectangles = plot.run()

    assert plot.rectangle_line_indices == sorted(plot.rectangle_line_indices)
    assert set(plot.rectangle_line_indices) == {0, 1}
    assert len(plot.rectangle_line_indices) == len(rectangles)
    assert QgsGeometry.fromRect(rectangles[0]).contains(QgsGeometry.fromPointXY(main_road[0]))
    assert QgsGeometry.fromRect(rectangles[-1]).contains(QgsGeometry.fromPointXY(side_road[-1]))


def test_short_line_in_one_rectangle(plugin_qgis_new_project):
    from ...qgis.plot_rectangles_from_lines import PlotRectanglesFromLines

    line = _line((0, 0), (30, 20), (60, 5))
    rectangles = PlotRectanglesFromLines([line], TEMPLATES).run()

    assert len(rectangles) == 1
    assert QgsGeometry.fromRect(rectangles[0]).contains(_line_geometry(line))


def test_single_point_and_empty_lines(plugin_qgis_new_project):
    from ...qgis.plot_rectangles_from_lines import PlotRectanglesFromLines

    point = QgsPointXY(10, 20)
    plot = PlotRectanglesFromLines([[], [point], []], TEMPLATES)
    rectangles = plot.run()

    assert len(rectangles) == 1
    assert plot.rectangle_line_indices == [1]
    assert rectangles[0].center() == point


def test_empty_list(plugin_qgis_new_project):
    from ...qgis.plot_rectangles_from_lines import PlotRectanglesFromLines

    assert PlotRectanglesFromLines([], TEMPLATES).run() == []


def test_no_run_in_init(plugin_qgis_new_project):
    from ...qgis.plot_rectangles_from_lines import PlotRectanglesFromLines

    plot = PlotRectanglesFromLines(TEST_LINES, TEMPLATES)

    assert plot.rectangles == []
    assert plot.rectangle_line_indices == []
    assert plot.rectangle_template_indices == []


def test_run_recalculates(plugin_qgis_new_project):
    from ...qgis.plot_rectangles_from_lines import PlotRectanglesFromLines

    plot = PlotRectanglesFromLines(TEST_LINES, [LANDSCAPE, PORTRAIT])
    first = [rectangle.toString() for rectangle in plot.run()]
    first_indices = list(plot.rectangle_line_indices)
    first_template_indices = list(plot.rectangle_template_indices)

    plot.run()

    assert [rectangle.toString() for rectangle in plot.rectangles] == first
    assert plot.rectangle_line_indices == first_indices
    assert plot.rectangle_template_indices == first_template_indices


def test_progress_signals(plugin_qgis_new_project):
    from ...qgis.plot_rectangles_from_lines import PlotRectanglesFromLines

    plot = PlotRectanglesFromLines(TEST_LINES, TEMPLATES)

    progress = []
    sub_progress = []
    plot.progressChanged.connect(lambda current, maximum, text: progress.append((current, maximum, text)))
    plot.subProgressChanged.connect(lambda current, maximum, text: sub_progress.append((current, maximum)))
    plot.run()

    assert progress == [(1, 1, "Berechne Rechtecke entlang der Linien")]
    assert sub_progress == [(i, len(TEST_LINES)) for i in range(len(TEST_LINES) + 1)]


@pytest.mark.parametrize('overlap', [-0.1, 0.95, 1.0])
def test_invalid_overlap(plugin_qgis_new_project, overlap):
    from ...qgis.plot_rectangles_from_lines import PlotRectanglesFromLines

    with pytest.raises(ValueError):
        PlotRectanglesFromLines([], TEMPLATES, overlap=overlap)


@pytest.mark.parametrize('templates', [[], [QgsRectangle(0, 0, 0, 10)], [PLOT_RECTANGLE, QgsRectangle(0, 0, 10, 0)]])
def test_invalid_templates(plugin_qgis_new_project, templates):
    from ...qgis.plot_rectangles_from_lines import PlotRectanglesFromLines

    with pytest.raises(ValueError):
        PlotRectanglesFromLines([], templates)


@pytest.mark.parametrize('line, expected_template_index', [
    (_line((0, 0), (1000, 0)), 0),
    (_line((0, 0), (0, 1000)), 1),
    (_line((0, 0), (1000, 100)), 0),
    (_line((0, 0), (100, 1000)), 1),
])
def test_best_template_for_line_direction(plugin_qgis_new_project, line, expected_template_index):
    from ...qgis.plot_rectangles_from_lines import PlotRectanglesFromLines

    plot = PlotRectanglesFromLines([line], [LANDSCAPE, PORTRAIT])
    rectangles = plot.run()

    # the last rectangle covers only the rest of the line, so both templates may fit there
    assert set(plot.rectangle_template_indices[:-1]) == {expected_template_index}
    assert _union(rectangles).contains(_line_geometry(line))


def test_template_order_is_irrelevant_for_long_sections(plugin_qgis_new_project):
    from ...qgis.plot_rectangles_from_lines import PlotRectanglesFromLines

    line = _line((0, 0), (0, 1000))
    plot = PlotRectanglesFromLines([line], [PORTRAIT, LANDSCAPE])
    plot.run()

    assert set(plot.rectangle_template_indices[:-1]) == {0}


def test_mixed_templates_along_line(plugin_qgis_new_project):
    from ...qgis.plot_rectangles_from_lines import PlotRectanglesFromLines

    # east, then north
    line = _line((0, 0), (1000, 0), (1000, 1000))
    plot = PlotRectanglesFromLines([line], [LANDSCAPE, PORTRAIT])
    rectangles = plot.run()

    indices = plot.rectangle_template_indices
    assert indices[0] == 0
    assert indices[-2] == 1
    assert _union(rectangles).contains(_line_geometry(line))
    for rectangle, template_index in zip(rectangles, indices):
        template = [LANDSCAPE, PORTRAIT][template_index]
        assert rectangle.width() == pytest.approx(template.width())
        assert rectangle.height() == pytest.approx(template.height())


def test_equal_coverage_uses_first_template(plugin_qgis_new_project):
    from ...qgis.plot_rectangles_from_lines import PlotRectanglesFromLines

    line = _line((0, 0), (10, 10))

    plot = PlotRectanglesFromLines([line], [PORTRAIT, LANDSCAPE])
    plot.run()
    assert plot.rectangle_template_indices == [0]

    plot = PlotRectanglesFromLines([line], [LANDSCAPE, PORTRAIT])
    plot.run()
    assert plot.rectangle_template_indices == [0]
