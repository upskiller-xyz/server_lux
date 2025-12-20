from typing import Dict, Any, Tuple
import logging
import traceback

from flask import Request, Response, jsonify

from .enums import EndpointType, HTTPStatus
from .controllers.endpoint_controller import EndpointController
from .response_builder import ErrorResponseBuilder

logger = logging.getLogger("logger")


class RequestParser:
    """Parses incoming Flask requests"""

    @staticmethod
    def extract_endpoint(request: Request) -> EndpointType:
        """Extract endpoint from request path"""
        path_parts = request.path.strip('/').split('/', 1)
        endpoint_str = path_parts[1] if len(path_parts) > 1 else path_parts[0]

        endpoint = EndpointType.by_value(endpoint_str)
        if not endpoint:
            endpoint = EndpointType.STATUS

        return endpoint

    @staticmethod
    def extract_params(request: Request) -> Dict[str, Any]:
        """Extract parameters from request"""
        try:
            return request.get_json()
        except Exception:
            return request.form.to_dict()

    @staticmethod
    def extract_file(request: Request) -> Any:
        """Extract file from request if present"""
        return request.files.get('file')


class ResponseBuilder:
    """Builds Flask responses from controller results"""

    @staticmethod
    def build(result: Any) -> Tuple[Response, int]:
        """Build appropriate response based on result type"""
        if isinstance(result, bytes):
            # Check if it's NPZ data (starts with PK for ZIP header) or PNG
            mimetype = 'application/octet-stream' if result[:2] == b'PK' else 'image/png'
            return Response(result, mimetype=mimetype), HTTPStatus.OK.value

        if isinstance(result, dict) and result.get("status") == "error":
            return jsonify(result), HTTPStatus.INTERNAL_SERVER_ERROR.value

        return jsonify(result), HTTPStatus.OK.value


class EndpointRequestHandler:
    """Handles endpoint requests with proper error handling"""

    def __init__(self):
        self._endpoint_controller = EndpointController()
        self._request_parser = RequestParser()
        self._response_builder = ResponseBuilder()
        self._error_builder = ErrorResponseBuilder()

    def handle(self, request: Request) -> Tuple[Response, int]:
        """Handle a request to any endpoint

        Args:
            request: Flask request object

        Returns:
            Tuple of (response, status_code)
        """
        endpoint = None
        try:
            endpoint = self._request_parser.extract_endpoint(request)
            logger.info(f"Processing endpoint: {endpoint.value}")

            params = self._request_parser.extract_params(request)
            file = self._request_parser.extract_file(request)

            result = self._endpoint_controller.run(endpoint, params, file)

            return self._response_builder.build(result)

        except Exception as e:
            endpoint_str = endpoint.value if endpoint else "unknown"
            logger.error(f"{endpoint_str} failed: {str(e)}")
            logger.error(f"Traceback:\n{traceback.format_exc()}")
            return self._error_builder.build_from_exception(e)
