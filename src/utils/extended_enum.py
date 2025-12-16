from __future__ import annotations
from typing import Any
from enum import Enum

class ExtendedEnum(Enum):
    """
    Extension of the basic enumerator.
    """
    OTHER = ""

    @classmethod
    def by_value(cls, val):
        res = [x.name for x in cls.__members__.values() if x.value == val]
        if len(res) > 0:
            return cls[res[0]]
        return cls.OTHER
    
    @classmethod
    def from_name(cls, val):
        res = [x.name for x in cls.__members__.values() if x.name.lower() == val.lower()]
        if len(res) > 0:
            return cls[res[0]]
        return cls.OTHER
    
    @classmethod
    def get_members(cls):
        return [cls[x] for x in cls.__members__]
    
    @classmethod
    def get_values(cls):
        return [x.value for x in cls.get_members()]