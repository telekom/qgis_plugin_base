# -*- coding: utf-8 -*-
# SPDX-FileCopyrightText: 2025 Deutsche Telekom Technik GmbH <f.vonstudsinske@telekom.de>
# SPDX-License-Identifier: GPL-3.0-only

import pytest

from qgis.core import QgsVectorLayer, QgsField
from qgis.PyQt.QtCore import QVariant

from .fixtures import plugin_qgis_new_project


def test_get_field_errors_by_fields(plugin_qgis_new_project):

    from ..qgis.layer_utils import get_field_errors_by_fields

    test_layer = QgsVectorLayer("Point?crs=EPSG:25832", "test", "memory")
    test_layer.dataProvider().addAttributes([
        QgsField("field_a", QVariant.LongLong),
    ])

    # test, field must exists, no errors
    template = {
        "field_a": -1
    }
    assert not get_field_errors_by_fields(test_layer, template)

    # test, field must be String, errors
    template = {
        "field_a": QVariant.String
    }
    assert get_field_errors_by_fields(test_layer, template)

    # test, field must be Int, LongLong or Double, no errors
    template = {
        "field_a": [QVariant.Int, QVariant.LongLong, QVariant.Double]
    }
    assert not get_field_errors_by_fields(test_layer, template)

    # test, field must be String or Bool, errors
    template = {
        "field_a": [QVariant.String, QVariant.Bool]
    }
    assert get_field_errors_by_fields(test_layer, template)
