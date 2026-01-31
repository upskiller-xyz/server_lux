from dataclasses import dataclass
from typing import Dict, Any, Optional
import numpy as np

from .base_contracts import RemoteServiceRequest, StandardResponse
from ....enums import RequestField, ResponseKey


@dataclass
class StatsRequest(RemoteServiceRequest):
    """Request for statistics calculation

    Used for /get_stats and /calculate endpoints to compute daylight statistics
    from simulation results with an optional mask.
    """
    df_values: np.ndarray
    mask: Optional[np.ndarray] = None

    @classmethod
    def parse(cls, content: Dict[str, Any]) -> list['StatsRequest']:
        """Parse dictionary into StatsRequest

        Args:
            content: Dictionary with df_values and optional mask

        Returns:
            List with single StatsRequest instance
        """
        df_values = content.get(RequestField.RESULT.value)
        mask = content.get(RequestField.MASK.value)

        if df_values is None:
            raise ValueError(f"Missing '{RequestField.RESULT.value}' field in request data for StatsService")

        # Convert to numpy arrays if they're lists
        if isinstance(df_values, list):
            df_values = np.array(df_values)
        if isinstance(mask, list):
            mask = np.array(mask)

        return [cls(df_values=df_values, mask=mask)]

    @property
    def to_dict(self) -> Dict[str, Any]:
        return self._build_dict(
            **{
                RequestField.RESULT.value: self._array_to_list(self.df_values),
                RequestField.MASK.value: self._array_to_list(self.mask)
            }
        )


@dataclass
class StatsResponse(StandardResponse):
    """Response from statistics calculation

    Used for /get_stats and /calculate endpoints.
    Stores statistics data and provides as_dict() method to access it.
    """
    stats: Dict[str, Any] = None

    @classmethod
    def parse(cls, content: Dict[str, Any]) -> 'StatsResponse':
        """Parse response data from statistics service

        Returns StatsResponse instance with statistics data.
        """
        # Remove status/error/mask keys to get just the statistics
        stats = {k: v for k, v in content.items()
                if k not in [ResponseKey.STATUS.value, ResponseKey.ERROR.value, RequestField.MASK.value]}
        return cls(stats=stats)

    def as_dict(self) -> Dict[str, Any]:
        """Get statistics as dictionary"""
        return self.stats if self.stats is not None else {}

    @property
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization"""
        return self.as_dict()
