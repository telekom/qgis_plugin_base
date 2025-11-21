# -*- coding: utf-8 -*-
# SPDX-FileCopyrightText: 2025 Deutsche Telekom Technik GmbH <f.vonstudsinske@telekom.de>
# SPDX-License-Identifier: GPL-3.0-or-later

import os

from pathlib import Path
from typing import Optional, Tuple, List, Dict, Any

from qgis.core import (QgsMapLayer, QgsVectorLayer, QgsWkbTypes, QgsError, QgsRectangle,
                       QgsApplication, QgsField, QgsCoordinateReferenceSystem)


def get_layer_source(layer: QgsMapLayer) -> str:
    """ Returns file path to layer """
    source = layer.source()
    source = source.split("|")[0]  # "path/awdawd.gpkg|name"

    return source


def is_layer_local(layer: QgsMapLayer) -> bool:
    """ Returns True, if layer is on a drive (e.g. C:)

        :param layer: vector layer
        :return: True = Layer wurden lokal gespeichert, False = Layer liegt auf einem Netzlaufwerk
    """
    try:
        return Path(get_layer_source(layer)).is_file()
    except OSError:
        # e.g. when parsing a web address with HTTPS or similar
        return False


def get_layer_table_name(layer: QgsMapLayer) -> Optional[str]:
    """ Returns table name in saved gis file. In GeoPackage it is the table name.

        :param layer: vector layer
        :return: returns table (from gis files supporting multiple layers per file), else None

    """
    source = layer.source()

    if "layername=" not in source:
        return None

    name = source.split("|")[1]  # "path/awdawd.gpkg|name"
    start_text = "layername="
    if name.startswith(start_text):
        # experienced with GeoPackage files
        return name[len(start_text):]

    # not needed yet to implement other checks
    return None


def check_file_type(layer: QgsMapLayer, allowed_source_types: List[str]) -> Tuple[bool, str]:
    """ Check if layer has a valid file ending.

        :param layer:
        :param allowed_source_types:
    """

    src = layer.source()
    path, name = os.path.split(src)
    if not path:
        # temporary layer/no path
        return False, ''

    if not is_layer_local(layer):
        # layer is not avaialable in the file system
        # memory layer or WFS/WMS?
        return False, ''

    # get the layer source (file path), internal table name removed ("|layername=")
    source = get_layer_source(layer)
    filetype = source.split(".")[-1]

    allowed = filetype.lower() in allowed_source_types

    return allowed, filetype


def get_error_list(layer: QgsMapLayer) -> List[str]:
    """ Returns a error list, if `layer.error()` is not empty. """
    error: QgsError = layer.error()
    if not error.isEmpty():
        # some errors here
        messages = [str(error)]
        for i, message in enumerate(error.messageList()):
            messages.append(
                f"i={i}: file='{message.file()}', function='{message.function()}', line='{message.line()}', "
                f"tag='{message.tag()}', message='{message.message()}'")
        return messages

    return []


def clone_vector_layer_format(vector_layer: QgsVectorLayer) -> QgsVectorLayer:
    """ Clones the given vector layer in to an empty vector layer with same crs, fields and geometry type.
        New layer won't have any features.

        :param vector_layer:
        :return: empty and cloned vector layer
    """
    wkb_type: str = QgsWkbTypes.displayString(vector_layer.wkbType())
    authid = vector_layer.dataProvider().crs().authid()
    layer = QgsVectorLayer(f"{wkb_type}?crs={authid}", vector_layer.name() + " - clone", "memory")
    layer.dataProvider().addAttributes(vector_layer.dataProvider().fields().toList())
    layer.updateFields()

    return layer


