# -*- coding: utf-8 -*-
# SPDX-FileCopyrightText: 2025 Deutsche Telekom Technik GmbH <f.vonstudsinske@telekom.de>
# SPDX-License-Identifier: GPL-3.0-or-later

import os
import processing

from typing import List, Optional

from qgis.core import (QgsVectorLayer, QgsProject, QgsWkbTypes, QgsField, QgsFeature,
                       QgsGeometry, QgsFeatureRequest, QgsPointXY, QgsFeatureSink)
from qgis.PyQt.QtCore import QVariant
from qgis.PyQt.QtWidgets import QLabel, QProgressBar

from .geometry import get_multi_polyline, is_feat_geometry_valid
from ..constants import RADIUS_BUFFER, EPSILON


def change_layer_epsg(src_layer: QgsVectorLayer, target_epsg: str = "EPSG:3857"):
    """ resaves vector layer with new crs

        :param src_layer: vector layer
        :param target_epsg: target epsg name
        :return: new vector layer with changed provider crs
    """
    from builtins import unicode

    if not target_epsg.casefold().startswith("epsg:"):
        target_epsg = f"EPSG:{target_epsg}"

    # remove layer from current QgsProject to replace file
    layer_name = src_layer.sourceName()
    path_in = unicode(src_layer.dataProvider().dataSourceUri())
    path_out = os.path.dirname(unicode(src_layer.dataProvider().dataSourceUri()))
    QgsProject.instance().removeMapLayers([src_layer.id()])

    parameter = {'INPUT': path_in, 'TARGET_CRS': target_epsg, 'OUTPUT': path_out}

    path_in = path_in.split("|")[0]
    path_new_layer = processing.run('qgis:reprojectlayer', parameter)["OUTPUT"]
    try:
        os.rename(path_in, path_in + "_backup.gpkg")
        os.rename(path_new_layer, path_in)
    except FileExistsError:
        pass

    layer = QgsVectorLayer(path_in, layer_name)
    QgsProject.instance().addMapLayer(layer)

    return layer


def get_field_errors_by_fields(layer: QgsVectorLayer, field_map: dict) -> List[str]:
    """ Returns field errors for compatibility checks with given field_map.

        .. code-block:: python

            # required field_map structure
            {
                "attribute a": -1,  # field required, field/data type will be not checked
                "attribute b": QVariant.Int  # field required with the given QVariant (data type)
            }

        :param layer:
        :param field_map: e.g. `{'fieldname': QVariant.Int}`, use value `-1` to only look for fieldname
        :return: list with error texts
    """
    to_return = []

    # Prüft, ob Layer das Feld besitzt mit Datentyp dahinter
    fields = layer.dataProvider().fields()
    for name, required_field_types in field_map.items():
        if required_field_types == -1:
            field_type_value = []
        else:
            field_type_value = required_field_types

        field_type_values = [field_type_value] if not isinstance(field_type_value, (list, tuple)) else field_type_value

        if field_type_values:
            # join the allowed field type names
            field_types = ", ".join(QVariant.typeToName(variant) for variant in field_type_values)
        else:
            # field must only exist
            field_types = ""

        # check, if the field exists
        index = fields.indexFromName(name)
        if index == -1:
            if field_types:
                to_return.append(f"Attributfeld `{name}` ({field_types}) fehlt.")
            else:
                to_return.append(f"Attributfeld `{name}` fehlt.")
            continue

        current_type = fields.at(index).type()
        if field_type_values and current_type not in field_type_values:
            to_return.append(f"Datentyp von Attribut "
                             f"`{name}` ist `{current_type}` ({QVariant.typeToName(current_type)}), "
                             f"muss aber vom Typ {field_types} sein.")
            continue

    return to_return



