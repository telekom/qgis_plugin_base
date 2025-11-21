# -*- coding: utf-8 -*-
# SPDX-FileCopyrightText: 2025 Deutsche Telekom Technik GmbH <f.vonstudsinske@telekom.de>
# SPDX-License-Identifier: GPL-3.0-or-later

import configparser
import traceback

from pkg_resources import packaging
from typing import Union, Tuple, Optional

from qgis.PyQt.QtXml import QDomDocument
from qgis.PyQt.QtNetwork import QNetworkReply

from . import constants
from .qgis.qgis_network_requests import get


class VersionPlugin:

    @classmethod
    def get_repository_version_name(cls, xml_url: str, plugin_name: str) -> tuple:
        """ Reads plugins.xml content and returns version number from given plugin.

            :param xml_url: web url
            :param plugin_name: name of plugin
            :returns: version string/None and error text
        """

        # read the XML content from the url
        response = get(xml_url)
        if response.error() != QNetworkReply.NoError or response.status_code != 200:
            return None, response.errorString()
        else:
            return cls.get_version_from_xml(response.content, plugin_name)

    @classmethod
    def get_version_from_xml(cls, xml_content: bytes,
                             plugin_name: str) -> Tuple[Optional[packaging.version.Version], str]:

        # parse the XML content into the dom
        document = QDomDocument()
        document.setContent(xml_content, False)

        # get all plugins from the XML document
        plugin_nodes = document.elementsByTagName("pyqgis_plugin")
        for i in range(plugin_nodes.size()):
            element = plugin_nodes.item(i).toElement()
            name = element.attribute("name")
            version = element.attribute("version")
            if name == plugin_name:
                version_obj = packaging.version.parse(version)
                return version_obj, ""

        return None, f"plugin '{plugin_name}' not found on xml_content"

    @classmethod
    def get_repository_version_zipname(cls, xml_url: str, zip_file: str) -> Union[constants.VersionInfo,
                                                                                  constants.VersionError]:
        """ Reads plugins.xml content and returns version number and error string from given zip file name

            :param xml_url: web url
            :param zip_file: zip file name (e.g. "plugin.zip")
            :returns: VersionInfo or VersionError dataclass
        """

        # read the XML content from the url
        response = get(xml_url)
        if response.error() != QNetworkReply.NoError or response.status_code != 200:
            err = f"Bei der Abfrage ist ein Fehler aufgetreten:\n\n{traceback.format_exc()}"
            return constants.VersionError(err)
        else:
            return cls.get_version_info_from_xml(response.content, zip_file)

    @classmethod
    def get_version_info_from_xml(cls, xml_content: bytes, zip_file_name: str) -> Union[constants.VersionInfo,
                                                                                        constants.VersionError]:
        # parse the XML content
        document = QDomDocument()
        document.setContent(xml_content, False)

        # iter over all plugins within the url
        plugin_nodes = document.elementsByTagName("pyqgis_plugin")
        for i in range(plugin_nodes.size()):

            # get plugin data from the XML content
            element = plugin_nodes.item(i).toElement()
            version = element.attribute("version")
            commit = element.firstChildElement("commit").text().strip()
            qgis_minimum_version = element.firstChildElement("qgis_minimum_version").text().strip()
            if qgis_minimum_version:
                qgis_minimum_version = packaging.version.parse(qgis_minimum_version)
            qgis_maximum_version = element.firstChildElement("qgis_maximum_version").text().strip()
            if qgis_maximum_version:
                qgis_maximum_version = packaging.version.parse(qgis_maximum_version)
            file_name = element.firstChildElement("file_name").text().strip()

            if file_name == zip_file_name:
                # plugin with the given ZIP file name found
                version_obj = packaging.version.parse(version)
                return constants.VersionInfo(version_obj, str(version_obj), commit,
                                             qgis_minimum_version, qgis_maximum_version)

        return constants.VersionError(f"plugin '{zip_file_name}' not found")

    @classmethod
    def get_local_version(cls, metadata_path: str) -> packaging.version.Version:
        """ Reads local version string from local metadata.txt

            :param metadata_path: path to metadata.txt file
        """
        version_str = cls.get_meta_value(metadata_path, 'version')
        version_obj = packaging.version.parse(version_str)
        return version_obj

    @classmethod
    def get_local_zipname(cls, metadata_path) -> str:
        """ Reads zip file name from local metadata.txt

            :param metadata_path: path to metadata.txt file
        """

        return cls.get_meta_value(metadata_path, 'zipFilename')

    @classmethod
    def get_local_xml_url(cls, metadata_path: str) -> str:
        """ Reads url to plugins.xml repo from local metadata.txt

            :param metadata_path: path to metadata.txt file
        """

        return cls.get_meta_value(metadata_path, 'pluginXmlUrl')

    @staticmethod
    def get_version_int(version: str) -> int:
        """ converts version str e.g. "1.0.1" into version integer 101 """

        version = version.replace(".", "").replace(",", "")
        version = int(version)
        return version

    @staticmethod
    def get_meta_value(metadata_path: str, key: str) -> str:
        """ Reads a value from metadata.txt.

            :param metadata_path: path to metadata.txt file
            :param key: key in 'general' section
        """

        config = configparser.ConfigParser()
        config.read(metadata_path, encoding='utf-8')
        return config['general'][key]
