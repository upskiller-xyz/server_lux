from typing import Dict, Any, Optional
import json
import io
import numpy as np
import cv2
from ..interfaces import IRemoteService, IHTTPClient, ILogger
from ..enums import ServiceURL, EndpointType


class RemoteServiceFactory:
    """Factory for creating remote service instances"""

    @staticmethod
    def create(service_url: ServiceURL, http_client: IHTTPClient, logger: ILogger) -> 'RemoteService':
        """Create remote service instance"""
        return RemoteService(service_url, http_client, logger)


class RemoteService(IRemoteService):
    """Service for calling remote endpoints"""

    def __init__(self, service_url: ServiceURL, http_client: IHTTPClient, logger: ILogger):
        self._service_url = service_url
        self._http_client = http_client
        self._logger = logger

    def call(self, endpoint: str, data: Dict[str, Any]) -> Dict[str, Any]:
        """Call remote service endpoint with data"""
        url = f"{self._service_url.value}{endpoint}"
        self._logger.info(f"Calling {self._service_url.name} service: {endpoint}")
        return self._http_client.post(url, data)


class ColorManageService(RemoteService):
    """Service for color management operations"""

    def __init__(self, http_client: IHTTPClient, logger: ILogger):
        super().__init__(ServiceURL.COLORMANAGE, http_client, logger)

    def to_rgb(self, data: list, colorscale: str="df") -> Dict[str, Any]:
        """Convert values to RGB using specified colorscale"""
        request_data = {"data": data, "colorscale": colorscale}
        return self.call(f"/{EndpointType.TO_RGB.value}", request_data)

    def to_values(self, data: list, colorscale: str="df") -> Dict[str, Any]:
        """Convert RGB to values using specified colorscale"""
        request_data = {"data": data, "colorscale": colorscale}
        return self.call(f"/{EndpointType.TO_VALUES.value}", request_data)


class DaylightService(RemoteService):
    """Service for daylight data operations"""

    def __init__(self, http_client: IHTTPClient, logger: ILogger):
        super().__init__(ServiceURL.DAYLIGHT, http_client, logger)

    def get_df(self, file: Any, form_data: Dict[str, Any]) -> Dict[str, Any]:
        """Get dataframe from daylight service with file upload"""
        url = f"{self._service_url.value}/{EndpointType.GET_DF.value}"
        self._logger.info(f"Calling {self._service_url.name} service: {EndpointType.GET_DF.value}")

        # Prepare file for multipart upload
        files = {"file": (file.filename, file.stream, file.content_type)}

        return self._http_client.post_multipart(url, files, form_data)


class DFEvalService(RemoteService):
    """Service for dataframe evaluation operations"""

    def __init__(self, http_client: IHTTPClient, logger: ILogger):
        super().__init__(ServiceURL.DF_EVAL, http_client, logger)

    def get_stats(self, **kwargs) -> Dict[str, Any]:
        """Get statistics from DF evaluation service"""
        return self.call(f"/{EndpointType.GET_STATS.value}", kwargs)
