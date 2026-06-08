# -*- coding: utf-8 -*-
# SPDX-FileCopyrightText: 2025 Deutsche Telekom Technik GmbH <f.vonstudsinske@telekom.de>
# SPDX-License-Identifier: GPL-3.0-only

import inspect

from qgis.PyQt.QtWidgets import (QComboBox, QWidget, QSpinBox, QTabBar,
                                 QLineEdit, QLabel, QMessageBox,
                                 QGridLayout, QTextEdit, QDoubleSpinBox, QAbstractSpinBox)
from qgis.PyQt.QtGui import QWheelEvent, QHideEvent, QShowEvent
from qgis.PyQt.QtCore import Qt, pyqtSignal

from typing import List, Tuple, Optional, Type


class Widget(QWidget):
    # True=visible, False=not visible
    widgetVisibilityChanged = pyqtSignal(bool, name="widgetVisibilityChanged")

    def hideEvent(self, event: QHideEvent):
        event.accept()
        self.widgetVisibilityChanged.emit(False)

    def showEvent(self, event: QShowEvent):
        event.accept()
        self.widgetVisibilityChanged.emit(True)


class NoWheelComboBox(QComboBox):

    def __init__(self, parent: QWidget = None):
        super(NoWheelComboBox, self).__init__(parent)
        self.setSizeAdjustPolicy(self.AdjustToMinimumContentsLengthWithIcon)

    def wheelEvent(self, event: QWheelEvent):
        """ reimplemented PyQt function to ignore this event """
        event.ignore()


class NoWheelTabBar(QTabBar):

    def __init__(self, parent: QWidget = None):
        super(NoWheelTabBar, self).__init__(parent)

    def wheelEvent(self, event: QWheelEvent):
        """ reimplemented PyQt function to ignore this event """
        event.ignore()


class NoWheelSpinBox(QSpinBox):

    def __init__(self, parent: QWidget = None):
        super(NoWheelSpinBox, self).__init__(parent)

    def wheelEvent(self, event: QWheelEvent):
        """ reimplemented PyQt function to ignore this event """
        event.ignore()


class NoWheelDoubleSpinBox(QDoubleSpinBox):

    def __init__(self, parent: QWidget = None):
        super(NoWheelDoubleSpinBox, self).__init__(parent)

    def wheelEvent(self, event: QWheelEvent):
        """ reimplemented PyQt function to ignore this event """
        event.ignore()


class MultiLineEditBox(QMessageBox):
    """ creates a message with line edits

        .. code-block:: python

            result = MultiLineEditBox.enter(
                iface.mainWindow(),
                "This is a test",
                "Please enter your value:",
                ["First", "Second", "Third"]
            )
            print(result)
    """

    def __init__(self, parent: QWidget = None):
        super().__init__(parent)
        layout = QGridLayout()
        self.setLayout(layout)
        self.setSizeGripEnabled(True)
        self.setStandardButtons(QMessageBox.Ok | QMessageBox.Cancel)
        self.line_edits = []
        self.rows = 0

    @classmethod
    def enter(cls, parent: QWidget, title: str, text: str, lines: List[str]) -> List[str]:
        """ Create a Message Box window with QLineEdits.
            Returns the entered text in same order how it was given.
            Returns empty list, if action canceled.

            :param parent: parents QWidget
            :param title: window title
            :param text: message text
            :param lines: line edits, display names for labels

        """
        if not lines:
            raise ValueError("lines list is empty")

        window = cls(parent)

        window.setWindowTitle(title)
        window.setText(text)

        # move all default label widgets to layout
        for w in window.findChildren(QLabel):
            window.layout().addWidget(w.parent(), window.rows, 0, -1, -1)
            window.rows += 1

        window._add_line_edits(lines)

        widget = QWidget()
        widget.setLayout(QGridLayout())
        window.layout().addWidget(widget, window.rows, 0, -1, -1)
        window.rows += 1

        # move dialog button box to widget
        for i, btn in enumerate(window.buttons()):
            widget.layout().addWidget(btn.parent(), 0, i, -1, -1)
            break

        role = window.exec_()
        if role == QMessageBox.Ok:
            return [e.text() for e in window.line_edits]

        return []

    def _add_line_edits(self, lines: List[str]):

        for row, edit in enumerate(lines):

            # create new widget and save new line edit to list to keep provided order
            label = QLabel()
            label.setText(edit)
            line_edit = QLineEdit()
            self.line_edits.append(line_edit)

            self.layout().addWidget(label, self.rows, 0)
            self.layout().addWidget(line_edit, self.rows, 1)
            self.rows += 1

    def event(self, e):
        """ make the window resizable (overload) """
        result = QMessageBox.event(self, e)
        self.setMinimumWidth(0)
        self.setMaximumWidth(16777215)

        return result


