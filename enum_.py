# -*- coding: utf-8 -*-
# SPDX-FileCopyrightText: 2025 Deutsche Telekom Technik GmbH <f.vonstudsinske@telekom.de>
# SPDX-License-Identifier: GPL-3.0-only

from enum import Enum as Enum_
from typing import Any, Dict, List, Optional, get_type_hints


class Enum(Enum_):
    """ Reimplementation of default Enum class with extra methods.
        No relevant changes in default functionality.
        On equality check the raw values are compared.

        Examples:

            .. code-block:: python

                class MyEnums(Enum):
                    Red = 'red'

                MyEnums.contains("Herbert")

            .. code-block:: python

                class MyEnums(Enum):
                    Red: Annotated[str, "Ich bin eine rote Farbe"] = 'red'

                print(MyEnums.get_doct(MyEnums.Red))

            True: MyEnums.Red == MyEnums.Red
            True: MyEnums.Red == "red"
            True: MyEnums.Red.value == "red" ("red" == "red")

    """

    @classmethod
    def contains(cls, member: object) -> bool:
        """ Does Enum contains given member/value?

            :param member: `member`s value, member -> Enum.member
            :return: True when `member` is a member of this Enum-class
        """
        if isinstance(member, cls):
            return member in cls.members().values()
        else:
            return member in cls.keys()

    @classmethod
    def members(cls) -> Dict[Any, 'Enum']:
        """ returns all members as dict.
            Keys are the raw values and referenced values are the enum values.
        """
        return cls.__members__

    @classmethod
    def keys(cls) -> List[Any]:
        """ returns all member values in a list """
        return [_.value for _ in cls.members().values()]

    @classmethod
    def get_enum(cls, value) -> 'Enum':
        """ Returns the enum value for the given raw value, value or value name.

            :param value: enum value key, enum value name or enum value itself to look for

            :raises ValueError: No enum value found for given value
        """
        for key_str, enum_value in cls.members().items():

            if enum_value == value:
                return enum_value

        for key_str, enum_value in cls.members().items():

            if key_str == value:
                return enum_value

        raise ValueError(f"{value} not found in {cls.__name__}")

    @classmethod
    def get_doc(cls, value: Enum_) -> Optional[str]:
        """ Returns a doc string for the given enum value, defaults to None if not set. """
        try:
            # get the type hints from the given value
            hints = get_type_hints(value, include_extras=True)

            # get the metadata values to return the docstring
            annotated_hint = hints[value.name]
            return "\n".join(annotated_hint.__metadata__)
        except (TypeError, KeyError):
            return None

    def __eq__(self, o: object) -> bool:
        if isinstance(o, Enum):
            v = o.value
        else:
            v = o
        return self.value == v

    def __hash__(self) -> int:
        return hash(self.value)

    def __str__(self) -> str:
        return str(self.value)