def get_orthogonal_split_layer(line_layer: QgsVectorLayer, distance: float = 0.25,
                               progressbar: Optional[QProgressBar] = None,
                               lbl: Optional[QLabel] = None) -> QgsVectorLayer:
    """ Erstellt einen neuen temporären Layer,
        der zur Verschneidung mit einem anderen Linienlayer
        benötigt wird.
        -> Erzeugen von Verschneidungslinien orthogonal zur Geometrie
        -> benachbarte Bestandstrassen

        :param line_layer: Einzelgeometrie und Linien-Layer mit nur benötigten Features/Geometrien vorhanden.
                           Linien dürfen nur jeweils aus genau zwei Knotenpunkten bestehen.
        :param distance: Distanz vom Linienende, wo ein Linienpunkt erzeugt werden soll
                              -> Zahl muss dem vorliegendem KBS entsprechen (bspw. Meter)
                              -> Bestandstrassen: 0.25 empfohlen
        :param progressbar: QProgressBar (es wird pro Feature +1 gerechnet)
        :param lbl: Statusanzeige

        :return: Neuer Linienlayer

        :raises TypeError: Geometrietyp-Fehler
    """
    if isinstance(lbl, QLabel):
        lbl.setText("Erzeuge Verschneidungslayer für Parallellauf (Bestandstrasse)")

    if line_layer.geometryType() != QgsWkbTypes.LineGeometry:
        raise TypeError("Vector-Layer `%s` ist kein Linienl-Layer" % line_layer.id())

    if line_layer.wkbType() != QgsWkbTypes.LineString:
        raise TypeError("Vector-Layer `%s` ist kein Einzel-Geometrie-Layer" % line_layer.id())

    # Splitlayer erstellen
    split_layer = QgsVectorLayer('LineString?crs={}'.format(line_layer.dataProvider().crs().authid()),
                                 'layer',
                                 'memory')
    split_layer.dataProvider().addAttributes(
        [
            QgsField("ID", QVariant.LongLong),
            QgsField("REF_ID", QVariant.LongLong)
        ]
    )
    split_layer.updateFields()

    if isinstance(progressbar, QProgressBar):
        progressbar.setValue(0)
        progressbar.setMaximum(line_layer.featureCount() + 1)

    counter = 1
    created_well_known_texts = set()  # Verhindert Duplikate
    used_points = []  # an bereits genutzte Punkte für Schnittlinie

    for feature in line_layer.getFeatures():

        geometry = feature.geometry()

        if isinstance(progressbar, QProgressBar):
            progressbar.setValue(progressbar.value() + 1)

        if not is_feat_geometry_valid(feature):
            continue

        new_features = []

        start, *_, end = geometry.asPolyline()
        azimuth_start = start.azimuth(end)

        # print(azimuth_start, azimuth_end)

        # Zeichne Referenzlinie am Startpunkt dieser Geometrie
        # Feature-Geometrie wird orthogonal zur Originalgeometrie angelegt
        if start not in used_points:
            used_points.append(start)
            nf_1 = QgsFeature(split_layer.fields())
            nf_1['ID'] = counter
            nf_1['REF_ID'] = feature.id()
            new_line_1 = [
                start.project(distance, azimuth_start - 90),  # gehe in die eine Richtung
                start.project(distance, azimuth_start + 90)  # gehe in die andere Richtung
            ]
            nf_1.setGeometry(QgsGeometry.fromPolylineXY(new_line_1))
            k0 = "%s-%s" % (new_line_1[0].asWkt(), new_line_1[1].asWkt())
            k1 = "%s-%s" % (new_line_1[1].asWkt(), new_line_1[0].asWkt())
            if k0 not in created_well_known_texts and k1 not in created_well_known_texts:
                created_well_known_texts |= {k0, k1}
                new_features.append(nf_1)

        counter += 1

        if end not in used_points:
            used_points.append(end)
            nf_2 = QgsFeature(split_layer.fields())
            nf_2['ID'] = counter
            nf_2['REF_ID'] = feature.id()
            new_line_2 = [
                end.project(distance, azimuth_start - 90),  # gehe in die eine Richtung
                end.project(distance, azimuth_start + 90)  # gehe in die andere Richtung
            ]
            nf_2.setGeometry(QgsGeometry.fromPolylineXY(new_line_2))
            k0 = "%s-%s" % (new_line_2[0].asWkt(), new_line_2[1].asWkt())
            k1 = "%s-%s" % (new_line_2[1].asWkt(), new_line_2[0].asWkt())
            if k0 not in created_well_known_texts and k1 not in created_well_known_texts:
                created_well_known_texts |= {k0, k1}
                new_features.append(nf_2)

        counter += 1

        if new_features:
            split_layer.dataProvider().addFeatures(new_features)

    # Snappen
    # Trasselayer auf sich selber einrasten
    paramaters_snap = {'BEHAVIOR': 0,
                       'INPUT': split_layer,
                       'OUTPUT': 'memory:',
                       'REFERENCE_LAYER': split_layer,
                       'TOLERANCE': 0.01}
    split_layer = processing.run('qgis:snapgeometries', paramaters_snap)['OUTPUT']

    parameters_fix = {'INPUT': split_layer, 'OUTPUT': 'memory:'}
    split_layer = processing.run('native:fixgeometries', parameters_fix)['OUTPUT']

    parameters_m2s = {'INPUT': split_layer, 'OUTPUT': 'memory:'}
    split_layer = processing.run('native:multiparttosingleparts', parameters_m2s)['OUTPUT']

    parameters_fix = {'INPUT': split_layer, 'OUTPUT': 'memory:'}
    split_layer = processing.run('qgis:deleteduplicategeometries', parameters_fix)['OUTPUT']

    parameters_fix = {'INPUT': split_layer, 'OUTPUT': 'memory:'}
    split_layer = processing.run('native:fixgeometries', parameters_fix)['OUTPUT']

    parameters_m2s = {'INPUT': split_layer, 'OUTPUT': 'memory:'}
    split_layer = processing.run('native:multiparttosingleparts', parameters_m2s)['OUTPUT']

    return split_layer


