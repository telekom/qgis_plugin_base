<!--
SPDX-FileCopyrightText: 2025 Deutsche Telekom Technik GmbH <f.vonstudsinske@telekom.de>

SPDX-License-Identifier: GPL-3.0-only
-->

# Code Example (run from QGIS console)

Code example from plot plugin

```python
# import qgis stuff
import qgis.utils

from qgis.core import (QgsCoordinateReferenceSystem, QgsGeometry,
                       QgsRectangle, QgsProject)

# import needed plot modules/classes
from <plugin>.submodules.base.qgis.plot_layout_templates import PlotLayoutTemplates
from <plugin>.submodules.base.qgis.plot_layout import PlotLayout
from <plugin>.submodules.base.qgis.plot_layer import PlotLayerMemory
from <plugin>.submodules.base.qgis.plot import PrintLayout


# get module object from loaded qgis plugins
plugin = qgis.utils.plugins["plot"]

# load templates module
templates = plugin.add_module("PlotLayoutTemplates", PlotLayoutTemplates)
# add path to templates-folder, where to find individual qpt-templates
templates.plots.append(r"a/b/c")
# load plot templates into layout paths
templates.load_plots()
# cache qpt-template (all layout elements will be cached), possible long loading here
templates.load_layouts()

# get template names
name_portrait = "<folder>/<name>.qpt"
name_landscape = "<folder>/<name>.qpt"
layout = templates[name_portrait]

# create a memory instance from plot class
# no GPKG will be created here
# not loadable to Plot Plugin Menu
plot_layer = PlotLayerMemory.create_new(QgsCoordinateReferenceSystem("EPSG:3857"), "test memory")
plot_layer.file = layout.path

# create a landscape and portrait page geometries
page_geometry_1 = QgsGeometry.fromWkt('Polygon ((-109650.19729748170357198 1627.17737902050930643, -109555.20129738480318338 1627.17737902050930643, -109555.20129738480318338 1753.91555262589872655, -109650.19729748170357198 1753.91555262589872655, -109650.19729748170357198 1627.17737902050930643))')

page_geometry_2 = QgsGeometry.fromWkt('Polygon ((-109610.28156478832534049 1524.58526357826144704, -109471.78156464705534745 1524.58526357826144704, -109471.78156464705534745 1607.71026366397813945, -109610.28156478832534049 1607.71026366397813945, -109610.28156478832534049 1524.58526357826144704))')

# create pages from page geometries
rectangle_1: QgsRectangle = templates.get_layout_extent(
	name_portrait, page_geometry_1.boundingBox().center(), 500)
page_geometry_1 = QgsGeometry.fromRect(rectangle_1)
page = plot_layer.add_page(name_portrait, page_geometry_1, 500)

rectangle_2: QgsRectangle = templates.get_layout_extent(
	name_landscape, page_geometry_2.boundingBox().center(), 500)
page_geometry_2 = QgsGeometry.fromRect(rectangle_2)
page = plot_layer.add_page(name_landscape, page_geometry_2, 500)

# add plot layer to current qgis instance (only for testing)
QgsProject.instance().addMapLayer(plot_layer.layer_pages)

# adds a print layout module to print PDF
print_ = plugin.add_module("PrintLayout", PrintLayout, plot_layer=plot_layer, layouts=templates)
# create pdf
result = print_.create_pdf(r"C:\Users\ABC\Downloads\TEST.pdf")
print("result print", result)

# self_unload=True important here
print_.unload(True)  # unload print layout module
# unload templates module, if no more needed, or keep alive
templates.unload(True)

```
