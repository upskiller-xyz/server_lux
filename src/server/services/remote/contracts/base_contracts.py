from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Dict, Any, Optional
import numpy as np

from ....enums import ResponseKey


@dataclass
class RemoteServiceRequest(ABC):
    """Base class for all remote service requests

    Encapsulates request parameters with type safety.
    Eliminates Dict[str, Any] in service calls.
    """

    @property
    @abstractmethod
    def to_dict(self) -> Dict[str, Any]:
        """Convert request to dictionary using enums"""
        pass

    def _build_dict(self, **kwargs) -> Dict[str, Any]:
        """Helper to build dictionary, filtering None values"""
        return {k: v for k, v in kwargs.items() if v is not None}

    @staticmethod
    def _array_to_list(arr: Optional[np.ndarray]) -> Optional[list]:
        """Convert numpy array to list for JSON serialization"""
        return arr.tolist() if arr is not None else None


class RemoteServiceResponse(ABC):
    """Base class for all remote service responses

    Parses response data into typed structures.
    """

    def __init__(self, raw_response: Dict[str, Any]):
        self._raw = raw_response
        self.status = raw_response.get(ResponseKey.STATUS.value)
        self.error = raw_response.get(ResponseKey.ERROR.value)

    @property
    def is_success(self) -> bool:
        return self.status == ResponseKey.SUCCESS.value

    @property
    def is_error(self) -> bool:
        return self.status == ResponseKey.ERROR.value

    def _get_required(self, key: str, error_msg: str = "") -> Any:
        if key not in self._raw:
            raise ValueError(error_msg or f"Missing required field: {key}")
        return self._raw[key]

    def _get_optional(self, key: str, default: Any = None) -> Any:
        return self._raw.get(key, default)

    @classmethod
    def parse(cls, content: Dict[Any, Any]) -> 'RemoteServiceResponse':
        """Default parse method - return raw response

        Override in subclasses for custom parsing logic.
        """
        return cls(content)


class StandardResponse(RemoteServiceResponse):
    """Standard JSON response with status, data/error"""

    @classmethod
    def parse(cls, content: Dict[Any, Any]) -> 'StandardResponse':
        return cls(content)


class BinaryResponse(RemoteServiceResponse):
    """Binary data response (e.g., PNG images)"""

    def __init__(self, raw_data: bytes):
        self._binary_data = raw_data
        super().__init__({})

    @property
    def is_success(self) -> bool:
        return self._binary_data is not None

    @property
    def binary_data(self)->bytes:
        return self._binary_data
    
    @classmethod
    def parse(cls, content: Any) -> 'RemoteServiceResponse':
        """Default parse method - return raw response

        Override in subclasses for custom parsing logic.
        """
        return cls(content)
    
