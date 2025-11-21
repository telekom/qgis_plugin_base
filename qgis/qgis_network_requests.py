# -*- coding: utf-8 -*-
# SPDX-FileCopyrightText: 2025 Deutsche Telekom Technik GmbH <f.vonstudsinske@telekom.de>
# SPDX-License-Identifier: GPL-3.0-or-later

from qgis.core import QgsNetworkAccessManager, QgsNetworkReplyContent
from qgis.PyQt.QtNetwork import QNetworkRequest
from qgis.PyQt.QtCore import QUrl

from typing import Optional, Dict, Any
from urllib.parse import urlencode

from .qgis_requests_response import QgisResponse


def get_network_request(url: str, url_values: Optional[Dict[Any, Any]] = None,
                        headers: Optional[Dict[Any, Any]] = None) -> QNetworkRequest:
    """ Returns a QNetworkRequest to use it in post or get requests.

        :param url: network url
        :param url_values: values to add to url (?value=n...)
        :param headers: header data, more information for headers at https://doc.qt.io/qt-5/qnetworkrequest.html#KnownHeaders-enum
                        {QNetworkRequest.ContentTypeHeader: "application/json"}
                        or use (byte-)string, when using string or byte string, both of them must be same type
    """
    # create Qt request object
    if url_values:
        url_values_str = "?" + urlencode(url_values)
    else:
        url_values_str = ""

    request = QNetworkRequest(QUrl(f"{url}{url_values_str}"))
    if headers:
        for header, header_value in headers.items():
            if isinstance(header, str):

                if not isinstance(header_value, (bytes, str)):
                    header_value = str(header_value).encode("utf-8")

                if isinstance(header_value, str):
                    header_value = header_value.encode("utf-8")

                request.setRawHeader(header.encode("utf-8"), header_value)
    request.setAttribute(QNetworkRequest.AutoDeleteReplyOnFinishAttribute, True)

    return request


def get(url: str, url_values: Optional[Dict[Any, Any]] = None, headers: Optional[Dict[Any, Any]] = None,
        authCfg: str = "", forceRefresh: bool = True) -> QgisResponse:
    """ Allows a network GET request with QgsNetworkAccessManager to use defined proxy settings and more.

        :param url: network url
        :param url_values: values to add to url (?value=n...)
        :param headers: header data, more information for headers at https://doc.qt.io/qt-5/qnetworkrequest.html#KnownHeaders-enum
                        {QNetworkRequest.ContentTypeHeader: "application/json"}
                        or use (byte-)string, when using string or byte string, both of them must be same type
        :param authCfg: QGIS argument, See `QgsNetworkAccessManager.blockingGet`. True to refresh/not use the cache
        :param forceRefresh: QGIS argument, See `QgsNetworkAccessManager.blockingGet`. True to refresh/not use the cache
    """
    # create Qt request object
    request = get_network_request(url, url_values, headers)

    # query via network manager with qgis
    manager = QgsNetworkAccessManager.instance()
    response: QgsNetworkReplyContent = manager.blockingGet(request, authCfg, forceRefresh)
    return QgisResponse(response)


def post(url: str, *, url_values: Optional[Dict[Any, Any]] = None, post_data: Optional[bytes] = None,
         headers: Optional[Dict[Any, Any]] = None, authCfg: str = "",
         forceRefresh: bool = True) -> QgisResponse:
    """ Allows a network POST request with QgsNetworkAccessManager to use defined proxy settings and more.

        :param url: network url
        :param url_values: values to add to url (?value=n...)
        :param post_data: Data to post. E.g. url encoded dictionary and converted to bytes.
        :param headers: header data, more information for headers at https://doc.qt.io/qt-5/qnetworkrequest.html#KnownHeaders-enum
                        {QNetworkRequest.ContentTypeHeader: "application/json"}
                        or use (byte-)string, when using string or byte string, both of them must be same type
        :param forceRefresh: True to refresh/not use the cache
    """
    # create Qt request object
    request = get_network_request(url, url_values, headers)

    # use the given post_data or fall back to an empty byte string
    post_data = post_data or b""  # defaults to empty byte string

    # query via network manager with qgis
    manager = QgsNetworkAccessManager.instance()
    response: QgsNetworkReplyContent = manager.blockingPost(request, post_data, authCfg, forceRefresh)
    return QgisResponse(response)
