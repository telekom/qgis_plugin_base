# -*- coding: utf-8 -*-
# SPDX-FileCopyrightText: 2025 Deutsche Telekom Technik GmbH <f.vonstudsinske@telekom.de>
# SPDX-License-Identifier: GPL-3.0-only

from pathlib import Path

from qgis.PyQt.QtXml import QDomDocument
from qgis.PyQt.QtCore import QObject, pyqtSignal
from qgis.core import (QgsPrintLayout, QgsProject, QgsReadWriteContext,
                       QgsApplication, QgsPointXY, QgsRectangle)
from typing import Dict


from .plot_layout import PlotLayout
from ..functions import get_files


class PlotLayoutTemplates(QObject):
    """ Containing all configured layout files from QGIS.
        Must be defined in templates/plots/xx/plots.xml.

        get layout from file: PlotLayoutTemplates["plots/xasd.qpt"]

        .. code-block:: python

            # example for loading in plot plugin
            self.layouts: PlotLayoutTemplates = self.add_module(
                "PlotLayoutTemplates", PlotLayoutTemplates,
                plot_plugin_plots_dir=[self.get_plugin().plots_dir])
            self.layouts.load_default_paths()  # initialize default paths (QGIS layout paths)
            self.layouts.load_plots()  # load plots to template

        .. code-block:: python

            # example for loading from another plugin
            my_own_plot_directory = [...]
            layouts: PlotLayoutTemplates = self.add_module(
                "PlotLayoutTemplates", PlotLayoutTemplates,
                plot_plugin_plots_dir=[my_own_plot_directory])
            self.layouts.load_plots()  # load plots to template from my_own_plot_directory


        :param plot_plugin_plots_dir: Predefined list where to find some layouts
    """
    # pyqtSignal(current step, max steps, text)
    progressChanged = pyqtSignal(int, int, str, name="progressChanged")

    def __init__(self, *args, **kwargs):
        QObject.__init__(self, kwargs.get("parent"))

        self.plots = []
        self.plots.extend(kwargs.get("plot_plugin_plots_dir", []))

        # will be filled later in self.load_plots
        self.__layouts: Dict[str, PlotLayout] = {}
        self.__paths = set()
        self.exceptions = []
        self.document = QDomDocument()
        self.document.setContent("<plots/>", False)

    def load_default_paths(self):
        """ Load default paths for XML/Template loading.
            In these paths we expect the XML template files.

            Added paths:
                - QGIS layoutTemplatePaths
                - qgisSettingsDirPath() + "/composer_templates"
        """

        # default own plugin layouts
        # try to find layouts in qgis profile path
        # https://github.com/qgis/QGIS/search?q=composer_templates
        self.plots.append(QgsApplication.instance().qgisSettingsDirPath() + "/composer_templates")
        self.plots.extend(QgsApplication.instance().layoutTemplatePaths())

    def load_plots(self):
        """ Loads plots from given plots-list (paths with XML templates) """

        plot_files = []
        loaded_plot_file_names = []
        for path in self.plots:
            plot_files.extend(f for f in get_files(path)
                              if f.lower().endswith("plots.xml"))

        if not plot_files:
            raise ValueError(f"no xml files found in {self.plots}")

        first_plots_element = self.document.firstChildElement("plots")

        for i, path in enumerate(plot_files):
            # get the necessary paths
            file_path = str(Path(path).parent.parent).replace("\\", "/")
            icon_root_path = str(Path(path).parent).replace("\\", "/")

            # load the XML content
            document = QDomDocument()

            result = document.setContent(Path(path).read_bytes())
            if not result[0]:
                raise ValueError(f"plots.xml not loaded: {path}\n{result}")
            dom_plot_elements = document.elementsByTagName("plot")

            for index in range(dom_plot_elements.size()):
                # get the node
                node = dom_plot_elements.item(index)
                element = node.cloneNode(deep=True).toElement()
                if element.isNull():
                    raise ValueError("element is unexpected null")

                element.setAttribute("filename", element.attribute("file"))
                element.setAttribute("plots_xml_folder", icon_root_path)
                element.setAttribute(
                    "file",
                    file_path + "/" + element.attribute("file").replace("\\", "/"))

                file_name = element.attribute("filename")
                if file_name in loaded_plot_file_names:
                    raise ValueError(f"Layout {file_name} already loaded")
                loaded_plot_file_names.append(file_name)

                first_plots_element.appendChild(element)

    def get_orientation(self, file: str):
        """ returns Qgis page orientation

            :param file: file
        """
        layout = self.__layouts[file]
        page = layout.page
        return page.orientation()

    def get_layout_extent(self, file: str, center: QgsPointXY, scale: int) -> QgsRectangle:
        """ Returns extent with given center and scale from layout

            :param file: file
            :param center: center of rectangle/extent (e.g. mouse position on plot layer
            :param scale: map scale
        """
        item_map = self.__layouts[file].item_map

        x_center = center.x()
        y_center = center.y()

        x_low = x_center - (x_center / 100)
        x_high = x_center + (x_center / 100)

        y_low = y_center - (y_center / 100)
        y_high = y_center + (y_center / 100)

        rectangle = QgsRectangle(x_low, y_low, x_high, y_high)
        rectangle.normalize()

        item_map.zoomToExtent(rectangle)
        item_map.setScale(scale)

        return item_map.extent()

    @classmethod
    def tr_(cls, text: str):
        result = QgsApplication.translate("QgsApplication", text)
        return result

    def load_layouts(self):
        """ Loads templates into local dictionary.
            Emits the progressChanged signal.
        """

        plot_elements = self.document.elementsByTagName("plot")
        count = plot_elements.size()

        for i in range(count):
            # xml child from plots.xml
            element = plot_elements.item(i).toElement()
            name = element.attribute("name")
            filename = element.attribute('filename')
            path = element.attribute('file')
            group = element.attribute('group')

            project = QgsProject.instance()
            layout = QgsPrintLayout(project)
            document = QDomDocument()

            # progress
            msg = self.tr_('Loading') + " " + self.tr_('Template') + f" '{filename}'"
            self.progressChanged.emit(i, count, msg)
            document.setContent(Path(path).read_bytes(), False)

            item_list = layout.loadFromTemplate(document, QgsReadWriteContext())[0]
            plot_layout = PlotLayout(name, filename, group, layout, item_list, dom_element=element, filepath=path)
            plot_layout.set_parent(self)
            self.__layouts[filename] = plot_layout

    @property
    def layouts(self):
        return self.__layouts.values()

    def __getitem__(self, item) -> PlotLayout:
        return self.__layouts[item]

    def __iter__(self):
        """ you can iterate over this object """
        for layout in self.__layouts.values():
            yield layout
