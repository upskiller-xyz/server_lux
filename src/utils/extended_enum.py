from __future__ import annotations
from typing import Any
from enum import Enum


class ExtendedEnumMixin:
    """
    Mixin class to extend Enum functionality.

    Usage: class MyEnum(ExtendedEnumMixin, Enum)

    This provides additional methods for enum classes without
    preventing inheritance (Python enums with members cannot be extended).
    """

    @classmethod
    def by_value(cls, val):
        """Find enum member by value, return None if not found"""
        res = [x for x in cls.__members__.values() if x.value == val]
        if len(res) > 0:
            return res[0]
        return None

    @classmethod
    def from_name(cls, val):
        """Find enum member by name (case-insensitive), return None if not found"""
        res = [x for x in cls.__members__.values() if x.name.lower() == val.lower()]
        if len(res) > 0:
            return res[0]
        return None

    @classmethod
    def get_members(cls):
        """Get all enum members as a list"""
        return [cls[x] for x in cls.__members__]

    @classmethod
    def get_values(cls):
        """Get all enum values as a list"""
        return [x.value for x in cls.get_members()]


# Backward compatibility alias
class ExtendedEnum(ExtendedEnumMixin, Enum):
    """
    Backward compatibility class.

    Note: This class should NOT be extended directly as it contains a member (OTHER).
    Use ExtendedEnumMixin instead:

    Correct:   class MyEnum(ExtendedEnumMixin, Enum)
    Incorrect: class MyEnum(ExtendedEnum)  # Will fail!
    """
    OTHER = ""