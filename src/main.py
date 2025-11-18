import os
from typing import Dict, Any

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

from src.server.enums import ContentType, HTTPStatus
from src.server.auth import TokenAuthenticator




class ServerApplication:
    """Main application class implementing dependency injection and OOP principles"""

    def __init__(self, app_name: str = "Server Application"):
        self._app = Flask(app_name)
        CORS(self._app)
        self._controller = None
        self._endpoint_controller = None
        self._logger = None
        self._authenticator = TokenAuthenticator()
        self._setup_dependencies()
        self._setup_routes()

    def _setup_dependencies(self) -> None:
        """Setup all dependencies using dependency injection"""
        from src.server.services.logging import StructuredLogger
        from src.server.enums import LogLevel
        from src.server.controllers.base_controller import ServerController
        from src.server.services.http_client import HTTPClient
        from src.server.services.remote_service import (
            ColorManageService, DaylightService, DFEvalService, ObstructionService, EncoderService, PostprocessService
        )
        from src.server.services.orchestration import OrchestrationService, RunOrchestrationService
        from src.server.services.obstruction_calculation import (
            ObstructionCalculationService, ParallelObstructionCalculator
        )
        from src.server.controllers.endpoint_controller import EndpointController

        # Logger
        self._logger = StructuredLogger("Server", LogLevel.INFO)

        # HTTP Client
        http_client = HTTPClient(self._logger)

        # Remote Services
        colormanage_service = ColorManageService(http_client, self._logger)
        daylight_service = DaylightService(http_client, self._logger)
        df_eval_service = DFEvalService(http_client, self._logger)
        obstruction_service = ObstructionService(http_client, self._logger)
        encoder_service = EncoderService(http_client, self._logger)
        postprocess_service = PostprocessService(http_client, self._logger)

        # Orchestration Services
        orchestration_service = OrchestrationService(
            colormanage_service, daylight_service, self._logger
        )
        run_orchestration_service = RunOrchestrationService(
            obstruction_service, encoder_service, daylight_service, postprocess_service, self._logger
        )

        # Obstruction Calculation Service
        obstruction_calculator = ParallelObstructionCalculator(self._logger)
        obstruction_calculation_service = ObstructionCalculationService(
            obstruction_calculator, self._logger
        )

        # Endpoint Controller
        self._endpoint_controller = EndpointController(
            colormanage_service,
            daylight_service,
            df_eval_service,
            obstruction_service,
            obstruction_calculation_service,
            encoder_service,
            orchestration_service,
            run_orchestration_service,
            self._logger
        )

        services = {
            "http_client": http_client,
            "colormanage_service": colormanage_service,
            "daylight_service": daylight_service,
            "df_eval_service": df_eval_service,
            "obstruction_service": obstruction_service,
            "encoder_service": encoder_service,
            "orchestration_service": orchestration_service
        }

        # Controller
        self._controller = ServerController(
            logger=self._logger,
            services=services
        )

        # Initialize controller
        self._controller.initialize()

    def _setup_routes(self) -> None:
        """Setup Flask routes using strategy pattern"""
        routes = [
            ("/", "get_status", self._get_status, ["GET"]),
            ("/to_rgb", "to_rgb", self._to_rgb, ["POST"]),
            ("/to_values", "to_values", self._to_values, ["POST"]),
            ("/get_df", "get_df", self._get_df, ["POST"]),  # Legacy endpoint
            ("/simulate", "simulate", self._simulate, ["POST"]),  # New daylight simulation endpoint
            ("/get_stats", "get_stats", self._get_stats, ["POST"]),
            ("/get_df_rgb", "get_df_rgb", self._get_df_rgb, ["POST"]),
            ("/horizon_angle", "horizon_angle", self._horizon_angle, ["POST"]),
            ("/zenith_angle", "zenith_angle", self._zenith_angle, ["POST"]),
            ("/obstruction", "obstruction", self._obstruction, ["POST"]),
            ("/obstruction_multi", "obstruction_multi", self._obstruction_multi, ["POST"]),
            ("/encode", "encode", self._encode, ["POST"]),
            ("/run", "run", self._run, ["POST"])  # Complete workflow endpoint
        ]

        [self._app.add_url_rule(path, name, handler, methods=methods)
         for path, name, handler, methods in routes]

    def _get_status(self) -> Dict[str, Any]:
        """Get server status endpoint"""
        return jsonify(self._controller.get_status())

    def _to_rgb(self) -> Dict[str, Any]:
        """Convert values to RGB endpoint"""
        try:
            request_data = request.get_json()
            if not request_data:
                raise BadRequest("No JSON data provided")

            result = self._endpoint_controller.to_rgb(request_data)

            if result.get("status") == "error":
                return jsonify(result), HTTPStatus.INTERNAL_SERVER_ERROR.value

            return jsonify(result)

        except Exception as e:
            self._logger.error(f"to_rgb failed: {str(e)}")
            return jsonify({"status": "error", "error": str(e)}), HTTPStatus.INTERNAL_SERVER_ERROR.value

    def _to_values(self) -> Dict[str, Any]:
        """Convert RGB to values endpoint"""
        try:
            request_data = request.get_json()
            if not request_data:
                raise BadRequest("No JSON data provided")

            result = self._endpoint_controller.to_values(request_data)

            if result.get("status") == "error":
                return jsonify(result), HTTPStatus.INTERNAL_SERVER_ERROR.value

            return jsonify(result)

        except Exception as e:
            self._logger.error(f"to_values failed: {str(e)}")
            return jsonify({"status": "error", "error": str(e)}), HTTPStatus.INTERNAL_SERVER_ERROR.value

    def _get_df(self) -> Dict[str, Any]:
        """Get dataframe endpoint (legacy, use /simulate instead)"""
        try:
            # Handle multipart form data with file upload
            if 'file' not in request.files:
                raise BadRequest("No file provided in request")

            file = request.files['file']
            form_data = request.form.to_dict()

            result = self._endpoint_controller.get_df(file, form_data)

            if result.get("status") == "error":
                return jsonify(result), HTTPStatus.INTERNAL_SERVER_ERROR.value

            return jsonify(result)

        except Exception as e:
            self._logger.error(f"get_df failed: {str(e)}")
            return jsonify({"status": "error", "error": str(e)}), HTTPStatus.INTERNAL_SERVER_ERROR.value

    def _simulate(self) -> Dict[str, Any]:
        """Run daylight simulation endpoint"""
        try:
            # Handle multipart form data with file upload
            if 'file' not in request.files:
                raise BadRequest("No file provided in request")

            file = request.files['file']
            form_data = request.form.to_dict()

            result = self._endpoint_controller.simulate(file, form_data)

            if result.get("status") == "error":
                return jsonify(result), HTTPStatus.INTERNAL_SERVER_ERROR.value

            return jsonify(result)

        except Exception as e:
            self._logger.error(f"simulate failed: {str(e)}")
            return jsonify({"status": "error", "error": str(e)}), HTTPStatus.INTERNAL_SERVER_ERROR.value

    def _get_stats(self) -> Dict[str, Any]:
        """Get statistics endpoint"""
        try:
            request_data = request.get_json()
            if not request_data:
                raise BadRequest("No JSON data provided")

            result = self._endpoint_controller.get_stats(request_data)

            if result.get("status") == "error":
                return jsonify(result), HTTPStatus.INTERNAL_SERVER_ERROR.value

            return jsonify(result)

        except Exception as e:
            self._logger.error(f"get_stats failed: {str(e)}")
            return jsonify({"status": "error", "error": str(e)}), HTTPStatus.INTERNAL_SERVER_ERROR.value

    def _get_df_rgb(self) -> Dict[str, Any]:
        """Get dataframe and convert to RGB endpoint"""
        try:
            # Handle multipart form data with file upload
            if 'file' not in request.files:
                raise BadRequest("No file provided in request")

            file = request.files['file']
            form_data = request.form.to_dict()

            result = self._endpoint_controller.get_df_rgb(file, form_data)

            if result.get("status") == "error":
                return jsonify(result), HTTPStatus.INTERNAL_SERVER_ERROR.value

            return jsonify(result)

        except Exception as e:
            self._logger.error(f"get_df_rgb failed: {str(e)}")
            return jsonify({"status": "error", "error": str(e)}), HTTPStatus.INTERNAL_SERVER_ERROR.value

    def _horizon_angle(self) -> Dict[str, Any]:
        """Calculate horizon angle endpoint"""
        try:
            request_data = request.get_json()
            if not request_data:
                raise BadRequest("No JSON data provided")

            result = self._endpoint_controller.horizon_angle(request_data)

            if result.get("status") == "error":
                return jsonify(result), HTTPStatus.INTERNAL_SERVER_ERROR.value

            return jsonify(result)

        except Exception as e:
            self._logger.error(f"horizon_angle failed: {str(e)}")
            return jsonify({"status": "error", "error": str(e)}), HTTPStatus.INTERNAL_SERVER_ERROR.value

    def _zenith_angle(self) -> Dict[str, Any]:
        """Calculate zenith angle endpoint"""
        try:
            request_data = request.get_json()
            if not request_data:
                raise BadRequest("No JSON data provided")

            result = self._endpoint_controller.zenith_angle(request_data)

            if result.get("status") == "error":
                return jsonify(result), HTTPStatus.INTERNAL_SERVER_ERROR.value

            return jsonify(result)

        except Exception as e:
            self._logger.error(f"zenith_angle failed: {str(e)}")
            return jsonify({"status": "error", "error": str(e)}), HTTPStatus.INTERNAL_SERVER_ERROR.value

    def _obstruction(self) -> Dict[str, Any]:
        """Calculate both horizon and zenith angles endpoint"""
        try:
            request_data = request.get_json()
            if not request_data:
                raise BadRequest("No JSON data provided")

            result = self._endpoint_controller.obstruction(request_data)

            if result.get("status") == "error":
                return jsonify(result), HTTPStatus.INTERNAL_SERVER_ERROR.value

            return jsonify(result)

        except Exception as e:
            self._logger.error(f"obstruction failed: {str(e)}")
            return jsonify({"status": "error", "error": str(e)}), HTTPStatus.INTERNAL_SERVER_ERROR.value

    def _obstruction_multi(self) -> Dict[str, Any]:
        """Calculate obstruction for 64 directions endpoint"""
        try:
            request_data = request.get_json()
            if not request_data:
                raise BadRequest("No JSON data provided")

            result = self._endpoint_controller.obstruction_multi(request_data)

            if result.get("status") == "error":
                return jsonify(result), HTTPStatus.INTERNAL_SERVER_ERROR.value

            return jsonify(result)

        except Exception as e:
            self._logger.error(f"obstruction_multi failed: {str(e)}")
            return jsonify({"status": "error", "error": str(e)}), HTTPStatus.INTERNAL_SERVER_ERROR.value

    @TokenAuthenticator().require_token
    def _encode(self) -> Response:
        """Encode room data to PNG image endpoint (protected by token)"""
        try:
            request_data = request.get_json()
            if not request_data:
                raise BadRequest("No JSON data provided")

            image_bytes = self._endpoint_controller.encode(request_data)

            # Return binary PNG data
            return Response(
                image_bytes,
                mimetype=ContentType.IMAGE_PNG.value,
                headers={"Content-Type": ContentType.IMAGE_PNG.value}
            )

        except ValueError as e:
            self._logger.error(f"encode validation failed: {str(e)}")
            return jsonify({"status": "error", "error": str(e)}), HTTPStatus.BAD_REQUEST.value
        except Exception as e:
            self._logger.error(f"encode failed: {str(e)}")
            return jsonify({"status": "error", "error": str(e)}), HTTPStatus.INTERNAL_SERVER_ERROR.value

    def _run(self) -> Dict[str, Any]:
        """Complete workflow: obstruction → encoding → daylight simulation"""
        try:
            request_data = request.get_json()
            if not request_data:
                raise BadRequest("No JSON data provided")

            result = self._endpoint_controller.run(request_data)

            if result.get("status") == "error":
                return jsonify(result), HTTPStatus.INTERNAL_SERVER_ERROR.value

            return jsonify(result)

        except Exception as e:
            self._logger.error(f"run failed: {str(e)}")
            return jsonify({"status": "error", "error": str(e)}), HTTPStatus.INTERNAL_SERVER_ERROR.value

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