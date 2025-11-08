from typing import Dict, Any, Optional, List
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
        """Get dataframe from daylight service with file upload (legacy method)"""
        return self.simulate(file, form_data)

    def simulate(self, file: Any, form_data: Dict[str, Any]) -> Dict[str, Any]:
        """Run daylight simulation on uploaded image"""
        url = f"{self._service_url.value}/{EndpointType.SIMULATE.value}"
        self._logger.info(f"Calling {self._service_url.name} service: {EndpointType.SIMULATE.value}")

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


class ObstructionService(RemoteService):
    """Service for obstruction angle calculations"""

    def __init__(self, http_client: IHTTPClient, logger: ILogger):
        super().__init__(ServiceURL.OBSTRUCTION, http_client, logger)

    def calculate_horizon_angle(self, x: float, y: float, z: float,
                               rad_x: float, rad_y: float, mesh: list) -> Dict[str, Any]:
        """Calculate horizon angle from window position"""
        request_data = {
            "x": x,
            "y": y,
            "z": z,
            "rad_x": rad_x,
            "rad_y": rad_y,
            "mesh": mesh
        }
        return self.call(f"/{EndpointType.HORIZON_ANGLE.value}", request_data)

    def calculate_zenith_angle(self, x: float, y: float, z: float,
                              rad_x: float, rad_y: float, mesh: list) -> Dict[str, Any]:
        """Calculate zenith angle from window position"""
        request_data = {
            "x": x,
            "y": y,
            "z": z,
            "rad_x": rad_x,
            "rad_y": rad_y,
            "mesh": mesh
        }
        return self.call(f"/{EndpointType.ZENITH_ANGLE.value}", request_data)

    def calculate_obstruction(self, x: float, y: float, z: float,
                            rad_x: float, rad_y: float, mesh: list) -> Dict[str, Any]:
        """Calculate both horizon and zenith angles from window position"""
        request_data = {
            "x": x,
            "y": y,
            "z": z,
            "rad_x": rad_x,
            "rad_y": rad_y,
            "mesh": mesh
        }
        return self.call(f"/{EndpointType.OBSTRUCTION.value}", request_data)

    def calculate_obstruction_all(self, x: float, y: float, z: float,
                                  rad_x: float, rad_y: float, mesh: list) -> Dict[str, Any]:
        """Calculate horizon and zenith angle vectors (64 floats each) from window position"""
        request_data = {
            "x": x,
            "y": y,
            "z": z,
            "rad_x": rad_x,
            "rad_y": rad_y,
            "mesh": mesh
        }
        return self.call(f"/{EndpointType.OBSTRUCTION_ALL.value}", request_data)


class EncoderService(RemoteService):
    """Service for encoding room data to images"""

    def __init__(self, http_client: IHTTPClient, logger: ILogger):
        super().__init__(ServiceURL.ENCODER, http_client, logger)

    def encode(self, model_type: str, parameters: Dict[str, Any]) -> bytes:
        """Encode room parameters to PNG image"""
        request_data = {
            "model_type": model_type,
            "parameters": parameters
        }
        url = f"{self._service_url.value}/{EndpointType.ENCODE.value}"
        self._logger.info(f"Calling {self._service_url.name} service: {EndpointType.ENCODE.value}")

        # Use post_binary instead of post since we expect image bytes
        return self._http_client.post_binary(url, request_data)

    def encode_with_obstruction(
        self,
        model_type: str,
        parameters: Dict[str, Any],
        obstruction_angles_horizon: List[float],
        obstruction_angles_zenith: List[float]
    ) -> bytes:
        """Encode room parameters with obstruction angles to PNG image

        Args:
            model_type: Model type identifier
            parameters: Room and window parameters
            obstruction_angles_horizon: Vector of 64 horizon angles
            obstruction_angles_zenith: Vector of 64 zenith angles

        Returns:
            PNG image bytes
        """
        # Merge obstruction angles into parameters
        enhanced_parameters = parameters.copy()

        # Add obstruction angles to each window in parameters
        if "windows" in enhanced_parameters:
            for window_name, window_data in enhanced_parameters["windows"].items():
                window_data["obstruction_angle_horizon"] = obstruction_angles_horizon
                window_data["obstruction_angle_zenith"] = obstruction_angles_zenith

        return self.encode(model_type, enhanced_parameters)
