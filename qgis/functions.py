# -*- coding: utf-8 -*-
# SPDX-FileCopyrightText: 2025 Deutsche Telekom Technik GmbH <f.vonstudsinske@telekom.de>
# SPDX-License-Identifier: GPL-3.0-only

import logging
import importlib
import qgis.utils
import sys
from pathlib import Path

from qgis.core import (QgsNetworkAccessManager, QgsProject, QgsUnitTypes,
                       QgsGeometry, QgsVectorLayer, QgsPointXY, QgsCoordinateReferenceSystem,
                       QgsSpatialIndex, QgsFeature, QgsWkbTypes, QgsFeatureRequest,
                       QgsDistanceArea, NULL, QgsSettings)
from qgis.gui import QgsMapCanvas, QgsMapTool
from qgis.PyQt.QtCore import QPoint

from typing import Any, Optional, List, Union, Dict

from .geometry import transform_geometry, transform_point


def update_qgis_plugin(plugin_name: str, logger: Optional[logging.Logger] = None, *, 
                       reload_plugins: bool = False, force_installation: bool = False) -> bool:
    """ Updates the given QGIS plugin.
        Returns True, if the plugin is still active after this function.
        False in case of no update done or no plugin found.

        :param plugin_name: plugin name, usually the folder name
        :param logger: logging.Logger to log messages to
        :param reload_plugins: True to refetch plugin data, with UI dialog from QGIS
        :param force_installation: True to force a re-installation/update
    """

    from pyplugin_installer import instance as pyplugin_instance
    from pyplugin_installer.installer_data import plugins as QgsPythonPlugins_

    # clear the network cache from QGIS/Qt to refetch all plugin data
    #   and do not use the network cache
    if logger is not None:
        logger.log(logging.DEBUG, "update_qgis_plugin: Clear the network cache")
    QgsNetworkAccessManager.instance().cache().clear()
    QgsNetworkAccessManager.instance().clearAccessCache()
    QgsNetworkAccessManager.instance().clearConnectionCache()

    if logger is not None:
        logger.log(logging.DEBUG, "update_qgis_plugin: Reload the plugin metadata and availability")
    # get current QGIS plugin instance
    plugin_installer = pyplugin_instance()
    # fetch local available plugins
    plugin_installer.fetchAvailablePlugins(reload_plugins)

    # reload the internal plugin cache
    qgis.utils.updateAvailablePlugins()

    # abort, if the plugin name is no more available :o
    if plugin_name not in QgsPythonPlugins_.all().keys():
        if logger is not None:
            logger.log(logging.WARNING, f"update_qgis_plugin: Plugin {plugin_name} is not available")
        return False

    # abort, if no new version is available for the installed plugin
    dep_plugin = QgsPythonPlugins_.all()[plugin_name]
    to_download = False or force_installation
    if dep_plugin['status'] == 'installed' and dep_plugin['installed']:
        if logger is not None:
            logger.log(logging.DEBUG, f"update_qgis_plugin: No update available for {plugin_name}.")
    else:
        # does not exist locally, needs to be downloaded
        to_download = True

    # file path, if locally installed and the repository is not serving the folder name
    #   or HTTP/HTTPS url if installed from a url/provided from a repository
    download_url = dep_plugin["download_url"]

    # install plugin from key, automatically the newest version will be used
    downloaded = False
    if download_url.startswith(("https", "http")):
        if to_download:
            if logger is not None:
                logger.log(logging.DEBUG, f"update_qgis_plugin: Install or update {plugin_name} from repository '{download_url}'.")
            # install/update from the url
            plugin_installer.installPlugin(plugin_name, quiet=True)
            downloaded = True
    else:
        if logger is not None:
            logger.log(logging.DEBUG, f"update_qgis_plugin: Plugin {plugin_name} installed locally "
                                      f"and not from a repository. The folder is '{download_url}'")
    try:
        importlib.import_module(plugin_name)
        if logger is not None:
            logger.log(logging.DEBUG, f"update_qgis_plugin: {plugin_name} is importable")
    except ModuleNotFoundError:
        if logger is not None:
            logger.log(logging.WARNING, f"update_qgis_plugin: {plugin_name} is not importable")
        return False

    started = False
    if plugin_name in qgis.utils.plugins and downloaded:
        # reload the updated and active plugin
        started = qgis.utils.reloadPlugin(plugin_name)
        if logger is not None:
            logger.log(logging.DEBUG, f"update_qgis_plugin: Plugin {plugin_name} {started=} (reloadPlugin)")
    elif plugin_name not in qgis.utils.plugins:
        # activate the installed/fresh downloaded plugin but inactive
        started = qgis.utils.startPlugin(plugin_name)
        if logger is not None:
            logger.log(logging.DEBUG, f"update_qgis_plugin: Plugin {plugin_name} {started=} (startPlugin)")

    if started:
        # add the plugin to the active_plugins list, if not in this list
        if plugin_name not in qgis.utils.active_plugins:
            qgis.utils.active_plugins.append(plugin_name)

        # mark the plugin as active
        settings = QgsSettings()
        settings.setValue('/PythonPlugins/' + plugin_name, True)
        if logger is not None:
            logger.log(logging.DEBUG, f"update_qgis_plugin: Plugin {plugin_name} activated successfully.")

    # reload the internal plugin cache
    qgis.utils.updateAvailablePlugins()

    # do not update the plugin manager ui. it can cause a QGIS crash

    return plugin_name in qgis.utils.plugins


