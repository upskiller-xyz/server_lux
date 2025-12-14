import os
from enum import Enum


class DeploymentMode(Enum):
    """Deployment mode configuration"""
    LOCAL = "local"
    PRODUCTION = "production"


class ServiceConfig:
    """Configuration for microservice URLs based on deployment mode"""

    def __init__(self):
        self._mode = self._get_deployment_mode()

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

    def get_service_url(self, service_name: str) -> str:
        """Get service URL based on deployment mode

        Args:
            service_name: Name of the service (colormanage, daylight, etc.)

        Returns:
            Service URL string
        """
        if self._mode == DeploymentMode.LOCAL:
            return self._get_local_url(service_name)
        return self._get_production_url(service_name)

    def _get_local_url(self, service_name: str) -> str:
        """Get local Docker Compose service URL

        Args:
            service_name: Name of the service

        Returns:
            Local service URL
        """
        # Special case: encoder runs on same host as main server (port 8082)
        if service_name == "encoder":
            return os.getenv("ENCODER_SERVICE_URL", "http://localhost:8082")

        # Special case: model server runs on external host (port 8083)
        if service_name == "model":
            return os.getenv("MODEL_SERVICE_URL", "http://51.15.197.220:8083")

        # Special case: merger service runs on localhost (port 8084)
        if service_name == "merger":
            return os.getenv("MERGER_SERVICE_URL", "http://51.15.197.220:8084")

        local_urls = {
            "colormanage": "http://colormanage:8001",
            "daylight": "http://daylight:8002",
            "df_eval": "http://metrics:8003",
            "obstruction": "http://obstruction:8004",
            "postprocess": "http://postprocess:8006"
        }

        # Allow override via environment variable
        env_key = f"{service_name.upper()}_SERVICE_URL"
        return os.getenv(env_key, local_urls.get(service_name, ""))

    def _get_production_url(self, service_name: str) -> str:
        """Get production GCP service URL

        Args:
            service_name: Name of the service

        Returns:
            Production service URL
        """
        # Special case: encoder runs on same host as main server (port 8082)
        # Get the host from current environment or default
        if service_name == "encoder":
            # If ENCODER_SERVICE_URL is set, use it; otherwise construct from host
            encoder_url = os.getenv("ENCODER_SERVICE_URL")
            if encoder_url:
                return encoder_url
            # Try to construct from main server host
            main_host = os.getenv("SERVER_HOST", "localhost")
            return f"http://{main_host}:8082"

        # Special case: model server (port 8083)
        if service_name == "model":
            # If MODEL_SERVICE_URL is set, use it; otherwise use default production server
            model_url = os.getenv("MODEL_SERVICE_URL")
            if model_url:
                return model_url
            # Default to the external model server
            return "http://51.15.197.220:8083"

        # Special case: merger service (port 8084)
        if service_name == "merger":
            merger_url = os.getenv("MERGER_SERVICE_URL")
            if merger_url:
                return merger_url
            # Default to localhost for merger service
            main_host = os.getenv("SERVER_HOST", "localhost")
            return f"http://51.15.197.220:8084"

        production_urls = {
            "colormanage": "https://colormanage-server-182483330095.europe-north2.run.app",
            "daylight": "https://daylight-factor-182483330095.europe-north2.run.app",
            "df_eval": "https://df-eval-server-182483330095.europe-north2.run.app",
            "obstruction": "https://obstruction-server-182483330095.europe-north2.run.app",
            "postprocess": "https://daylight-processing-182483330095.europe-north2.run.app"
        }

        # Allow override via environment variable
        print("SERVICE", service_name)
        env_key = f"{service_name.upper()}_SERVICE_URL"
        return os.getenv(env_key, production_urls.get(service_name, ""))


# Singleton instance
_config = ServiceConfig()


def get_service_config() -> ServiceConfig:
    """Get the service configuration singleton"""
    return _config
