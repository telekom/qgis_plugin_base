# -*- coding: utf-8 -*-
# SPDX-FileCopyrightText: 2025 Deutsche Telekom Technik GmbH <f.vonstudsinske@telekom.de>
# SPDX-License-Identifier: GPL-3.0-only

import json
import os

from pathlib import Path

from qgis.PyQt.QtCore import pyqtSignal, QObject
from qgis.core import (QgsVectorLayer, QgsFeature, QgsVectorFileWriter,
                       QgsCoordinateReferenceSystem, QgsProject,
                       QgsFeatureRequest, QgsVectorDataProvider,
                       QgsGeometry, QgsMapLayer, QgsCoordinateTransform,
                       NULL)

from typing import List, Union, Dict, Optional

from .plot_config import PLOT_PAGES, PLOT_OPTIONS
from .geopackage import GeoPackage
from .layer import get_layer_source, create_layer_by_template
from .project import get_layer_from_source


class PlotLayer(QObject):
    """ This PlotLayer holds information about page-layer and options-layer and global plot layout too.

        :param gpkg: path to geo package or vector layer
    """
    saved = pyqtSignal(name="saved")

    defaults = {
        'legend_on_extra_page': True,
        'create_overview_page': True,
        'show_mini_map': True,
        'show_map_tips': True,
        'show_legend_on_page': False,
        'dpi': 150,
        'scale': 500,
        'options': "{}",
        'visibility': "{}",
    }

    def __init__(self, gpkg: Union[str, QgsVectorLayer], name: str = ""):
        super(QObject, self).__init__()

        if isinstance(gpkg, str):
            self.source = gpkg
        else:
            self.source = get_layer_source(gpkg)

        self.gpkg_data: GeoPackage = GeoPackage(self.source)
        self.name = os.path.basename(self.source)
        self.uri_pages = self.gpkg_data.get_uri("pages")
        self.uri_options = self.gpkg_data.get_uri("options")

        layer = get_layer_from_source(self.uri_pages)
        if layer is not None:
            # already loaded in QGIS
            self.layer_pages_id = layer.id()
        else:
            # not loaded in QGIS instance
            name = name if name else os.path.basename(self.source).split(".", 1)[0]
            layer_pages = QgsVectorLayer(self.uri_pages,
                                         name,
                                         "ogr")
            QgsProject.instance().addMapLayer(layer_pages, False)
            root = QgsProject.instance().layerTreeRoot()
            root.insertLayer(0, layer_pages)
            self.layer_pages_id = layer_pages.id()

        layer_options = self.layer_options
        if layer_options.featureCount() != 1:
            self.load_defaults()
        self.feature: QgsFeature = next(layer_options.getFeatures())
        del layer_options

    def get_next_page_number(self) -> int:
        layer_pages = self.layer_pages
        provider: QgsVectorDataProvider = layer_pages.dataProvider()
        value = provider.maximumValue(provider.fieldNameMap()['page'])
        if not value or value < 0:
            value = 0
        return value + 1

    def add_page(self, layout: Union['PlotLayout', str], geometry: QgsGeometry, scale: Union[int, float]) -> 'PlotPage':
        """ Appends a new page to page layer.

            On plot the page will zoom to geometry's extent and then zoom to given scale.

            :param layout: Layout object or layout name (internal path).
                           No will be performed here, if the layout exists.
            :param geometry: Valid geometry where to zoom on map to (expecting polygon and rectangle)
            :param scale: Valid scale for geometry and layout with map

        """
        layer_pages = self.layer_pages
        fields = layer_pages.dataProvider().fields()

        feature = QgsFeature(fields)
        feature.setGeometry(geometry)
        feature['scale'] = scale
        feature['page'] = self.get_next_page_number()
        feature['show_mini_map'] = self.show_mini_map
        feature['show_legend_on_page'] = self.show_legend_on_page
        feature['show_map_tips'] = self.show_map_tips
        feature['file'] = layout.path if not isinstance(layout, str) else layout
        feature['options'] = "{}"
        feature['visibility'] = "{}"

        layer_pages.dataProvider().addFeatures([feature])
        layer_pages.triggerRepaint()

        del layer_pages

        return self.get_page(feature['page'])

    def select_feature(self, fid: Optional[int] = None):
        """ selects feature with given fid """
        if not hasattr(self, "layer_pages"):
            return

        if fid is None:
            self.layer_pages.selectByIds([])
            return

        self.select_features([fid])

    def select_features(self, fids: List[int]):
        """ selects features with given fids """
        if not hasattr(self, "layer_pages"):
            return

        self.layer_pages.selectByIds(fids)

    def select_feature_page_num(self, page: int):
        """ selects feature with given fid """
        self.layer_pages.selectByExpression(f""" "page" = '{page}' """)

    def select_page(self, page: Union[int, 'PlotPage']):
        if isinstance(page, PlotPage):
            self.select_feature(page.fid)
        else:
            self.select_feature_page_num(page)

    def delete_fids(self, fids):
        if not fids:
            return

        self.layer_pages.dataProvider().deleteFeatures(fids)
        self.saved.emit()

    @property
    def layer_pages(self):
        layer_pages = QgsProject.instance().mapLayer(self.layer_pages_id)
        layer_pages.updateExtents(force=True)
        layer_pages.dataProvider().updateExtents()
        layer_pages.reload()
        return layer_pages

    @property
    def layer_options(self):
        return QgsVectorLayer(self.uri_options, "layer_options", "ogr")

    def load_defaults(self):
        """ restores default into options layer """
        layer_options = self.layer_options
        features = [f.id() for f in layer_options.getFeatures()]
        layer_options.dataProvider().deleteFeatures(features)
        feature = QgsFeature(layer_options.dataProvider().fields())
        for field_name, field_value in self.defaults.items():
            feature[field_name] = field_value
        layer_options.dataProvider().addFeatures([feature])

        del layer_options

    @classmethod
    def is_plot_layer(cls, layer: QgsMapLayer):
        """ returns True, if layer is a valid plot layer
            Given layer must be page layer
        """

        if not isinstance(layer, QgsVectorLayer):
            return False

        if layer.isTemporary():
            return False

        source = get_layer_source(layer)

        try:
            if not Path(source).is_file():
                return False
        except OSError:
            # e.g. WFS/WMS
            return False

        if not source.casefold().endswith(".gpkg"):
            return False

        geo = GeoPackage(source)
        if has_pages_layer := geo.has_layer("pages"):
            # all expected columns in the pages layer present?
            pages_layer_columns = geo.get_columns("pages")
            pages_columns_valid = all(map(lambda x: x in pages_layer_columns, PLOT_PAGES['Attributes']))
        else:
            # no pages layer found
            pages_columns_valid = False

        if has_options_layer := geo.has_layer("options"):
            # all expected columns in the options layer present?
            options_layer_columns = geo.get_columns("options")
            options_columns_valid = all(map(lambda x: x in options_layer_columns, PLOT_OPTIONS['Attributes']))
        else:
            # no options layer found
            options_columns_valid = False

        return has_pages_layer and pages_columns_valid and has_options_layer and options_columns_valid

    @classmethod
    def is_plot_file(cls, path: str):
        """ is given path a GeoPackage file and PlotLayer? """

        if not path.casefold().endswith(".gpkg"):
            return False

        try:
            geo = GeoPackage(path)
        except:
            return False

        return geo.has_layer("pages") and geo.has_layer("options")

    @classmethod
    def get_plot_uri(cls, path: str):
        """ returns layer uri from geopackage path """
        if not cls.is_plot_file(path):
            return False
        geo = GeoPackage(path)

        return geo.get_uri("pages")

    @classmethod
    def create_new(cls, path: str, crs: QgsCoordinateReferenceSystem, name: str = ""):
        """ Creates a new empty plot layer.

        """

        if Path(path).is_file():
            os.remove(path)

        layer_plot_pages = create_layer_by_template("pages", crs.authid(), PLOT_PAGES)
        layer_plot_options = create_layer_by_template("options", crs.authid(), PLOT_OPTIONS)

        for layer in [layer_plot_pages, layer_plot_options]:

            options = QgsVectorFileWriter.SaveVectorOptions()
            options.layerName = layer.name()

            # transform
            transform_params = QgsCoordinateTransform(
                crs,
                crs,
                QgsProject.instance())
            options.ct = transform_params

            if Path(path).is_file():
                # important, if gpkg already exists
                options.actionOnExistingFile = QgsVectorFileWriter.CreateOrOverwriteLayer

            result = QgsVectorFileWriter.writeAsVectorFormatV3(
                layer,
                path,
                QgsProject.instance().transformContext(),
                options
            )
            if result[0] != QgsVectorFileWriter.NoError:
                raise TypeError(f"layer {layer.name()} can not be save at destination '{path}'. Reason: {result[1]}")

        obj = cls(path, name=name)

        return obj

    def save_value(self, field_name: str, value):
        layer_options = self.layer_options
        self.feature[field_name] = value
        index = layer_options.dataProvider().fieldNameMap()[field_name]
        layer_options.dataProvider().changeAttributeValues({self.feature.id(): {index: value}})
        self.saved.emit()

        del layer_options

    def get_value(self, attribute: str):
        """ returns value from self.feature, if NULL, then use default value and save it """
        value = self.feature[attribute]

        if value == NULL:

            if attribute not in PlotLayer.defaults:
                return value

            value = PlotLayer.defaults[attribute]
            self.save_value(attribute, value)

        return value

    def get_crs(self) -> QgsCoordinateReferenceSystem:
        layer_pages = self.layer_pages
        crs = layer_pages.dataProvider().crs()
        del layer_pages
        return crs

    @property
    def fid(self) -> int:
        return self.feature.id()

    @property
    def legend_on_extra_page(self) -> bool:
        return self.get_value('legend_on_extra_page')

    @legend_on_extra_page.setter
    def legend_on_extra_page(self, value):
        self.save_value("legend_on_extra_page", value)

    @property
    def create_overview_page(self) -> bool:
        return self.get_value('create_overview_page')

    @create_overview_page.setter
    def create_overview_page(self, value):
        self.save_value("create_overview_page", value)

    @property
    def dpi(self) -> int:
        return self.get_value('dpi')

    @dpi.setter
    def dpi(self, value):
        self.save_value("dpi", value)

    @property
    def show_map_tips(self) -> bool:
        return self.get_value('show_map_tips')

    @show_map_tips.setter
    def show_map_tips(self, value):
        self.save_value("show_map_tips", value)

    @property
    def show_legend_on_page(self) -> bool:
        return self.get_value('show_legend_on_page')

    @show_legend_on_page.setter
    def show_legend_on_page(self, value):
        self.save_value("show_legend_on_page", value)

    @property
    def file(self) -> str:

        file = self.get_value('file').replace(" ", "")
        if file != self.feature['file']:
            self.save_value("file", file)

        return file

    @file.setter
    def file(self, value):

        if self.get_value('file'):
            raise TypeError("an existing template can not be changed later - `file`")

        if value.replace(" ", "") != value:
            raise ValueError(f"no spaces allowed in file `{value}`")

        self.save_value("file", value)

    @property
    def options(self) -> dict:
        value = json.loads(self.get_value('options'))
        return value

    @options.setter
    def options(self, value):
        if isinstance(value, dict):
            value = json.dumps(value)
        self.save_value("options", value)

    @property
    def visibility(self) -> 'VisibilityCollection':
        """
        format: {
            'layer.id()': {'mini_map': bool, 'overview': bool, 'legend': bool, 'page': bool}
        }

        :mini_map: visible on mini map?
        :overview: visible on overview page?
        :legend: visible in legend?
        :page: visible on page?

        """
        value = json.loads(self.get_value('visibility'))
        return VisibilityCollection(self, value)

    @visibility.setter
    def visibility(self, value):
        if isinstance(value, dict):
            value = json.dumps(value)
        self.save_value("visibility", value)

    @property
    def scale(self) -> str:
        return self.get_value('scale')

    @scale.setter
    def scale(self, value):
        self.save_value("scale", value)

    @property
    def show_mini_map(self) -> int:
        return self.get_value('show_mini_map')

    @show_mini_map.setter
    def show_mini_map(self, value: bool):
        self.save_value('show_mini_map', value)

    def get_page_from_fid(self, fid: int) -> 'PlotPage':
        return PlotPage(self.layer_pages.getFeature(fid), self)

    def get_page(self, page: int) -> 'PlotPage':
        req = QgsFeatureRequest().setFilterExpression(f""" "page"='{page}' """)
        return PlotPage(next(self.layer_pages.getFeatures(req)), self)

    def __repr__(self):
        return f"{self.__class__.__name__}('{self.source}')"

    def __iter__(self):
        for i, feature in enumerate(self.layer_pages.getFeatures(QgsFeatureRequest().addOrderBy("page", True))):
            page_nr = i + 1
            page = PlotPage(feature, self)

            # test if page number is correct
            if page_nr != page.page:
                page.page = page_nr

            yield page


