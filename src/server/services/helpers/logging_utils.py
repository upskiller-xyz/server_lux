from typing import Any, Dict, List, Set
from abc import ABC, abstractmethod


class ILoggingFormatter(ABC):
    """Interface for logging formatters"""

    @abstractmethod
    def format(self, data: Any) -> Any:
        """Format data for logging"""
        pass


class LengthReplacementStrategy:
    """Strategy for replacing long values with their lengths

    Uses Strategy Pattern - defines keys that should be replaced with length info.
    """

    # Keys that should show length instead of full content
    KEYS_TO_TRIM: Set[str] = {
        'mesh',
        'obstruction_angle_horizon',
        'obstruction_angle_zenith',
        'horizon_angles',
        'zenith_angles',
        'direction_angles',
        'direction_angles_degrees',
        'df_values',
        'mask',
        'room_mask',
        'df_matrix',
        'image_array',
        'image_base64',
        'data'
    }

    # Keys that should recurse into if they are dicts
    DICT_RECURSE_KEYS: Set[str] = {
        'result',
        'results'
    }

    # Keys that contain coordinate/mesh data that should have floats rounded
    COORDINATE_KEYS: Set[str] = {
        'mesh',
        'windows',
        'room_polygon',
        'x', 'y', 'z',
        'x1', 'y1', 'z1',
        'x2', 'y2', 'z2',
        'reference_point',
        'highest_point'
    }

    @classmethod
    def should_trim(cls, key: str) -> bool:
        """Check if key should be trimmed"""
        return key in cls.KEYS_TO_TRIM

    @classmethod
    def should_recurse_dict(cls, key: str) -> bool:
        """Check if dict value should be recursed into"""
        return key in cls.DICT_RECURSE_KEYS

    @classmethod
    def should_round_coordinates(cls, key: str) -> bool:
        """Check if key contains coordinate data that should be rounded"""
        return key in cls.COORDINATE_KEYS

    @classmethod
    def format_value(cls, value: Any) -> str:
        """Format value to show its length/size and first element

        Args:
            value: Value to format

        Returns:
            Formatted string with length/shape and first element info
        """
        if isinstance(value, (list, tuple)):
            length = len(value)
            if length == 0:
                return f"<empty {type(value).__name__}>"

            first_elem = cls._safe_get_first_element(value)
            return f"<{type(value).__name__} of {length} items, first={first_elem}>"

        elif isinstance(value, dict):
            keys = list(value.keys())
            return f"<dict with keys: {keys}>"

        elif isinstance(value, str):
            if len(value) > 100:
                return f"<string of {len(value)} chars>"
            return value

        elif hasattr(value, 'shape'):  # numpy arrays
            first_elem = cls._safe_get_first_element(value)
            return f"<array shape={value.shape}, first={first_elem}>"

        elif hasattr(value, '__len__'):
            length = len(value)
            first_elem = cls._safe_get_first_element(value)
            return f"<{type(value).__name__} length={length}, first={first_elem}>"

        return value

    @staticmethod
    def _round_float(value: Any) -> Any:
        """Round float values to 2 decimal places"""
        if isinstance(value, float):
            return round(value, 2)
        return value

    @classmethod
    def _round_nested_floats(cls, value: Any, max_depth: int = 3, _current_depth: int = 0) -> Any:
        """Recursively round all floats in nested structures

        Args:
            value: Value to process (can be float, list, dict, etc.)
            max_depth: Maximum recursion depth
            _current_depth: Current recursion depth (internal)

        Returns:
            Value with all floats rounded to 2 decimal places
        """
        if _current_depth >= max_depth:
            return value

        if isinstance(value, float):
            return round(value, 2)
        elif isinstance(value, (list, tuple)):
            rounded = [cls._round_nested_floats(item, max_depth, _current_depth + 1) for item in value]
            return type(value)(rounded)
        elif isinstance(value, dict):
            return {k: cls._round_nested_floats(v, max_depth, _current_depth + 1) for k, v in value.items()}
        elif hasattr(value, 'shape'):  # numpy array
            # For numpy arrays, use numpy's round
            try:
                import numpy as np
                if np.issubdtype(value.dtype, np.floating):
                    return np.round(value, 2)
            except ImportError:
                pass
        return value

    @staticmethod
    def _safe_get_first_element(value: Any) -> Any:
        """Safely get first element from a collection

        For 2D arrays/lists, gets [0][0]. For 1D, gets [0].
        Rounds floats to 2 decimal places.
        Handles errors gracefully.
        """
        try:
            if hasattr(value, 'shape') and len(value.shape) >= 2:
                # 2D+ array - get [0][0]
                elem = value[0][0]
                return LengthReplacementStrategy._round_float(elem)
            elif hasattr(value, '__getitem__'):
                first = value[0]
                # Check if first element is also indexable (2D list)
                if hasattr(first, '__getitem__') and not isinstance(first, str):
                    try:
                        elem = first[0]
                        return LengthReplacementStrategy._round_float(elem)
                    except (IndexError, TypeError):
                        return LengthReplacementStrategy._round_float(first)
                return LengthReplacementStrategy._round_float(first)
            return "N/A"
        except (IndexError, TypeError, KeyError):
            return "N/A"


