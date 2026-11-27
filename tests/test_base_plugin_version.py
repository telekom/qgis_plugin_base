# -*- coding: utf-8 -*-
# SPDX-FileCopyrightText: 2025 Deutsche Telekom Technik GmbH <f.vonstudsinske@telekom.de>
# SPDX-License-Identifier: GPL-3.0-only
""" Tests for the plugin version lookup and the version error dialog. """

import logging
import pytest

from pathlib import Path
from pkg_resources import packaging
from qgis.PyQt.QtNetwork import QNetworkReply
from types import SimpleNamespace
from unittest.mock import Mock

from ..constants import VersionError, VersionInfo
from ..ui import base_class, base_plugin
from ..ui.base_class import ModuleBase
from ..ui.base_plugin import Plugin

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
def plugin() -> Plugin:
    """ Return a Plugin without __init__ (no QGIS interface needed) and with a mocked plugin logger. """
    instance = Plugin.__new__(Plugin)
    instance.log = Mock()
    return instance


@pytest.fixture()
def auth_ids(monkeypatch: pytest.MonkeyPatch) -> list[str]:
    """ Replace the native QGIS auth manager and return its configurable list of authcfg IDs.

        :param monkeypatch: pytest monkeypatch fixture
    """
    ids = []
    auth_manager = SimpleNamespace(configIds=lambda: ids)
    monkeypatch.setattr(base_plugin, "QgsApplication", SimpleNamespace(authManager=lambda: auth_manager))
    return ids


def _response(error: QNetworkReply.NetworkError = QNetworkReply.NoError, status_code: int = 200,
              content: bytes = TEST_XML, error_string: str = "") -> SimpleNamespace:
    """ Return a fake network response with the interface used by the version lookup.

        :param error: Qt network error code
        :param status_code: HTTP status code
        :param content: response body
        :param error_string: network error text
    """
    return SimpleNamespace(error=lambda: error, status_code=status_code, content=content,
                           errorString=lambda: error_string)


def test_version_error_is_plain_exception() -> None:
    """ VersionError is a plain exception that keeps the error text. """
    error = VersionError("text")

    assert isinstance(error, Exception)
    assert error.error == "text"
    assert str(error) == "text"


def test_get_version_from_xml() -> None:
    """ Find versions by plugin name. """
    assert Plugin.get_version_from_xml(TEST_XML, "Plugin Template") == (packaging.version.parse("2.1.2"), "")
    assert Plugin.get_version_from_xml(TEST_XML, "Plugin 1") == (packaging.version.parse("1.0.0"), "")

    version, error = Plugin.get_version_from_xml(TEST_XML, "abcdef")
    assert version is None and error.endswith(" not found on xml_content")


def test_get_version_info_from_xml() -> None:
    """ Find version info by zip file name. """
    expected = VersionInfo(packaging.version.parse("2.1.2"), "2.1.2", "12852478",
                           packaging.version.parse("3.34.6"), packaging.version.parse("3.40.99"))
    assert Plugin.get_version_info_from_xml(TEST_XML, "plugin_template.zip") == expected

    error = Plugin.get_version_info_from_xml(TEST_XML, "error.zip")
    assert isinstance(error, VersionError) and error.error.endswith(" not found")


def test_get_local_metadata_values(tmp_path: Path) -> None:
    """ Read metadata values statically, i.e. before Plugin.__init__.

        :param tmp_path: pytest temporary directory fixture
    """
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
def test_get_local_repository_authcfg(tmp_path: Path, metadata: str, expected: str) -> None:
    """ Read an optional authcfg, defaulting to an empty value.

        :param tmp_path: pytest temporary directory fixture
        :param metadata: content of metadata.txt
        :param expected: expected authcfg ID
    """
    metadata_path = tmp_path / "metadata.txt"
    metadata_path.write_text(metadata, encoding="utf-8")

    assert Plugin.get_local_repository_authcfg(str(metadata_path)) == expected


