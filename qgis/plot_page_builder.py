# -*- coding: utf-8 -*-
# SPDX-FileCopyrightText: 2026 Deutsche Telekom IT GmbH <sandro.kerner@telekom.de>
# SPDX-License-Identifier: GPL-3.0-only

from pathlib import Path


from qgis.core import (QgsPrintLayout, QgsLayoutItemPage, QgsLayoutItem,
                       QgsLayoutItemMap, QgsLayoutItemPicture)

from typing import Dict, NamedTuple

from .plot_item_copy import CopyLayoutItem

from .plot_layer import PlotLayer
from .plot_layout_templates import PlotLayoutTemplates


class PageCreationResult(NamedTuple):
    """ Objects created for one page in the print layout
        :returns page index, page, item dictionary of items with element id
    """

    index: int
    page: QgsLayoutItemPage
    items: Dict[str, QgsLayoutItem]


class PageBuilder():
    """ Create the new page with the copied items from the layout template """

    def __init__(self, target_layout: QgsPrintLayout, layouts: PlotLayoutTemplates, plot_layer: PlotLayer):
        """ Initializes PageBuilder """
        self.layout = target_layout
        self.layouts = layouts
        self.plot_layer = plot_layer
        self.__item_copier = CopyLayoutItem(self)
        self.__page_picture_item_with_new_map: Dict[QgsLayoutItemPicture, QgsLayoutItemMap] = {}

    def create_page(self, file: str) -> PageCreationResult:
        """ Creates a page.
            Most individual options per layout item will be copied to new layout item.
        """
        layout = self.layouts[file]  # layout to use as new page
        item_page = QgsLayoutItemPage(self.layout)
        item_page.setPageSize(layout.page.pageSize())
        self.layout.pageCollection().addPage(item_page)
        index = self.layout.pageCollection().pageCount() - 1

        page_items = {}
        map_old_new = {}
        map_new_old = {}

        linked_maps = {}  # new item, old map

        for item in layout.item_list:

            if isinstance(item, QgsLayoutItemPage):
                continue

            new_item = self.__item_copier.run(item, self.layout, linked_maps).new_item
            new_item.setZValue(item.zValue())  # stacking/overlapping

            new_item.setReferencePoint(item.referencePoint())

            new_item.attemptMove(item.positionWithUnits(), page=index)
            new_item.attemptResize(item.sizeWithUnits())

            if item.id():
                page_items[item.id()] = new_item
                new_item.setId(f"{item.id()}_p{index}")

            if (icon_path := layout.get_icon(item.id())) and Path(icon_path).is_file():
                # icon path exists
                if hasattr(new_item, "setPicturePath"):
                    new_item.setPicturePath(icon_path)
                    new_item.refreshPicture()

            # mappings
            map_old_new[item] = new_item
            map_new_old[new_item] = item

        # load linked maps
        for new_item, old_map in linked_maps.items():
            new_item.setLinkedMap(map_old_new.get(old_map, None))
            new_linked_map = map_old_new.get(old_map, None)
            new_item.setLinkedMap(new_linked_map)
            if isinstance(new_item, QgsLayoutItemPicture):
                self.__page_picture_item_with_new_map[new_item] = new_linked_map

        return PageCreationResult(index, item_page, page_items)
