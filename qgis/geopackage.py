# -*- coding: utf-8 -*-
# SPDX-FileCopyrightText: 2025 Deutsche Telekom Technik GmbH <f.vonstudsinske@telekom.de>
# SPDX-License-Identifier: GPL-3.0-only

import sqlite3
from typing import Any, Dict, Optional, Union

SQL_ALL_LAYERS = """SELECT table_name, column_name, geometry_type_name, srs_id FROM gpkg_geometry_columns;"""
SQL_ALL_TABLES = """SELECT table_name, data_type, identifier FROM gpkg_contents;"""
SQL_JOINED_TABLES = """SELECT gpkg_contents.table_name, gpkg_contents.data_type, gpkg_contents.identifier, 
                              gpkg_geometry_columns.column_name, gpkg_geometry_columns.geometry_type_name, 
                              gpkg_geometry_columns.srs_id 
                       FROM gpkg_contents LEFT JOIN gpkg_geometry_columns 
                                                    ON gpkg_contents.table_name=gpkg_geometry_columns.table_name;"""
SQL_LAYER_COLUMNS = """PRAGMA table_info(%s);"""
SQL_SRS = ("""SELECT srs_name, srs_id, organization, organization_coordsys_id, definition, description """
           """FROM gpkg_spatial_ref_sys WHERE srs_id=?;""")
SQL_TABLE_EXISTS = "SELECT COUNT(table_name) FROM gpkg_contents WHERE table_name=?"


class GeoPackage:
    """ This class provides read methods to the sqlite3
        database.
        GeoPackage: www.geopackage.org

        :param path: path to geo package file
    """

    def __init__(self, path: str) -> None:
        self.path: str = path

    def connect(self) -> sqlite3.Connection:
        """ connects to geo package file and returns connection object

            :return: connection,
            :rtype: sqlite3.Connection
        """

        return sqlite3.connect(self.path)

    def has_layer(self, layer_name: str) -> bool:
        """ Returns True, if `layer_name` is in GeoPackage (layer or table).
            Search is case sensitive!

            :param layer_name: case sensitive layer name
        """

        con = self.connect()
        cur = con.cursor()
        cur.execute(SQL_TABLE_EXISTS, (layer_name, ))
        result = cur.fetchone()
        con.close()

        return bool(result[0])

    def get_layers(self) -> Dict[str, Dict[str, Union[Any, Dict[str, str]]]]:
        """ get all available layers in geo package

            :return: dict with available layers
        """
        layers = {}

        con = self.connect()
        cur = con.cursor()
        cur.execute(SQL_JOINED_TABLES)

        for table_name, data_type, identifier, column_name, geometry_type_name, srs_id in cur.fetchall():
            if srs_id is not None:
                cur.execute(SQL_SRS, (srs_id,))
                srs_name, srs_id, organization, organization_coord_sys_id, definition, description = cur.fetchone()
            else:
                srs_name = organization = organization_coord_sys_id = definition = description = None
            layers[table_name] = {
                'name': table_name,  # table-/layer name
                'geometrycolumn': column_name,  # column for geometry
                'geometrytype': geometry_type_name,  # geometry type, e.g. POINT
                'data_type': data_type,  # feature for features with SRS and attribute for NON geometry values
                'identifier': identifier,  # identifier, usually equal to table_name
                'srs': {  # srs id for x/y transform
                    'srsid': srs_id,  # srs id, None in case of no SRS set (e.g.
                    'srs_name': srs_name,  # display name of srs
                    'organization': organization,  # e.g. EPSG
                    'organization_coordsys_id': organization_coord_sys_id,
                    'definition': definition,
                    'description': description,
                },
                'uri': self.get_uri(table_name),  # qgis uri to access this layer
            }

        con.close()

        return layers

    def get_uri(self, layer_name: str) -> str:
        """ creates qgis compatible uri to access layer in geo package file

            :param layer_name: layer name/table name
            :return: path to layer
        """
        uri = f"{self.path}|layername={layer_name}"

        return uri

    def get_columns(self, table_name: str) -> Dict[str, Dict[str, object]]:
        """ Reads available layer columns

            :param table_name: layer name/table name
            :return: ordered dict with columns and more info
        """

        columns = {}

        if not self.has_layer(table_name):
            raise ValueError(f"Missing table '{table_name}'")

        con = self.connect()
        cur = con.cursor()

        for column in cur.execute(SQL_LAYER_COLUMNS % table_name):
            index, name, value_type, notnull, default, primary = column
            columns[name] = {
                'index': index,
                'column': name,
                'type': value_type,
                'notnull': notnull,
                'default': default,
                'primary': primary,
            }

        con.close()

        return columns

    def fetchone(self, query: str, args: Optional[list] = None) -> Optional[tuple]:
        """ fetches one sql value from query

            :param query: query string
            :param args: query string, indexed iterable, like list/tuple
            :return: None or tuple with values
        """

        if args is None:
            args = []

        con = self.connect()
        cur = con.cursor()
        cur.execute(query, args)
        result = cur.fetchone()

        return result

    def fetchmany(self, query: str, args: Optional[list] = None):
        """ fetches many sql values from query

            :param query: query string
            :param args: query string, indexed iterable, like list/tuple
            :return: any
        """

        if args is None:
            args = []

        con = self.connect()
        cur = con.cursor()
        cur.execute(query, args)
        result = cur.fetchmany()

        return result

    def fetchall(self, query: str, args: Optional[list] = None):
        """ fetches all sql values from query

            :param query: query string
            :param args: query string, indexed iterable, like list/tuple
            :return: any
        """

        if args is None:
            args = []

        con = self.connect()
        cur = con.cursor()
        cur.execute(query, args)
        result = cur.fetchall()

        return result
