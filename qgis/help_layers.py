# -*- coding: utf-8 -*-
# SPDX-FileCopyrightText: 2025 Deutsche Telekom Technik GmbH <f.vonstudsinske@telekom.de>
# SPDX-License-Identifier: GPL-3.0-only

from qgis.core import QgsProject, QgsVectorLayer, QgsMapLayer

from typing import List, Optional, Dict


class HelpLayerGroups:
    """ Helper class to handle help layers. Can only be used with active QgsProject

        :param name: group name
    """

    def __init__(self, names: List[str]):
        self._names = names

        self._handled_layer_ids: Dict[str, List[str]] = {}

    @property
    def names(self):
        return self._names

    def get_group(self, create_new: bool = True, name: Optional[str] = None):
        """ creates new or uses existing group

            :param create_new: create group when missing
            :param name: name to use in this helper groups, defaults to first element in group
        """
        if not name:
            name = self.names[0]

        if name not in self.names:
            self.names.append(name)

        root = QgsProject.instance().layerTreeRoot()
        group = root.findGroup(name)

        if group is None and create_new:
            # create a new group with name
            group = root.insertGroup(0, name)

        return group

    def add_help_layer(self, layer: QgsMapLayer, name: Optional[str] = None):
        """ add layer to group. """

        # test if layer is already loaded to qgis instance
        if not QgsProject.instance().mapLayer(layer.id()):
            # add layer silence
            layer = QgsProject.instance().addMapLayer(layer, False)
        layer_id = layer.id()

        # use or create group
        group = self.get_group(name=name)
        if layer_id not in group.findLayerIds():
            # insert only, when not already loaded
            group.insertLayer(0, layer)
        self._handled_layer_ids.setdefault(name, [])
        self._handled_layer_ids[name].append(layer.id())

        return layer

    def clear_group(self, name: Optional[str] = None):
        """ removes all layers and this group from instance """
        group = self.get_group(create_new=False, name=name)
        if group is None:
            return

        layers = group.findLayerIds()
        if layers:
            for layer in layers:
                if isinstance(layer, QgsVectorLayer):
                    if layer.isEditable():
                        layer.rollBack()
            QgsProject.instance().removeMapLayers(layers)

        try:
            QgsProject.instance().layerTreeRoot().removeChildNode(group)
        except RuntimeError:
            ...

        if name in self._handled_layer_ids:
            del self._handled_layer_ids[name]

    def clear_all_groups(self):
        for name in self.names:
            self.clear_group(name=name)

    def unload_group(self, name: Optional[str] = None):
        """ unloads all layer from _handled_layer_ids list.
            If group is empty, group will be removed. """
        group = self.get_group(name=name, create_new=False)
        if not group:
            # no group create with this
            return

        self.clear_group(name=name)

    def unload_all_groups(self):
        """ unloads all layer from _handled_layer_ids list.
            If group is empty, group will be removed. """

        for name in self.names:
            self.unload_group(name=name)
