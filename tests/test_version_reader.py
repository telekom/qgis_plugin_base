# -*- coding: utf-8 -*-
# SPDX-FileCopyrightText: 2025 Deutsche Telekom Technik GmbH <f.vonstudsinske@telekom.de>
# SPDX-License-Identifier: GPL-3.0-only

import logging
from types import SimpleNamespace

import pytest
from pkg_resources import packaging
from qgis.PyQt.QtNetwork import QNetworkReply

from .. import versions_reader
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


@pytest.mark.parametrize(("metadata", "expected"), [
    ("[general]\n", ""),
    ("[general]\npluginRepositoryAuthcfg=\n", ""),
    ("[general]\npluginRepositoryAuthcfg=auth-id\n", "auth-id"),
])
def test_get_local_repository_authcfg(tmp_path, metadata, expected):
    """Reads an optional authcfg, defaulting to an empty value."""
    metadata_path = tmp_path / "metadata.txt"
    metadata_path.write_text(metadata, encoding="utf-8")

    assert VersionPlugin.get_local_repository_authcfg(str(metadata_path)) == expected


@pytest.mark.parametrize(("method", "plugin"), [
    (VersionPlugin.get_repository_version_name, "Plugin Template"),
    (VersionPlugin.get_repository_version_zipname, "plugin_template.zip"),
])
def test_repository_version_reader_passes_authcfg(monkeypatch, method, plugin):
    """Passes configured authcfg IDs to the GET request."""
    auth_manager = SimpleNamespace(configIds=lambda: ["auth-id"])
    monkeypatch.setattr(versions_reader, "QgsApplication",
                        SimpleNamespace(authManager=lambda: auth_manager))
    response = SimpleNamespace(
        error=lambda: QNetworkReply.NoError,
        status_code=200,
        content=TEST_XML,
    )
    requests = []

    def get_mock(url, **kwargs):
        requests.append((url, kwargs))
        return response

    monkeypatch.setattr(versions_reader, "get", get_mock)

    result = method("https://test.url.de/plugins.xml", plugin, auth_cfg="auth-id")

    assert result is not None
    assert requests == [("https://test.url.de/plugins.xml", {"authCfg": "auth-id"})]


@pytest.mark.parametrize(("method", "plugin"), [
    (VersionPlugin.get_repository_version_name, "Plugin Template"),
    (VersionPlugin.get_repository_version_zipname, "plugin_template.zip"),
])
def test_repository_version_reader_rejects_unknown_authcfg(monkeypatch, caplog, method, plugin):
    """Rejects unknown authcfg IDs before issuing a request."""
    auth_manager = SimpleNamespace(configIds=lambda: ["known-id"])
    monkeypatch.setattr(versions_reader, "QgsApplication",
                        SimpleNamespace(authManager=lambda: auth_manager))

    def get_mock(*args, **kwargs):
        pytest.fail("No request should be sent for an unknown authcfg")

    monkeypatch.setattr(versions_reader, "get", get_mock)

    with (caplog.at_level(logging.WARNING, logger=versions_reader.__name__),
          pytest.raises(VersionError, match="auth-id") as exc_info):
        method("https://test.url.de/plugins.xml", plugin, auth_cfg="auth-id")

    assert "importiere oder erstelle" in str(exc_info.value)
    assert any(record.levelno == logging.WARNING for record in caplog.records)


def test_repository_version_zipname_reports_http_error(monkeypatch):
    """Includes HTTP status and network error text in the ZIP lookup result."""
    response = SimpleNamespace(
        error=lambda: QNetworkReply.NoError,
        status_code=401,
        errorString=lambda: "unauthorized",
    )
    monkeypatch.setattr(versions_reader, "get", lambda url, **kwargs: response)

    result = VersionPlugin.get_repository_version_zipname("https://test.url.de/plugins.xml", "plugin.zip")

    assert isinstance(result, VersionError)
    assert "401" in result.error
    assert "unauthorized" in result.error


def test_repository_version_name_reports_http_error(monkeypatch):
    """Includes HTTP status and network error text in the name lookup result."""
    response = SimpleNamespace(
        error=lambda: QNetworkReply.ConnectionRefusedError,
        status_code=503,
        errorString=lambda: "upstream unavailable",
    )
    monkeypatch.setattr(versions_reader, "get", lambda url, **kwargs: response)

    version, error = VersionPlugin.get_repository_version_name("https://test.url.de/plugins.xml", "Plugin")

    assert version is None
    assert "503" in error
    assert "upstream unavailable" in error
