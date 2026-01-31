from typing import List, Tuple, Callable, Dict
from flask import Flask

from .enums import EndpointType, Methods


class Route:
    """Represents a single route configuration"""

    def __init__(self, path: str, endpoint: EndpointType, methods: List[str], handler: Callable = None):
        self.path = path
        self.endpoint = endpoint
        self.methods = methods
        self.handler = handler


class RouteBuilder:
    """Builds route configurations based on API version"""

    def __init__(self, version: str):
        self._version = f"v{version.split('.')[0]}"

    def build_routes(self, handlers: Dict[EndpointType, Callable]) -> List[Route]:
        """Build all route configurations

        Args:
            handlers: Dictionary mapping endpoint types to handler functions

        Returns:
            List of Route objects
        """
        return [
            Route("/", EndpointType.STATUS, [Methods.GET.value], handlers.get(EndpointType.STATUS)),
            Route(f"/{self._version}/simulate", EndpointType.SIMULATE, [Methods.POST.value], handlers.get(EndpointType.SIMULATE)),
            Route(f"/{self._version}/stats", EndpointType.STATS_CALCULATE, [Methods.POST.value], handlers.get(EndpointType.STATS_CALCULATE)),
            Route(f"/{self._version}/horizon", EndpointType.HORIZON, [Methods.POST.value], handlers.get(EndpointType.HORIZON)),
            Route(f"/{self._version}/zenith", EndpointType.ZENITH, [Methods.POST.value], handlers.get(EndpointType.ZENITH)),
            Route(f"/{self._version}/obstruction", EndpointType.OBSTRUCTION, [Methods.POST.value], handlers.get(EndpointType.OBSTRUCTION)),
            Route(f"/{self._version}/obstruction_all", EndpointType.OBSTRUCTION_ALL, [Methods.POST.value], handlers.get(EndpointType.OBSTRUCTION_ALL)),
            Route(f"/{self._version}/obstruction_multi", EndpointType.OBSTRUCTION_MULTI, [Methods.POST.value], handlers.get(EndpointType.OBSTRUCTION_MULTI)),
            Route(f"/{self._version}/obstruction_parallel", EndpointType.OBSTRUCTION_PARALLEL, [Methods.POST.value], handlers.get(EndpointType.OBSTRUCTION_PARALLEL)),
            Route(f"/{self._version}/encode_raw", EndpointType.ENCODE_RAW, [Methods.POST.value], handlers.get(EndpointType.ENCODE_RAW)),
            Route(f"/{self._version}/encode", EndpointType.ENCODE, [Methods.POST.value], handlers.get(EndpointType.ENCODE)),
            Route(f"/{self._version}/calculate-direction", EndpointType.CALCULATE_DIRECTION, [Methods.POST.value], handlers.get(EndpointType.CALCULATE_DIRECTION)),
            Route(f"/{self._version}/get-reference-point", EndpointType.REFERENCE_POINT, [Methods.POST.value], handlers.get(EndpointType.REFERENCE_POINT)),
            Route(f"/{self._version}/run", EndpointType.RUN, [Methods.POST.value], handlers.get(EndpointType.RUN)),
            Route(f"/{self._version}/merge", EndpointType.MERGE, [Methods.POST.value], handlers.get(EndpointType.MERGE)),
        ]


class RouteConfigurator:
    """Configures Flask app routes"""

    def __init__(self, route_builder: RouteBuilder):
        self._route_builder = route_builder

    def configure(
        self,
        app: Flask,
        handlers: Dict[EndpointType, Callable]
    ) -> None:
        """Configure all routes on Flask app

        Args:
            app: Flask application instance
            handlers: Dictionary mapping endpoint types to handler functions
        """
        routes = self._route_builder.build_routes(handlers)

        for route in routes:
            if route.handler:
                app.add_url_rule(
                    route.path,
                    route.endpoint.value,
                    route.handler,
                    methods=route.methods
                )
