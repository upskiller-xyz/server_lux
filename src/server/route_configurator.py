from typing import List, Tuple, Callable
from flask import Flask

from .enums import EndpointType, Methods


class Route:
    """Represents a single route configuration"""

    def __init__(self, path: str, endpoint: EndpointType, methods: List[str]):
        self.path = path
        self.endpoint = endpoint
        self.methods = methods


class RouteBuilder:
    """Builds route configurations based on API version"""

    def __init__(self, version: str):
        self._version = f"v{version.split('.')[0]}"

    def build_routes(self) -> List[Route]:
        """Build all route configurations

        Returns:
            List of Route objects
        """
        return [
            Route("/", EndpointType.STATUS, [Methods.GET.value]),
            Route(f"/{self._version}/simulate", EndpointType.SIMULATE, [Methods.POST.value]),
            Route(f"/{self._version}/stats", EndpointType.STATS_CALCULATE, [Methods.POST.value]),
            Route(f"/{self._version}/horizon", EndpointType.HORIZON, [Methods.POST.value]),
            Route(f"/{self._version}/zenith", EndpointType.ZENITH, [Methods.POST.value]),
            Route(f"/{self._version}/obstruction", EndpointType.OBSTRUCTION_ALL, [Methods.POST.value]),
            Route(f"/{self._version}/obstruction_all", EndpointType.OBSTRUCTION_ALL, [Methods.POST.value]),
            Route(f"/{self._version}/obstruction_multi", EndpointType.OBSTRUCTION_MULTI, [Methods.POST.value]),
            Route(f"/{self._version}/obstruction_parallel", EndpointType.OBSTRUCTION_PARALLEL, [Methods.POST.value]),
            Route(f"/{self._version}/encode_raw", EndpointType.ENCODE_RAW, [Methods.POST.value]),
            Route(f"/{self._version}/encode", EndpointType.ENCODE, [Methods.POST.value]),
            Route(f"/{self._version}/calculate-direction", EndpointType.CALCULATE_DIRECTION, [Methods.POST.value]),
            Route(f"/{self._version}/get-reference-point", EndpointType.REFERENCE_POINT, [Methods.POST.value]),
            Route(f"/{self._version}/run", EndpointType.RUN, [Methods.POST.value]),
            Route(f"/{self._version}/merge", EndpointType.MERGE, [Methods.POST.value]),
        ]


class RouteConfigurator:
    """Configures Flask app routes"""

    def __init__(self, route_builder: RouteBuilder):
        self._route_builder = route_builder

    def configure(
        self,
        app: Flask,
        status_handler: Callable,
        request_handler: Callable
    ) -> None:
        """Configure all routes on Flask app

        Args:
            app: Flask application instance
            status_handler: Handler for status endpoint
            request_handler: Handler for all other endpoints
        """
        routes = self._route_builder.build_routes()

        for route in routes:
            handler = status_handler if route.endpoint == EndpointType.STATUS else request_handler
            app.add_url_rule(
                route.path,
                route.endpoint.value,
                handler,
                methods=route.methods
            )
