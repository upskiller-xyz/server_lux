import os
from typing import Callable, Dict
from .enums import ServicePort, ServiceName, DeploymentMode
from .maps import BaseUrlMap


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
        self._config_maps = ServiceConfigMaps()
        self._adapters = self._build_url_adapters()

    def _get_deployment_mode(self) -> DeploymentMode:
        mode = os.getenv("DEPLOYMENT_MODE", "production").lower()
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
            return os.getenv(env_var, f"http://{host}:{port.value}")
        return get_url

    def get_service_url(self, service_name: str) -> str:
        adapter = self._adapters.get(service_name)
        if not adapter:
            raise ValueError(f"Unknown service name: {service_name}")

        return adapter()


_config = ServiceConfig()


def get_service_config() -> ServiceConfig:
    return _config
