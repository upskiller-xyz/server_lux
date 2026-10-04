from typing import Callable, Dict, List, Tuple

from flask import Flask

from .enums import ApiVersion, EndpointType, Methods


class Route:
    """Represents a single route configuration"""

    def __init__(self, path: str, endpoint: EndpointType, methods: List[str], handler: Callable = None):
        self.path = path
        self.endpoint = endpoint
        self.methods = methods
        self.handler = handler


class RoutePathBuilder:
    """Builds versioned route paths, so the layout lives in one place."""

    SEPARATOR = "/"
    TEMPLATE = "/{version}/{segment}"

    def __init__(self, api_version: str):
        self._api_version = api_version

    def build(self, segment: str) -> str:
        """``"run/detailed"`` → ``"/v1/run/detailed"``; an empty segment → ``"/"``."""
        if not segment:
            return self.SEPARATOR
        return self.TEMPLATE.format(version=self._api_version, segment=segment)


class RouteBuilder:
    """Builds route configurations based on API version"""

    # (path segment below the version prefix, endpoint, methods). The empty
    # segment is the unversioned health check at "/".
    ROUTE_SPECS: List[Tuple[str, EndpointType, List[str]]] = [
        ("", EndpointType.STATUS, [Methods.GET.value]),
        ("simulate", EndpointType.SIMULATE, [Methods.POST.value]),
        ("stats", EndpointType.STATS_CALCULATE, [Methods.POST.value]),
        ("horizon", EndpointType.HORIZON, [Methods.POST.value]),
        ("zenith", EndpointType.ZENITH, [Methods.POST.value]),
        ("obstruction", EndpointType.OBSTRUCTION, [Methods.POST.value]),
        ("obstruction_all", EndpointType.OBSTRUCTION_ALL, [Methods.POST.value]),
        ("obstruction_multi", EndpointType.OBSTRUCTION_MULTI, [Methods.POST.value]),
        ("obstruction_parallel", EndpointType.OBSTRUCTION_PARALLEL, [Methods.POST.value]),
        ("encode_raw", EndpointType.ENCODE_RAW, [Methods.POST.value]),
        ("encode", EndpointType.ENCODE, [Methods.POST.value]),
        ("calculate-direction", EndpointType.CALCULATE_DIRECTION, [Methods.POST.value]),
        ("get-reference-point", EndpointType.REFERENCE_POINT, [Methods.POST.value]),
        ("run", EndpointType.RUN, [Methods.POST.value]),
        ("run/detailed", EndpointType.RUN_DETAILED, [Methods.POST.value]),
        ("merge", EndpointType.MERGE, [Methods.POST.value]),
        ("trial/status", EndpointType.TRIAL_STATUS, [Methods.GET.value]),
    ]

    def __init__(self, api_version: str = ApiVersion.V1.value):
        # The API version is the URL prefix (``v1``), deliberately independent
        # of the package version — a patch release must not move the routes.
        self._paths = RoutePathBuilder(api_version)

    def build_routes(self, handlers: Dict[EndpointType, Callable]) -> List[Route]:
        """Build all route configurations

        Args:
            handlers: Dictionary mapping endpoint types to handler functions

        Returns:
            List of Route objects
        """
        return [
            Route(self._paths.build(segment), endpoint, methods, handlers.get(endpoint))
            for segment, endpoint, methods in self.ROUTE_SPECS
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