def get_wfs_layer(type_name: str, url: str, srs_name: str, version: str = "auto", table: str = "", sql: str = "",
                  bbox: Optional[QgsRectangle] = None, auth_cfg: Optional[str] = None) -> QgsVectorLayer:
    """ Returns a vector layer from given params.

        See `constants` "WFS_xx_DEFAULT" names to use default/regular

        :param type_name:
        :param url:
        :param srs_name:
        :param version:
        :param table:
        :param sql:
        :param bbox:
        :param auth_cfg:

    """
    auth_mgr = QgsApplication.authManager()
    ids = auth_mgr.configIds()

    uri = ("""pagingEnabled='true' restrictToRequestBBOX='1' """
           f"""srsname='{srs_name}' typename='{type_name}' """
           f"""url='{url}' version='{version}' """
           f"""table="{table}" """)

    # add only authcfg to the uri, if the authcfg is available in the authmanager
    if auth_cfg and auth_cfg in ids:
        uri += f" authcfg={auth_cfg} "

    if bbox:
        bbox.normalize()
        uri += " bbox=%s,%s,%s,%s" % (bbox.xMinimum(), bbox.yMinimum(),
                                      bbox.xMaximum(), bbox.yMaximum())

    if sql:
        uri += f" sql={sql}"

    layer = QgsVectorLayer(uri, f"{type_name}/auth:{auth_cfg}", "WFS")

    return layer


def get_layers_by_fields(layers: List[QgsVectorLayer], field_map: Dict[str, Any]) -> List[QgsVectorLayer]:
    """ Find layers with given minimum layer structure from field_map.

        .. code-block:: python

            # required field_map structure
            {
                "attribute a": -1,  # field required, field/data type will be not checked
                "attribute b": QVariant.Int  # field required with the given QVariant (data type)
            }

        :param layers:
        :param field_map: E.g. `{'fieldname': QVariant.Int}`, use value `-1` to only look for fieldname
        :return: found layers
    """
    to_return = []

    for layer in layers:
        # Prüft, ob Layer das Feld besitzt mit Datentyp dahinter
        fields = layer.dataProvider().fields()
        everything_ok = True
        for name, field_type in field_map.items():
            index = fields.indexFromName(name)
            if index == -1:
                # Benötigtes Feld existiert nicht
                everything_ok = False
                break

            if fields.at(index).type() != field_type and field_type > -1:
                # Datentyp falsch
                everything_ok = False
                break

        if everything_ok:
            to_return.append(layer)

    return to_return


def create_layer_by_template(name: str, epsg: str, template: Dict[Any, Any]) -> QgsVectorLayer:
    """ Creates new layer with given `epsg` and `template`.

        :param name: layer name
        :param epsg: crs auth id
        :param template: template to use (containing columns, layer type)
        :return:
        :rtype:
    """
    layer_type: str = {
        QgsWkbTypes.Point: "Point",
        QgsWkbTypes.LineString: "Linestring",
        QgsWkbTypes.Polygon: "Polygon",
        QgsWkbTypes.NoGeometry: "NoGeometry",
    }[template['WKBTYPE']]

    if not epsg.casefold().startswith("epsg:"):
        epsg = f"EPSG:{epsg}"

    new_layer = QgsVectorLayer(layer_type + "?crs=" + epsg, name, "memory")

    # Erstelle Attribut-Listen für Provider
    attributes = []
    for name, value in template['Attributes'].items():
        field = QgsField(name, value['type'])
        attributes.append(field)

    new_layer.dataProvider().addAttributes(attributes)
    new_layer.updateFields()

    return new_layer


def get_layer_crs(layer: QgsMapLayer) -> Tuple[bool, QgsCoordinateReferenceSystem]:
    """ Returns tuple with available crs on data provider and crs validity.

        :param layer: map layer
        :return: bool (0) -> True = crs set on QgsDataProvider or False only set on map layer, crs (1)
    """
    layer_crs = layer.dataProvider().crs()
    if layer_crs.authid() == "":
        layer_crs = layer.crs()
        return False, layer_crs

    return True, layer_crs


def check_crs(layer: QgsVectorLayer, crs: str) -> Tuple[bool, str]:
    """ compares crs names

        :param layer:
        :param crs: crs.authid() (e.g. "EPSG:3857")
        :return: bool (0, True = crs is provider crs) and found authid (1)
    """
    if layer.dataProvider().crs().authid().lower() != crs.lower():
        return False, layer.dataProvider().crs().authid()

    return True, layer.dataProvider().crs().authid()