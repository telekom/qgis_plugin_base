# -*- coding: utf-8 -*-
# SPDX-FileCopyrightText: 2025 Deutsche Telekom Technik GmbH <f.vonstudsinske@telekom.de>
# SPDX-License-Identifier: GPL-3.0-only

import pytest

from qgis.core import QgsGeometry, QgsRectangle

from ..fixtures import plugin_qgis_new_project

PLOT_RECTANGLE = QgsRectangle(0, 0, 100, 50)

TEST_GEOMETRIES_WKT = [
    'Point (0 0)',
    'Point (10 10)',
    'Point (-500 300)',
    'MultiPoint ((1000 1000), (1010 1005), (5000 -2000))',
    'LineString (0 0, 30 20)',
    'LineString (0 0, 1000 0, 1000 800, 200 400)',
    'MultiLineString ((2000 2000, 2050 2010), (-300 -300, 400 900))',
    'Polygon ((10 10, 40 10, 40 30, 10 30, 10 10))',
    'Polygon ((0 0, 700 0, 700 600, 0 600, 0 0), (100 100, 200 100, 200 200, 100 200, 100 100))',
    'MultiPolygon (((3000 0, 3010 0, 3010 10, 3000 10, 3000 0)), ((4000 0, 4500 0, 4500 500, 4000 0)))',
]


def _union(rectangles):
    return QgsGeometry.unaryUnion([QgsGeometry.fromRect(rectangle) for rectangle in rectangles])


def _assert_all_contained(geometries, rectangles):
    assert rectangles
    union = _union(rectangles)
    for geometry in geometries:
        assert union.contains(geometry), f"not contained: {geometry.asWkt()}"


def _assert_rectangle_sizes(plot, templates):
    assert len(plot.rectangles) == len(plot.rectangle_template_indices)
    for rectangle, template_index in zip(plot.rectangles, plot.rectangle_template_indices):
        template = templates[template_index]
        assert rectangle.width() == pytest.approx(template.width())
        assert rectangle.height() == pytest.approx(template.height())


@pytest.mark.parametrize('overlap', [0.0, 0.075, 0.3, 0.9])
def test_all_geometries_contained(plugin_qgis_new_project, overlap):
    from ...qgis.plot_rectangles_from_geometries import PlotRectanglesFromGeometries

    geometries = [QgsGeometry.fromWkt(wkt) for wkt in TEST_GEOMETRIES_WKT]
    templates = [PLOT_RECTANGLE]
    plot = PlotRectanglesFromGeometries(geometries, templates, overlap=overlap)
    plot.run()

    assert not plot.positions
    _assert_rectangle_sizes(plot, templates)
    _assert_all_contained(geometries, plot.rectangles)


@pytest.mark.parametrize('wkt', TEST_GEOMETRIES_WKT)
def test_single_geometry_contained(plugin_qgis_new_project, wkt):
    from ...qgis.plot_rectangles_from_geometries import PlotRectanglesFromGeometries

    geometry = QgsGeometry.fromWkt(wkt)
    templates = [PLOT_RECTANGLE]
    plot = PlotRectanglesFromGeometries([geometry], templates)
    plot.run()

    _assert_rectangle_sizes(plot, templates)
    _assert_all_contained([geometry], plot.rectangles)


def test_small_geometry_in_one_rectangle(plugin_qgis_new_project):
    from ...qgis.plot_rectangles_from_geometries import PlotRectanglesFromGeometries

    geometry = QgsGeometry.fromWkt('LineString (0 0, 30 20, 60 5)')
    rectangles = PlotRectanglesFromGeometries([geometry], [PLOT_RECTANGLE]).run()

    assert len(rectangles) == 1
    assert QgsGeometry.fromRect(rectangles[0]).contains(geometry)


def test_nearby_geometries_share_rectangle(plugin_qgis_new_project):
    from ...qgis.plot_rectangles_from_geometries import PlotRectanglesFromGeometries

    geometries = [QgsGeometry.fromWkt('Point (0 0)'),
                  QgsGeometry.fromWkt('Point (20 10)'),
                  QgsGeometry.fromWkt('Polygon ((30 5, 40 5, 40 15, 30 5))')]
    rectangles = PlotRectanglesFromGeometries(geometries, [PLOT_RECTANGLE]).run()

    assert len(rectangles) == 1
    _assert_all_contained(geometries, rectangles)


def test_distant_points_get_own_rectangles(plugin_qgis_new_project):
    from ...qgis.plot_rectangles_from_geometries import PlotRectanglesFromGeometries

    geometries = [QgsGeometry.fromWkt('Point (0 0)'),
                  QgsGeometry.fromWkt('Point (1000 0)'),
                  QgsGeometry.fromWkt('Point (0 1000)')]
    rectangles = PlotRectanglesFromGeometries(geometries, [PLOT_RECTANGLE]).run()

    assert len(rectangles) == 3
    for geometry in geometries:
        assert any(QgsGeometry.fromRect(rectangle).contains(geometry) for rectangle in rectangles)