def convert_meter_to_units(source_map_units: QgsUnitTypes.DistanceUnit,
                           dst_map_units: QgsUnitTypes.DistanceUnit, value: float) -> float:
    """ Converts given value between map units. Be careful with this calculation.

        :param source_map_units: source map units from coordinate reference system
        :param dst_map_units: destination map units from coordinate reference system
        :param value: value to convert
        :return: float
    """
    if not isinstance(source_map_units, (int, QgsUnitTypes.DistanceUnit)):
        raise TypeError
    if not isinstance(dst_map_units, (int, QgsUnitTypes.DistanceUnit)):
        raise TypeError

    factor = QgsUnitTypes.fromUnitToUnitFactor(source_map_units, dst_map_units)

    return value * factor


def get_points_from_meter_steps(poly_line: List[QgsPointXY], step_meter: float,
                                source_crs: QgsCoordinateReferenceSystem,
                                calculate_crs: Optional[Union[QgsCoordinateReferenceSystem, str]] = "EPSG:3857"):
    """ Returns points along given poly list in steps of meters.
        Start point (0 m) not included.
        Small inaccurracies are possible through transformation.

        Uses internal PolylineWrapper util class.

        :param poly_line: Poly line list
        :param step_meter: Distance to locate points
        :param source_crs: Needed for calculation and temporary transformation
        :param calculate_crs: Needed for calculation and temporary transformation. Distance calculation will be done with this CRS.
    """

    from .poly_line_wrapper import PolylineWrapper

    if isinstance(calculate_crs, str):
        # load the temporary crs for calculation, if not given
        calculate_crs = QgsCoordinateReferenceSystem(calculate_crs)

    # transform geometry to temporary crs
    geometry = transform_geometry(QgsGeometry.fromPolylineXY(poly_line),
                                    source_crs,
                                    calculate_crs)
    use_poly_line = geometry.asPolyline()

    # load into poly line wrapper
    wrapper = PolylineWrapper.from_point_list(use_poly_line)
    points = wrapper.get_points_from_meter_steps(step_meter, calculate_crs)

    # transform back to source crs
    points = [
        transform_point(point, calculate_crs, source_crs)
        for point in points
    ]
    return points


