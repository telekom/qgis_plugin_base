# -*- coding: utf-8 -*-
# SPDX-FileCopyrightText: 2025 Deutsche Telekom Technik GmbH <f.vonstudsinske@telekom.de>
# SPDX-License-Identifier: GPL-3.0-only

class NoIntersectionFoundError(Exception):
    ...


class PointNotOnPolyLineError(Exception):
    ...


class NoPathFoundError(Exception):
    ...


class PreparationError(Exception):
    ...


class TransformError(Exception):
    ...


class RollbackError(Exception):
    ...


class ReadOnlyActiveException(Exception):
    """ thrown if layer is in readOnly mode and further actions can not be processed
    """
    ...


class UpdateFeatureException(Exception):
    """ thrown if changes in layer / dataprovider not possible
    """
    ...
