# -*- coding: utf-8 -*-
# SPDX-FileCopyrightText: 2025 Deutsche Telekom Technik GmbH <f.vonstudsinske@telekom.de>
# SPDX-License-Identifier: GPL-3.0-or-later

import hashlib
import os

from pathlib import Path
from typing import List, Optional
from zipfile import ZipFile, ZIP_DEFLATED

from .functions import get_files


class CreatePluginZip:
    """ CreatePluginZip will create a new plugin zip file for QGIS.

        All __pycache__ files will not be zipped.
        To ignore specific paths, you have to specify them in the parameters.

        :param zip_file_name: new zip file name (without file ending)
        :param source_location: source folder to zip
        :param destination_path: destination path for new zip file
        :param ignore_paths: ignore given relative paths in this folder
    """

    def __init__(self, zip_file_name: str, source_location: str,
                 destination_path: str, ignore_paths: List[str],
                 overwrite: bool = False,
                 write_hash: bool = True):

        if not overwrite:
            if Path(destination_path).is_file():
                raise FileExistsError(f"file '{destination_path}' already exists")
        else:
            if Path(destination_path).is_file():
                os.remove(destination_path)

        self.zip_file_name = zip_file_name
        self.source_location = os.path.normpath(source_location)
        self.destination_path = os.path.normpath(destination_path)
        self.ignore_paths = [os.path.normpath(os.path.join(self.source_location, path))
                             for path in ignore_paths if path]  # remove empty path string
        if self.destination_path in self.ignore_paths:
            self.ignore_paths.remove(self.destination_path)

        self.errors = []
        self.log = []

        self.files_to_zip = list(get_files(source_location, ignore_paths=self.ignore_paths))
        if not self.files_to_zip:
            raise FileNotFoundError("no files found to zip")

        self.hash: Optional[str] = None
        if write_hash:
            self.get_hash_value()
        self.log.append(f"hash value generated: {self.hash}")

        self.write()

        self.__validate_plugin_zip()

    def __validate_plugin_zip(self):
        """ Validates the created zip file with the minimum files and structure

            Checks the zip file structure:

                - plugin_name.zip/
                    - plugin_name/
                        - __init__.py
                        - plugin.py
                        - metadata.txt

            :raises FileNotFoundError: Missing paths in the zipfile.
        """
        root_path = f"{self.zip_file_name}/{Path(self.destination_path).stem}"
        required_paths = [root_path, f"{root_path}/metadata.txt", f"{root_path}/plugin.py", f"{root_path}/__init__.py"]
        with ZipFile(self.destination_path, mode="r", compression=ZIP_DEFLATED) as zip_:
            zip_paths = [zip_path.filename for zip_path in zip_.filelist]

            if not all(map(lambda x: x not in zip_paths, required_paths)):
                raise FileNotFoundError(f"missing at least one path in the zip file, {required_paths=}")

    def write(self):
        """ writes to new zip zile """

        with ZipFile(self.destination_path, mode="w", compression=ZIP_DEFLATED) as zip_:
            for file in self.files_to_zip:

                if "__pycache__" in file:
                    continue

                self.log.append(f"writing {file}")
                path_in_zip = self.zip_file_name + "/" + file[len(self.source_location):]
                zip_.write(file, path_in_zip)

    def get_hash_value(self):
        """ calculating hash value of all files to zip """

        hash_object = hashlib.blake2b()

        def hash_file(file: str):
            with open(file, "rb") as f:
                bytes_ = f.read()
                hash_object.update(bytes_)

        list(map(hash_file, self.files_to_zip))

        self.hash = hash_object.digest().hex()