def get_nearest_neighbor(canvas: QgsMapCanvas, position_source: Any,
                         layer_list: List[QgsVectorLayer], own_spindex_list: List[QgsSpatialIndex] = None,
                         return_layer: bool = False) -> tuple:
    """ gets the closest point and feature to `position_source`

        :param canvas: canvas
        :param position_source: types QgsPointXY, QgsFeature, QPoint
        :param layer_list: unknown
        :param own_spindex_list: unknown
        :param return_layer: return nearest layer?
        :return: different return length!

        :raises AttributeError: invalid parameter
        :raises TypeError: invalid `position_source`
    """
    if not isinstance(position_source, (QgsPointXY, QgsFeature, QPoint)):
        raise TypeError(f"Expecting QgsPointXY, QgsFeature or QPoint, got {position_source}")

    # erstellt QgsPointXY
    # wenn position_source = QgsFeature
    map_tool = QgsMapTool(canvas)
    if isinstance(position_source, QgsFeature):
        geometry = position_source.geometry()
        if geometry.type() != QgsWkbTypes.PointGeometry:
            raise TypeError("Übergebenes Feature besitzt keine Punkt-Geometrie (evtl ein LinienFeature?)")
        qpoint_xy_projekt = geometry.asPoint()
    # wenn position_source = QPoint (z.B. von einem Event wie Rechtsklick --> event.pos())
    elif isinstance(position_source, QPoint):
        qpoint_xy_projekt = map_tool.toMapCoordinates(position_source)
    # wenn position_source = QgsPointXY
    else:
        qpoint_xy_projekt = position_source

    shortest_distance = float("inf")
    closest_qpoint_xy = None
    closest_feature_id = None
    closest_layer = None

    # suche innerhalb der übergebenen Layer den nächstgelegenen Nachbarn
    for idx, layer in enumerate(layer_list):

        # setzt QPointXY auf die Koordinaten des Layers (falls Projekt EPSG != Layer EPSG)
        qpoint_xy_layer = map_tool.toLayerCoordinates(layer, qpoint_xy_projekt)
        # erzeuge dummy geometry um Abstand zwischen dieser und den nearestNeighbor zu messen
        # geometry_dummy_layer = QgsGeometry.fromPointXY(qpoint_xy_layer)
        # suche nächsten Nachbarn ([feat.id()]) im layer
        if own_spindex_list is None:
            sp_index = QgsSpatialIndex(layer)
        else:
            sp_index = own_spindex_list[idx]
        nearest_feat_ids = sp_index.nearestNeighbor(qpoint_xy_layer, 5)
        # holt die nächstgelegenen Features um diese zu vergleichen
        req = QgsFeatureRequest().setFilterFids(nearest_feat_ids)
        features = layer.getFeatures(req)

        # ist Layer Linien oder Punktlayer?
        # sammle Geometrie und feat.id() in Liste qpoints_array
        # --> [[[QPointXY, QPointXY], feat.id()],[[QPointXY], feat.id()], ...]
        wkb_type = layer.wkbType()
        qpoints_array = []
        # für LinienLayer
        if wkb_type == QgsWkbTypes.LineString or wkb_type == QgsWkbTypes.MultiLineString:
            for feature in features:
                qpoints_array += [[feature.geometry().asPolyline(), feature.id()]] \
                    if not feature.geometry().isMultipart() else feature.geometry().asMultiPolyline()
        # für Punktlayer
        elif wkb_type == QgsWkbTypes.Point:
            for feature in features:
                qpoints_array.append([[feature.geometry().asPoint()], feature.id()])
        # weder noch --> Error
        else:
            raise ValueError("übergebener Layer besitzt keine gültige Punkt oder Liniengeometrie")

        # geht die ermittelten Punkte der Features durch und vergleicht diese mit dem Ursprungspunkt
        for qpoint_xy_list, feat_id in qpoints_array:
            # geht alle Punkte durch
            for qpoint_xy_feat in qpoint_xy_list:
                # erstellt weitere dummy Geometrie zum vergleich mit der Geometry des Eingangspunktes
                # geometry_dummy_feat = QgsGeometry.fromPointXY(qpoint_xy_feat)
                distance = get_distance_area(layer.crs())
                # nimmt die Distanz von Trassenpunkt zur Maus
                dist = distance.measureLine(qpoint_xy_feat, qpoint_xy_layer)
                if dist < shortest_distance:
                    shortest_distance = dist
                    closest_qpoint_xy = qpoint_xy_feat
                    closest_feature_id = feat_id
                    closest_layer = layer

    if not return_layer:
        return closest_qpoint_xy, closest_feature_id

    else:
        return closest_qpoint_xy, closest_feature_id, closest_layer


