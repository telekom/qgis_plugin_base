# -*- coding: utf-8 -*-
# SPDX-FileCopyrightText: 2025 Deutsche Telekom Technik GmbH <f.vonstudsinske@telekom.de>
# SPDX-License-Identifier: GPL-3.0-or-later

import tempfile
import pytest
from pathlib import Path

from qgis.core import (QgsGeometry, QgsProject,
                       QgsFeature, QgsVectorLayer, QgsVectorFileWriter,
                       QgsCoordinateTransform)

from ..fixtures import qgis_activate_internet_proxy, plugin_qgis_new_project
from ...qgis.plot_layout_templates import PlotLayoutTemplates
from ...qgis.plot_layer import PlotLayerMemory
from ...qgis.plot import PrintLayout

# Münster, Schlosspark, EPSG:3857
WKT_STAR = 'Polygon ((846688.23712304513901472 6793603.60052668862044811, 846953.10358861752320081 6793768.75255816336721182, 847024.77333812532015145 6793980.64573062118142843, 847236.66651058325078338 6793806.14547094982117414, 847498.41690009005833417 6793787.44901455659419298, 847445.44360697560478002 6793282.64469193667173386, 847208.621825993177481 6793320.03760472312569618, 846999.84472960082348436 6793186.04633390437811613, 846912.59459976525977254 6793419.75203882064670324, 846688.23712304513901472 6793603.60052668862044811))'


def test_plot_pdf(plugin_qgis_new_project, qgis_activate_internet_proxy):

    # load the basic template from the "test_plot" folder
    templates = PlotLayoutTemplates()
    templates.plots.append(Path(__file__).parent / "public1")
    templates.load_plots()
    templates.load_layouts()

    # check, if every layout has been loaded
    layout = templates["public1/A3_Landscape.qpt"]

    # create a temporary polygon layer
    polygon_layer = QgsVectorLayer("Polygon?crs=epsg:3857", "star", "memory")
    feature = QgsFeature()
    feature.setGeometry(QgsGeometry.fromWkt(WKT_STAR))
    polygon_layer.dataProvider().addFeature(feature)
    QgsProject.instance().addMapLayer(polygon_layer)
    assert polygon_layer.isValid()

    # create plot layer for plotting
    plot_layer = PlotLayerMemory.create_new(polygon_layer.crs(), "OSM test_plot_pdf")
    plot_layer.create_overview_page = False
    plot_layer.legend_on_extra_page = False

    # sets "HAMSTER" in Export-PDF
    options = plot_layer.options
    options["item_page_text_plot_title"] = ["HAMSTER", False]
    plot_layer.options = options
    plot_layer.file = layout.path

    # get scale for overview plan for line features
    extent_ = polygon_layer.extent()
    layout.item_map.setCrs(polygon_layer.crs())
    layout.item_map.zoomToExtent(extent_)
    layout.item_map.setScale(10000)

    # add main page for overview plan
    page_geometry_1 = QgsGeometry.fromRect(layout.item_map.extent())
    page = plot_layer.add_page(layout, page_geometry_1, layout.item_map.scale())

    print_ = PrintLayout(plot_layer, templates)
    print_.progressChanged.connect(print)
    print_.init()

    with tempfile.TemporaryDirectory(prefix=".test-results", dir=Path(__file__).parent, delete=False) as tempdir:
        pdf_file = Path(tempdir) / "test_plot.pdf"
        gpkg_file = str(Path(tempdir) / "plot.gpkg")

        result = print_.create_pdf(str(pdf_file))
        assert result == ""

        # save the plot layer to a gpkg
        for layer in [plot_layer.layer_options, plot_layer.layer_pages]:
            options = QgsVectorFileWriter.SaveVectorOptions()
            options.layerName = layer.name()

            if Path(gpkg_file).is_file():
                # important, if gpkg already exists
                options.actionOnExistingFile = QgsVectorFileWriter.CreateOrOverwriteLayer

            # transform
            transform_params = QgsCoordinateTransform(
                layer.crs(),
                layer.crs(),
                QgsProject.instance())
            options.ct = transform_params

            QgsVectorFileWriter.writeAsVectorFormatV3(
                layer,
                gpkg_file,
                QgsProject.instance().transformContext(),
                options
            )

def test_load_templates(plugin_qgis_new_project):

    # load the basic template from the "test_plot" folder
    templates = PlotLayoutTemplates()
    templates.plots.append(Path(__file__).parent / "public0")
    templates.plots.append(Path(__file__).parent / "public1")
    templates.load_plots()
    templates.load_layouts()

    # check, if every layout has been loaded
    layout = templates["public0/A3_Landscape_1.qpt"]
    layout_0_2 = templates["public0/A3_Landscape_2.qpt"]
    layout_1 = templates["public1/A3_Landscape.qpt"]
