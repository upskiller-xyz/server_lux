from typing import Optional
from abc import ABC


class ServiceException(Exception, ABC):
    """Base exception for all service-related errors"""

    def __init__(self, message: str, service_name: Optional[str] = None):
        self.message = message
        self.service_name = service_name
        super().__init__(self.message)


class ServiceConnectionError(ServiceException):
    """Exception raised when unable to connect to a remote service"""

    def __init__(
        self,
        service_name: str,
        endpoint: str,
        address: str,
        original_error: Optional[Exception] = None
    ):
        self.endpoint = endpoint
        self.address = address
        self.original_error = original_error

        message = f"Failed to connect to {service_name} service at {address}"
        super().__init__(message, service_name)

    def get_user_message(self, is_local: bool = False) -> str:
        """Get user-friendly error message"""
        if is_local:
            return (
                f"⚠️  Connection failed: {self.service_name} service at {self.address} is not responding.\n"
                f"   Please restart the {self.service_name} service and try again."
            )
        else:
            return (
                f"⚠️  Server Error: {self.service_name} service is currently unavailable.\n"
                f"   This is an internal error. Please contact support for assistance."
            )

    def get_log_message(self) -> str:
        """Get concise log message for connection failures"""
        return f"Connection failed - Service: {self.service_name}, Endpoint: {self.endpoint}, Address: {self.address}"


class ServiceTimeoutError(ServiceException):
    """Exception raised when service request times out"""

    def __init__(self, service_name: str, endpoint: str, timeout_seconds: int):
        self.endpoint = endpoint
        self.timeout_seconds = timeout_seconds

        message = f"{service_name} service timeout after {timeout_seconds}s"
        super().__init__(message, service_name)

    def get_log_message(self) -> str:
        """Get concise log message for timeout errors"""
        return f"Request timeout - Service: {self.service_name}, Endpoint: {self.endpoint}, Timeout: {self.timeout_seconds}s"


class ServiceResponseError(ServiceException):
    """Exception raised when service returns an error response"""

    def __init__(self, service_name: str, endpoint: str, status_code: int, error_message: str):
        self.endpoint = endpoint
        self.status_code = status_code
        self.error_message = error_message

        message = f"{service_name} service error: {status_code} - {error_message}"
        super().__init__(message, service_name)

    def get_log_message(self) -> str:
        """Get concise log message for response errors"""
        return f"HTTP {self.status_code} - Service: {self.service_name}, Endpoint: {self.endpoint}, Error: {self.error_message}"


class ServiceAuthorizationError(ServiceException):
    """Exception raised when service returns 403 Forbidden (missing or invalid authorization)"""

    def __init__(self, service_name: str, endpoint: str, error_message: str):
        self.endpoint = endpoint
        self.error_message = error_message

        message = f"Authorization failed for {service_name} service"
        super().__init__(message, service_name)

    def get_log_message(self) -> str:
        """Get concise log message for authorization errors"""
        return f"HTTP 403 - Service: {self.service_name}, Endpoint: {self.endpoint}, Error: {self.error_message}"

    def get_user_message(self) -> str:
        """Get user-friendly authorization error message"""
        return (
            "⚠️  Authorization Error: You don't have authorization to use this web service.\n"
            "   Please provide a valid authorization token or deploy the local version.\n"
            "   More info: https://docs.upskiller.xyz/docs/click-user/local-installation/"
        )
