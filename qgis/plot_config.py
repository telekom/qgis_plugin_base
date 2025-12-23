# -*- coding: utf-8 -*-
# SPDX-FileCopyrightText: 2025 Deutsche Telekom Technik GmbH <f.vonstudsinske@telekom.de>
# SPDX-License-Identifier: GPL-3.0-only

from qgis.core import QgsWkbTypes, NULL
from qgis.PyQt.QtCore import QVariant

PLOT_PAGES = {
    'NAME': 'pages',
    'WKBTYPE': QgsWkbTypes.Polygon,
    'WKBTYPES': [QgsWkbTypes.Polygon],
    'Attributes': {
        # page number
        'page': {
            'type': QVariant.Int,
            'default': NULL
        },
        # show qgis map tips on this page
        'show_map_tips': {
            'type': QVariant.Bool,
            'default': True
        },
        # show legend on page
        'show_legend_on_page': {
            'type': QVariant.Bool,
            'default': True
        },
        # page number
        'scale': {
            'type': QVariant.Int,
            'default': NULL
        },
        # show mini map
        'show_mini_map': {
            'type': QVariant.Bool,
            'default': True
        },
        # file-attribute from plots.xml
        'file': {
            'type': QVariant.String,
            'default': "{}"
        },
        # PlotLayout option string
        # {item-name: (value, boolean)}
        # boolean -> True: use global option
        # boolean -> False: use entered valued
        'options': {
            'type': QVariant.String,
            'default': "{}"
        },
        # layer visibility
        'visibility': {
            'type': QVariant.String,
            'default': "{}"
        },
    },
}

PLOT_OPTIONS = {
    # only one QgsFeature for this table
    'NAME': 'pages',
    'WKBTYPE': QgsWkbTypes.NoGeometry,
    'WKBTYPES': [QgsWkbTypes.NoGeometry],
    'Attributes': {
        # merge legend together on one page
        'legend_on_extra_page': {
            'type': QVariant.Bool,
            'default': False
        },
        # show legend on page
        'show_legend_on_page': {
            'type': QVariant.Bool,
            'default': True
        },
        # show mini map
        'show_mini_map': {
            'type': QVariant.Bool,
            'default': True
        },
        # merge legend together on one page
        'create_overview_page': {
            'type': QVariant.Bool,
            'default': True
        },
        # show qgis map tips
        'show_map_tips': {
            'type': QVariant.Bool,
            'default': True
        },
        # default dpi
        'dpi': {
            'type': QVariant.Int,
            'default': 150
        },
        # default scale
        'scale': {
            'type': QVariant.Int,
            'default': 500
        },
        # file-attribute from plots.xml
        'file': {
            'type': QVariant.String,
            'default': NULL
        },
        # PlotLayout option string
        # {item-name: (value, boolean)}
        # boolean: always True
        'options': {
            'type': QVariant.String,
            'default': "{}"
        },
        # layer visibility
        'visibility': {
            'type': QVariant.String,
            'default': "{}"
        },
    },
}