def get_distance_area(crs: QgsCoordinateReferenceSystem, ellipsoid: str = "WGS84") -> QgsDistanceArea:
    """ Gets distance are object for calculating length in meters.

        .. code-block:: python

            distance = get_distance_area(layer.dataProvider().crs())
            print("measured feature length in meters", distance.measureLength(feature.geometry()))

        :param crs: coordinate reference system
        :param ellipsoid: ellipsoid name, keep empty when using from crs
        :return: distance area object
        :rtype: QgsDistanceArea
    """

    dist_area = QgsDistanceArea()
    crs = QgsCoordinateReferenceSystem(crs)
    dist_area.setSourceCrs(crs, QgsProject.instance().transformContext())
    dist_area.setEllipsoid(ellipsoid if ellipsoid else crs.ellipsoidAcronym())

    return dist_area


def get_query_condition(feature: Union[QgsFeature, Dict[str, Any]], attribute_names: List[str], operand: str = " AND ") -> str:
    """ Joins given attributes from given feature to a sql like condition used in `QgsFeatureRequest`.


        :param feature: feature with attributes
        :param attribute_names: attributes to build new query
        :param operand: sql operand

        :return: sql condition
    """
    if operand not in [" AND ", " OR "]:
        raise ValueError("operand is not valid, only AND/OR allowed")

    query = []
    for attr_name in attribute_names:
        try:  # attribute_names berücksichtige nicht AN Exoort (KeyError)
            attribute = feature[attr_name]
        except KeyError:
            continue

        if attribute == NULL:
            query.append(attr_name + " IS NULL")
        else:
            if isinstance(attribute, str):
                # String escaping
                attribute = attribute.replace("'", "\\\'")
            query.append(attr_name + " = '%s'" % attribute)
    query = operand.join(query)

    if query == "":
        query = "1"

    return query


def request_to_filter(request: QgsFeatureRequest) -> str:
    """ Converts QgsFeatureRequest to a simple filter string.
        It uses filterExpression, filterFids and filterFid to create new filter string.
        Set filter rect will be ignored.

        .. code-block:: python

            request = QgsFeatureRequest().setFilterFids([1, 5, 7])
            request = request.setFilterExpression("ID IS NOT NULL")

            str_ = request_to_filter(request)
            print(str_)  # "$id IN (1, 5, 6) AND ID IS NOT NULL"

        :param request: QgsFeatureRequest
        :return: filter string
    """
    expression = request.filterExpression()  # QgsExpression there?
    fid = request.filterFid()
    filter_fids = request.filterFids() + ([fid] if fid > -1 else [])

    to_return = []
    if expression:
        if expression.expression():
            to_return.append(expression.expression())

    if filter_fids:
        filter_fids = "$id IN (" + (",".join(map(lambda x: str(x), filter_fids))) + ")"
        to_return.append(filter_fids)

    return " AND ".join(to_return)


def get_prefix_path() -> Optional[Path]:
    """ Returns a prefix path to use to start a QgsApplication.instance.

        Supported platforms:
            - win32
            - linux, always "/usr"

        For other platforms it returns None
    """

    if sys.platform == "win32":
        import qgis.core
        # usually path <qgis>\\apps\\qgis-ltr\\python\\qgis\\core
        path = Path(qgis.core.__path__[0])
        return path.parent.parent.parent

    if sys.platform == "linux":
        return Path("/usr")

    return None
