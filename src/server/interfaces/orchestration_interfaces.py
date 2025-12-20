from abc import ABC, abstractmethod
from typing import Dict, Any

from ..enums import EndpointType


class IOrchestrator(ABC):
    """Interface for orchestrators that process endpoint requests"""

    @abstractmethod
    def run(self, endpoint: EndpointType, request_data: dict, file: Any) -> Any:
        """Execute orchestration for an endpoint

        Args:
            endpoint: The endpoint type to process
            request_data: Request parameters
            file: File data if any

        Returns:
            Result from orchestration (dict or bytes depending on endpoint)
        """
        pass
