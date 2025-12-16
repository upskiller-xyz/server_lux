import os
from typing import Dict, Any
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Disable GPU/CUDA to prevent bus errors on WSL2
os.environ['CUDA_VISIBLE_DEVICES'] = '-1'
os.environ['TF_CPP_MIN_LOG_LEVEL'] = '3'
os.environ['OPENCV_IO_ENABLE_OPENEXR'] = '0'
os.environ['OMP_NUM_THREADS'] = '1'

import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from flask import Flask, request, jsonify, Response
from flask_cors import CORS
from werkzeug.exceptions import BadRequest

from src.server.enums import ContentType, HTTPStatus, ErrorType
from src.server.auth import TokenAuthenticator
from src.server.response_builder import ErrorResponseBuilder
from src.server.services.logging import StructuredLogger
from src.server.enums import LogLevel
from src.server.controllers.base_controller import ServerController

from src.server.services.orchestration import RunOrchestrationService, EncodeOrchestrationService
from src.server.services.obstruction import (
    ObstructionCalculationService, ParallelObstructionCalculator, SingleRequestObstructionCalculator
)
from src.server.controllers.endpoint_controller import EndpointController
from src.__version__ import version


class ServerApplication:
    """Main application class implementing dependency injection and OOP principles"""

    def __init__(self, app_name: str = "Server Application"):
        self._app = Flask(app_name)
        CORS(self._app)
        self._controller = None
        self._endpoint_controller = None
        self._logger = None
        self._authenticator = TokenAuthenticator()
        self._error_builder = ErrorResponseBuilder()
        self._setup_dependencies()
        self._setup_routes()

    def _setup_dependencies(self) -> None:
        """Setup all dependencies using dependency injection"""
        # Logger
        self._logger = StructuredLogger("Server", LogLevel.INFO)


        # Obstruction Calculation Service (initialize before orchestration services)
        # Use SingleRequestObstructionCalculator to send ONE request to /obstruction_parallel
        api_token = os.getenv("API_TOKEN")
        obstruction_parallel_url = os.getenv("OBSTRUCTION_PARALLEL_URL", "http://51.15.197.220:8081/obstruction_parallel")
        self._logger.info(f"Using obstruction_parallel endpoint: {obstruction_parallel_url}")

        obstruction_calculator = SingleRequestObstructionCalculator(
            self._logger,
            api_url=obstruction_parallel_url,
            api_token=api_token
        )
        obstruction_calculation_service = ObstructionCalculationService(
            obstruction_calculator, self._logger
        )

        # Orchestration Services
        run_orchestration_service = RunOrchestrationService(
        )
        encode_orchestration_service = EncodeOrchestrationService(
        )

        # Endpoint Controller
        self._endpoint_controller = EndpointController(
        )
        

        # Controller
        self._controller = ServerController(
        )

        # Initialize controller
        self._controller.initialize()

    def _setup_routes(self) -> None:
        """Setup Flask routes using strategy pattern with versioned endpoints"""
        # Extract major version from version string (e.g., "1.0.0" -> "v1")
        major_version = f"v{version.split('.')[0]}"

        routes = [
            ("/", "get_status", self._get_status, ["GET"]),
            (f"/{major_version}/get_df_direct", "get_df_direct", self._get_df_direct, ["POST"]),  # Direct image to simulation
            (f"/{major_version}/simulate", "simulate", self._simulate, ["POST"]),  # New daylight simulation endpoint
            (f"/{major_version}/get_stats", "get_stats", self._get_stats, ["POST"]),
            
            (f"/{major_version}/horizon_angle", "horizon_angle", self._horizon_angle, ["POST"]),
            (f"/{major_version}/zenith_angle", "zenith_angle", self._zenith_angle, ["POST"]),
            (f"/{major_version}/obstruction", "obstruction", self._obstruction, ["POST"]),
            (f"/{major_version}/obstruction_multi", "obstruction_multi", self._obstruction_multi, ["POST"]),
            (f"/{major_version}/obstruction_parallel", "obstruction_parallel", self._obstruction_parallel, ["POST"]),
            (f"/{major_version}/encode_raw", "encode_raw", self._encode_raw, ["POST"]),  # Direct encode without obstruction
            (f"/{major_version}/encode", "encode", self._encode, ["POST"]),  # Obstruction + encode workflow
            (f"/{major_version}/run", "run", self._run, ["POST"]),  # Complete workflow endpoint
            (f"/{major_version}/merge", "merge", self._merge, ["POST"]),  # Merge multiple window simulations
            (f"/{major_version}/stats", "stats", self._stats, ["POST"])  # Calculate statistics
        ]

        [self._app.add_url_rule(path, name, handler, methods=methods)
         for path, name, handler, methods in routes]

    def _get_status(self) -> Dict[str, Any]:
        """Get server status endpoint"""
        return jsonify(self._controller.get_status())

    def _simulate(self) -> Dict[str, Any]:
        """Run daylight simulation endpoint"""
        try:
            # Handle multipart form data with file upload
            if 'file' not in request.files:
                return self._error_builder.build(ErrorType.MISSING_FILE)

            file = request.files['file']
            form_data = request.form.to_dict()

            result = self._endpoint_controller.simulate(file, form_data)

            if result.get("status") == "error":
                return jsonify(result), HTTPStatus.INTERNAL_SERVER_ERROR.value

            return jsonify(result)

        except Exception as e:
            self._logger.error(f"simulate failed: {str(e)}")
            return self._error_builder.build_from_exception(e)

    def _get_stats(self) -> Dict[str, Any]:
        """Get statistics endpoint"""
        try:
            request_data = request.get_json()
            if not request_data:
                return self._error_builder.build(ErrorType.MISSING_JSON)

            result = self._endpoint_controller.get_stats(request_data)

            if result.get("status") == "error":
                return jsonify(result), HTTPStatus.INTERNAL_SERVER_ERROR.value

            return jsonify(result)

        except Exception as e:
            self._logger.error(f"get_stats failed: {str(e)}")
            return self._error_builder.build_from_exception(e)

    def _get_df_rgb(self) -> Dict[str, Any]:
        """Get dataframe and convert to RGB endpoint"""
        try:
            # Handle multipart form data with file upload
            if 'file' not in request.files:
                return self._error_builder.build(ErrorType.MISSING_FILE)

            file = request.files['file']
            form_data = request.form.to_dict()

            result = self._endpoint_controller.get_df_rgb(file, form_data)

            if result.get("status") == "error":
                return jsonify(result), HTTPStatus.INTERNAL_SERVER_ERROR.value

            return jsonify(result)

        except Exception as e:
            self._logger.error(f"get_df_rgb failed: {str(e)}")
            return self._error_builder.build_from_exception(e)

    def _horizon_angle(self) -> Dict[str, Any]:
        """Calculate horizon angle endpoint"""
        try:
            request_data = request.get_json()
            if not request_data:
                return self._error_builder.build(ErrorType.MISSING_JSON)

            result = self._endpoint_controller.horizon_angle(request_data)

            if result.get("status") == "error":
                return jsonify(result), HTTPStatus.INTERNAL_SERVER_ERROR.value

            return jsonify(result)

        except Exception as e:
            self._logger.error(f"horizon_angle failed: {str(e)}")
            return self._error_builder.build_from_exception(e)

    def _zenith_angle(self) -> Dict[str, Any]:
        """Calculate zenith angle endpoint"""
        try:
            request_data = request.get_json()
            if not request_data:
                return self._error_builder.build(ErrorType.MISSING_JSON)

            result = self._endpoint_controller.zenith_angle(request_data)

            if result.get("status") == "error":
                return jsonify(result), HTTPStatus.INTERNAL_SERVER_ERROR.value

            return jsonify(result)

        except Exception as e:
            self._logger.error(f"zenith_angle failed: {str(e)}")
            return self._error_builder.build_from_exception(e)

    def _obstruction(self) -> Dict[str, Any]:
        """Calculate both horizon and zenith angles endpoint"""
        try:
            request_data = request.get_json()
            if not request_data:
                return self._error_builder.build(ErrorType.MISSING_JSON)

            result = self._endpoint_controller.obstruction(request_data)

            if result.get("status") == "error":
                return jsonify(result), HTTPStatus.INTERNAL_SERVER_ERROR.value

            return jsonify(result)

        except Exception as e:
            self._logger.error(f"obstruction failed: {str(e)}")
            return self._error_builder.build_from_exception(e)

    def _obstruction_multi(self) -> Dict[str, Any]:
        """Calculate obstruction for 64 directions endpoint"""
        try:
            request_data = request.get_json()
            if not request_data:
                return self._error_builder.build(ErrorType.MISSING_JSON)

            result = self._endpoint_controller.obstruction_multi(request_data)

            if result.get("status") == "error":
                return jsonify(result), HTTPStatus.INTERNAL_SERVER_ERROR.value

            return jsonify(result)

        except Exception as e:
            self._logger.error(f"obstruction_multi failed: {str(e)}")
            return self._error_builder.build_from_exception(e)

    def _obstruction_parallel(self) -> Dict[str, Any]:
        """Calculate obstruction for all directions using parallel service (compatible with /obstruction_all)"""
        try:
            request_data = request.get_json()
            if not request_data:
                return self._error_builder.build(ErrorType.MISSING_JSON)

            result = self._endpoint_controller.obstruction_parallel(request_data)

            if result.get("status") == "error":
                return jsonify(result), HTTPStatus.INTERNAL_SERVER_ERROR.value

            return jsonify(result)

        except Exception as e:
            self._logger.error(f"obstruction_parallel failed: {str(e)}")
            return self._error_builder.build_from_exception(e)

    @TokenAuthenticator().require_token
    def _encode_raw(self) -> Response:
        """Direct encode endpoint - calls remote encode service without obstruction calculation (protected by token)"""
        try:
            request_data = request.get_json()
            if not request_data:
                return self._error_builder.build(ErrorType.MISSING_JSON)

            image_bytes = self._endpoint_controller.encode_raw(request_data)

            # Return binary PNG data
            return Response(
                image_bytes,
                mimetype=ContentType.IMAGE_PNG.value,
                headers={"Content-Type": ContentType.IMAGE_PNG.value}
            )

        except ValueError as e:
            self._logger.error(f"encode_raw validation failed: {str(e)}")
            return self._error_builder.build_from_exception(e, HTTPStatus.BAD_REQUEST.value)
        except Exception as e:
            self._logger.error(f"encode_raw failed: {str(e)}")
            return self._error_builder.build_from_exception(e)

    def _encode(self) -> Dict[str, Any]:
        """Encode endpoint - obstruction + encoding workflow (similar to /run but without simulation)"""
        try:
            request_data = request.get_json()
            if not request_data:
                return self._error_builder.build(ErrorType.MISSING_JSON)

            result = self._endpoint_controller.encode(request_data)

            if result.get("status") == "error":
                return jsonify(result), HTTPStatus.INTERNAL_SERVER_ERROR.value

            return jsonify(result)

        except Exception as e:
            self._logger.error(f"encode failed: {str(e)}")
            return self._error_builder.build_from_exception(e)

    def _run(self) -> Dict[str, Any]:
        """Complete workflow: obstruction → encoding → daylight simulation"""
        try:
            request_data = request.get_json()
            if not request_data:
                return self._error_builder.build(ErrorType.MISSING_JSON)

            result = self._endpoint_controller.run(request_data)

            if result.get("status") == "error":
                return jsonify(result), HTTPStatus.INTERNAL_SERVER_ERROR.value

            return jsonify(result)

        except Exception as e:
            self._logger.error(f"run failed: {str(e)}")
            return self._error_builder.build_from_exception(e)

    def _merge(self) -> Dict[str, Any]:
        """Merge multiple window simulations into a single room result"""
        try:
            request_data = request.get_json()
            if not request_data:
                return self._error_builder.build(ErrorType.MISSING_JSON)

            result = self._endpoint_controller.merge(request_data)

            if result.get("status") == "error":
                return jsonify(result), HTTPStatus.INTERNAL_SERVER_ERROR.value

            return jsonify(result)

        except Exception as e:
            self._logger.error(f"merge failed: {str(e)}")
            return self._error_builder.build_from_exception(e)

    def _stats(self) -> Dict[str, Any]:
        """Calculate statistics endpoint"""
        try:
            request_data = request.get_json()
            if not request_data:
                return self._error_builder.build(ErrorType.MISSING_JSON)

            result = self._endpoint_controller.stats(request_data)

            if result.get("status") == "error":
                return jsonify(result), HTTPStatus.INTERNAL_SERVER_ERROR.value

            return jsonify(result)

        except Exception as e:
            self._logger.error(f"stats failed: {str(e)}")
            return self._error_builder.build_from_exception(e)

    def _get_df_direct(self) -> Dict[str, Any]:
        """Send image directly to simulation service for prediction"""
        try:
            # Try to handle file upload first
            file = None
            if 'file' in request.files:
                file = request.files['file']
                # Get optional JSON data from form or query params
                form_data = request.form.to_dict()
                result = self._endpoint_controller.get_df_direct(file=file, request_data=form_data)
            else:
                # Handle JSON request with base64 or array data
                request_data = request.get_json()
                if not request_data:
                    raise BadRequest("No file or JSON data provided")
                result = self._endpoint_controller.get_df_direct(file=None, request_data=request_data)

            if result.get("status") == "error":
                return jsonify(result), HTTPStatus.INTERNAL_SERVER_ERROR.value

            return jsonify(result)

        except Exception as e:
            self._logger.error(f"get_df_direct failed: {str(e)}")
            return self._error_builder.build_from_exception(e)

    @property
    def app(self) -> Flask:
        """Get Flask application instance"""
        return self._app


