from typing import Dict, Any, Optional, List
import json
import io
import numpy as np
import cv2
from PIL import Image
from io import BytesIO
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

    def calculate_direction_angles(self, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """Calculate direction angles for windows based on room geometry

        Args:
            parameters: Dictionary containing room_polygon and windows

        Returns:
            Dictionary with direction_angles (radians) and direction_angles_degrees for each window
        """
        request_data = {"parameters": parameters}
        url = f"{self._service_url.value}/{EndpointType.CALCULATE_DIRECTION.value}"
        self._logger.info(f"Calling {self._service_url.name} service: {EndpointType.CALCULATE_DIRECTION.value}")

        return self._http_client.post(url, request_data)

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


class PostprocessService(RemoteService):
    """Service for postprocessing daylight simulation results"""

    def __init__(self, http_client: IHTTPClient, logger: ILogger):
        super().__init__(ServiceURL.POSTPROCESS, http_client, logger)

    def postprocess(
        self,
        window_results: Dict[str, Dict[str, Any]],
        room_polygon: List[List[float]]
    ) -> Dict[str, Any]:
        """Postprocess daylight simulation results for all windows

        Args:
            window_results: Dictionary mapping window names to their simulation results and locations
                Format: {
                    "window_name": {
                        "result": {...},  # Daylight simulation result
                        "x1": float, "y1": float, "z1": float,
                        "x2": float, "y2": float, "z2": float
                    }
                }
            room_polygon: Room polygon coordinates [[x, y], ...]

        Returns:
            Postprocessed result matrix
        """
        # Construct request payload
        windows_data = {}
        results_data = {}

        for window_name, window_info in window_results.items():
            # Extract window location
            windows_data[window_name] = {
                "x1": window_info.get("x1"),
                "y1": window_info.get("y1"),
                "z1": window_info.get("z1"),
                "x2": window_info.get("x2"),
                "y2": window_info.get("y2"),
                "z2": window_info.get("z2")
            }

            # Extract simulation result
            results_data[window_name] = window_info.get("result")

        request_data = {
            "windows": windows_data,
            "results": results_data,
            "room_polygon": room_polygon
        }

        url = f"{self._service_url.value}/{EndpointType.POSTPROCESS.value}"
        self._logger.info(f"Calling {self._service_url.name} service: {EndpointType.POSTPROCESS.value}")

        return self._http_client.post(url, request_data)


class ModelService(RemoteService):
    """Service for running model inference"""

    def __init__(self, http_client: IHTTPClient, logger: ILogger):
        super().__init__(ServiceURL.MODEL, http_client, logger)

    def run(self, image_bytes: bytes, filename: str = "image.png", invert_channels: bool = False) -> Dict[str, Any]:
        """Run model inference on image

        Args:
            image_bytes: Image data as bytes
            filename: Name of the image file (default: "image.png")
            invert_channels: If True, convert RGB to BGR before sending (default: False)

        Returns:
            Model inference result
        """
        url = f"{self._service_url.value}/{EndpointType.RUN.value}"
        self._logger.info(f"Calling {self._service_url.name} service: {EndpointType.RUN.value}")

        # Convert RGB to BGR (or RGBA to BGRA) if requested
        if invert_channels:
            # Load image from bytes
            img = Image.open(BytesIO(image_bytes))

            # Convert RGB to BGR or RGBA to BGRA
            if img.mode == 'RGB':
                r, g, b = img.split()
                img_inverted = Image.merge('RGB', (b, g, r))
                self._logger.info(f"Converted image from RGB to BGR")

                # Save back to bytes
                buffer = BytesIO()
                img_inverted.save(buffer, format='PNG')
                image_bytes = buffer.getvalue()
            elif img.mode == 'RGBA':
                r, g, b, a = img.split()
                img_inverted = Image.merge('RGBA', (b, g, r, a))
                self._logger.info(f"Converted image from RGBA to BGRA")

                # Save back to bytes
                buffer = BytesIO()
                img_inverted.save(buffer, format='PNG')
                image_bytes = buffer.getvalue()
            else:
                self._logger.warning(f"Image mode is {img.mode}, not RGB or RGBA. Skipping channel inversion.")

        # Prepare file for multipart upload
        files = {"file": (filename, io.BytesIO(image_bytes), "image/png")}

        return self._http_client.post_multipart(url, files, {})

    def get_df(self, image_data: Any, invert_channels: bool = False) -> Dict[str, Any]:
        """Send image to simulation service for prediction (legacy daylight simulation)

        Args:
            image_data: Either bytes, numpy array, or PIL Image
            invert_channels: If True, convert RGB to BGR before sending (default: False)

        Returns:
            Simulation result from model service
        """
        # Convert input to bytes
        if isinstance(image_data, np.ndarray):
            # Convert numpy array to PIL Image then to bytes
            # Ensure the array is uint8 for PIL compatibility
            if image_data.dtype != np.uint8:
                # Normalize to 0-255 range if needed
                if image_data.max() <= 1.0:
                    image_data = (image_data * 255).astype(np.uint8)
                else:
                    image_data = image_data.astype(np.uint8)

            img = Image.fromarray(image_data)
            buffer = BytesIO()
            img.save(buffer, format='PNG')
            image_bytes = buffer.getvalue()
        elif isinstance(image_data, Image.Image):
            # Convert PIL Image to bytes
            buffer = BytesIO()
            image_data.save(buffer, format='PNG')
            image_bytes = buffer.getvalue()
        elif isinstance(image_data, bytes):
            image_bytes = image_data
        else:
            raise ValueError(f"Unsupported image_data type: {type(image_data)}. Expected bytes, numpy array, or PIL Image.")

        # Use the run method to send to simulation service
        return self.run(image_bytes, filename="input_image.png", invert_channels=invert_channels)


class MergerService(RemoteService):
    """Service for merging multiple window simulations into a single room result"""

    def __init__(self, http_client: IHTTPClient, logger: ILogger):
        super().__init__(ServiceURL.MERGER, http_client, logger)

    def merge(
        self,
        room_polygon: List[List[float]],
        windows: Dict[str, Dict[str, float]],
        simulations: Dict[str, Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Merge multiple window simulations into a single room-level result

        Args:
            room_polygon: Room polygon coordinates [[x, y], ...]
            windows: Dictionary of window configurations
                {
                    "window_name": {
                        "x1": float, "y1": float, "z1": float,
                        "x2": float, "y2": float, "z2": float,
                        "direction_angle": float
                    }
                }
            simulations: Dictionary of simulation results for each window
                {
                    "window_name": {
                        "df_values": [[float]], # 2D array of daylight factor values
                        "mask": [[int]]         # 2D binary mask
                    }
                }

        Returns:
            {
                "status": "success" | "error",
                "df_matrix": [[float]],  # Combined daylight factor matrix
                "room_mask": [[int]]      # Combined room mask
            }
        """
        request_data = {
            "room_polygon": room_polygon,
            "windows": windows,
            "simulations": simulations
        }

        url = f"{self._service_url.value}/{EndpointType.MERGE.value}"
        self._logger.info(f"Calling {self._service_url.name} service: {EndpointType.MERGE.value}")
        self._logger.info(f"Merging {len(windows)} window simulations for room")

        return self._http_client.post(url, request_data)