class PlotLayerMemory(PlotLayer):
    """ Represents a memory layer for current QGIS instance without temporary files.
        Creates PlotLayers from this memory class cannot be added to the user interface Plot Menu.

        Prefer the memory instantiation with the `create_new` method.

        .. code-block:: python

            templates = PlotLayoutTemplates()

            plot_layer = PlotLayerMemory.create_new(QgsCoordinateReferenceSystem("EPSG:3857"), "test memory")
            page = plot_layer.add_page("FiberFactory/A4_Portrait_FF", geometry, 500)


            rectangle: QgsRectangle = self.layout.get_parent().get_layout_extent(self.layout.path,
                                                                                 center,
                                                                                 self.scale)

        :param layer_plot_pages:
        :param layer_plot_options:
        :param template_name: Template name

    """

    def __init__(self, layer_plot_pages: QgsVectorLayer, layer_plot_options: QgsVectorLayer, template_name: str):
        super(QObject, self).__init__()

        self.name = template_name
        self.__layer_pages = layer_plot_pages
        self.__layer_options = layer_plot_options

        layer_options = self.layer_options
        if layer_options.featureCount() != 1:
            self.load_defaults()
        self.feature: QgsFeature = next(layer_options.getFeatures())
        del layer_options

    @classmethod
    def create_new(cls, crs: QgsCoordinateReferenceSystem, template_name: str):
        """ Creates a new empty plot layer in QGIS memory. Not visible to user.

            :param crs: coordinate reference system for this plot
            :param template_name: Name/Template path to QGIS print layout template

        """

        layer_plot_pages = create_layer_by_template("pages", crs.authid(), PLOT_PAGES)
        layer_plot_options = create_layer_by_template("options", crs.authid(), PLOT_OPTIONS)

        plot_layer = cls(layer_plot_pages, layer_plot_options, template_name)

        return plot_layer

    @property
    def layer_options(self) -> QgsVectorLayer:
        return self.__layer_options

    @property
    def layer_pages(self) -> QgsVectorLayer:
        return self.__layer_pages


