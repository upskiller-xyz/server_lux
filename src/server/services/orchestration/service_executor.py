from abc import ABC, abstractmethod
from typing import Any, Dict, List
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

        # Each parallel task returns one window's slice, either as a plain dict or a
        # response object (services are inconsistent — DirectionAngle returns a dict,
        # ReferencePoint/ExternalReferencePoint return objects). Normalize to a dict,
        # then DEEP-merge: window slices share the same top-level key
        # (e.g. ``external_reference_point``), so a shallow update would drop every
        # window but the last — which left obstruction with no reference points and
        # thus no requests to run.
        response: Dict[str, Any] = {}
        for single_response in results:
            part = single_response.to_dict if hasattr(single_response, "to_dict") else single_response
            if isinstance(part, dict):
                self._merge(response, part)

        return response

    @staticmethod
    def _merge(target: Dict[str, Any], source: Dict[str, Any]) -> None:
        """Merge ``source`` into ``target``, combining nested per-window dicts.

        Window entries live one level down under a shared key, so when both sides
        hold a dict for the same key their entries are combined rather than the
        whole nested dict being overwritten.
        """
        for key, value in source.items():
            existing = target.get(key)
            if isinstance(existing, dict) and isinstance(value, dict):
                existing.update(value)
            else:
                target[key] = value


class ExecutorFactory:
    """Factory for creating appropriate executor based on request count"""

    @staticmethod
    def create(request_count: int) -> IServiceExecutor:
        if request_count == 1:
            return SingleServiceExecutor()
        return ParallelServiceExecutor()
