# -*- coding: utf-8 -*-
# SPDX-FileCopyrightText: 2026 Deutsche Telekom IT GmbH <sandro.kerner@telekom.de>
# SPDX-License-Identifier: GPL-3.0-only

from __future__ import annotations
from pathlib import Path

from qgis.core import (QgsPrintLayout, QgsLayoutItem, QgsLayoutItemScaleBar,
                       QgsLayoutItemMap, QgsLayoutItemPicture, QgsLayoutItemLabel,
                       QgsLayoutItemLegend, QgsLegendStyle, QgsRectangle,
                       QgsLayoutItemPolyline, QgsLayoutFrame, QgsTextFormat)

from typing import Dict, NamedTuple

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .plot_page_builder import PageBuilder


class CopyLayoutItemResult(NamedTuple):
    """ Return Type for CopyLayoutItem.
        :returns page index, page, item dictionary of items with element id
    """

    new_item: QgsLayoutItem
    linked_maps: Dict[QgsLayoutItem, QgsLayoutItemMap]


class CopyLayoutItem():
    """ Create the new page with the copied items from the layout template """

    def __init__(self, page_builder: PageBuilder):
        """" Copies items in a new Layout """
        self.__page_builder = page_builder

    def run(self, item: QgsLayoutItem, layout: QgsPrintLayout, linked_maps) -> CopyLayoutItemResult:
        """" Starts the copy process """
        new_item = type(item)(layout, None) if isinstance(item, QgsLayoutFrame) else type(item)(layout)

        layout.addLayoutItem(new_item)

        self.__copy_common_properties(item, new_item, linked_maps)

        if isinstance(new_item, QgsLayoutItemMap):
            self.__copy_map_properties(item, new_item)

        if isinstance(new_item, QgsLayoutItemPicture):
            self.__copy_picture_properties(item, new_item)

        if isinstance(new_item, QgsLayoutItemLabel):
            self.__copy_label_properties(item, new_item)

        if isinstance(new_item, QgsLayoutItemLegend):
            # exportLayerBehavior: not used
            self.__copy_legend_properties(item, new_item)

        if isinstance(new_item, QgsLayoutItemScaleBar):
            self.__copy_scale_bar_properties(item, new_item)

        if isinstance(new_item, QgsLayoutItemPolyline):
            self.__copy_polyline_properties(item, new_item)

        return CopyLayoutItemResult(new_item, linked_maps)

    def __copy_common_properties(self, source, new_item, linked_maps):
        # copy default options to new item
        if hasattr(source, 'textFormat'):
            # textFormat (old font) copy to new item
            new_item.setTextFormat(QgsTextFormat(source.textFormat()))
        elif hasattr(source, 'font'):
            # DEPRECATED IN QGIS 3.34
            # Font aufs neue Item übertragen
            new_item.setFont(source.font())

        # copy default options to new item
        if hasattr(source, 'linkedMap'):
            link = source.linkedMap()
            if link is not None:
                linked_maps[new_item] = link

        # take flags
        new_item.setFrameEnabled(source.frameEnabled())
        if new_item.frameEnabled():
            new_item.setFrameStrokeColor(source.frameStrokeColor())
            new_item.setFrameStrokeWidth(source.frameStrokeWidth())
        new_item.setBackgroundEnabled(source.hasBackground())
        if new_item.hasBackground():
            new_item.setBackgroundColor(source.backgroundColor())
        new_item.setItemRotation(source.itemRotation())
        new_item.setLocked(source.isLocked())
        new_item.setExcludeFromExports(source.excludeFromExports())

    def __copy_map_properties(self, source, new_item):
        """ Copy type specific options to new item """
        # exportLayerDetails: not used, because it can be different between project files
        # exportLayerBehavior: not used, because it can be different between project files
        # mapRotation: every time north
        # setAtlasDriven: every time False, no Atlas support
        # setDrawAnnotations: maybe overwritten
        # dpi: will be set later
        # scale: will be set later
        # setExtent: will be set later
        new_item.setFrameStrokeWidth(source.frameStrokeWidth())
        new_item.setMapRotation(0)

        # if not set (setExtent), map will not be valid (containing nan-values)
        size = new_item.sizeWithUnits()  # old/copied size
        new_item.attemptResize(size)  # MUST HAVE, bad QGIS! 1. attemptResize
        new_item.setRect(source.rect())  # MUST HAVE, bad QGIS! 2. setRect
        new_item.setExtent(QgsRectangle(0.1, 0.1, 0.2, 0.2))  # MUST HAVE, bad QGIS! 3. setExtent
        new_item.setCrs(self.__page_builder.plot_layer.get_crs())
        new_item.setScale(500, True)

    def __copy_picture_properties(self, source, new_item):
        """ setPicturePath: Use picture, if it is there """
        # setSvgFillColor: not used
        # setSvgStrokeColor: not used
        # setSvgStrokeWidth: not used
        new_item.setMode(source.mode())

        if source.linkedMap() is not None:
            new_item.setNorthMode(source.northMode())
            new_item.setNorthOffset(source.northOffset())
        else:
            new_item.setPictureRotation(source.pictureRotation())
            new_item.setPictureAnchor(source.pictureAnchor())

        new_item.setResizeMode(source.resizeMode())

        picture_path = source.picturePath()
        if Path(picture_path).is_file():
            new_item.setPicturePath(picture_path)

        # if an svg mode is set, apply the svg settings
        if new_item.mode() == QgsLayoutItemPicture.FormatSVG:
            new_item.setSvgDynamicParameters(source.svgDynamicParameters())
            new_item.setSvgFillColor(source.svgFillColor())
            new_item.setSvgStrokeColor(source.svgStrokeColor())
            new_item.setSvgStrokeWidth(source.svgStrokeWidth())

    def __copy_label_properties(self, source, new_item):
        new_item.setHAlign(source.hAlign())
        new_item.setVAlign(source.vAlign())
        new_item.setMarginX(source.marginX())
        new_item.setMarginY(source.marginY())
        new_item.setMode(source.mode())
        new_item.setText(source.text())

    def __copy_legend_properties(self, source, new_item):
        new_item.setLegendFilterByMapEnabled(source.legendFilterByMapEnabled())
        new_item.setLineSpacing(source.lineSpacing())
        new_item.setMaximumSymbolSize(source.maximumSymbolSize())
        new_item.setAutoUpdateModel(source.autoUpdateModel())
        new_item.setBoxSpace(source.boxSpace())
        new_item.setEqualColumnWidth(source.equalColumnWidth())
        new_item.setResizeToContents(source.resizeToContents())
        new_item.setSplitLayer(source.splitLayer())
        new_item.setSymbolAlignment(source.symbolAlignment())
        new_item.setSymbolHeight(source.symbolHeight())
        new_item.setSymbolWidth(source.symbolWidth())
        new_item.setTitle(source.title())
        new_item.setTitleAlignment(source.titleAlignment())
        new_item.setWmsLegendHeight(source.wmsLegendHeight())
        new_item.setWmsLegendWidth(source.wmsLegendWidth())
        new_item.setWrapString(source.wrapString())
        if source.drawRasterStroke():
            new_item.setDrawRasterStroke(True)
            new_item.setRasterStrokeColor(source.rasterStrokeColor())
            new_item.setRasterStrokeWidth(source.rasterStrokeWidth())

        # styles
        styles = [QgsLegendStyle.Title, QgsLegendStyle.Subgroup,
                    QgsLegendStyle.SymbolLabel, QgsLegendStyle.Symbol,
                    QgsLegendStyle.Group]
        for style in styles:
            new_item.setStyleFont(style, source.styleFont(style))
            new_item.setStyle(style, source.style(style))

    def __copy_scale_bar_properties(self, item, new_item):
        new_item.setAlignment(item.alignment())
        symbol = item.alternateFillSymbol().clone()  # without clone, Qgis crash (object ownership)!
        new_item.setAlternateFillSymbol(symbol)

        new_item.setBoxContentSpace(item.boxContentSpace())

        symbol = item.divisionLineSymbol().clone()  # without clone, Qgis crash (object ownership)!
        new_item.setDivisionLineSymbol(symbol)

        symbol = item.fillSymbol().clone()  # without clone, Qgis crash (object ownership)!
        new_item.setFillSymbol(symbol)

        new_item.setHeight(item.height())
        new_item.setLabelBarSpace(item.labelBarSpace())
        new_item.setLabelHorizontalPlacement(item.labelHorizontalPlacement())
        new_item.setLabelVerticalPlacement(item.labelVerticalPlacement())

        symbol = item.lineSymbol().clone()  # without clone, Qgis crash (object ownership)!
        new_item.setLineSymbol(symbol)

        new_item.setMapUnitsPerScaleBarUnit(item.mapUnitsPerScaleBarUnit())
        new_item.setSegmentSizeMode(item.segmentSizeMode())
        new_item.setMaximumBarWidth(item.maximumBarWidth())
        new_item.setMinimumBarWidth(item.minimumBarWidth())
        new_item.setStyle(item.style())

        symbol = item.subdivisionLineSymbol().clone()  # without clone, Qgis crash (object ownership)!
        new_item.setSubdivisionLineSymbol(symbol)

        new_item.setSubdivisionsHeight(item.subdivisionsHeight())
        new_item.setTextFormat(item.textFormat())
        new_item.setUnitLabel(item.unitLabel())
        new_item.setUnits(item.units())
        new_item.setUnitsPerSegment(item.unitsPerSegment())

    def __copy_polyline_properties(self, item, new_item):
        new_item.setArrowHeadFillColor(item.arrowHeadFillColor())
        new_item.setArrowHeadStrokeColor(item.arrowHeadStrokeColor())
        new_item.setArrowHeadStrokeWidth(item.arrowHeadStrokeWidth())
        new_item.setArrowHeadWidth(item.arrowHeadWidth())
        new_item.setEndSvgMarkerPath(item.endSvgMarkerPath())
        new_item.setStartSvgMarkerPath(item.startSvgMarkerPath())
        new_item.setEndMarker(item.endMarker())
        new_item.setStartMarker(item.startMarker())
        new_item.setMinimumSize(item.minimumSize())

        symbol = item.symbol().clone()
        new_item.setSymbol(symbol)

        new_item.refresh()