class LoggingDictFormatter(ILoggingFormatter):
    """Formats dictionaries for logging by trimming long values

    Implements Strategy Pattern - uses LengthReplacementStrategy to determine
    which keys to trim.
    """

    def format(self, data: Any, max_depth: int = 5, _current_depth: int = 0) -> Any:
        """Format data for logging by replacing long values with length info

        Args:
            data: Data to format
            max_depth: Maximum recursion depth
            _current_depth: Current recursion depth (internal use)

        Returns:
            Formatted data safe for logging
        """
        if _current_depth >= max_depth:
            return "<max depth reached>"

        if isinstance(data, dict):
            return self._format_dict(data, max_depth, _current_depth)
        elif isinstance(data, (list, tuple)):
            return self._format_list(data, max_depth, _current_depth)
        else:
            return data

    def _format_dict(self, data: Dict[str, Any], max_depth: int, current_depth: int) -> Dict[str, Any]:
        """Format dictionary for logging

        Special handling:
        - result/results keys: If value is a dict, recurse into it
        - Coordinate keys (mesh, windows, x/y/z): Round floats to 2 decimal places
        - Trim keys: Format as summary with length info
        """
        formatted = {}
        for key, value in data.items():
            if LengthReplacementStrategy.should_trim(key):
                # Direct trim keys - format as summary, but round if it's coordinate data
                if LengthReplacementStrategy.should_round_coordinates(key):
                    rounded_value = LengthReplacementStrategy._round_nested_floats(value)
                    formatted[key] = LengthReplacementStrategy.format_value(rounded_value)
                else:
                    formatted[key] = LengthReplacementStrategy.format_value(value)
            elif LengthReplacementStrategy.should_recurse_dict(key) and isinstance(value, dict):
                # Special keys like result/results - recurse into dict
                formatted[key] = self._format_dict(value, max_depth, current_depth + 1)
            elif LengthReplacementStrategy.should_round_coordinates(key):
                # Coordinate keys - round floats but don't trim
                formatted[key] = LengthReplacementStrategy._round_nested_floats(value)
            else:
                # Regular keys - recurse normally
                formatted[key] = self.format(value, max_depth, current_depth + 1)
        return formatted

    def _format_list(self, data: List[Any], max_depth: int, current_depth: int) -> Any:
        """Format list for logging

        For large lists (>10 items), shows summary with length and first element.
        For small lists, formats each item.
        """
        # For large lists, show summary with first element
        if len(data) > 10:
            first_elem = LengthReplacementStrategy._safe_get_first_element(data)
            return f"<list of {len(data)} items, first={first_elem}>"

        # For small lists, format each item
        return [self.format(item, max_depth, current_depth + 1) for item in data]


class LoggingFormatter:
    """Singleton formatter for consistent logging across the application

    Uses Singleton Pattern - single shared instance for all logging.
    """
    _instance: LoggingDictFormatter = None

    @classmethod
    def get_instance(cls) -> LoggingDictFormatter:
        """Get singleton instance"""
        if cls._instance is None:
            cls._instance = LoggingDictFormatter()
        return cls._instance

    @classmethod
    def format_for_logging(cls, data: Any) -> Any:
        """Format data for logging

        Args:
            data: Data to format (dict, list, or other)

        Returns:
            Formatted data with long values replaced by length info
        """
        return cls.get_instance().format(data)
