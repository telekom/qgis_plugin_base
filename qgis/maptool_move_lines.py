# -*- coding: utf-8 -*-
# SPDX-FileCopyrightText: 2025 Deutsche Telekom Technik GmbH <f.vonstudsinske@telekom.de>
# SPDX-License-Identifier: GPL-3.0-or-later

import traceback

from qgis.core import QgsPointXY, QgsGeometry, QgsWkbTypes
from qgis.PyQt.QtCore import pyqtSignal

from typing import List


from .maptool_digitize_geometry import MapToolDigitizeFeature
from .transform_poly_line import TransformPolyline
from .geometry import get_polyline
from ..constants import TO_STRING_PREC


class MapToolMoveLinesV2(MapToolDigitizeFeature):
    """ Creates a map tool for line remodeling and activates it.
        Uses the default QGIS Maptool to draw a line including current snapping settings
        in the current QGIS project.

        .. code-block:: python

            # get layers
            line_layer = ...
            point_layer = ...

            # create map tool object
            tool = MapToolMoveLinesV2.start_from_layer(line_layer, iface,
                                                       previous_layer_id=line_layer.id(),
                                                       other_layers=[point_layer],
                                                       commit=False,
                                                       allow_multi_line_type=True)
            tool.drawingFinished.connect(tool.transform_lines)

        :param **other_layers: List of line and point layers to keep ratio on connected lines/points.
        :param **commit: Auto-Commit changes after remodelling. Defaults to False (no commit)
        :param **allow_multi_line_type: True to allow line vector layer from type MultiLineString.
                                        Still expecting only 1 geometry part).
                                        Defaults to False.

    """
    exceptionRaised = pyqtSignal(tuple, name="exceptionRaised")
    success = pyqtSignal()

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        allow_multi_line_type = kwargs.get("allow_multi_line_type", False)

        if not allow_multi_line_type and self.layer().wkbType() == QgsWkbTypes.MultiLineString:
            raise ValueError(f"{self.layer().id} is from type MultiLineString, but not allowed/forced")

        # get layers from kwargs
        self.other_layers = kwargs.get("other_layers", [])
        self.commit = kwargs.get("commit", False)

    def transform_lines(self, geometry: QgsGeometry):
        poly_line: List[QgsPointXY] = get_polyline(geometry)

        try:
            TransformPolyline.from_new_poly_line(poly_line,
                                                 main_layer=self.origin_layer,
                                                 other_layers=self.other_layers,
                                                 commit=self.commit)
            self.success.emit()
        except Exception as e:
            tb = str(traceback.format_exc())
            tb += "\n\n Used poly_line in transform_lines: " \
                  f"{QgsGeometry.fromPolylineXY(poly_line).asWkt(TO_STRING_PREC)}"
            self.exceptionRaised.emit((str(e), tb))

            # roll back changes
            for layer in self.other_layers + [self.origin_layer]:
                layer.rollBack()

