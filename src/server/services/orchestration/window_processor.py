from typing import Any, Tuple, List
import asyncio
import logging

from src.server.services.helpers.parallel import ParallelRequest
from .request_builder import WindowRequestBuilder
from ...enums import EndpointType, RequestField

logger = logging.getLogger("logger")


class WindowProcessor:
    """Processes individual windows in parallel"""

    def __init__(self, orchestrator):
        """Initialize with orchestrator instance to avoid circular import"""
        self._orchestrator = orchestrator

    def process_single_window(self, endpoint: EndpointType, window_name: str, window_data: Any,
                             request_data: dict, file: Any) -> Tuple[str, Any]:
        """Process a single window request

        Args:
            endpoint: Endpoint to call
            window_name: Name of the window
            window_data: Window configuration data
            request_data: Original request data
            file: File data if any

        Returns:
            Tuple of (window_name, result)
        """
        single_window_request = WindowRequestBuilder.from_request_data(
            request_data, window_name, window_data
        )

        result = self._orchestrator.run(endpoint, single_window_request, file)
        return (window_name, result)

    def process_all_windows(self, endpoint: EndpointType, request_data: dict, file: Any) -> List[Tuple[str, Any]]:
        """Process all windows in parallel

        Args:
            endpoint: Endpoint to call
            request_data: Request data containing windows
            file: File data if any

        Returns:
            List of (window_name, result) tuples
        """
        params = request_data.get(RequestField.PARAMETERS.value, {})
        windows = params.get(RequestField.WINDOWS.value, {})

        if not windows:
            raise ValueError("No windows provided")

        args_list = [
            (endpoint, name, data, request_data, file)
            for name, data in windows.items()
        ]

        async def process_all():
            loop = asyncio.get_event_loop()
            tasks = [
                loop.run_in_executor(
                    None,
                    self.process_single_window,
                    *args
                )
                for args in args_list
            ]
            return await asyncio.gather(*tasks)

        return ParallelRequest.run(process_all, [])
