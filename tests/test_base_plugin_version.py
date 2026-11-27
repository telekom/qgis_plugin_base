# -*- coding: utf-8 -*-
# SPDX-FileCopyrightText: 2025 Deutsche Telekom Technik GmbH <f.vonstudsinske@telekom.de>
# SPDX-License-Identifier: GPL-3.0-only

import logging
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from pkg_resources import packaging
from qgis.PyQt.QtNetwork import QNetworkReply

from ..ui import base_plugin
from ..ui.base_plugin import Plugin
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
</plugins>"""

XML_URL = "https://test.url.de/plugins.xml"


@pytest.fixture()
def plugin():
    """Plugin without __init__ (no QGIS interface needed) and a mocked plugin logger."""
    instance = Plugin.__new__(Plugin)
    instance.log = Mock()
    return instance


@pytest.fixture()
def auth_ids(monkeypatch):
    """Replaces the native QGIS auth manager with a configurable list of authcfg IDs."""
    ids = []
    auth_manager = SimpleNamespace(configIds=lambda: ids)
    monkeypatch.setattr(base_plugin, "QgsApplication", SimpleNamespace(authManager=lambda: auth_manager))
    return ids


def _response(error=QNetworkReply.NoError, status_code=200, content=TEST_XML, error_string=""):
    return SimpleNamespace(error=lambda: error, status_code=status_code, content=content,
                           errorString=lambda: error_string)


def test_version_error_is_plain_exception():
    """VersionError is a plain exception that keeps the error text."""
    error = VersionError("text")

    assert isinstance(error, Exception)
    assert error.error == "text"
    assert str(error) == "text"


def test_get_version_from_xml():
    """Finds versions by plugin name."""
    assert Plugin.get_version_from_xml(TEST_XML, "Plugin Template") == (packaging.version.parse("2.1.2"), "")
    assert Plugin.get_version_from_xml(TEST_XML, "Plugin 1") == (packaging.version.parse("1.0.0"), "")

    version, error = Plugin.get_version_from_xml(TEST_XML, "abcdef")
    assert version is None and error.endswith(" not found on xml_content")


def test_get_version_info_from_xml():
    """Finds version info by zip file name."""
    expected = VersionInfo(packaging.version.parse("2.1.2"), "2.1.2", "12852478",
                           packaging.version.parse("3.34.6"), packaging.version.parse("3.40.99"))
    assert Plugin.get_version_info_from_xml(TEST_XML, "plugin_template.zip") == expected

    error = Plugin.get_version_info_from_xml(TEST_XML, "error.zip")
    assert isinstance(error, VersionError) and error.error.endswith(" not found")


def test_get_local_metadata_values(tmp_path):
    """Reads metadata values statically, i.e. before Plugin.__init__."""
    metadata_path = tmp_path / "metadata.txt"
    metadata_path.write_text("[general]\nversion=1.2.3\nzipFilename=plugin.zip\npluginXmlUrl=https://x\n",
                             encoding="utf-8")

    assert Plugin.get_local_version(str(metadata_path)) == packaging.version.parse("1.2.3")
    assert Plugin.get_local_zipname(str(metadata_path)) == "plugin.zip"
    assert Plugin.get_local_xml_url(str(metadata_path)) == "https://x"
    with pytest.raises(KeyError):
        Plugin.get_meta_value(str(metadata_path), "missing")


@pytest.mark.parametrize(("metadata", "expected"), [
    ("[general]\n", ""),
    ("[general]\npluginRepositoryAuthcfg=\n", ""),
    ("[general]\npluginRepositoryAuthcfg=auth-id\n", "auth-id"),
])
def test_get_local_repository_authcfg(tmp_path, metadata, expected):
    """Reads an optional authcfg, defaulting to an empty value."""
    metadata_path = tmp_path / "metadata.txt"
    metadata_path.write_text(metadata, encoding="utf-8")

    assert Plugin.get_local_repository_authcfg(str(metadata_path)) == expected


@pytest.mark.parametrize(("method", "plugin_ref"), [
    ("get_repository_version_name", "Plugin Template"),
    ("get_repository_version_zipname", "plugin_template.zip"),
])
@pytest.mark.parametrize("auth_cfg", ["", "auth-id"])
def test_repository_version_passes_authcfg(monkeypatch, plugin, auth_ids, method, plugin_ref, auth_cfg):
    """Passes the (optional) authcfg ID to the GET request."""
    auth_ids.append("auth-id")
    requests = []

    def get_mock(url, **kwargs):
        requests.append((url, kwargs))
        return _response()

    monkeypatch.setattr(base_plugin, "get", get_mock)

    result = getattr(plugin, method)(XML_URL, plugin_ref, auth_cfg=auth_cfg)

    assert not isinstance(result, VersionError)
    assert requests == [(XML_URL, {"authCfg": auth_cfg})]
    plugin.log.assert_not_called()


@pytest.mark.parametrize(("method", "plugin_ref"), [
    ("get_repository_version_name", "Plugin Template"),
    ("get_repository_version_zipname", "plugin_template.zip"),
])
def test_repository_version_rejects_unknown_authcfg(monkeypatch, plugin, auth_ids, method, plugin_ref):
    """Rejects unknown authcfg IDs before any request and logs a warning via the plugin logger."""
    auth_ids.append("known-id")

    def get_mock(*args, **kwargs):
        pytest.fail("No request should be sent for an unknown authcfg")

    monkeypatch.setattr(base_plugin, "get", get_mock)

    with pytest.raises(VersionError, match="auth-id") as exc_info:
        getattr(plugin, method)(XML_URL, plugin_ref, auth_cfg="auth-id")

    assert "importiere oder erstelle" in exc_info.value.error
    plugin.log.assert_called_once_with(exc_info.value.error, level=logging.WARNING)


@pytest.mark.parametrize(("error", "status_code", "error_string"), [
    (QNetworkReply.NoError, 401, "unauthorized"),
    (QNetworkReply.ConnectionRefusedError, 503, "upstream unavailable"),
])
def test_repository_version_reports_http_error(monkeypatch, plugin, error, status_code, error_string):
    """Includes HTTP status and network error text in both lookup results."""
    response = _response(error=error, status_code=status_code, error_string=error_string)
    monkeypatch.setattr(base_plugin, "get", lambda url, **kwargs: response)

    result = plugin.get_repository_version_zipname(XML_URL, "plugin.zip")
    assert isinstance(result, VersionError)
    assert str(status_code) in result.error and error_string in result.error

    version, text = plugin.get_repository_version_name(XML_URL, "Plugin")
    assert version is None
    assert str(status_code) in text and error_string in text