class PlotPage:

    def __init__(self, feature: QgsFeature, plot_layer: PlotLayer):
        self.feature = {name: feature[name] for name in feature.fields().names()}
        self.feature_id = feature.id()
        self.plot_layer = plot_layer

    def save_value(self, field_name: str, value):
        layer_pages = self.plot_layer.layer_pages

        self.feature[field_name] = value
        index = layer_pages.dataProvider().fieldNameMap()[field_name]
        layer_pages.dataProvider().changeAttributeValues({self.feature_id: {index: value}})
        self.plot_layer.saved.emit()

    def get_value(self, attribute: str):
        """ returns value from self.feature, if NULL, then use default value and save it """
        value = self.feature[attribute]

        if value == NULL:

            if attribute not in PlotLayer.defaults:
                return value

            value = PlotLayer.defaults[attribute]
            self.save_value(attribute, value)

        return value

    def delete(self):
        """ deletes this page from plot layer """
        layer_pages = self.plot_layer.layer_pages
        layer_pages.dataProvider().deleteFeatures([self.fid])
        self.plot_layer.saved.emit()
        layer_pages.triggerRepaint()

        del layer_pages

    @property
    def fid(self) -> int:
        return self.feature_id

    @property
    def page(self) -> int:
        return self.get_value('page')

    @page.setter
    def page(self, value: int):
        self.save_value('page', value)

    @property
    def show_map_tips(self) -> bool:
        return self.get_value('show_map_tips')

    @show_map_tips.setter
    def show_map_tips(self, value):
        self.save_value("show_map_tips", value)

    @property
    def show_legend_on_page(self) -> bool:
        return self.get_value('show_legend_on_page')

    @show_legend_on_page.setter
    def show_legend_on_page(self, value):
        self.save_value("show_legend_on_page", value)

    @property
    def scale(self) -> int:
        return self.get_value('scale')

    @scale.setter
    def scale(self, value: int):
        self.save_value('scale', value)

    @property
    def show_mini_map(self) -> int:
        return self.get_value('show_mini_map')

    @show_mini_map.setter
    def show_mini_map(self, value: bool):
        self.save_value('show_mini_map', value)

    @property
    def file(self) -> str:

        file = self.get_value('file').replace(" ", "")
        if file != self.get_value('file'):
            self.save_value("file", file)

        return file

    @file.setter
    def file(self, value):

        if self.get_value('file'):
            raise TypeError("an existing template can not be changed later - `file`")

        if value.replace(" ", "") != value:
            raise ValueError(f"no spaces allowed in file `{value}`")

        self.save_value("file", value)

    @property
    def options(self) -> dict:
        value = json.loads(self.get_value('options'))
        return value

    @options.setter
    def options(self, value):
        if isinstance(value, dict):
            value = json.dumps(value)
        self.save_value("options", value)

    @property
    def visibility(self) -> 'VisibilityCollection':
        """ format: see PlotLayer.visibility """
        value = json.loads(self.get_value('visibility'))
        return VisibilityCollection(self, value)

    @visibility.setter
    def visibility(self, value):
        if isinstance(value, dict):
            value = json.dumps(value)
        self.save_value("visibility", value)


