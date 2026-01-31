import os
from typing import Dict, Any
from dotenv import load_dotenv

load_dotenv()

os.environ['CUDA_VISIBLE_DEVICES'] = '-1'
os.environ['TF_CPP_MIN_LOG_LEVEL'] = '3'
os.environ['OPENCV_IO_ENABLE_OPENEXR'] = '0'
os.environ['OMP_NUM_THREADS'] = '1'

import sys
from pathlib import Path

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from flask import Flask, Response, jsonify, request
from flask_cors import CORS
from flasgger import Swagger

from src.server.auth import TokenAuthenticator
from src.server.enums import ServiceName, EndpointType
from src.server.controllers.base_controller import ServerController
from src.server.services.remote import (
    ObstructionService, EncoderService, ModelService, MergerService, StatsService
)
from src.server.request_handler import EndpointRequestHandler
from src.server.endpoint_handlers import EndpointHandlers
from src.server.route_configurator import RouteBuilder, RouteConfigurator
from src.server.swagger_config import get_swagger_template, get_swagger_config
from src.__version__ import version

import logging

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger("logger")
logger.setLevel(logging.INFO)


class ServiceRegistry:
    """Registry for service dependencies"""

    @staticmethod
    def create_service_map() -> Dict[str, Any]:
        """Create mapping of service names to service classes"""
        return {
            ServiceName.OBSTRUCTION.value: ObstructionService,
            ServiceName.ENCODER.value: EncoderService,
            ServiceName.MODEL.value: ModelService,
            ServiceName.MERGER.value: MergerService,
            ServiceName.STATS.value: StatsService
        }


class ServerApplication:
    """Main server application encapsulating Flask app and dependencies"""

    def __init__(self, app_name: str = "Server Application"):
        self._app = Flask(app_name)
        CORS(self._app)

        # Initialize Swagger
        Swagger(self._app, template=get_swagger_template(), config=get_swagger_config())

        self._initialize_components()
        self._setup_routes()

    def _initialize_components(self) -> None:
        """Initialize all application components"""
        services = ServiceRegistry.create_service_map()

        self._controller = ServerController(services=services)
        self._controller.initialize()

        self._authenticator = TokenAuthenticator()
        self._request_handler = EndpointRequestHandler()
        self._endpoint_handlers = EndpointHandlers(self._request_handler)

    def _setup_routes(self) -> None:
        """Setup Flask routes using route configurator"""
        route_builder = RouteBuilder(version)
        route_configurator = RouteConfigurator(route_builder)

        # Create handler mapping for all endpoints
        handlers = {
            EndpointType.STATUS: self._get_status,
            EndpointType.SIMULATE: self._endpoint_handlers.handle_simulate,
            EndpointType.STATS_CALCULATE: self._endpoint_handlers.handle_stats,
            EndpointType.HORIZON: self._endpoint_handlers.handle_horizon,
            EndpointType.ZENITH: self._endpoint_handlers.handle_zenith,
            EndpointType.OBSTRUCTION: self._endpoint_handlers.handle_obstruction,
            EndpointType.OBSTRUCTION_ALL: self._endpoint_handlers.handle_obstruction_all,
            EndpointType.OBSTRUCTION_MULTI: self._endpoint_handlers.handle_obstruction_multi,
            EndpointType.OBSTRUCTION_PARALLEL: self._endpoint_handlers.handle_obstruction_parallel,
            EndpointType.ENCODE_RAW: self._endpoint_handlers.handle_encode_raw,
            EndpointType.ENCODE: self._endpoint_handlers.handle_encode,
            EndpointType.CALCULATE_DIRECTION: self._endpoint_handlers.handle_calculate_direction,
            EndpointType.REFERENCE_POINT: self._endpoint_handlers.handle_reference_point,
            EndpointType.RUN: self._endpoint_handlers.handle_run,
            EndpointType.MERGE: self._endpoint_handlers.handle_merge,
        }

        route_configurator.configure(self._app, handlers)

    def _get_status(self) -> Response:
        """Get server status
        ---
        tags:
          - Health
        responses:
          200:
            description: Server status information
            schema:
              type: object
              properties:
                status:
                  type: string
                  example: "ok"
                services:
                  type: object
        """
        return jsonify(self._controller.get_status())

    @property
    def app(self) -> Flask:
        """Get Flask application instance"""
        return self._app


class ServerLauncher:
    """Launcher for creating and running the server"""

    @staticmethod
    def create_application() -> ServerApplication:
        """Create server application instance"""
        return ServerApplication()

    @staticmethod
    def run_server(
        app: ServerApplication,
        host: str = "0.0.0.0",
        port: int = 8080,
        debug: bool = True
    ) -> None:
        """Run the server with specified configuration

        Args:
            app: Server application instance
            host: Host address to bind to
            port: Port number to bind to
            debug: Enable debug mode
        """
        log_msg = (
            f"Flask app '{app.app.name}' starting on "
            f"host {host}, port {port}. Debug mode: {debug}"
        )
        app.app.logger.info(log_msg)
        app.app.run(host=host, port=port, debug=debug, use_reloader=False)


def main() -> None:
    """Main entry point for running the server"""
    launcher = ServerLauncher()
    application = launcher.create_application()
    port = int(os.getenv("PORT", 8080))
    launcher.run_server(application, port=port, debug=True)


def create_app():
    """Factory function for creating Flask app (used by WSGI servers)"""
    _application = ServerApplication()
    return _application.app


if __name__ != "__main__":
    app = create_app()
else:
    main()
