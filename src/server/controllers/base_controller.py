from typing import Dict, Any, Optional

from src.server.interfaces import IServerController, ILogger
from src.server.enums import ServerStatus


class ServerController(IServerController):
    """Generic server controller implementing IServerController interface"""

    def __init__(
        self,
        logger: ILogger,
        services: Optional[Dict[str, Any]] = None
    ):
        """
        Initialize the controller with dependencies

        Args:
            logger: Logger instance for structured logging
            services: Optional dictionary of service name -> service instance
        """
        self._logger = logger
        self._services = services or {}
        self._status = ServerStatus.STARTING

    def initialize(self) -> None:
        """Initialize the server and its components"""
        self._logger.info("Initializing server controller")
        try:
            # Initialize all registered services
            for service_name, service in self._services.items():
                if hasattr(service, 'initialize'):
                    self._logger.debug(f"Initializing service: {service_name}")
                    service.initialize()

            self._status = ServerStatus.RUNNING
            self._logger.info("Server controller initialized successfully")
        except Exception as e:
            self._status = ServerStatus.ERROR
            self._logger.error(f"Failed to initialize server controller: {str(e)}")
            raise

    def get_status(self) -> Dict[str, Any]:
        """
        Get current server status

        Returns:
            Dictionary containing status information
        """
        components = {}
        for service_name, service in self._services.items():
            if hasattr(service, 'get_status'):
                components[service_name] = service.get_status()
            else:
                components[service_name] = "ready"

        return {
            "status": self._status.value,
            "services": components
        }
