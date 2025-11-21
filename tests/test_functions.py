# -*- coding: utf-8 -*-
# SPDX-FileCopyrightText: 2025 Deutsche Telekom Technik GmbH <f.vonstudsinske@telekom.de>
# SPDX-License-Identifier: GPL-3.0-only

import pytest
import re
import tempfile

from pathlib import Path
from re import compile

from ..functions import file_matches_pattern, get_python_site_version_folder_name, get_uri_mode, get_test_folders
from ..constants import URI_OS, URI_WEB, URI_ERROR

# use the root dir of the basics module
ROOT_DIR = Path(__file__).parent.parent


def test_python_site():
    site_python_name = get_python_site_version_folder_name()
    assert site_python_name

    assert re.fullmatch(r"^Python\d+$", site_python_name)


@pytest.mark.parametrize("uri,mode", [("https://telekom.de", URI_WEB),
                                      ("www.telekom.de", URI_WEB),
                                      (__file__, URI_OS),
                                      ("error", URI_ERROR)])
def test_get_uri_mode(uri: str, mode: str):
    assert get_uri_mode(uri) == mode


@pytest.mark.parametrize("ends_with, ignore_list, result_count",
                         [
                             (["tests"], [re.compile("^one/tests$")], 3),
                             (["tests"], [re.compile("^(one|two|three)/tests$")], 1),  # only sub/four
                             (["tests"], [], 4),  # only sub/four
                             (["tests"], [re.compile(".*/tests$")], 0),
                             (["tests"], ["one/tests", "two/tests", "three/tests", "sub/four/tests"], 0),
                             (["tests"], [re.compile(".*four.*")], 3),
                             (["tests"], [], 4),
                         ])
def test_get_test_folders(ends_with, ignore_list, result_count):
    with tempfile.TemporaryDirectory() as tempdir:
        temp_dir = Path(tempdir)

        test_1 = temp_dir / "one" / "tests"
        test_1.mkdir(parents=True, exist_ok=True)

        test_2 = temp_dir / "two" / "tests"
        test_2.mkdir(parents=True, exist_ok=True)

        test_3 = temp_dir / "three" / "tests"
        test_3.mkdir(parents=True, exist_ok=True)

        test_4 = temp_dir / "sub" / "four" / "tests"
        test_4.mkdir(parents=True, exist_ok=True)

        assert len(get_test_folders(temp_dir, ends_with=ends_with, ignore_paths=ignore_list)) == result_count, \
            "Returned path count not matches the expected path count"


@pytest.mark.parametrize("file,root_dir,input_list,expected_result",
                         [
                             (ROOT_DIR / "basics.py", ROOT_DIR, ["basics.py"], True),
                             (ROOT_DIR / "basics.py", ROOT_DIR, [compile(".*[.]py")], True),
                             (ROOT_DIR / "basics.py", None, ["basics.py"], False),
                             (ROOT_DIR / "basics.py", None, [(ROOT_DIR / "basics.py").as_posix()], True),

                             (ROOT_DIR / "workaround" / "openpyxl.py", ROOT_DIR, [compile("^workaround/openpyxl[.]py$")], True),
                             (ROOT_DIR / "workaround" / "openpyxl.py", None, ["basics.py"], False),
                         ])
def test_file_matches_pattern(file, root_dir, input_list, expected_result):

    assert file_matches_pattern(file, root_dir, input_list) is expected_result