class ServerLauncher:
    """Launcher class for the server application"""

    @staticmethod
    def create_application() -> ServerApplication:
        """Create and configure the application"""
        return ServerApplication()

    @staticmethod
    def run_server(
        app: ServerApplication,
        host: str = "0.0.0.0",
        port: int = 8080,
        debug: bool = True
    ) -> None:
        """Run the server"""
        """Run the server"""
        log_msg = (
            f"Flask app '{app.app.name}' starting on "
            f"host {host}, port {port}. Debug mode: {debug}"
        )
        app.app.logger.info(log_msg)
        # Disable reloader to prevent bus errors/hangs on WSL2
        app.app.run(host=host, port=port, debug=debug, use_reloader=False)


def main() -> None:
    """Main entry point"""
    launcher = ServerLauncher()
    application = launcher.create_application()
    port = int(os.getenv("PORT", 8081))
    launcher.run_server(application, port=port, debug=True)


# Create app instance for gunicorn only when needed
# Don't create at module import time to avoid bus errors
def create_app():
    """Factory function for creating the Flask app (for gunicorn)"""
    _application = ServerApplication()
    return _application.app


# Only create app instance if not running as main (i.e., when imported by gunicorn)
if __name__ != "__main__":
    app = create_app()
else:
    # Running as main script
    main()