@pytest.mark.parametrize(("method", "plugin_ref"), [
    ("get_repository_version_name", "Plugin Template"),
    ("get_repository_version_zipname", "plugin_template.zip"),
])
@pytest.mark.parametrize("auth_cfg", ["", "auth-id"])
def test_repository_version_passes_authcfg(monkeypatch: pytest.MonkeyPatch, plugin: Plugin, auth_ids: list[str],
                                          method: str, plugin_ref: str, auth_cfg: str) -> None:
    """ Pass the (optional) authcfg ID to the GET request.

        :param monkeypatch: pytest monkeypatch fixture
        :param plugin: plugin with mocked logger
        :param auth_ids: configurable authcfg IDs known to QGIS
        :param method: name of the lookup method
        :param plugin_ref: plugin name or zip file name
        :param auth_cfg: authcfg ID to pass
    """
    auth_ids.append("auth-id")
    requests = []

    def get_mock(url: str, **kwargs: object) -> SimpleNamespace:
        """ Record the request and return a successful response.

            :param url: requested url
            :param kwargs: request keyword arguments
        """
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
def test_repository_version_rejects_unknown_authcfg(monkeypatch: pytest.MonkeyPatch, plugin: Plugin,
                                                    auth_ids: list[str], method: str, plugin_ref: str) -> None:
    """ Reject unknown authcfg IDs before any request and log a warning via the plugin logger.

        :param monkeypatch: pytest monkeypatch fixture
        :param plugin: plugin with mocked logger
        :param auth_ids: configurable authcfg IDs known to QGIS
        :param method: name of the lookup method
        :param plugin_ref: plugin name or zip file name
    """
    auth_ids.append("known-id")

    def get_mock(*args: object, **kwargs: object) -> None:
        """ Fail the test, because no request is expected.

            :param args: request arguments
            :param kwargs: request keyword arguments
        """
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
def test_repository_version_reports_http_error(monkeypatch: pytest.MonkeyPatch, plugin: Plugin,
                                               error: QNetworkReply.NetworkError, status_code: int,
                                               error_string: str) -> None:
    """ Include HTTP status and network error text in both lookup results.

        :param monkeypatch: pytest monkeypatch fixture
        :param plugin: plugin with mocked logger
        :param error: Qt network error code
        :param status_code: HTTP status code
        :param error_string: network error text
    """
    response = _response(error=error, status_code=status_code, error_string=error_string)
    monkeypatch.setattr(base_plugin, "get", lambda url, **kwargs: response)

    result = plugin.get_repository_version_zipname(XML_URL, "plugin.zip")
    assert isinstance(result, VersionError)
    assert str(status_code) in result.error and error_string in result.error

    version, text = plugin.get_repository_version_name(XML_URL, "Plugin")
    assert version is None
    assert str(status_code) in text and error_string in text


def test_version_error_dialog_mentions_authentication(monkeypatch: pytest.MonkeyPatch) -> None:
    """ Show a hint on network connection and QGIS authentication when the version lookup failed.

        :param monkeypatch: pytest monkeypatch fixture
    """
    plugin_data = SimpleNamespace(repo_version=None, repo_version_error="HTTP-Status: 401", plugin_version="1.0.0",
                                  commit=None, repo_commit=None, plugin_menu_name="Plugin",
                                  get_release_info=lambda: "Testversion")
    module = SimpleNamespace(get_plugin=lambda: plugin_data, log=Mock(), mainWindow=lambda: None, ERROR=logging.ERROR)
    warning = Mock()
    monkeypatch.setattr(base_class, "QMessageBox", SimpleNamespace(warning=warning))

    assert ModuleBase.set_ui_version_info(module) is False

    text = warning.call_args.args[2]
    assert "HTTP-Status: 401" in text
    assert "Firmennetz" in text and "Authentifizierung in QGIS" in text
