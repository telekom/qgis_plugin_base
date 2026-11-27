# -*- coding: utf-8 -*-
# SPDX-FileCopyrightText: 2025 Deutsche Telekom Technik GmbH <f.vonstudsinske@telekom.de>
# SPDX-License-Identifier: GPL-3.0-only
""" Parse and compare the numeric versions used by the plugin template. """

import re

from dataclasses import dataclass, field


@dataclass(frozen=True, order=True, init=False)
class Version:
    """ Represent an immutable numeric version without full PEP 440 compatibility.

        Accept one to three ASCII numeric components and an optional lowercase v.
        Examples: 1, 1.1, 1.1.1, v1, v1.1, v1.1.1.
        Comparisons pad missing components with zeros; string output retains the
        component count and removes the prefix and leading zeros. Invalid strings
        raise ValueError, and non-string inputs raise TypeError. Comparisons with
        other version types are not supported.

        :param version: numeric version string
    """

    _parts: tuple[int, int, int]
    _display: str = field(compare=False)

    def __init__(self, version: str) -> None:
        """ Parse the version string.

            :param version: numeric version string
        """
        if not isinstance(version, str):
            raise TypeError("version must be a string")
        if re.fullmatch(r"v?[0-9]+(?:\.[0-9]+){0,2}", version) is None:
            raise ValueError(f"Invalid version: {version!r}")

        components = tuple(int(component) for component in version.removeprefix("v").split("."))
        object.__setattr__(self, "_parts", (*components, 0, 0, 0)[:3])
        object.__setattr__(self, "_display", ".".join(str(component) for component in components))

    def __str__(self) -> str:
        """ Return the normalized version string. """
        return self._display
