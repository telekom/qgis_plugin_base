# -*- coding: utf-8 -*-
# SPDX-FileCopyrightText: 2025 Deutsche Telekom Technik GmbH <f.vonstudsinske@telekom.de>
# SPDX-License-Identifier: GPL-3.0-only

import os
import tempfile

from pathlib import Path

from qgis.core import (QgsProject, QgsLayoutExporter,
                       QgsLayoutRenderContext, QgsLayoutUtils, Qgis)


project = QgsProject.instance()

layout_to_export = "plot nrw.gpkg"

layout = None
manager = project.layoutManager()
for l in manager.printLayouts():
    if l.name() == layout_to_export:
        layout = l



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
    pdf_path = tempdir + "/export.pdf"
    exporter.exportToPdf(pdf_path, export_settings)
project.clear()
print("done")