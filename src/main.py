import os
import sys
from pathlib import Path
from typing import Any, Dict

from dotenv import load_dotenv

# The project root must be importable before anything under `src.` is imported,
# so this runs ahead of the environment setup below (which needs EnvKey).
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.server.env_keys import EnvKey  # noqa: E402  (needs the path above)

load_dotenv()

os.environ[EnvKey.CUDA_VISIBLE_DEVICES.value] = '-1'
os.environ[EnvKey.TF_CPP_MIN_LOG_LEVEL.value] = '3'
os.environ[EnvKey.OPENCV_IO_ENABLE_OPENEXR.value] = '0'
os.environ[EnvKey.OMP_NUM_THREADS.value] = '1'

import logging

from flasgger import Swagger
from flask import Flask, Response, jsonify

from src.server.auth import Authenticator
from src.server.controllers.base_controller import ServerController
from src.server.cors_config import CorsConfig
from src.server.endpoint_handlers import EndpointHandlers
from src.server.enums import AuthType, EndpointType, ServiceName
from src.server.maps import AuthTypeMessageMap
from src.server.rate_limiter import RateLimiter
from src.server.request_handler import EndpointRequestHandler
from src.server.route_configurator import RouteBuilder, RouteConfigurator
from src.server.services.helpers.call_recorder import RequestIdMiddleware
from src.server.services.remote import (
    EncoderService,
    MergerService,
    ModelService,
    ObstructionService,
    StatsService,
)
from src.server.swagger_config import get_swagger_config, get_swagger_template
from src.server.telemetry import TelemetryMiddleware
from src.server.trial_guard import TrialGuard

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
        CorsConfig.from_environment().apply(self._app)

        if self._api_docs_enabled():
            Swagger(self._app, template=get_swagger_template(), config=get_swagger_config())

        self._initialize_components()
        self._setup_routes()
        RequestIdMiddleware().register(self._app)
        TelemetryMiddleware().register(self._app)

    @staticmethod
    def _api_docs_enabled() -> bool:
        """Swagger UI + apispec (/docs/, /apispec.json); disable on public gateways."""
        return os.getenv(EnvKey.API_DOCS_ENABLED.value, "true").strip().lower() in ("true", "1", "yes")

    def _initialize_components(self) -> None:
        """Initialize all application components"""
        services = ServiceRegistry.create_service_map()

        self._controller = ServerController(services=services)
        self._controller.initialize()

        self._authenticator = Authenticator()
        self._rate_limiter = RateLimiter.from_environment()
        logger.info(
            "Per-user rate limiting: %s",
            "enabled" if self._rate_limiter.is_enabled else "disabled",
        )
        self._trial_guard = TrialGuard.from_environment()
        logger.info(
            "Trial guard: %s", "enabled" if self._trial_guard.is_enabled else "disabled"
        )

        # Log authentication mode for visibility
        auth_type_value = os.getenv(EnvKey.AUTH_TYPE.value, AuthType.TOKEN.value).lower()
        auth_type = AuthType.by_value(auth_type_value)
        logger.info(
            "Authentication Type: %s (%s)",
            auth_type_value,
            AuthTypeMessageMap.get(auth_type),
        )

        self._request_handler = EndpointRequestHandler()
        self._endpoint_handlers = EndpointHandlers(self._request_handler)

    def _setup_routes(self) -> None:
        """Setup Flask routes using route configurator"""
        route_builder = RouteBuilder()
        route_configurator = RouteConfigurator(route_builder)
        auth = self._authenticator.require_auth
        quota = self._rate_limiter.require_quota          # prediction bucket (10/day)
        aux_quota = self._rate_limiter.require_aux_quota  # supporting compute (ceiling)
        # Trial guard: time-limits only the trial Auth0 client (TRIAL_CLIENT_ID);
        # paying customers and the web app pass through. Outermost after auth so
        # it can gate every trial request, including the aux endpoints.
        trial = self._trial_guard.require_trial

        handlers = {
            EndpointType.STATUS: self._get_status,
            # Read-only trial status for the plugin. NOT wrapped in the trial
            # guard — the guard would 403 an expired trial before this could
            # report it. get_status() performs the lookup itself and reports
            # "expired" instead of rejecting. The aux quota applies for the same
            # reason it does elsewhere: every /v1 route gets a ceiling, so no
            # endpoint is unmetered by omission.
            EndpointType.TRIAL_STATUS: auth(aux_quota(self._trial_guard.get_status)),
            # Auth outer, quota inner: authentication runs first and sets the
            # subject + client id the rate limiter keys/gates the daily quota on.
            # The web daylight tool predicts via /run (and /run/detailed in debug);
            # /simulate is covered too for defence-in-depth. The quota only counts
            # requests from the web app's Auth0 client (RATE_LIMIT_CLIENT_ID), so
            # the Revit add-in stays unlimited even on these shared endpoints.
            EndpointType.SIMULATE: auth(trial(quota(self._endpoint_handlers.handle_simulate))),
            # Supporting compute endpoints — the generous aux ceiling (stops
            # hammering; a normal run makes several of these calls). Trial callers
            # are additionally time-limited by the trial guard.
            EndpointType.STATS_CALCULATE: auth(trial(aux_quota(self._endpoint_handlers.handle_stats))),
            EndpointType.HORIZON: auth(trial(aux_quota(self._endpoint_handlers.handle_horizon))),
            EndpointType.ZENITH: auth(trial(aux_quota(self._endpoint_handlers.handle_zenith))),
            EndpointType.OBSTRUCTION: auth(trial(aux_quota(self._endpoint_handlers.handle_obstruction))),
            EndpointType.OBSTRUCTION_ALL: auth(trial(aux_quota(self._endpoint_handlers.handle_obstruction_all))),
            EndpointType.OBSTRUCTION_MULTI: auth(trial(aux_quota(self._endpoint_handlers.handle_obstruction_multi))),
            EndpointType.OBSTRUCTION_PARALLEL: auth(trial(aux_quota(self._endpoint_handlers.handle_obstruction_parallel))),
            EndpointType.ENCODE_RAW: auth(trial(aux_quota(self._endpoint_handlers.handle_encode_raw))),
            EndpointType.ENCODE: auth(trial(aux_quota(self._endpoint_handlers.handle_encode))),
            EndpointType.CALCULATE_DIRECTION: auth(trial(aux_quota(self._endpoint_handlers.handle_calculate_direction))),
            EndpointType.REFERENCE_POINT: auth(trial(aux_quota(self._endpoint_handlers.handle_reference_point))),
            # Prediction endpoints — the 10/day quota.
            EndpointType.RUN: auth(trial(quota(self._endpoint_handlers.handle_run))),
            EndpointType.RUN_DETAILED: auth(trial(quota(self._endpoint_handlers.handle_run_detailed))),
            EndpointType.MERGE: auth(trial(aux_quota(self._endpoint_handlers.handle_merge))),
        }

        route_configurator.configure(self._app, handlers)

    def _get_status(self) -> Response:
        """Get server status
        ---
        tags:
          - Health
        security: []
        responses:
          200:
            description: Server status
            schema:
              type: object
              properties:
                status:
                  type: string
                  example: "ok"
        """
        return jsonify({"status": "ok"})

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
        debug: bool = False
    ) -> None:
        """Run the server with specified configuration

        Args:
            app: Server application instance
            host: Host address to bind to
            port: Port number to bind to
            debug: Enable debug mode
        """
        app.app.logger.info(
            "Flask app '%s' starting on host %s, port %s. Debug mode: %s",
            app.app.name,
            host,
            port,
            debug,
        )
        app.app.run(host=host, port=port, debug=debug, use_reloader=False)


def main() -> None:
    """Main entry point for running the server"""
    launcher = ServerLauncher()
    application = launcher.create_application()
    port = int(os.getenv(EnvKey.PORT.value, 8080))
    debug = os.getenv(EnvKey.FLASK_DEBUG.value, "false").strip().lower() in ("true", "1", "yes")
    launcher.run_server(application, port=port, debug=debug)


def create_app():
    """Factory function for creating Flask app (used by WSGI servers)"""
    _application = ServerApplication()
    return _application.app


if __name__ != "__main__":
    app = create_app()
else:
    main()
