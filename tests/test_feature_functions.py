# -*- coding: utf-8 -*-
# SPDX-FileCopyrightText: 2025 Deutsche Telekom Technik GmbH <f.vonstudsinske@telekom.de>
# SPDX-License-Identifier: GPL-3.0-or-later

import pytest

from qgis.core import QgsGeometry, QgsFeature, QgsVectorLayer

from ..qgis.layer_features import get_touching_features


def test_get_touching_features():

    # create the test layer with a simple line
    layer = QgsVectorLayer("LineString?crs=epsg:3857", "test", "memory")
    feature = QgsFeature(layer.fields())
    feature.setGeometry(QgsGeometry.fromWkt('LineString (816381.9444280075840652 6826932.21430961228907108, 816383.42208930104970932 6826932.57374073844403028)'))
    assert layer.dataProvider().addFeature(feature)

    # create the point geometry to check
    point_geometry = QgsGeometry.fromWkt('Point (816381.9444280075840652 6826932.21430961228907108)')

    # get the touching features
    assert get_touching_features(point_geometry, layer)
