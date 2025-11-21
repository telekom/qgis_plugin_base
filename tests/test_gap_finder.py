# -*- coding: utf-8 -*-
# SPDX-FileCopyrightText: 2025 Deutsche Telekom Technik GmbH <f.vonstudsinske@telekom.de>
# SPDX-License-Identifier: GPL-3.0-or-later

import pytest

from qgis.core import QgsVectorLayer, QgsFeature, QgsGeometry

from .fixtures import plugin_qgis_new_project


def __get_new_feature(wkt: str):
    feature = QgsFeature()
    feature.setGeometry(QgsGeometry.fromWkt(wkt))
    return feature


def test_gap_finder_wkt_equal(plugin_qgis_new_project):
    from ..qgis.gap_finder import GapFinder, CheckTypes

    # create test data first (layer in meter units)
    layer = QgsVectorLayer("LineString?crs=epsg:25832", "test", "memory")

    # geometries PointWktEquals
    #   Außerste Genauigkeit gefragt:
    #       787995.25384134985506535 5672519.0972892539575696
    #       787995.25384137232322246 5672519.09728925488889217
    #       distance=2.2487450850961194e-08
    geometry_wkt = ('LineString (787963.07026331056840718 5672521.16033982764929533, '
                    '787995.25384134985506535 5672519.0972892539575696)')
    assert layer.dataProvider().addFeature(__get_new_feature(geometry_wkt))
    geometry_wkt = ('LineString (787995.25384137232322246 5672519.09728925488889217, '
                    '787993.94465674983803183 5672497.45677325036376715)')
    assert layer.dataProvider().addFeature(__get_new_feature(geometry_wkt))
    point_wkt_equal_1 = QgsGeometry.fromWkt('Point (787995.25384134985506535 5672519.0972892539575696)').asPoint()
    point_wkt_equal_2 = QgsGeometry.fromWkt('Point (787995.25384137232322246 5672519.09728925488889217)').asPoint()

    gap_finder = GapFinder(layer,
                           modes=[CheckTypes.PointWktEquals],
                           distance=0.01)
    gap_finder.run()

    # test point_check_wkt_equal
    for point, type_, detail in gap_finder.points:
        if (type_ == CheckTypes.PointWktEquals and (
                point.compare(point_wkt_equal_2) or point.compare(point_wkt_equal_1))):
            # OK :)
            break
    else:
        raise AssertionError(f"check for point_check_wkt_equal failed")


def test_gap_finder_on_segment(plugin_qgis_new_project):
    from ..qgis.gap_finder import GapFinder, CheckTypes

    # create test data first (layer in meter units)
    layer = QgsVectorLayer("LineString?crs=epsg:25832", "test", "memory")

    # OnSegmentSnapped
    geometry_wkt = ('LineString (787963.07026331056840718 5672521.16033982764929533, '
                    '788025.21742945967707783 5672517.17654712498188019)')
    assert layer.dataProvider().addFeature(__get_new_feature(geometry_wkt))
    geometry_wkt = ('LineString (787995.25367830821778625 5672519.09090990759432316, '
                    '787993.94465674983803183 5672497.45677325036376715)')
    assert layer.dataProvider().addFeature(__get_new_feature(geometry_wkt))
    point_on_segment = QgsGeometry.fromWkt('Point (787995.25367830821778625 5672519.09090990759432316)').asPoint()

    gap_finder = GapFinder(layer,
                           modes=[CheckTypes.OnSegmentSnapped],
                           distance=0.01)
    gap_finder.run()

    # test point_on_segment
    for point, type_, detail in gap_finder.points:
        if type_ == CheckTypes.OnSegmentSnapped and point.compare(point_on_segment):
            # OK :)
            break
    else:
        raise AssertionError(f"check for point_on_segment failed")


def test_gap_finder_overlapping(plugin_qgis_new_project):

    from ..qgis.gap_finder import GapFinder, CheckTypes

    # create test data first (layer in meter units)
    layer = QgsVectorLayer("LineString?crs=epsg:25832", "test", "memory")

    # OverlappingParts
    geometry_wkt = ('LineString (752586.0 5904064.0, '
                    '752590.0 5904100.0, '
                    '752600.0 5904150.0, '
                    '752600.0 5904063.0)')
    assert layer.dataProvider().addFeature(__get_new_feature(geometry_wkt))
    geometry_wkt = ('LineString (752593.0 5904067.0, '
                    '752590.0 5904100.0, '
                    '752600.0 5904150.0, '
                    '752594.0 5904061.0)')
    assert layer.dataProvider().addFeature(__get_new_feature(geometry_wkt))
    point_overlapping_1 = QgsGeometry.fromWkt('Point (752590.0 5904100.0)').asPoint()
    point_overlapping_2 = QgsGeometry.fromWkt('Point (752600.0 5904150.0)').asPoint()

    gap_finder = GapFinder(layer,
                           modes=[CheckTypes.OverlappingParts],
                           distance=0.01)
    gap_finder.run()

    # test overlapping 1
    for point, _ in gap_finder.overlapping_points:
        if point.compare(point_overlapping_1):
            # OK :)
            break
    else:
        raise AssertionError(f"check for point_overlapping_1 failed")

    # test overlapping 2
    for point, _ in gap_finder.overlapping_points:
        if point.compare(point_overlapping_2):
            # OK :)
            break
    else:
        raise AssertionError(f"check for point_overlapping_2 failed")
