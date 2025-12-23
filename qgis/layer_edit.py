# -*- coding: utf-8 -*-
# SPDX-FileCopyrightText: 2025 Deutsche Telekom Technik GmbH <f.vonstudsinske@telekom.de>
# SPDX-License-Identifier: GPL-3.0-only

from typing import List, Tuple

from qgis.core import QgsVectorLayer, QgsEditError, QgsPointXY, QgsGeometry

from .geometry import get_polyline, is_point_in_polylist
from .poly_line_wrapper import PolylineWrapper


class EditLayerCache:
    """ Based on QGIS example `from qgis.core.additions.edit import edit` class.

        :param commit_on_success: True to auto commit on exit-method, False to keep layer modified
    """

    def __init__(self, layer: QgsVectorLayer, commit_on_success: bool = True) -> None:
        if not isinstance(layer, QgsVectorLayer):
            raise TypeError("layer must be type of QgsVectorLayer")
        self.layer = layer

        # store current changes for commit later
        self.was_editable = layer.isEditable()
        self.commit_on_success = commit_on_success

    def __enter__(self):
        if not self.layer.startEditing() and not self.layer.isEditable():
            raise QgsEditError(f"layer '{self.layer.id()}' could not be set into edit mode")
        return self.layer

    def __exit__(self, ex_type, ex_value, traceback):
        if ex_type is None:
            if self.commit_on_success:
                # commit changes
                # may layer will stay in edit mode, when layer was in edit mode before
                if not self.layer.commitChanges(stopEditing=not self.was_editable):
                    raise QgsEditError(self.layer.commitErrors())
            return True
        else:
            self.layer.rollBack()
            return False


def add_vertices(vertices: List[Tuple[int, QgsPointXY]], layer: QgsVectorLayer,
                 commit: bool = False):
    """ Updates features geometry and add vertex to poly line.
        Changes will be done in vector layers edit buffer, not on the provider!

        :param vertices: List of tuples with fid and point
        :param layer: Line layer where to add point in given fid
        :param commit: commit changes
    """

    stop_editing = not layer.isEditable()
    if not layer.isEditable():
        layer.startEditing()

    layer.beginEditCommand("add_vertices")
    for fid, point in vertices:
        geometry = layer.getGeometry(fid)
        poly = get_polyline(geometry)

        if is_point_in_polylist(point, poly):
            # point already in list, skip it
            continue

        # add point to geometry with poly wrapper
        wrapper = PolylineWrapper.from_point_list(poly)
        distance = wrapper.get_distance_on_line(point)  # get distance
        wrapper.insert_point_in_line(distance)  # insert at distance
        layer.changeGeometry(fid, QgsGeometry.fromPolylineXY(wrapper.as_point_list()))

    layer.endEditCommand()

    if commit:
        layer.commitChanges(stopEditing=stop_editing)