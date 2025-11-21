# -*- coding: utf-8 -*-
# SPDX-FileCopyrightText: 2025 Deutsche Telekom Technik GmbH <f.vonstudsinske@telekom.de>
# SPDX-License-Identifier: GPL-3.0-or-later

# Hint: Some content is inspired by `requests.modules.Response`.

import json

from qgis.core import QgsNetworkReplyContent
from qgis.PyQt.QtNetwork import QNetworkRequest, QNetworkReply

from requests.compat import chardet
from requests.structures import CaseInsensitiveDict


class RequestError(Exception):
    ...


class QgisResponse:
    """ Method and attribute names bases on `requests.modules.Response` """

    def __init__(self, network_reply: QgsNetworkReplyContent):

        self.network_reply: QgsNetworkReplyContent = network_reply

        self.encoding = None
        """ encoding for the response e.g., "utf-8" """

        self.headers = CaseInsensitiveDict({
            bytes(header).decode(): network_reply.rawHeader(header) for header in network_reply.rawHeaderList()
        })

    def __repr__(self):
        return f"<QgisResponse [{self.status_code}]>"

    def error(self) -> QNetworkReply.NetworkError:
        """ See `QgsNetworkReplyContent.error` """
        return self.network_reply.error()

    def errorString(self) -> str:
        """ See `QgsNetworkReplyContent.errorString` """
        return self.network_reply.errorString()

    @property
    def status_code(self):
        return self.network_reply.attribute(QNetworkRequest.HttpStatusCodeAttribute)

    @property
    def content(self) -> bytes:
        """Content of the response, in bytes."""

        return bytes(self.network_reply.content())

    @property
    def text(self) -> str:
        """Content of the response, in unicode.

        If Response.encoding is None, encoding will be guessed using
        ``charset_normalizer`` or ``chardet``.

        The encoding of the response content is determined based solely on HTTP
        headers, following RFC 2616 to the letter. If you can take advantage of
        non-HTTP knowledge to make a better guess at the encoding, you should
        set ``r.encoding`` appropriately before accessing this property.
        """

        # Try charset from content-type
        encoding = self.encoding

        if not self.content:
            # empty content, return an empty string
            return ""

        # Fallback to auto-detected encoding.
        if self.encoding is None:
            encoding = self.apparent_encoding

        # Decode unicode from given encoding.
        try:
            content = str(self.content, encoding, errors="replace")
        except (LookupError, TypeError):
            # A LookupError is raised if the encoding was not found which could
            # indicate a misspelling or similar mistake.
            #
            # A TypeError can be raised if encoding is None
            #
            # So we try blindly encoding.
            content = str(self.content, errors="replace")

        return content

    def json(self):
        """ Call it to get the content as a json object (dict/list). """

        return json.loads(self.content)

    @property
    def apparent_encoding(self):
        """The apparent encoding, provided by the charset_normalizer or chardet libraries."""
        return chardet.detect(self.content)["encoding"]

    @property
    def url(self):
        """The requested url"""
        return self.network_reply.request().url()

    def raise_for_status(self):
        """Raises :class:`HTTPError`, if one occurred."""

        http_error_msg = ""

        if 400 <= self.status_code < 500:
            http_error_msg = (
                f"{self.status_code} Client Error: {self.errorString()} for url: {self.url}"
            )

        elif 500 <= self.status_code < 600:
            http_error_msg = (
                f"{self.status_code} Server Error: {self.errorString()} for url: {self.url}"
            )

        if http_error_msg:
            raise RequestError(http_error_msg)