class TextInfoBox(QMessageBox):
    """ Creates a message box with a scrollable text widget. """

    def __init__(self, parent: QWidget = None):
        super().__init__(parent)
        layout = QGridLayout()
        self.setLayout(layout)
        self.setSizeGripEnabled(True)
        self.rows = 0
        self.setWindowModality(Qt.NonModal)

    @classmethod
    def show_content(cls, parent: Optional[QWidget], title: str, text: str, content: str,
                     buttons: QMessageBox.StandardButtons = None,
                     icon: QMessageBox.Icon = None) -> QMessageBox.StandardButtons:
        """ Show your info text.

            .. code-block:: python

                TextInfoBox.show_content(
                    iface.mainWindow(),
                    "I am a window title",
                    "I am a short description",
                    "<html><h1>Header</h1></html>",
                    buttons=TextInfoBox.Yes | TextInfoBox.No,
                    icon=QMessageBox.Information
                )

            :param parent: parents widget
            :param title: window title
            :param text: Short description text above the content
            :param content: Content to set in QTextEdit. HTML allowed.
            :param buttons: standard buttons. defaults to Ok and Cancel
            :param icon: Icon for the message box. defaults to no icon

        """

        window = cls(parent)
        buttons = buttons or (QMessageBox.Ok | QMessageBox.Cancel)
        window.setStandardButtons(buttons)

        window.setWindowTitle(title)
        if icon:
            # set a icon if provided, otherwise no icon will be shown
            window.setIcon(icon)

        # load a QLabel and a QTextEdit and set the content to the edit widget
        label, edit = window._load_widgets()
        edit.setText(content)
        # the created QLabel will be ignored

        # set the text into the default QLabel within the QMessageBox
        window.setText(text)

        widget = QWidget()
        widget.setLayout(QGridLayout())
        window.layout().addWidget(widget, window.rows, 0, -1, -1)
        window.rows += 1

        # move dialog button box to widget
        for i, btn in enumerate(window.buttons()):
            widget.layout().addWidget(btn.parent(), 0, i, -1, -1)
            break

        role = window.exec_()

        return role

    @classmethod
    def question(cls, parent: Optional[QWidget], title: str, text: str, content: str):

        role = cls.show_content(parent, title, text, content, buttons=QMessageBox.Yes | QMessageBox.No)
        return role

    def _load_widgets(self) -> Tuple[QLabel, QTextEdit]:

        label = QLabel()
        label.setWordWrap(True)
        self.layout().addWidget(label, self.rows, 0)
        self.rows += 1

        edit = QTextEdit()
        edit.setReadOnly(True)
        self.layout().addWidget(edit, self.rows, 0, 1, -1)
        self.rows += 1

        return label, edit

    def event(self, e):
        """ make the window resizable (overload) """
        result = super().event(e)
        self.setMinimumWidth(400)
        self.setMaximumWidth(16777215)
        self.setMinimumHeight(300)
        self.setMaximumHeight(16777215)

        return result


def is_widget_compatible(source_widget: QWidget, target_type: Type[QWidget]) -> bool:
    """ Returns True, if the type of source_widget is part of the type inheritance in the target_type """
    return type(source_widget) in inspect.getmro(target_type)


def apply_widget_options(source_widget: QWidget, target_widget: QWidget) -> bool:
    """ Applies the source_widget options to the target_widget, e.g. Tooltip, text etc.

        Common values used from the Qt Designer.

        Returns True, if options has been applied.
    """

    if not is_widget_compatible(source_widget, type(target_widget)):
        raise TypeError(f"The source_widget type is not compatible with the target_widget type. "
                        f"Missing inheritance/equal type.\n"
                        f"source_widget: {type(source_widget).__name__}\n"
                        f"mro: {[cls.__name__ for cls in inspect.getmro((type(target_widget)))]}"
                        )

    # transfer default settings
    target_widget.setEnabled(source_widget.isEnabled())
    target_widget.setSizePolicy(source_widget.sizePolicy())
    target_widget.setMinimumSize(source_widget.minimumSize())
    target_widget.setMaximumSize(source_widget.maximumSize())
    target_widget.setSizeIncrement(source_widget.sizeIncrement())
    target_widget.setBaseSize(source_widget.baseSize())
    target_widget.setPalette(source_widget.palette())
    target_widget.setFont(source_widget.font())
    target_widget.setCursor(source_widget.cursor())
    target_widget.setMouseTracking(source_widget.hasMouseTracking())
    target_widget.setTabletTracking(source_widget.hasTabletTracking())
    target_widget.setFocusPolicy(source_widget.focusPolicy())
    target_widget.setContextMenuPolicy(source_widget.contextMenuPolicy())
    target_widget.setAcceptDrops(source_widget.acceptDrops())
    target_widget.setAccessibleName(source_widget.accessibleName())
    target_widget.setAccessibleDescription(source_widget.accessibleDescription())
    target_widget.setLayoutDirection(source_widget.layoutDirection())
    target_widget.setAutoFillBackground(source_widget.autoFillBackground())
    target_widget.setStyleSheet(source_widget.styleSheet())
    target_widget.setLocale(source_widget.locale())
    target_widget.setInputMethodHints(source_widget.inputMethodHints())

    if (isinstance(source_widget, QAbstractSpinBox)
            and isinstance(target_widget, QAbstractSpinBox)):
        target_widget.setWrapping(source_widget.wrapping())
        target_widget.setFrame(source_widget.hasFrame())
        target_widget.setAlignment(source_widget.alignment())
        target_widget.setReadOnly(source_widget.isReadOnly())
        target_widget.setButtonSymbols(source_widget.buttonSymbols())
        target_widget.setSpecialValueText(source_widget.specialValueText())
        target_widget.setAccelerated(source_widget.isAccelerated())
        target_widget.setCorrectionMode(source_widget.correctionMode())
        target_widget.setKeyboardTracking(source_widget.keyboardTracking())
        target_widget.setGroupSeparatorShown(source_widget.isGroupSeparatorShown())

    if (isinstance(source_widget, QDoubleSpinBox)
            and isinstance(target_widget, QDoubleSpinBox)):
        target_widget.setDecimals(source_widget.decimals())
        target_widget.setMinimum(source_widget.minimum())
        target_widget.setMaximum(source_widget.maximum())
        target_widget.setSingleStep(source_widget.singleStep())
        target_widget.setStepType(source_widget.stepType())
        target_widget.setValue(source_widget.value())
        target_widget.setPrefix(source_widget.prefix())
        target_widget.setSuffix(source_widget.suffix())
        return True

    return False
