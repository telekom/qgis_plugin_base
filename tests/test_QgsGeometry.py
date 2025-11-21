# -*- coding: utf-8 -*-
# SPDX-FileCopyrightText: 2025 Deutsche Telekom Technik GmbH <f.vonstudsinske@telekom.de>
# SPDX-License-Identifier: GPL-3.0-or-later

import pytest

from qgis.core import QgsGeometry


@pytest.mark.parametrize("wkt_geometry,wkt_geometry_to_touch",
                         [
                             (
                                 'Point (816381.9444280075840652 6826932.21430961228907108)',
                                 'LineString (816381.9444280075840652 6826932.21430961228907108, 816383.42208930104970932 6826932.57374073844403028)'
                             ),
                         ])
def test_touches(wkt_geometry: str, wkt_geometry_to_touch: str):
    geometry = QgsGeometry.fromWkt(wkt_geometry)
    assert geometry.isGeosValid()

    geometry_to_touch = QgsGeometry.fromWkt(wkt_geometry_to_touch)
    assert geometry_to_touch.isGeosValid()

    assert geometry.touches(geometry_to_touch)
