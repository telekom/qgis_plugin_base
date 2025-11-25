# -*- coding: utf-8 -*-
# SPDX-FileCopyrightText: 2025 Deutsche Telekom Technik GmbH <f.vonstudsinske@telekom.de>
# SPDX-License-Identifier: GPL-3.0-only

import sys

from lxml import etree
from lxml.etree import _Element, Element

from pathlib import Path

from qgis.PyQt.QtCore import Qt
from qgis.PyQt.QtGui import QColor, QIcon
from qgis.PyQt.QtWidgets import (QMainWindow, QApplication, QFileDialog,
                                 QMessageBox, QTreeWidgetItem, QInputDialog,
                                 QTreeWidgetItemIterator)
from qgis.PyQt.uic import loadUiType

FormClass, _ = loadUiType(__file__.replace(".py", ".ui"))

class TranslationHelper(QMainWindow, FormClass):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        QMainWindow.__init__(self, kwargs.get('parent'))

        self.setupUi(self)

        self.show()
        self.tree = None

        self.widget.layout().setAlignment(Qt.AlignTop)
        self.centralWidget().layout().setAlignment(Qt.AlignTop)

        # setup Qt connections
        self.But_Open.clicked.connect(self.open_ts_file)
        self.But_Add.clicked.connect(self.add_element)
        self.But_Remove.clicked.connect(self.remove_element)
        self.But_Save.clicked.connect(self.save_file)
        self.DrD_Context.currentIndexChanged.connect(self.__load_elements_to_tree_view)

        self.disable()

    def disable(self):
        self.DrD_Context.clear()
        self.Tree_Xml_View.clear()
        self.Tree_Xml_View.setEnabled(False)
        self.Frame_View.setEnabled(False)
        self.tree = None
        self.Frame_Save.setEnabled(False)
        self.Frame_Open.setEnabled(True)
        self.Label_File.setText("")
        self.Group_Context.setEnabled(False)

    def enable(self):
        self.Tree_Xml_View.clear()
        self.Tree_Xml_View.setEnabled(True)
        self.Frame_Save.setEnabled(True)
        self.Frame_View.setEnabled(True)
        self.Frame_Open.setEnabled(False)

    def error(self, msg: str):
        QMessageBox.warning(self, "Information/Warning", msg)

    def open_ts_file(self):
        """ try to open and parse ts/xml file. """
        file, _ = QFileDialog.getOpenFileName(
            self,
            "Choose your file",
            str(Path(__file__).parent),
            "Translation (*.ts)")

        self.disable()

        if not file:
            self.error("No file selected")
            return

        try:
            self.tree = etree.parse(file)
            self.Label_File.setText(file)
            self.enable()
            self.load_etree_to_dropdown()
        except Exception as e:
            self.error(f"File could not be loaded. Exception:\n\n{e}")
            self.disable()

    def add_element(self):

        # get the current context
        context = self.DrD_Context.currentData()

        text, ok = QInputDialog.getText(self, "Enter source text", "English:")

        text = text.lstrip().rstrip()

        if not ok or not text.strip():
            return

        # create the new translation element
        new_element = Element("message")
        new_elem_source = Element("source")
        new_elem_source.text = text
        new_element.append(new_elem_source)
        new_elem_translation = Element("translation")
        new_elem_translation.text = ""
        new_element.append(new_elem_translation)

        # add the element to the current context
        context.append(new_element)

        # load the element to the tree
        self.add_element_to_tree(new_element)

    def remove_element(self):
        items = self.Tree_Xml_View.selectedItems()
        if not items:
            return

        item: QTreeWidgetItem = items[0]

        element = item.data(0, Qt.UserRole)
        if not isinstance(element, _Element):
            return

        # remove the element
        parent = element.getparent()
        parent.remove(element)

        self.Tree_Xml_View.invisibleRootItem().removeChild(item)

    def save_file(self):
        reply = QMessageBox.question(
            self,
            "save ts file?",
            "Do you want to overwrite existing ts file?"
        )
        if reply != QMessageBox.Yes:
            return

        iterator = QTreeWidgetItemIterator(self.Tree_Xml_View)
        while iterator.value():

            item = iterator.value()
            data = item.data(0, Qt.UserRole)
            text = item.text(0) #.replace("'", "&apos;")

            # only save something, when it has no children (it is translation or source element)
            if len(data) == 0:
                data.text = text

            iterator += 1
        Path(self.Label_File.text()).write_bytes(etree.tostring(self.tree, pretty_print=True))

    def load_etree_to_dropdown(self):
        """ Loads ts/xml file to tree widget.
        """

        contexts = self.tree.getroot().findall("./context")

        if len(contexts) < 1:
            raise ValueError(f"ts file must have at least one context, got 0")

        for context in contexts:
            # get name information
            name = context.find('./name').text
            source_language = self.tree.getroot().attrib['sourcelanguage']
            dest_language = self.tree.getroot().attrib['language']

            # add the context to the dropdown
            self.DrD_Context.addItem(f"{name} ({source_language} -> {dest_language})", context)

        self.Group_Context.setEnabled(True)

    def __load_elements_to_tree_view(self):
        context = self.DrD_Context.currentData()
        self.Tree_Xml_View.clear()

        if context is None:
            # no context found
            return

        for i, element in enumerate(context.findall("./message")):
            self.add_element_to_tree(element)

    def add_element_to_tree(self, element: _Element):

        root = self.Tree_Xml_View.invisibleRootItem()
        source = element.find("./source")
        translation = element.find("./translation")

        item = QTreeWidgetItem([f"{root.childCount()} // {source.text}"])
        item.setData(0, Qt.UserRole, element)
        item_source = QTreeWidgetItem([source.text])
        item.addChild(item_source)

        if translation is not None:
            if translation.text:
                item_translation = QTreeWidgetItem([translation.text])
                item.setForeground(0, QColor(120, 120, 120, 255))
            else:
                item_translation = QTreeWidgetItem([""])
                item.setForeground(0, QColor(0, 0, 0, 255))
        else:
            translation = Element("translation")
            translation.text = ""
            element.append(translation)
            item_translation = QTreeWidgetItem([""])
            item.setForeground(0, QColor(0, 0, 0, 255))


        item_translation.setFlags(Qt.ItemIsEditable | Qt.ItemIsEnabled)
        item_source.setFlags(Qt.ItemIsEditable | Qt.ItemIsEnabled)
        item_source.setData(0, Qt.UserRole, source)
        item_translation.setData(0, Qt.UserRole, translation)
        item.addChild(item_translation)


        root.addChild(item)


if __name__ == "__main__":
    app = QApplication(sys.argv[1:])
    window = TranslationHelper()
    sys.exit(app.exec_())
