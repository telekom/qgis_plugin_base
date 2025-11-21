# -*- coding: utf-8 -*-
# SPDX-FileCopyrightText: 2025 Deutsche Telekom Technik GmbH <f.vonstudsinske@telekom.de>
# SPDX-License-Identifier: GPL-3.0-or-later

import sqlite3

from typing import List, Tuple


class ValidateSqlite3File:
    """ Validates a new DB has the same tables and columns with an DB template.

        .. code-block:: python

            # tests if `validate.db` has same tables, columns defined in `file.db`
            ok, results = ValidateSqlite3File.compare("main/file.db", "to/validate.db")
    """

    GET_TABLES = """SELECT name FROM sqlite_master WHERE type ='table' AND name NOT LIKE 'sqlite_%';"""
    GET_COLUMNS = """PRAGMA table_info({});"""

    @classmethod
    def compare(cls, template_db_file: str, check_db_file: str) -> Tuple[bool, Tuple[str, str]]:
        """ proofs whether the new DB has more or less Tables or columns than the DB template

            :param template_db_file: path to master db
            :param check_db_file: path to db to validate

            :return: boolean falls to False on error, Tuple with a bool and a tuple with error texts
        """
        # calls the compareTables method
        ok, table_error = cls.compare_tables(template_db_file, check_db_file)
        if not ok:
            # outputs an error and the missing tables
            name = ",".join(table_error)
            return False, ("Prüfdatenbank fehlerhaft, Tabellen Fehlen", name)

        ok, table_error = cls.compare_tables(check_db_file, template_db_file)
        if not ok:
            # outputs an error and the unknown tables
            name = ",".join(table_error)
            return False, ("Projektdatenbank fehlerhaft, Tabellen unbekannt", name)

        con_template = sqlite3.connect(template_db_file)
        cur_template = con_template.cursor()
        cur_template.execute(cls.GET_TABLES)
        template_tables = cur_template.fetchall()
        con_template.close()

        for table in template_tables:

            # calls the compare_columns method
            ok, column_error = cls.compare_columns(template_db_file, check_db_file, table[0])
            if not ok:
                column_names = ",".join(column_error)
                return False, ("Projektdatenbank fehlerhaft, Spalte:", column_names)

        return True, tuple()

    @classmethod
    def compare_tables(cls, template_db_file: str, check_db_file: str) -> Tuple[bool, List[str]]:
        """ compares whether the tables of the template are also in the new DB

            :param template_db_file: path to master db
            :param check_db_file: path to db to validate
            :return: Tuple with a bool and table names
        """

        template_tables_list = []
        data_tables_list = []
        table_error = []

        con_template = sqlite3.connect(template_db_file)  # DB Template connection
        cur_template = con_template.cursor()
        cur_template.execute(cls.GET_TABLES)  # gets all tables from DB Template

        con_database = sqlite3.connect(check_db_file)  # new DB connection
        cur_database = con_database.cursor()
        cur_database.execute(cls.GET_TABLES)

        for table in cur_template.fetchall():  # from all tables
            template_tables_list.append(table[0])
        for table in cur_database.fetchall():
            data_tables_list.append(table[0])

        for table in template_tables_list:
            if table not in data_tables_list:
                table_error.append(table)

        con_template.close()  # closes the template connection
        con_database.close()  # closes the new DB connection

        return not bool(table_error), table_error

    @classmethod
    def compare_columns(cls, template_db_file: str, check_db_file: str, name: str) -> Tuple[bool, List[str]]:
        """ Proofs whether the columns of the master DB are also in the check DB

            :param template_db_file: path to master db
            :param check_db_file: path to db to validate
            :param name: table name
            :return: Tuple with a bool and table names
        """

        # ["UID-CHAR", ...]
        template_columns_list = []
        data_columns_list = []
        column_error = []

        con_template = sqlite3.connect(template_db_file)
        cur_template = con_template.cursor()
        cur_template.execute(cls.GET_COLUMNS.format(name))

        con_database = sqlite3.connect(check_db_file)
        cur_database = con_database.cursor()
        cur_database.execute(cls.GET_COLUMNS.format(name))

        for column in cur_template.fetchall():
            template_columns_list.append(f"{column[1]}-{column[2]}")  # adds the column 1,2 to new list
        for column in cur_database.fetchall():
            data_columns_list.append(f"{column[1]}-{column[2]}")  # adds the column 1,2 to new list

        for column in template_columns_list:
            # proofs whether columns from master in new DB. if not adds column name to new list
            if column not in data_columns_list:
                column_error.append(column)

        con_template.close()
        con_database.close()

        return not bool(column_error), column_error
