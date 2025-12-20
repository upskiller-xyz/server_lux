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

    @property
    def to_dict(self) -> Dict[str, Any]:
        return self._build_dict(
            **{
                RequestField.DF_VALUES.value: self._array_to_list(self.df_values),
                RequestField.MASK.value: self._array_to_list(self.mask)
            }
        )


@dataclass
class StatsResponse(StandardResponse):
    """Response from statistics calculation

    Used for /get_stats and /calculate endpoints.
    """
    statistics: Dict[str, Any]

    @classmethod
    def parse(cls, content: Dict[str, Any]) -> 'StatsResponse':
        """Parse response data from statistics service

        Returns all statistics data from the response.
        """
        # Remove status/error keys to get just the statistics
        stats = {k: v for k, v in content.items()
                if k not in [ResponseKey.STATUS.value, ResponseKey.ERROR.value]}

        return cls(statistics=stats)

    @property
    def to_dict(self) -> Dict[str, Any]:
        return self.statistics
