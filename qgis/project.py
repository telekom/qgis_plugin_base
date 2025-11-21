# -*- coding: utf-8 -*-
# SPDX-FileCopyrightText: 2025 Deutsche Telekom Technik GmbH <f.vonstudsinske@telekom.de>
# SPDX-License-Identifier: GPL-3.0-only

import os
import sip

from qgis.core import (QgsMapLayerType, QgsMapLayer, QgsWkbTypes, QgsProject,
                       QgsVectorLayer)
from qgis.PyQt.QtWidgets import QMessageBox

from typing import Optional, List, Tuple, Union
from pathlib import Path


def get_project_layers(layer_type: QgsMapLayerType = QgsMapLayer.VectorLayer, 
                       geometry_type: Optional[QgsWkbTypes.GeometryType] = None) -> List[QgsMapLayer]:
    """ Returns all layers from qgis instance by layer type.

        :param layer_type: Layer type (defaults to only vector layers)
        :param geometry_type: Optional filter argument to get vector layers with a specific geometry type.
        :return: layers
    """
    to_return: List[QgsMapLayer] = []
    layers = QgsProject.instance().mapLayers().values()

    for layer in layers:
        if layer.type() == layer_type:
            if (layer_type == QgsMapLayer.VectorLayer and geometry_type is not None
                    and layer.geometryType() == geometry_type):
                # append filtered layer with the expected geometry type
                to_return.append(layer)
            else:
                # default behavior
                to_return.append(layer)

    return to_return


def get_line_layer() -> List[Tuple[str, QgsVectorLayer]]:
    """ gets all qgis instance line layers

        :return: list of tuples with name (0) and layer (1)
    """

    return get_project_layers(QgsMapLayer.VectorLayer, geometry_type=QgsWkbTypes.LineGeometry)


def get_point_layer() -> List[Tuple[str, QgsVectorLayer]]:
    """ gets all qgis instance point layers

        :return: list of tuples with name (0) and layer (1)
    """

    return get_project_layers(QgsMapLayer.VectorLayer, geometry_type=QgsWkbTypes.PointGeometry)


def get_polygon_layer() -> List[Tuple[str, QgsVectorLayer]]:
    """ gets all qgis instance polygon layers

        :return: list of tuples with name (0) and layer (1)
    """

    return get_project_layers(QgsMapLayer.VectorLayer, geometry_type=QgsWkbTypes.PolygonGeometry)


def is_layer_source_loaded(source: Union[str, QgsMapLayer]) -> bool:
    """ Is source already loaded into running QgsProject?

        :param source: layer source path or layer
        :return: returns True, if layer is already loaded with given source
    """
    if isinstance(source, QgsMapLayer):
        source = source.source()

    source = os.path.normpath(source)
    source = os.path.normcase(source)
    layers = QgsProject.instance().mapLayers().values()
    sources = [os.path.normpath(layer.source()) for layer in layers]
    sources = [os.path.normcase(s) for s in sources]

    return source in sources


def get_layer_from_source(source: str) -> Optional[QgsMapLayer]:
    """ Try to find layer from source (e.g. os path) from current `QgsProject.instance()`.

        :param source: layer source path (includung layername for e.g. GeoPackage
        :return: Layer with same source path or None, when not found
    """

    source = os.path.normpath(source)
    source = os.path.normcase(source)
    layers = QgsProject.instance().mapLayers().values()
    sources = {os.path.normcase(os.path.normpath(layer.source())): layer for layer in layers}

    return sources.get(source, None)

def get_layers_from_source_path(source: str) -> List[QgsMapLayer]:
    """ Returns a list of all loaded map layers from the given file path

        :param source: layer source path
        :return: Layer with same source path or None, when not found
    """
    from .layer import get_layer_source

    source = Path(source)

    layers = []
    for layer in QgsProject.instance().mapLayers().values():
        layer_source = get_layer_source(layer)
        if Path(layer_source) == source:
            layers.append(layer)

    return layers


def get_layers_from_source(source: str) -> List[QgsMapLayer]:
    """ Try to find layers from source (e.g. os path) from current `QgsProject.instance()`.

        :param source: layer source path
        :return: List of layers with same source path or empty list, when not found
    """
    to_return = []
    source = os.path.normpath(source)
    source = os.path.normcase(source)
    layers = QgsProject.instance().mapLayers().values()
    for layer in layers:
        if os.path.normcase(os.path.normpath(layer.source())) == source:
            to_return.append(layer)

    return to_return


def warn_unexpected_measurement_ellipsoid() -> bool:
    """ Shows a popup if the expected ellipsoid is different to the current ellipsoid.
        Returns True in case of shown messagebox.
    """
    from qgis.utils import iface

    current_ellipsoid = QgsProject.instance().ellipsoid()
    recommended_ellipsoid = "EPSG:7030"
    if current_ellipsoid != recommended_ellipsoid:
        # WGS 84
        reply = QMessageBox.warning(
            iface.mainWindow(),
            'Warnung: QGIS-Messwerkzeug',
            f'In den QGIS Projekteigenschaften ist das Mess-Ellipsoid {current_ellipsoid} eingestellt.\n\n'
            f'Für Meter-genaue Messungen wird das Ellipsoid {recommended_ellipsoid} empfohlen.\n\n'
            'Einstellbar ist dies über die QGIS Menüleiste:\n'
            '-> Projekt\n'
            '-> Eigenschaften\n'
            '-> Menü "Allgemein"\n'
            '-> Bereich "Messungen"\n'
            '-> Ellipsoid-Dropdown\n\n'
            f'Hier nach "WGS 84 ({current_ellipsoid})" suchen und wählen.')
        return True

    return False


def warn_inactive_snapping_tool() -> bool:
    """ Shows a popup if the snapping tools/options are disabled or with invalid typeFlag.
        Returns True in case of shown messagebox.
    """
    from qgis.utils import iface
    canvas = iface.mapCanvas()

    # test snapping config from canvas
    config = canvas.snappingUtils().config()
    if not config.typeFlag():
        # no snapping type (vertex, segment, controid etc.) set
        reply = QMessageBox.warning(
            iface.mainWindow(),
            'Kartenwerkzeug / Einrastoptionen',
            'Das Einrastwerkzeug ist nicht korrekt eingestellt. Einrasten nicht möglich.')

    if not config.enabled():
        reply = QMessageBox.warning(
            iface.mainWindow(),
            'Kartenwerkzeug / Einrastoptionen',
            "Das Einrastwerkzeug ist nicht aktiviert. Einrasten nicht möglich.")

    return False


def remove_layers_from_qgs_instance(layers: List[QgsVectorLayer]):
    """ save delete layers from QgsProject.instance

        :param layers: list of given QgsVectorLayer's
    """
    if not isinstance(layers, list):
        raise TypeError("layers is not a list")

    for layer in layers:
        # FIXME use "isinstance" instead
        if layer.__class__ != QgsVectorLayer:
            continue

        layer: QgsVectorLayer

        if sip.isdeleted(layer):
            # skip c++ deleted object
            continue

        id_ = layer.id()
        found_layer = QgsProject.instance().mapLayer(id_)
        if found_layer is None:
            layer.deleteLater()
            del layer
