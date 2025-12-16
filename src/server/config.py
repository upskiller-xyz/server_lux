import os
from enum import Enum
from typing import Callable, Dict
from .enums import ServicePort, ServiceHost, ServiceName, DeploymentMode
from .maps import BaseUrlMap



class SessionConfig:
    _mode = DeploymentMode.PRODUCTION

    @classmethod
    def get_url(cls):
        return BaseUrlMap.get(cls._mode)

class ServiceConfigMaps:
    """Configuration maps for service URL construction using Adapter-Map pattern

    Separates concerns:
    - Environment variable keys
    - Service hosts
    - Service ports
    """

    # Map: ServiceName -> Environment Variable Key
    ENV_VAR_MAP: Dict[str, str] = {
        ServiceName.ENCODER.value: "ENCODER_SERVICE_URL",
        ServiceName.MODEL.value: "MODEL_SERVICE_URL",
        ServiceName.MERGER.value: "MERGER_SERVICE_URL",
        ServiceName.STATS.value: "STATS_SERVICE_URL",
        ServiceName.COLORMANAGE.value: "COLORMANAGE_SERVICE_URL",
        ServiceName.OBSTRUCTION.value: "OBSTRUCTION_SERVICE_URL",
    }


    # Map: ServiceName -> ServicePort
    PORT_MAP: Dict[str, ServicePort] = {
        ServiceName.ENCODER.value: ServicePort.ENCODER,
        ServiceName.MODEL.value: ServicePort.MODEL,
        ServiceName.MERGER.value: ServicePort.MERGER,
        ServiceName.STATS.value: ServicePort.STATS,
        # ServiceName.COLORMANAGE.value: ServicePort.COLORMANAGE,
        ServiceName.OBSTRUCTION.value: ServicePort.OBSTRUCTION,
    }

   


class ServiceConfig:
    """Configuration for microservice URLs based on deployment mode

    Uses Adapter-Map pattern for URL resolution:
    - Strategy pattern for deployment mode selection
    - Adapter pattern for service-specific URL construction
    - Separate maps for env vars, hosts, and ports
    """

    def __init__(self):
        self._mode = self._get_deployment_mode()
        self._config_maps = ServiceConfigMaps()
        self._local_url_adapters = self._build_local_url_adapters()
        self._production_url_adapters = self._build_production_url_adapters()

    def _get_deployment_mode(self) -> DeploymentMode:
        """Get deployment mode from environment variable"""
        mode = os.getenv("DEPLOYMENT_MODE", "production").lower()
        if mode == "local":
            return DeploymentMode.LOCAL
        return DeploymentMode.PRODUCTION

    @property
    def mode(self) -> DeploymentMode:
        """Current deployment mode"""
        return self._mode

    def _build_local_url_adapters(self) -> Dict[str, Callable[[], str]]:
        """Build adapter map for local URLs using configuration maps

        Returns:
            Dictionary mapping service names to URL adapter functions
        """
        adapters = {}

        # Build adapters for all services using the configuration maps
        for service_name_value in self._config_maps.ENV_VAR_MAP.keys():
            env_var = self._config_maps.ENV_VAR_MAP[service_name_value]
            host = self._config_maps.LOCAL_HOST_MAP[service_name_value]
            port = self._config_maps.PORT_MAP[service_name_value]

            # Create adapter function for this service
            adapters[service_name_value] = lambda e=env_var, h=host, p=port: (
                os.getenv(e, f"http://{h.value}:{p.value}")
            )

        return adapters

    def _build_production_url_adapters(self) -> Dict[str, Callable[[], str]]:
        """Build adapter map for production URLs using configuration maps

        Returns:
            Dictionary mapping service names to URL adapter functions
        """
        adapters = {}

        # Build adapters for GCP services (use full GCP URL)
        for service_name_value, gcp_url in self._config_maps.GCP_URL_MAP.items():
            env_var = self._config_maps.ENV_VAR_MAP[service_name_value]
            adapters[service_name_value] = lambda e=env_var, g=gcp_url: (
                os.getenv(e, g.value)
            )

        # Build adapters for non-GCP services (construct from host:port)
        for service_name_value, host in self._config_maps.PRODUCTION_HOST_MAP.items():
            env_var = self._config_maps.ENV_VAR_MAP[service_name_value]
            port = self._config_maps.PORT_MAP[service_name_value]

            # Services using SERVER_HOST env var (encoder, stats)
            if host == ServiceHost.LOCALHOST:
                adapters[service_name_value] = lambda e=env_var, p=port: (
                    os.getenv(e) or f"http://{os.getenv('SERVER_HOST', ServiceHost.LOCALHOST.value)}:{p.value}"
                )
            # Services using fixed production host (model, merger)
            else:
                adapters[service_name_value] = lambda e=env_var, h=host, p=port: (
                    os.getenv(e, f"http://{h.value}:{p.value}")
                )

        return adapters

    def get_service_url(self, service_name: str) -> str:
        """Get service URL based on deployment mode using Adapter-Map pattern

        Args:
            service_name: Name of the service (colormanage, daylight, etc.)

        Returns:
            Service URL string

        Raises:
            ValueError: If service_name is unknown
        """
        # Strategy pattern: select adapter map based on deployment mode
        url_adapters = (
            self._local_url_adapters if self._mode == DeploymentMode.LOCAL
            else self._production_url_adapters
        )

        # Adapter pattern: get service-specific URL adapter
        adapter = url_adapters.get(service_name)
        if not adapter:
            raise ValueError(f"Unknown service name: {service_name}")

        return adapter()


# Singleton instance
_config = ServiceConfig()


def get_service_config() -> ServiceConfig:
    """Get the service configuration singleton"""
    return _config
