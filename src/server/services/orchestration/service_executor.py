from abc import ABC, abstractmethod
from typing import Any, List, Optional
import asyncio

from src.server.services.helpers.parallel import ParallelRequest
from ...enums import EndpointType


class IServiceExecutor(ABC):
    """Interface for executing service requests"""

    @abstractmethod
    def execute(self, service: type, endpoint: EndpointType, requests: List[Any], file: Any) -> Any:
        """Execute service request(s)

        Args:
            service: Service class to execute
            endpoint: Endpoint to call
            requests: List of request objects
            file: File data if any

        Returns:
            Service response
        """
        pass


class ServiceExecutor(IServiceExecutor):
    """Base class for executing service requests"""

    def execute(self, service: type, endpoint: EndpointType, requests: List[Any], file: Any) -> Any:
        raise NotImplementedError


class SingleServiceExecutor(ServiceExecutor):
    """Executes a single service request"""

    def execute(self, service: type, endpoint: EndpointType, requests: List[Any], file: Any) -> Any:
        return service.run(endpoint, requests[0], file)


class ParallelServiceExecutor(ServiceExecutor):
    """Executes multiple service requests in parallel"""

    def execute(self, service: type, endpoint: EndpointType, requests: List[Any], file: Any) -> Any:
        async def process_all():
            loop = asyncio.get_event_loop()
            tasks = [loop.run_in_executor(None, service.run, endpoint, req, file) for req in requests]
            return await asyncio.gather(*tasks)

        results = ParallelRequest.run(process_all, [])

        if results and isinstance(results[0], bytes):
            return results[0]

        response: dict = {}
        for single_response in results:
            as_dict = self._as_dict(single_response)
            if as_dict is not None:
                self._merge(response, as_dict)

        return response

    @staticmethod
    def _as_dict(single_response: Any) -> Optional[dict]:
        """View one request's response as a dict, or None if it is not mergeable.

        Services differ in what ``run()`` returns: ObstructionService returns a
        plain dict, while the reference-point services return a response
        dataclass carrying a ``to_dict`` property. Accepting only dicts dropped
        every dataclass result, so a multi-window fan-out of those services
        merged to an empty dict. Mirrors Orchestrator._update_params, which
        already normalizes both.
        """
        if isinstance(single_response, dict):
            return single_response
        if hasattr(single_response, "to_dict"):
            as_dict = single_response.to_dict
            return as_dict if isinstance(as_dict, dict) else None
        return None

    @staticmethod
    def _merge(response: dict, single_response: dict) -> None:
        """Merge one request's response into the accumulated response.

        Per-window services answer with a window-keyed mapping under a shared
        key (``{"horizon": {"window_1": [...]}}``). A plain ``dict.update``
        replaces that mapping wholesale, so every window but the last was lost.
        Dict values are therefore merged one level deep; any other value keeps
        last-wins, as before.
        """
        for key, value in single_response.items():
            existing = response.get(key)
            if isinstance(existing, dict) and isinstance(value, dict):
                existing.update(value)
                continue
            response[key] = value


class ExecutorFactory:
    """Factory for creating appropriate executor based on request count"""

    @staticmethod
    def create(request_count: int) -> IServiceExecutor:
        if request_count == 1:
            return SingleServiceExecutor()
        return ParallelServiceExecutor()
