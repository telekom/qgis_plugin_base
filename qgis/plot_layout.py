# -*- coding: utf-8 -*-
# SPDX-FileCopyrightText: 2025 Deutsche Telekom Technik GmbH <f.vonstudsinske@telekom.de>
# SPDX-License-Identifier: GPL-3.0-or-later

from pathlib import Path
from qgis.PyQt.QtXml import QDomElement
from qgis.core import (QgsPrintLayout, QgsLayoutItem, QgsLayoutItemMap,
                       QgsLayoutItemPicture, QgsLayoutItemLegend,
                       QgsLayoutItemLabel, QgsLayoutItemScaleBar,
                       QgsLayoutItemPage, QgsLayoutSize,
                       QgsApplication, QgsPageSize)
from typing import Dict, List, Optional, Tuple


class PlotLayout:
    """ PlotLayout for plot menu.

        Syntax for grouped elements with static label and label text per page (changeable by user):
            item_static_text_xx (if set, look for item_page_text) /QgsLayoutItemLabel
            item_page_text_xx (only visible, if item_static_text is set) /QgsLayoutItemLabel
                                on user/page text item you can setup a regex string starting with * in label.
                                Entered text will we used
            When you want to use different templates with name collisions,
            be sure to use in your own templates other element ids, e.g. with an extra suffix for your team/company.

        Syntax for unique elements:
            [necessary]
            item_map /QgsLayoutItemMap
            item_company_icon /QgsLayoutItemPicture

            [optional]
            item_page_current /QgsLayoutItemPicture
            item_page_max /QgsLayoutItemPicture
            item_legend /QgsLayoutItemLegend
            item_title /QgsLayoutItemLabel
            item_minimap /QgsLayoutItemPicture
            item_map_scale_text /QgsLayoutItemLabel
            item_map_scale_bar /QgsLayoutItemScaleBar

        :param name: layout name
        :param path: path in template folder, starting from plots.xml
        :param group: internal group name, can be empty string
        :param layout: print layout with items
        :param item_list: all items in print layout
        :param dom_element: Element from the XML file (plots.xml)
    """
    def __init__(self, name: str, path: str, group: str,
                 layout: QgsPrintLayout, item_list: List[QgsLayoutItem],
                 dom_element: QDomElement,
                 filepath: Optional[str] = None):

        self.__name = name
        self.__path = path
        self.__filepath = filepath
        self.__group = group
        self.__layout = layout
        self.__item_list = item_list
        self.__loaded_ids: List[str] = []
        self.__parent = None
        self.__dom_element = dom_element
        self.__icons: Dict[str, str] = {}
        self.__defaults: Dict[str, Tuple[str, str]] = {}

        self.item_map: Optional[QgsLayoutItemMap] = None
        self.id_item_map = "item_map"
        self.item_crs: Optional[QgsLayoutItemLabel] = None
        self.id_item_crs = "item_crs"

        # optional items
        self.item_company_icon: Optional[QgsLayoutItemPicture] = None
        self.id_item_company_icon = "item_company_icon"
        self.item_map_rotation_icon: Optional[QgsLayoutItemPicture] = None
        self.id_item_map_rotation_icon = "item_map_rotation_icon"
        self.item_page_current: Optional[QgsLayoutItemLabel] = None
        self.id_item_page_current = "item_page_current"
        self.item_date: Optional[QgsLayoutItemLabel] = None
        self.id_item_date = "item_date"
        self.item_legend: Optional[QgsLayoutItemLegend] = None
        self.id_item_legend = "item_legend"
        self.item_title: Optional[QgsLayoutItemLabel] = None
        self.id_item_title = "item_title"
        self.item_minimap: Optional[QgsLayoutItemMap] = None
        self.id_item_minimap = "item_minimap"
        self.item_map_scale_text: Optional[QgsLayoutItemLabel] = None
        self.id_item_map_scale_text = "item_map_scale_text"
        self.item_page_max: Optional[QgsLayoutItemLabel] = None
        self.id_item_page_max = "item_page_max"
        self.item_map_scale_bar: Optional[QgsLayoutItemScaleBar] = None
        self.id_item_map_scale_bar = "item_map_scale_bar"
        self.orientation: Optional[QgsLayoutItemPage.Orientation] = None
        self.size: Optional[QgsLayoutSize] = None

        self.necessary = [self.id_item_map, self.id_item_crs]
        self.known_names = self.necessary + [self.id_item_page_current, self.id_item_date,
                                             self.id_item_legend, self.id_item_title,
                                             self.id_item_minimap, self.id_item_map_scale_text,
                                             self.id_item_page_max, self.id_item_map_scale_bar,
                                             self.id_item_company_icon, self.id_item_map_rotation_icon]

        # mappings between static text and user editable boxes
        # key: (static text, user text, {'key': 'str value'})
        # key: (..., {'*': 'regex string for line edit', '#': 'Line Edit tooltip'})
        self.grouped_items: Dict[str, Tuple[QgsLayoutItemLabel, QgsLayoutItemLabel, Dict[str, str]]] = {}

        self.setup()

    def get_page_size(self) -> Optional[QgsPageSize]:
        size = self.page.pageSize()
        for entry in QgsApplication.pageSizeRegistry().entries():

            # orientation x
            swapped = QgsLayoutSize(entry.size.height(),
                                    entry.size.width(),
                                    entry.size.units())
            if entry.size == size:
                return entry

            # orientation y
            if swapped == size:
                return entry

        return None

    def set_parent(self, parent: 'PlotLayer'):
        self.__parent = parent

    def get_parent(self) -> 'PlotLayer':
        return self.__parent

    def setup(self):
        """ loads all items and make them accessible.
            Do some checks to keep layout compatibility
        """
        for item in self.item_list:
            id_ = item.id()
            name = type(item).__name__
            item_str = f"{name}(id: '{item.id()}', uuid: '{item.uuid()}', path: '{self.path}')"

            if hasattr(item, "linkedMap") and not isinstance(item, QgsLayoutItemPicture):
                linked_map = item.linkedMap()
                if linked_map is None:
                    raise ValueError(f"{item_str} has no map linked")

            if not id_:
                # no id set
                continue

            if id_ in self.__loaded_ids:
                raise NameError(f"{item_str} in template '{self.path}' is used twice")
            self.__loaded_ids.append(id_)

            setattr(self, id_, item)

            # make standard item accessible
            if id_ in self.known_names:
                continue

            # is this a static text? try to find page text label
            if id_.startswith("item_static_text_") and isinstance(item, QgsLayoutItemLabel):
                id_int = id_[len("item_static_text_"):]
                reference_item: QgsLayoutItemLabel = self.layout.itemById(f"item_page_text_{id_int}")
                if reference_item is not None:
                    # delimiter |
                    opt_map = {}
                    for part in reference_item.text().split("|"):
                        if part.startswith(("#", "*")):
                            opt_map[reference_item.text()[0]] = reference_item.text()[1:]
                    self.grouped_items[id_int] = (item, reference_item, opt_map)

        for name in self.necessary:
            if getattr(self, name, None) is None:
                raise AttributeError(f"template '{self.path}' has no '{name}' item")

        self.grouped_items = {k: v for k, v in sorted(self.grouped_items.items(),
                                                      key=lambda x: self.get_sort_index(x[1][0]))}

        # check page count and collection
        collection = self.layout.pageCollection()
        if collection.pageCount() != 1:
            raise ValueError(f"template '{self.path}' has an incompatible pageCount "
                             f"of {collection.pageCount()}, expecting 1")
        self.orientation: QgsLayoutItemPage.Orientation = self.page.orientation()
        self.size: QgsLayoutSize = self.page.pageSize()

        # load xml data
        # 1. load icon data
        icons_elements: QDomElement = self.dom_element.firstChildElement("icons")
        plots_xml_folder = self.dom_element.attribute("plots_xml_folder")
        icon_elements = icons_elements.elementsByTagName("icon")
        for i in range(icon_elements.size()):
            icon_element: QDomElement = icon_elements.item(i).toElement()
            item_id = icon_element.attribute("name")
            file = icon_element.attribute("file")
            if not item_id:
                raise ValueError(f"invalid icon.name attribute for icon element index {i}")

            self.__icons[item_id] = (Path(plots_xml_folder) / file).as_posix()

        # 2. load defaults
        defaults_element = self.dom_element.firstChildElement("defaults").childNodes()
        for i in range(defaults_element.size()):
            element: QDomElement = defaults_element.item(i).toElement()
            label = element.attribute("label")
            type_ = element.attribute("type")
            value = element.attribute("value")

            if not label:
                raise ValueError(f"missing default.label for element index {i}")
            if type_ not in ('function', 'value'):
                raise ValueError(f"invalid default.type for element index {i}")

            self.__defaults[label] = (type_, value)

    @staticmethod
    def get_sort_index(item: QgsLayoutItemLabel) -> float:
        """ Splits label item text into prefix number for sorting and tail.
            If sorting index is not given, then the text is returned, else index.

            Splitting char: #
        """
        text = item.text()
        prefix, *tail = text.split("#")
        if not tail:
            return float("inf")

        if prefix.isnumeric():
            item.setText("#".join(tail))
            return float(int(prefix))

        return float("inf")

    def clone(self) -> 'PlotLayout':
        """ Return a cloned object with no information about options and layer visibility.
            LayoutItems are not cloned, only referenced to original.
        """
        obj = self.__class__(self.name, self.path, self.group, self.layout, self.item_list)

        return obj

    @property
    def name(self):
        return self.__name

    @property
    def path(self):
        return self.__path

    @property
    def dom_element(self):
        return self.__dom_element

    @property
    def page(self) -> QgsLayoutItemPage:
        return self.layout.pageCollection().page(0)

    @property
    def group(self):
        return self.__group

    @property
    def layout(self):
        return self.__layout

    @property
    def filepath(self):
        return self.__filepath

    @property
    def item_list(self):
        return self.__item_list

    @property
    def icons(self):
        return self.__icons

    @property
    def defaults(self):
        return self.__defaults

    def get_icon(self, item_id: str):
        return self.__icons.get(item_id, "")

    def get_default(self, item_id: str):
        return self.__defaults.get(item_id, None)

    def __repr__(self):
        name = self.__class__.__name__
        return f"{name}(name='{self.name}', path='{self.path}', group='{self.group}')"
