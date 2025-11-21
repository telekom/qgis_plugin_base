# -*- coding: utf-8 -*-
# SPDX-FileCopyrightText: 2025 Deutsche Telekom Technik GmbH <f.vonstudsinske@telekom.de>
# SPDX-License-Identifier: GPL-3.0-or-later

import pytest

from typing import Annotated

from ..enum_ import Enum


class MyTestEnum(Enum):
    IsAnnotated: Annotated[str, "Yes I am annotated!"] = "yes"
    IsAnnotatedEmpty: Annotated[str, ""] = "partiallyyes"
    IsNotAnnotated = "no"


def test_get_enum():
    assert MyTestEnum.get_enum(MyTestEnum.IsAnnotated) is MyTestEnum.IsAnnotated

    assert MyTestEnum.get_enum("yes") is MyTestEnum.IsAnnotated

    assert MyTestEnum.get_enum("IsNotAnnotated") is MyTestEnum.IsNotAnnotated

    with pytest.raises(ValueError):
        MyTestEnum.get_enum("roflcopter")


def test_is_annotated():
    assert MyTestEnum.get_doc(MyTestEnum.IsAnnotated) == "Yes I am annotated!"
    assert MyTestEnum.get_doc(MyTestEnum.IsAnnotatedEmpty) == ""


def test_is_not_annotated():
    assert MyTestEnum.get_doc(MyTestEnum.IsNotAnnotated) is None