def get_singled_line_layer(line_layer: QgsVectorLayer,
                           progressbar: Optional[QProgressBar] = None,
                           ignore_edit_mode: bool = False) -> QgsVectorLayer:
    """ Creates a new vector layer with only single lines.

        Fallback function for `processing.run("native:multiparttosingleparts", Dict[str, Any])`,
        because QGIS crash sometimes

        :param line_layer: vector layer to convert
        :param progressbar: Qt progress, per feature one bar value
        :param ignore_edit_mode: ignore current edit (read/write) from layer
        :return: new vector layer
    """

    if line_layer.isEditable() and not ignore_edit_mode:
        raise TypeError("layer is not allowed to be in edit mode!")

    if isinstance(progressbar, QProgressBar):
        progressbar.setValue(0)
        progressbar.setMaximum(line_layer.featureCount())

    wkb_type: str = QgsWkbTypes.displayString(QgsWkbTypes.LineString)
    authid = line_layer.dataProvider().crs().authid()
    new_layer = QgsVectorLayer(f"{wkb_type}?crs={authid}", line_layer.name() + " - singled", "memory")
    new_layer.dataProvider().addAttributes(line_layer.dataProvider().fields().toList())
    new_layer.updateFields()
    field_names = new_layer.fields().names()

    new_features = []
    for feature in line_layer.getFeatures():
        if isinstance(progressbar, QProgressBar):
            progressbar.setValue(progressbar.value() + 1)

        if not is_feat_geometry_valid(feature):
            continue

        for line in get_multi_polyline(feature.geometry()):

            nf = QgsFeature(new_layer.fields())
            nf.setGeometry(QgsGeometry.fromPolylineXY(line))
            for attr in field_names:
                nf[attr] = feature[attr]
            new_features.append(nf)

    new_layer.dataProvider().addFeatures(new_features)
    return new_layer


