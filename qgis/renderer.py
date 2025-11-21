# -*- coding: utf-8 -*-
# SPDX-FileCopyrightText: 2025 Deutsche Telekom Technik GmbH <f.vonstudsinske@telekom.de>
# SPDX-License-Identifier: GPL-3.0-or-later

from qgis.core import (QgsVectorLayer, QgsCategorizedSymbolRenderer, QgsSymbol,
                       QgsWkbTypes, QgsRandomColorRamp, QgsRendererCategory,
                       Qgis)


def create_simple_categorized_renderer(layer: QgsVectorLayer, name: str, attribute: str,
                                       label_expression=None) -> QgsCategorizedSymbolRenderer:
    """ Creates a new renderer object.

        :param layer:
        :param name:
        :param attribute:
        :param label_expression: callable to create

    """
    # create renderer
    renderer = QgsCategorizedSymbolRenderer(name)

    # create default symbol
    symbol = QgsSymbol.defaultSymbol(QgsWkbTypes.LineGeometry)
    color = symbol.color()
    color.setAlpha(150)
    symbol.setColor(color)
    symbol.setOpacity(0.30)

    # apply default symbol to renderer
    renderer.setSourceSymbol(symbol)

    # color ramp
    ramp = QgsRandomColorRamp()
    ramp.setTotalColorCount(layer.featureCount() * 2)
    renderer.setSourceColorRamp(ramp)

    for i, feature in enumerate(layer.getFeatures()):
        # calculates new line symbol with new color
        nf_symbol = QgsSymbol.defaultSymbol(QgsWkbTypes.LineGeometry)
        nf_symbol.setColor(ramp.color(i + 1))

        # creating new rule node
        if label_expression:
            label = label_expression(feature)
        else:
            label = feature[attribute]

        # add category
        cat = QgsRendererCategory(feature[attribute], nf_symbol, label, True)
        cat.setLabel(label)
        renderer.addCategory(cat)

    return renderer


def create_categorized_line_renderer_from_unique_values(layer: QgsVectorLayer, attribute: str) -> QgsCategorizedSymbolRenderer:
    """ Creates a new categorized render from the unique values.

        :param layer: Vector layer
        :param attribute: feature attribute to render with

    """
    # create renderer
    renderer = QgsCategorizedSymbolRenderer(attribute)

    # create default symbol
    symbol = QgsSymbol.defaultSymbol(QgsWkbTypes.LineGeometry)
    color = symbol.color()
    color.setAlpha(150)
    symbol.setColor(color)
    symbol.setWidthUnit(Qgis.RenderUnit.Millimeters)
    symbol.setWidth(1.0)

    # apply default symbol to renderer
    renderer.setSourceSymbol(symbol)

    # color ramp
    ramp = QgsRandomColorRamp()
    ramp.setTotalColorCount(layer.featureCount() * 2)
    renderer.setSourceColorRamp(ramp)

    unique_values = layer.uniqueValues(layer.fields().indexFromName(attribute))

    for i, value in enumerate(unique_values):
        # calculates new line symbol with new color
        nf_symbol = symbol.clone()
        nf_symbol.setColor(ramp.color(i + 1))

        # add category
        cat = QgsRendererCategory(value, nf_symbol, str(value), True)
        cat.setLabel(str(value))
        renderer.addCategory(cat)

    return renderer


def create_categorized_point_renderer_from_unique_values(layer: QgsVectorLayer, attribute: str) -> QgsCategorizedSymbolRenderer:
    """ Creates a new categorized render from the unique values.

        :param layer: Vector layer
        :param attribute: feature attribute to render with

    """
    # create renderer
    renderer = QgsCategorizedSymbolRenderer(attribute)

    # create default symbol
    symbol = QgsSymbol.defaultSymbol(QgsWkbTypes.PointGeometry)
    color = symbol.color()
    color.setAlpha(150)
    symbol.setColor(color)
    symbol.setSizeUnit(Qgis.RenderUnit.Millimeters)
    symbol.setSize(3.0)

    # apply default symbol to renderer
    renderer.setSourceSymbol(symbol)

    # color ramp
    ramp = QgsRandomColorRamp()
    ramp.setTotalColorCount(layer.featureCount() * 2)
    renderer.setSourceColorRamp(ramp)

    unique_values = layer.uniqueValues(layer.fields().indexFromName(attribute))

    for i, value in enumerate(unique_values):
        # calculates new line symbol with new color
        nf_symbol = symbol.clone()
        nf_symbol.setColor(ramp.color(i + 1))
        # add category
        cat = QgsRendererCategory(value, nf_symbol, str(value), True)
        cat.setLabel(str(value))
        renderer.addCategory(cat)

    return renderer
