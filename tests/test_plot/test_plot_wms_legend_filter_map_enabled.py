# -*- coding: utf-8 -*-
# SPDX-FileCopyrightText: 2025 Deutsche Telekom Technik GmbH <f.vonstudsinske@telekom.de>
# SPDX-License-Identifier: GPL-3.0-only

import tempfile
from pathlib import Path

from qgis.core import (QgsRasterLayer,
                       QgsLayoutItemLegend, QgsLayoutItemMap, QgsPrintLayout,
                       QgsProject, QgsLayoutPoint, QgsUnitTypes, QgsLayoutSize, QgsLayoutExporter,
                       QgsRectangle, QgsLegendStyle, QgsLayoutRenderContext, QgsLayoutUtils, Qgis)
from qgis.PyQt.QtGui import QColor, QFont

from ..fixtures import plugin_qgis_new_project
from ..markers import skipif_no_qgis_app


@skipif_no_qgis_app
def test_plot_with_legend_and_filter_by_map_enabled(plugin_qgis_new_project):

    # example from https://docs.qgis.org/3.34/en/docs/pyqgis_developer_cookbook/composer.html#output-using-print-layout

    # create the layout
    project = QgsProject.instance()
    layout = QgsPrintLayout(project)
    layout.initializeDefaults()

    # get the test layer and add it to the project
    layer = QgsRasterLayer("IgnoreGetFeatureInfoUrl=1&IgnoreGetMapUrl=1&contextualWMSLegend=0&crs=EPSG:3857&dpiMode=7&featureCount=10&format=image/png&layers=Strasse:Strassennetz&styles=&url=http://www.nwsib-online.nrw.de/GCGisService", "Straßennetz", "wms")
    assert layer.isValid()
    project.addMapLayer(layer)

    # add the map item
    map_item = QgsLayoutItemMap(layout)
    map_item.setCrs(layer.crs())
    # Set map item position and size (by default, it is a 0 width/0 height item placed at 0,0)
    map_item.attemptMove(QgsLayoutPoint(5, 5, QgsUnitTypes.LayoutMillimeters), page=0)
    map_item.attemptResize(QgsLayoutSize(200, 200, QgsUnitTypes.LayoutMillimeters))
    # Provide an extent to render
    map_item.zoomToExtent(QgsRectangle(753295, 6702871, 759034, 6706505))
    map_item.setLayers([layer])
    map_item.setKeepLayerSet(True)
    map_item.setKeepLayerStyles(True)
    map_item.setDrawAnnotations(True)
    map_item.setFrameEnabled(True)
    layout.addLayoutItem(map_item)

    # add the legend item
    legend_item = QgsLayoutItemLegend(layout)
    legend_item.setTitle("Legende")
    legend_item.setAutoUpdateModel(False)
    legend_item.setColumnCount(6)
    legend_item.setLegendFilterByMapEnabled(True)
    legend_item.setLinkedMap(None)  # map is an instance of QgsLayoutItemMap
    legend_item.setFilterByMapItems([map_item])

    legend_item.setStyleFont(QgsLegendStyle.Title, QFont('Arial', 12))
    legend_item.setStyleFont(QgsLegendStyle.Subgroup, QFont('Arial', 8))
    legend_item.setStyleFont(QgsLegendStyle.SymbolLabel, QFont('Arial', 8))
    legend_item.setBackgroundColor(QColor(255, 255, 255, 30))

    layout.addLayoutItem(legend_item)

    exporter = QgsLayoutExporter(layout)

    export_settings = QgsLayoutExporter.PdfExportSettings()
    export_settings.dpi = 300

    # apply the default flags from the current render context first
    export_settings.flags = layout.renderContext().flags()

    # apply settings to the PDFExportSettings
    export_settings.forceVectorOutput = False
    export_settings.appendGeoreference = False
    export_settings.exportMetadata = False
    # ui settings "Text exports"
    # > Always Export Text as Paths (Recommended): Qgis.TextRenderFormat.AlwaysOutlines
    # > Always Export Text as Text Objects: Qgis.TextRenderFormat.AlwaysText
    export_settings.textRenderFormat = Qgis.TextRenderFormat.AlwaysOutlines  # or Qgis.TextRenderFormat.AlwaysText
    export_settings.simplifyGeometries = True
    export_settings.writeGeoPdf = False
    export_settings.useOgcBestPracticeFormatGeoreferencing = True  # depends on writeGeoPDF=True
    export_settings.useIso32000ExtensionFormatGeoreferencing = False  # depends on writeGeoPDF=True
    export_settings.exportThemes = []  # list of map theme names; depends on writeGeoPDF=True
    export_settings.predefinedMapScales = QgsLayoutUtils.predefinedScales(layout)
    export_settings.rasterizeWholeImage = False

    # add the flag to for lossless Image
    # > ui setting: "Image compression"
    # settings.flags = settings.flags | QgsLayoutRenderContext.FlagLosslessImageRendering
    # remove the lossless tag
    export_settings.flags = export_settings.flags ^ QgsLayoutRenderContext.FlagLosslessImageRendering

    # add the flag to disable the tiled rasters
    # > in the exporter settings ui: checkbox checked "Disable tiled raster layer exports"
    # settings.flags = settings.flags | QgsLayoutRenderContext.FlagDisableTiledRasterLayerRenders
    # remove the flag
    export_settings.flags = export_settings.flags ^ QgsLayoutRenderContext.FlagDisableTiledRasterLayerRenders

    root_dir = Path(__file__).parent
    with tempfile.TemporaryDirectory(prefix=".test-results", dir=root_dir, delete=False) as tempdir:
        pdf_path = tempdir + "/plot_with_legend_and_filter_by_map_enabled.pdf"
        exporter.exportToPdf(pdf_path, export_settings)