def get_singled_line_layer_v2(line_layer: QgsVectorLayer) -> QgsVectorLayer:
    """ Creates a new vector layer with only single lines.
        Invalid geometries with geometry.isGeosValid()=False, geometry.isNull()=True or geometry.isEmpty()=True
        will be ignored.

        In the case of multi-line strings, invalid parts will be ignored.

        Fallback function for `processing.run("native:multiparttosingleparts", Dict[str, Any])`,
        because QGIS crash sometimes

        :param line_layer: vector layer to convert
        :return: new vector layer
    """

    # clone the vector layer format (attribute fields)
    # hard coded wkb type is LineString
    authid = line_layer.dataProvider().crs().authid()
    new_layer = QgsVectorLayer(f"LineString?crs={authid}", line_layer.name() + " - clone", "memory")
    new_layer.dataProvider().addAttributes(line_layer.dataProvider().fields().toList())
    new_layer.updateFields()

    for feature in line_layer.getFeatures():

        # get the geometry
        geometry = feature.geometry()

        if not geometry.isGeosValid() or geometry.isNull() or geometry.isEmpty():
            # skip invalid geometry
            continue

        # in the case of a multi poly line, handle each poly line
        multi_poly_line = geometry.asMultiPolyline() if geometry.isMultipart() else [geometry.asPolyline()]
        for poly_line in multi_poly_line:

            len_poly_line = len(poly_line)

            if len_poly_line < 2:
                # skip poly lines, where only 1 or zero vertices are available
                continue

            elif len_poly_line == 2 and poly_line[0].compare(poly_line[-1], EPSILON):
                # first and last vertex are equal, ignore this line with length=0
                continue

            # clone the feature
            nf = QgsFeature(feature)
            nf.setId(-1)
            # apply the new poly_line
            nf.setGeometry(QgsGeometry.fromPolylineXY(poly_line))

            new_layer.dataProvider().addFeature(nf, QgsFeatureSink.FastInsert)

    return new_layer


def get_temp_layer_from_radius(layer: QgsVectorLayer, points: List,
                               radius: int = RADIUS_BUFFER) -> QgsVectorLayer:
    """ Creates a layer copy, which has been reduced to the features within a certain radius.
        The distance is given in meters and is calculated cartographically.

        :param layer: source layer for the reduction
        :param points: points around which the radius buffer is created
        :param radius: radius around the given points in meters (kartesisch), defaults to _constants.RADIUS_BUFFER
        :return: a reduced copy of the given vector layer
    """
    new_feats = []
    epsg = layer.crs().postgisSrid()
    uri = "LineString?crs=epsg:" + str(epsg) + "&field=id:integer""&index=yes"

    # collect buffered features
    for point in points:
        geometry = QgsGeometry().fromPointXY(point)
        geom_buffer = geometry.buffer(radius, -1)

        req = QgsFeatureRequest().setFilterRect(geom_buffer.boundingBox())
        for feat in layer.getFeatures(req):
            if feat.geometry().intersects(geom_buffer):
                if feat not in new_feats:
                    new_feats.append(feat)

    mem_layer = QgsVectorLayer(uri,
                               'line',
                               'memory')

    prov = mem_layer.dataProvider()

    for i, feat in enumerate(new_feats):
        feat.setAttributes([i])

    prov.addFeatures(new_feats)

    return mem_layer


def get_temp_layer_from_line(layer: QgsVectorLayer, points: List[QgsPointXY],
                             radius: int = RADIUS_BUFFER) -> QgsVectorLayer:
    """ Creates a layer copy, which has been reduced to the features within a line buffer.
        The distance is given in layer coordinates. E.g. metres or degree.

        :param layer: source layer for the reduction
        :param points: points around which the radius buffer is created
        :param radius: radius around the given points in layer coordinates, defaults to _constants.RADIUS_BUFFER
        :return: a reduced copy of the given vector layer

    """

    e_g = QgsGeometry.fromRect(QgsGeometry.fromPolylineXY(points).boundingBox())
    e_g = e_g.buffer(radius, -1)

    mem_layer = layer.materialize(QgsFeatureRequest().setFilterRect(e_g.boundingBox()))
    mem_layer.setName("memory layer")

    return mem_layer