class VisibilityCollection:

    def __init__(self, parent: Union[PlotPage, PlotLayer],
                 visibility: Dict[str, Dict[str, bool]]):
        self.__parent = parent
        self.visibility = visibility

    @staticmethod
    def default():
        value = {'mini_map': True,
                 'overview': True,
                 'legend': True,
                 'page': True}
        return value

    @property
    def parent(self) -> Union[PlotPage, PlotLayer]:
        return self.__parent

    def clear(self):
        """ clears all options """
        self.visibility.clear()
        self.sync()

    def remove_layer(self, layer: Union[QgsMapLayer, str]):
        """ Removes layer id from visibility dict
            Changes will be saved in parent.
        """
        layer_id = layer if isinstance(layer, str) else layer.id()
        try:
            del self.visibility[layer_id]
            self.sync()
        except KeyError:
            pass

    def get_layer_visibility(self, layer: Union[QgsMapLayer, str]):
        layer_id = layer if isinstance(layer, str) else layer.id()
        try:
            self.visibility[layer_id]
        except KeyError:
            self.visibility[layer_id] = self.default()

        return self.visibility[layer_id]

    def set_layer_visible_on_page(self, layer: Union[QgsMapLayer, str], visible: bool):
        visibility = self.get_layer_visibility(layer)
        visibility['page'] = visible
        self.sync()

    def set_layer_visible_mini_map(self, layer: Union[QgsMapLayer, str], visible: bool):
        visibility = self.get_layer_visibility(layer)
        visibility['mini_map'] = visible
        self.sync()

    def set_layer_visible_legend(self, layer: Union[QgsMapLayer, str], visible: bool):
        visibility = self.get_layer_visibility(layer)
        visibility['legend'] = visible
        self.sync()

    def set_layer_visible_overview(self, layer: Union[QgsMapLayer, str], visible: bool):
        visibility = self.get_layer_visibility(layer)
        visibility['overview'] = visible
        self.sync()

    def is_layer_visible_on_page(self, layer: Union[QgsMapLayer, str]) -> bool:
        return self.get_layer_visibility(layer)['page']

    def is_layer_visible_on_mini_map(self, layer: Union[QgsMapLayer, str]) -> bool:
        return self.get_layer_visibility(layer)['mini_map']

    def is_layer_visible_on_legend(self, layer: Union[QgsMapLayer, str]) -> bool:
        return self.get_layer_visibility(layer)['legend']

    def is_layer_visible_overview(self, layer: Union[QgsMapLayer, str]) -> bool:
        return self.get_layer_visibility(layer)['overview']

    def sync(self):
        self.parent.visibility = self.visibility

    def get_layers(self) -> List[QgsMapLayer]:
        """ Returns a list of layers.
            Only layers are in list, wich are in project too.
        """
        layers = []
        for key in self.visibility:
            layer = QgsProject.instance().mapLayer(key)
            if layer is not None:
                layers.append(layer)

        return layers

    def get_layer_visibilities(self, field: str) -> List[QgsMapLayer]:
        """ Returns a list of layers.
            Only layers are in list, wich are in project and option set for visibility.

            :param field: page, mini_map, legend, overview
        """
        layers = []

        if self.visibility:
            for key in self.visibility:
                layer = QgsProject.instance().mapLayer(key)
                if layer is not None:
                    if self.get_layer_visibility(layer)[field] and not PlotLayer.is_plot_layer(layer):
                        layers.append(layer)
        else:
            # nothing here on page, use layer visibility settings from plot layer
            if isinstance(self.parent, PlotLayer):
                ...
            else:
                layers.extend(self.parent.plot_layer.visibility.get_layer_visibilities(field))

        return layers

    def __getitem__(self, layer: Union[str, QgsMapLayer]) -> 'Visibility':
        return Visibility(self, self.get_layer_visibility(layer))


class Visibility:

    def __init__(self, collection: VisibilityCollection, values: Dict[str, bool]):
        self.values = values
        self.__collection = collection

    def sync(self):
        self.collection.sync()

    @property
    def collection(self):
        return self.__collection

    @property
    def page(self) -> bool:
        return self.values['page']

    @page.setter
    def page(self, state: bool):
        if not isinstance(state, bool):
            raise TypeError
        self.values['page'] = state

    @property
    def mini_map(self) -> bool:
        return self.values['mini_map']

    @mini_map.setter
    def mini_map(self, state: bool):
        if not isinstance(state, bool):
            raise TypeError
        self.values['mini_map'] = state

    @property
    def legend(self) -> bool:
        return self.values['legend']

    @legend.setter
    def legend(self, state: bool):
        if not isinstance(state, bool):
            raise TypeError
        self.values['legend'] = state

    @property
    def overview(self) -> bool:
        return self.values['overview']

    @overview.setter
    def overview(self, state: bool):
        if not isinstance(state, bool):
            raise TypeError
        self.values['overview'] = state

