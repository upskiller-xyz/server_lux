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
from src.server.enums import LogLevel, EndpointType
from src.server.controllers.base_controller import ServerController

from src.server.services.orchestration import RunOrchestrationService, EncodeOrchestrationService
from src.server.services.obstruction import (
    ObstructionCalculationService, SingleRequestObstructionCalculator
)
from src.server.controllers.endpoint_controller import EndpointController
from src.__version__ import version

import logging
logger = logging.getLogger("logger")


class ServerApplication:
    """Main application class implementing dependency injection and OOP principles"""

    def __init__(self, app_name: str = "Server Application"):
        self._app = Flask(app_name)
        CORS(self._app)
        self._controller = ServerController()
        self._controller.initialize()
        self._endpoint_controller = EndpointController()
        self._authenticator = TokenAuthenticator()
        self._error_builder = ErrorResponseBuilder()
        self._setup_dependencies()
        self._setup_routes()

    def _setup_dependencies(self) -> None:
        """Setup all dependencies using dependency injection"""
        pass

    def _setup_routes(self) -> None:
        """Setup Flask routes using strategy pattern with versioned endpoints"""
        # Extract major version from version string (e.g., "1.0.0" -> "v1")
        major_version = f"v{version.split('.')[0]}"

        routes = [
            ("/", EndpointType.STATUS, ["GET"]),
            # (f"/{major_version}/get_df_direct", "get_df_direct", End, ["POST"]),  # Direct image to simulation
            (f"/{major_version}/simulate", EndpointType.SIMULATE, ["POST"]),  # New daylight simulation endpoint
            (f"/{major_version}/stats", EndpointType.GET_STATS, ["POST"]),
            
            (f"/{major_version}/horizon_angle", EndpointType.HORIZON_ANGLE, ["POST"]),
            (f"/{major_version}/zenith_angle", EndpointType.ZENITH_ANGLE, ["POST"]),
            (f"/{major_version}/obstruction", EndpointType.OBSTRUCTION_ALL, ["POST"]),
            (f"/{major_version}/obstruction_multi", EndpointType.OBSTRUCTION_MULTI, ["POST"]),
            (f"/{major_version}/obstruction_parallel", EndpointType.OBSTRUCTION_PARALLEL, ["POST"]),
            (f"/{major_version}/encode_raw", EndpointType.ENCODE_RAW, ["POST"]),  # Direct encode without obstruction
            (f"/{major_version}/encode", EndpointType.ENCODE, ["POST"]),  # Obstruction + encode workflow
            (f"/{major_version}/run",EndpointType.RUN, ["POST"]),  # Complete workflow endpoint
            (f"/{major_version}/merge", EndpointType.MERGE, ["POST"]),  # Merge multiple window simulations
        ]
    
        [self._app.add_url_rule(path, endpoint.value, self._run, methods=methods)
         for path, endpoint, methods in routes]

    def _get_status(self) -> Dict[str, Any]:
        """Get server status endpoint"""
        return jsonify(self._controller.get_status())
    
    def _run(self)-> Dict[str, Any]:
         endpoint_str = request.path[1:]
         try:
            # Handle multipart form data with file upload
            # if 'file' not in request.files:
            #     return self._error_builder.build(ErrorType.MISSING_FILE)
            endpoint:EndpointType = EndpointType.by_value(endpoint_str)
            file = None
            if 'file' in request.files:
                file = request.files['file']
            params = request.get_json()
            if not params:
                params = request.form.to_dict()

            result = self._endpoint_controller.run(endpoint, params, file)

            if result.get("status") == "error":
                return jsonify(result), HTTPStatus.INTERNAL_SERVER_ERROR.value

            return jsonify(result)
         
         except Exception as e:
            logger.error(f"{endpoint_str} failed: {str(e)}")
            return self._error_builder.build_from_exception(e)


    # @TokenAuthenticator().require_token
    # def _encode_raw(self) -> Response:
    #     """Direct encode endpoint - calls remote encode service without obstruction calculation (protected by token)"""
    #     try:
    #         request_data = request.get_json()
    #         if not request_data:
    #             return self._error_builder.build(ErrorType.MISSING_JSON)

    #         image_bytes = self._endpoint_controller.encode_raw(request_data)

    #         # Return binary PNG data
    #         return Response(
    #             image_bytes,
    #             mimetype=ContentType.IMAGE_PNG.value,
    #             headers={"Content-Type": ContentType.IMAGE_PNG.value}
    #         )

    #     except ValueError as e:
    #         self._logger.error(f"encode_raw validation failed: {str(e)}")
    #         return self._error_builder.build_from_exception(e, HTTPStatus.BAD_REQUEST.value)
    #     except Exception as e:
    #         self._logger.error(f"encode_raw failed: {str(e)}")
    #         return self._error_builder.build_from_exception(e)

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