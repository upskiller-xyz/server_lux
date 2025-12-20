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

from src.server.auth import TokenAuthenticator
from src.server.enums import ServiceName
from src.server.controllers.base_controller import ServerController
from src.server.services.remote import (
    ObstructionService, EncoderService, ModelService, MergerService, StatsService
)
from src.server.request_handler import EndpointRequestHandler
from src.server.route_configurator import RouteBuilder, RouteConfigurator
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

        self._initialize_components()
        self._setup_routes()

    def _initialize_components(self) -> None:
        """Initialize all application components"""
        services = ServiceRegistry.create_service_map()

        self._controller = ServerController(services=services)
        self._controller.initialize()

        self._authenticator = TokenAuthenticator()
        self._request_handler = EndpointRequestHandler()

    def _setup_routes(self) -> None:
        """Setup Flask routes using route configurator"""
        route_builder = RouteBuilder(version)
        route_configurator = RouteConfigurator(route_builder)

        route_configurator.configure(
            self._app,
            status_handler=self._get_status,
            request_handler=self._handle_request
        )

    def _get_status(self) -> Response:
        """Handle status endpoint"""
        return jsonify(self._controller.get_status())

    def _handle_request(self) -> tuple[Response, int]:
        """Handle all non-status endpoint requests"""
        
        return self._request_handler.handle(request)

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
