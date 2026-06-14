from typing import Dict, Any, Tuple
import logging
import traceback

import orjson
from flask import Request, Response, jsonify

from .enums import EndpointType, HTTPStatus
from .controllers.endpoint_controller import EndpointController
from .response_builder import ErrorResponseBuilder
from .services.remote.model_prewarmer import ModelPrewarmer
from .services.helpers.timing import StageTimer

logger = logging.getLogger("logger")

# Endpoints whose pipeline runs GPU inference (call ModelService) — warm the model
# the moment they arrive. /spec-only endpoints (e.g. ENCODE, which calls
# ModelSpecService but not ModelService) are intentionally excluded: spec is cached
# metadata, not inference, so there is nothing to prewarm for.
_INFERENCE_ENDPOINTS = frozenset({
    EndpointType.RUN,
    EndpointType.RUN_DETAILED,
    EndpointType.SIMULATE,
})


class RequestParser:
    """Parses incoming Flask requests"""

    @staticmethod
    def extract_endpoint(request: Request) -> EndpointType:
        """Extract endpoint from Flask's route matching"""
        # Flask's request.endpoint contains the endpoint name registered via add_url_rule
        # which is route.endpoint.value from RouteConfigurator
        endpoint_str = request.endpoint

        if not endpoint_str:
            return EndpointType.STATUS

        endpoint = EndpointType.by_value(endpoint_str)
        if not endpoint:
            endpoint = EndpointType.STATUS

        return endpoint

    @staticmethod
    def extract_params(request: Request) -> Dict[str, Any]:
        """Extract parameters from the request body.

        Uses orjson (~10x faster than the stdlib json behind Flask's get_json).
        Parsing the body dominates latency for large payloads — the mesh can be
        several MB (parsing was ~4s with get_json). Falls back to form data for
        non-JSON requests; ``is_json`` gates so we never consume a multipart stream.
        """
        if request.is_json:
            try:
                return orjson.loads(request.get_data())
            except Exception:
                pass
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

            # Fire-and-forget GPU prewarm at the earliest point so the model's cold
            # start overlaps the CPU stages instead of stacking on /spec or /run.
            if endpoint in _INFERENCE_ENDPOINTS:
                ModelPrewarmer.prewarm()

            with StageTimer("extract_params", logger):
                params = self._request_parser.extract_params(request)
            with StageTimer("extract_file", logger):
                file = self._request_parser.extract_file(request)

            with StageTimer("controller.run", logger):
                result = self._endpoint_controller.run(endpoint, params, file)

            return self._response_builder.build(result)

        except Exception as e:
            endpoint_str = endpoint.value if endpoint else "unknown"
            logger.error(f"{endpoint_str} failed: {str(e)}")
            logger.error(f"Traceback:\n{traceback.format_exc()}")
            return self._error_builder.build_from_exception(e)
