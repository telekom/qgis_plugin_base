# -*- coding: utf-8 -*-
# SPDX-FileCopyrightText: 2025 Deutsche Telekom Technik GmbH <f.vonstudsinske@telekom.de>
# SPDX-License-Identifier: GPL-3.0-or-later

from pkg_resources import packaging

from ..versions_reader import VersionPlugin
from ..constants import VersionInfo, VersionError

TEST_XML = b"""<plugins>
  <pyqgis_plugin version="2.1.2" name="Plugin Template">
    <description>Plugin Template</description>
    <homepage>https://test.url.de</homepage>
    <qgis_minimum_version>3.34.6</qgis_minimum_version>
    <qgis_maximum_version>3.40.99</qgis_maximum_version>
    <file_name>plugin_template.zip</file_name>
    <author_name>Author</author_name>
    <author_email>email</author_email>
    <download_url>https://test.url.de</download_url>
    <commit>12852478</commit>
  </pyqgis_plugin>
  <pyqgis_plugin version="1.0.0" name="Plugin 1">
    <description>Plugin 1</description>
    <homepage>https://test.url.de</homepage>
    <qgis_minimum_version>3.34.6</qgis_minimum_version>
    <qgis_maximum_version>3.40.99</qgis_maximum_version>
    <file_name>plugin_one.zip</file_name>
    <author_name>Author</author_name>
    <author_email>email</author_email>
    <download_url>https://test.url.de</download_url>
    <commit>12852478</commit>
  </pyqgis_plugin>
  <pyqgis_plugin version="1.0.0" name="Plugin 2">
    <description>Plugin 2</description>
    <homepage>https://test.url.de</homepage>
    <qgis_minimum_version>3.34.6</qgis_minimum_version>
    <qgis_maximum_version>3.40.99</qgis_maximum_version>
    <file_name>plugin_two.zip</file_name>
    <author_name>Author</author_name>
    <author_email>email</author_email>
    <download_url>https://test.url.de</download_url>
    <commit>12852478</commit>
  </pyqgis_plugin>
</plugins>"""


def test_get_version_from_xml():

    version, error = VersionPlugin.get_version_from_xml(TEST_XML, "Plugin Template")
    assert version == packaging.version.parse("2.1.2")

    version, error = VersionPlugin.get_version_from_xml(TEST_XML, "Plugin 1")
    assert version == packaging.version.parse("1.0.0")

    version, error = VersionPlugin.get_version_from_xml(TEST_XML, "Plugin 2")
    assert version == packaging.version.parse("1.0.0")

    version, error = VersionPlugin.get_version_from_xml(TEST_XML, "abcdef")
    assert error.endswith(" not found on xml_content") and version is None

def test_get_version_info_from_xml():

    version = VersionPlugin.get_version_info_from_xml(TEST_XML, "plugin_template.zip")
    v_info = VersionInfo(
        packaging.version.parse("2.1.2"),
        "2.1.2",
        "12852478",
        packaging.version.parse("3.34.6"),
        packaging.version.parse("3.40.99"))
    assert v_info == version

    error = VersionPlugin.get_version_info_from_xml(TEST_XML, "error.zip")
    assert isinstance(error, VersionError) and error.error.endswith(" not found")
