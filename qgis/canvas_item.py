# -*- coding: utf-8 -*-
# SPDX-FileCopyrightText: 2025 Deutsche Telekom Technik GmbH <f.vonstudsinske@telekom.de>
# SPDX-License-Identifier: GPL-3.0-only

from qgis.PyQt.QtWidgets import QGraphicsTextItem
from qgis.PyQt.QtGui import QColor, QFont, QPainter, QPainterPath, QPen
from qgis.PyQt.QtCore import Qt, QPointF


class TextItemWithStroke(QGraphicsTextItem):
    def __init__(self, text: str, font: QFont, stroke_color: QColor, stroke_width: float):
        super().__init__(text)
        self.font = font
        self.stroke_color = stroke_color
        self.stroke_width = stroke_width

    def paint(self, painter: QPainter, option, widget):
        # set font for text
        painter.setFont(self.font)

        # create QPainterPath for text
        path = QPainterPath()
        path.addText(QPointF(0, 0), self.font, self.toPlainText())

        # draw the stroke
        if self.stroke_color:
            # create pen for white stroke
            white_stroke_pen = QPen(Qt.white)
            white_stroke_pen.setWidthF(self.stroke_width + 2.0)
            white_stroke_pen.setJoinStyle(Qt.RoundJoin)

            # create pen for stroke color
            stroke_pen = QPen(self.stroke_color)
            stroke_pen.setWidthF(self.stroke_width)
            stroke_pen.setJoinStyle(Qt.RoundJoin)

            # draw white stroke
            painter.setPen(white_stroke_pen)
            painter.setBrush(Qt.NoBrush)
            painter.drawPath(path)

            # draw selected stroke
            painter.setPen(stroke_pen)
            painter.setBrush(Qt.NoBrush)
            painter.drawPath(path)

        # draw text
        text_pen = QPen(Qt.black)
        painter.setPen(text_pen)
        painter.setBrush(Qt.black)
        painter.drawPath(path)