def test_ignores_null_empty_and_invalid_geometries(plugin_qgis_new_project):
    from ...qgis.plot_rectangles_from_geometries import PlotRectanglesFromGeometries

    geometries = [QgsGeometry(),
                  QgsGeometry.fromWkt('Point EMPTY'),
                  QgsGeometry.fromWkt('Polygon ((0 0, 10 10, 10 0, 0 10, 0 0))')]

    assert PlotRectanglesFromGeometries(geometries, [PLOT_RECTANGLE]).run() == []


def test_empty_list(plugin_qgis_new_project):
    from ...qgis.plot_rectangles_from_geometries import PlotRectanglesFromGeometries

    assert PlotRectanglesFromGeometries([], [PLOT_RECTANGLE]).run() == []


def test_no_run_in_init(plugin_qgis_new_project):
    from ...qgis.plot_rectangles_from_geometries import PlotRectanglesFromGeometries

    geometries = [QgsGeometry.fromWkt(wkt) for wkt in TEST_GEOMETRIES_WKT]
    plot = PlotRectanglesFromGeometries(geometries, [PLOT_RECTANGLE])

    assert plot.positions == []
    assert plot.rectangles == []


def test_progress_signals(plugin_qgis_new_project):
    from ...qgis.plot_rectangles_from_geometries import PlotRectanglesFromGeometries

    geometries = [QgsGeometry.fromWkt(wkt) for wkt in TEST_GEOMETRIES_WKT]
    plot = PlotRectanglesFromGeometries(geometries, [PLOT_RECTANGLE])

    progress = []
    sub_progress = []
    plot.progressChanged.connect(lambda current, maximum, text: progress.append((current, maximum, text)))
    plot.subProgressChanged.connect(lambda current, maximum, text: sub_progress.append((current, maximum)))
    plot.run()

    assert progress == [(1, 2, "Vorbereitung der Geometrien"), (2, 2, "Berechne Rechtecke")]
    assert sub_progress
    assert all(0 <= current <= maximum for current, maximum in sub_progress)
    assert sub_progress[-1][0] == sub_progress[-1][1]


def test_run_recalculates(plugin_qgis_new_project):
    from ...qgis.plot_rectangles_from_geometries import PlotRectanglesFromGeometries

    geometries = [QgsGeometry.fromWkt(wkt) for wkt in TEST_GEOMETRIES_WKT]
    plot = PlotRectanglesFromGeometries(geometries, [PLOT_RECTANGLE])
    first = [rectangle.toString() for rectangle in plot.run()]

    plot.run()

    assert [rectangle.toString() for rectangle in plot.rectangles] == first


@pytest.mark.parametrize('overlap', [-0.1, 0.95, 1.0])
def test_invalid_overlap(plugin_qgis_new_project, overlap):
    from ...qgis.plot_rectangles_from_geometries import PlotRectanglesFromGeometries

    with pytest.raises(ValueError):
        PlotRectanglesFromGeometries([], [PLOT_RECTANGLE], overlap=overlap)


def test_invalid_rectangle(plugin_qgis_new_project):
    from ...qgis.plot_rectangles_from_geometries import PlotRectanglesFromGeometries

    with pytest.raises(ValueError):
        PlotRectanglesFromGeometries([], [QgsRectangle(0, 0, 0, 10)])


def test_empty_templates(plugin_qgis_new_project):
    from ...qgis.plot_rectangles_from_geometries import PlotRectanglesFromGeometries

    with pytest.raises(ValueError):
        PlotRectanglesFromGeometries([], [])


@pytest.mark.parametrize('points, expected_template_index', [
    ([(0, 0), (30, 0), (60, 0), (90, 0)], 0),
    ([(0, 0), (0, 30), (0, 60), (0, 90)], 1),
])
def test_selects_template_covering_most_positions(plugin_qgis_new_project, points, expected_template_index):
    from ...qgis.plot_rectangles_from_geometries import PlotRectanglesFromGeometries

    templates = [QgsRectangle(0, 0, 100, 50), QgsRectangle(0, 0, 50, 100)]
    geometries = [QgsGeometry.fromWkt(f'Point ({x} {y})') for x, y in points]
    plot = PlotRectanglesFromGeometries(geometries, templates)
    plot.run()

    assert plot.rectangle_template_indices[0] == expected_template_index
    _assert_rectangle_sizes(plot, templates)
    _assert_all_contained(geometries, plot.rectangles)


def test_equal_coverage_uses_first_template(plugin_qgis_new_project):
    from ...qgis.plot_rectangles_from_geometries import PlotRectanglesFromGeometries

    templates = [QgsRectangle(0, 0, 100, 50), QgsRectangle(0, 0, 50, 100)]
    geometry = QgsGeometry.fromWkt('Point (10 10)')
    plot = PlotRectanglesFromGeometries([geometry], templates)
    plot.run()

    assert plot.rectangle_template_indices == [0]
    _assert_rectangle_sizes(plot, templates)
