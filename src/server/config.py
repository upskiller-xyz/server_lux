import os
from typing import Callable, Dict

from .enums import DeploymentMode, ServiceName, ServicePort
from .env_keys import EnvKey
from .maps import BaseUrlMap


class ServiceAddressBuilder:
    """Builds the default ``host:port`` address for a co-located service."""
    TEMPLATE: str = "{host}:{port}"
    UNKNOWN_SERVICE: str = "Unknown service name: {service}"

    @classmethod
    def address(cls, host: str, port: int) -> str:
        return cls.TEMPLATE.format(host=host, port=port)


class SessionConfig:
    _mode = DeploymentMode.PRODUCTION

    @classmethod
    def get_url(cls):
        return BaseUrlMap.get(cls._mode).value


class ServiceConfigMaps:

    ENV_VAR_MAP: Dict[str, str] = {
        ServiceName.ENCODER.value: "ENCODER_SERVICE_URL",
        ServiceName.MODEL.value: "MODEL_SERVICE_URL",
        ServiceName.MERGER.value: "MERGER_SERVICE_URL",
        ServiceName.STATS.value: "STATS_SERVICE_URL",
        ServiceName.OBSTRUCTION.value: "OBSTRUCTION_SERVICE_URL",
    }

    PORT_MAP: Dict[str, ServicePort] = {
        ServiceName.ENCODER.value: ServicePort.ENCODER,
        ServiceName.MODEL.value: ServicePort.MODEL,
        ServiceName.MERGER.value: ServicePort.MERGER,
        ServiceName.STATS.value: ServicePort.STATS,
        ServiceName.OBSTRUCTION.value: ServicePort.OBSTRUCTION,
    }


class ServiceConfig:

    def __init__(self):
        self._mode = self._get_deployment_mode()
        SessionConfig._mode = self._mode  # Sync SessionConfig with deployment mode
        self._config_maps = ServiceConfigMaps()
        self._adapters = self._build_url_adapters()

    def _get_deployment_mode(self) -> DeploymentMode:
        mode = os.getenv(EnvKey.DEPLOYMENT_MODE.value, "production").lower()
        if mode == "local":
            return DeploymentMode.LOCAL
        return DeploymentMode.PRODUCTION

    @property
    def mode(self) -> DeploymentMode:
        return self._mode

    def _build_url_adapters(self) -> Dict[str, Callable[[], str]]:
        adapters = {}

        for service_name_value in self._config_maps.ENV_VAR_MAP.keys():
            env_var = self._config_maps.ENV_VAR_MAP[service_name_value]
            host = SessionConfig.get_url()
            port = self._config_maps.PORT_MAP[service_name_value]

            adapters[service_name_value] = self._create_url_adapter(env_var, host, port)

        return adapters

    @staticmethod
    def _create_url_adapter(env_var: str, host: str, port: ServicePort) -> Callable[[], str]:
        def get_url() -> str:
            return os.getenv(env_var, ServiceAddressBuilder.address(host, port.value))
        return get_url

    def get_service_url(self, service_name: str) -> str:
        adapter = self._adapters.get(service_name)
        if not adapter:
            raise ValueError(ServiceAddressBuilder.UNKNOWN_SERVICE.format(service=service_name))

        return adapter()


_config = ServiceConfig()


def get_service_config() -> ServiceConfig:
    return _config
