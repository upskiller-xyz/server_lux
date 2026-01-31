from abc import ABC, abstractmethod
from typing import Any, List
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

        response = {}
        for single_response in results:
            if isinstance(single_response, dict):
                response.update(single_response)

        return response


class ExecutorFactory:
    """Factory for creating appropriate executor based on request count"""

    @staticmethod
    def create(request_count: int) -> IServiceExecutor:
        if request_count == 1:
            return SingleServiceExecutor()
        return ParallelServiceExecutor()
