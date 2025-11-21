# -*- coding: utf-8 -*-
# SPDX-FileCopyrightText: 2025 Deutsche Telekom Technik GmbH <f.vonstudsinske@telekom.de>
# SPDX-License-Identifier: GPL-3.0-only

import webbrowser

from qgis.PyQt.QtWidgets import QMainWindow, QTextEdit, QMessageBox
from qgis.PyQt.QtGui import QCloseEvent
from qgis.PyQt.QtCore import Qt
from qgis.PyQt.QtNetwork import QNetworkReply

from .base_class import UiModuleBase, ModuleBase
from ..qgis.qgis_network_requests import get

FORM_CLASS, _ = UiModuleBase.get_uic_classes(__file__)
FORM_CLASS: 'Ui'
try:
    from .static_plugin_news_generated_ui import Ui as FORM_CLASS

except ModuleNotFoundError:
    pass

KEY_LAST_NEWS_DATE = "LAST_NEWS_DATE"


class StaticPluginNews(UiModuleBase, QMainWindow, FORM_CLASS):

    def __init__(self, *args, **kwargs: dict):
        UiModuleBase.__init__(self, *args, **kwargs)
        QMainWindow.__init__(self, kwargs.get('parent', None))
        self.setupUi(self)
        self.fill_news(self.get_plugin().news_url, self.TextEdit_View_News)
        self.fill_news(self.get_plugin().changelog_url, self.TextEdit_View_Changelogs)
        self.But_Close.clicked.connect(self.news_close_button)

        if self.get_plugin().homepage_url:
            self.But_Yam.clicked.connect(self.news_yam_button)
        else:
            # noe hompage/yam page set, hide the button
            self.But_Yam.hide()

        # set current index in tab
        # 0: show news
        # 1: show versions
        tab = kwargs.get("tab", 0)
        self.tabWidget.setCurrentIndex(tab)

    @classmethod
    def open_news(cls, parent: ModuleBase, tab: int = 0):
        """opens QMainWindow used for StaticPluginNews class"""
        if cls.__name__ in parent:
            return
        ui = parent.add_module(
            cls.__name__,
            cls,
            parent=parent.get_main_plugin().iface.mainWindow(),
            tab=tab
        )
        ui.show()

    def keyReleaseEvent(self, event):
        """closes window, when Escape key is pressed"""
        pressed_key = event.key()
        if pressed_key == Qt.Key_Escape:
            self.close()
        event.accept()

    def closeEvent(self, event: QCloseEvent):
        """closes window"""
        self.unload(True)

    @staticmethod
    def fill_news(url: str, text_widget: QTextEdit):
        """fills QTextEdit window with information from url"""

        response = get(url)
        if response.error() != QNetworkReply.NoError or response.status_code != 200:
            text_widget.setMarkdown(f"## Fehler\n\nVerbindung fehlgeschlagen.\n\n"
                                    f"Statuscode: {response.status_code}\n\n"
                                    f"{response.errorString()}")
        else:
            text_widget.setMarkdown(response.text)

    @classmethod
    def compare_last_date_news(cls, plugin):
        """opens News window, if first line has changed in specific staticpluginnews.md file. """

        response = get(plugin.news_url)
        if response.error() != QNetworkReply.NoError or response.status_code != 200:
            QMessageBox.information(
                plugin.iface.mainWindow(),
                "Verbindungsfehler",
                "News konnten nicht abgefragt werden. Verbindung fehlgeschlagen.\n"
                f"Statuscode: {response.status_code}"
            )
        else:
            # connection ok
            news = response.text
            # get first line with date to compare
            dateline = news.partition("\n")[0]
            if dateline != plugin.get_option(KEY_LAST_NEWS_DATE):
                # saved date changed, show plugin news
                StaticPluginNews.open_news(plugin, tab=0)
                plugin.set_option(KEY_LAST_NEWS_DATE, dateline)

    def news_close_button(self):
        """closes window"""
        self.close()

    def news_yam_button(self):
        """opens provided website, in this case yam"""
        webbrowser.open_new_tab(self.get_plugin().homepage_url)
