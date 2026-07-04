from typing import Dict, Any, Optional, Tuple
import logging
import time
import traceback

import orjson
from flask import Request, Response, jsonify

from .enums import EndpointType, HTTPStatus, RequestField, ResponseKey
from .controllers.endpoint_controller import EndpointController
from .response_builder import ErrorResponseBuilder
from .services.remote.model_prewarmer import ModelPrewarmer
from .services.helpers.timing import StageTimer
from .services.telemetry import TelemetryRequestContext, build_default_reporter

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

        Two intake modes (the original endpoint is unchanged — JSON still works):

        - **JSON** (original): the whole body parsed with orjson (~faster than the
          stdlib json behind Flask's get_json).
        - **Multipart pass-through**: a small ``params`` JSON field parsed always; the
          large ``mesh`` field is never parsed by lux — obstruction is its sole
          consumer. A binary mesh (.npy / gzip) is kept as raw bytes and forwarded
          untouched to obstruction's binary endpoint; a JSON mesh is parsed only when
          obstruction will run. Requests with pre-calculated horizon+zenith skip
          obstruction, so the multi-MB mesh is dropped entirely.
        """
        if request.is_json:
            try:
                return orjson.loads(request.get_data())
            except Exception:
                return request.form.to_dict()

        raw_params = request.form.get("params")
        if raw_params is None:
            return request.form.to_dict()
        try:
            params = orjson.loads(raw_params)
        except orjson.JSONDecodeError:
            # Malformed params JSON falls back to flat form parsing (mirrors the
            # JSON-body path above) so bad input yields a controlled validation
            # error downstream instead of a 500.
            return request.form.to_dict()

        mesh_file = request.files.get("mesh")
        if mesh_file is not None:
            # Obstruction is skipped when horizon+zenith are pre-calculated (see
            # Orchestrator._should_skip_service) — then the mesh is never used.
            obstruction_skipped = (
                ResponseKey.HORIZON.value in params and ResponseKey.ZENITH.value in params
            )
            if obstruction_skipped:
                params[RequestField.MESH.value] = []
            else:
                raw = mesh_file.read()
                # Binary mesh (.npy, optionally gzipped) is forwarded to obstruction
                # as raw bytes — lux never parses it. Only a JSON mesh is parsed.
                params[RequestField.MESH.value] = (
                    raw if RequestParser._is_binary_mesh(raw) else orjson.loads(raw)
                )
        return params

    # Magic bytes identifying a binary mesh payload that lux forwards untouched.
    _NPY_MAGIC = b"\x93NUMPY"
    _GZIP_MAGIC = b"\x1f\x8b"

    @staticmethod
    def _is_binary_mesh(raw: bytes) -> bool:
        """True if the payload is a NumPy .npy (optionally gzipped) mesh."""
        return raw[:6] == RequestParser._NPY_MAGIC or raw[:2] == RequestParser._GZIP_MAGIC

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
        self._telemetry = build_default_reporter()

    def handle(self, request: Request) -> Tuple[Response, int]:
        """Handle a request to any endpoint

        Args:
            request: Flask request object

        Returns:
            Tuple of (response, status_code)
        """
        endpoint = None
        start = time.perf_counter()
        success = False
        error_code: Optional[str] = None
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

            response, status = self._response_builder.build(result)
            success = status == HTTPStatus.OK.value
            if not success:
                error_code = self._error_code_from_result(result)
            return response, status

        except Exception as e:
            endpoint_str = endpoint.value if endpoint else "unknown"
            logger.error(f"{endpoint_str} failed: {str(e)}")
            logger.error(f"Traceback:\n{traceback.format_exc()}")
            error_code = type(e).__name__
            return self._error_builder.build_from_exception(e)

        finally:
            duration_ms = int((time.perf_counter() - start) * 1000)
            self._report_telemetry(request, endpoint, duration_ms, success, error_code)

    @staticmethod
    def _error_code_from_result(result: Any) -> str:
        """Derive a telemetry error code from a non-OK result payload."""
        if isinstance(result, dict):
            return result.get(ResponseKey.ERROR_TYPE.value) or ResponseKey.ERROR.value
        return ResponseKey.ERROR.value

    def _report_telemetry(
        self,
        request: Request,
        endpoint: Optional[EndpointType],
        duration_ms: int,
        success: bool,
        error_code: Optional[str],
    ) -> None:
        """Emit one telemetry event for the request (best-effort, never raises)."""
        try:
            ctx = TelemetryRequestContext.extract(request)
            self._telemetry.report(
                endpoint=endpoint.value if endpoint else EndpointType.STATUS.value,
                duration_ms=duration_ms,
                success=success,
                error_code=error_code,
                user_sub=ctx.user_sub,
                session_id=ctx.session_id,
                project_id=ctx.project_id,
            )
        except Exception as e:
            logger.warning(f"telemetry.report failed: {e}")
