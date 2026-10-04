from abc import ABC
from enum import Enum
from typing import Optional


class ExcMsg(Enum):
    """Named templates for the exception messages raised in this module.

    Filled with ``.format()`` so the wording lives here rather than inline at
    every raise site, and so the same text can be asserted on in tests.
    """

    CONNECTION = "Failed to connect to {service} service at {address}"
    CONNECTION_LOG = (
        "Connection failed - Service: {service}, Endpoint: {endpoint}, Address: {address}"
    )
    CONNECTION_USER_LOCAL = (
        "⚠️  Connection failed: {service} service at {address} is not responding.\n"
        "   Please restart the {service} service and try again."
    )
    CONNECTION_USER_REMOTE = (
        "⚠️  Server Error: {service} service is currently unavailable.\n"
        "   This is an internal error. Please contact support for assistance."
    )
    TIMEOUT = "{service} service timeout after {timeout}s"
    TIMEOUT_LOG = (
        "Request timeout - Service: {service}, Endpoint: {endpoint}, Timeout: {timeout}s"
    )
    RESPONSE = "{service} service error: {status} - {error}"
    RESPONSE_LOG = (
        "HTTP {status} - Service: {service}, Endpoint: {endpoint}, Error: {error}"
    )
    MODAL_CREDENTIALS = (
        "Modal proxy-auth credentials missing: {missing}. Set these environment "
        "variables to call a Modal-hosted service."
    )
    MODAL_CREDENTIALS_LOG = "Modal credentials missing: {missing}"
    SCALEWAY_CREDENTIALS = (
        "Scaleway serverless auth token missing: {missing}. Set this environment "
        "variable to call a private Scaleway serverless service."
    )
    SCALEWAY_CREDENTIALS_LOG = "Scaleway credentials missing: {missing}"
    MERGE_VALIDATION_LOG = "Merge input validation failed: {message}"
    AUTHORIZATION = "Authorization failed for {service} service"
    AUTHORIZATION_LOG = (
        "HTTP 403 - Service: {service}, Endpoint: {endpoint}, Error: {error}"
    )
    AUTHORIZATION_USER = (
        "⚠️  Authorization Error: You don't have authorization to use this web service.\n"
        "   Please provide a valid authorization token or deploy the local version.\n"
        "   More info: https://docs.upskiller.xyz/docs/click-user/local-installation/"
    )

    MISSING_SEPARATOR = ", "


class RequestValidationError(ValueError):
    """Invalid client input. Its message is safe to return to the caller."""


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

        message = ExcMsg.CONNECTION.value.format(service=service_name, address=address)
        super().__init__(message, service_name)

    def get_user_message(self, is_local: bool = False) -> str:
        """Get user-friendly error message"""
        if is_local:
            return ExcMsg.CONNECTION_USER_LOCAL.value.format(
                service=self.service_name, address=self.address
            )
        return ExcMsg.CONNECTION_USER_REMOTE.value.format(service=self.service_name)

    def get_log_message(self) -> str:
        """Get concise log message for connection failures"""
        return ExcMsg.CONNECTION_LOG.value.format(
            service=self.service_name, endpoint=self.endpoint, address=self.address
        )


class ServiceTimeoutError(ServiceException):
    """Exception raised when service request times out"""

    def __init__(self, service_name: str, endpoint: str, timeout_seconds: int):
        self.endpoint = endpoint
        self.timeout_seconds = timeout_seconds

        message = ExcMsg.TIMEOUT.value.format(service=service_name, timeout=timeout_seconds)
        super().__init__(message, service_name)

    def get_log_message(self) -> str:
        """Get concise log message for timeout errors"""
        return ExcMsg.TIMEOUT_LOG.value.format(
            service=self.service_name, endpoint=self.endpoint, timeout=self.timeout_seconds
        )


class ServiceResponseError(ServiceException):
    """Exception raised when service returns an error response"""

    def __init__(self, service_name: str, endpoint: str, status_code: int, error_message: str):
        self.endpoint = endpoint
        self.status_code = status_code
        self.error_message = error_message

        message = ExcMsg.RESPONSE.value.format(
            service=service_name, status=status_code, error=error_message
        )
        super().__init__(message, service_name)

    def get_log_message(self) -> str:
        """Get concise log message for response errors"""
        return ExcMsg.RESPONSE_LOG.value.format(
            status=self.status_code,
            service=self.service_name,
            endpoint=self.endpoint,
            error=self.error_message,
        )


class ModalCredentialsError(ServiceException):
    """Exception raised when a service URL is Modal-hosted but proxy-auth
    credentials (MODAL_KEY / MODAL_SECRET) are not configured."""

    def __init__(self, missing: list[str]):
        self.missing = missing

        message = ExcMsg.MODAL_CREDENTIALS.value.format(
            missing=ExcMsg.MISSING_SEPARATOR.value.join(missing)
        )
        super().__init__(message)

    def get_log_message(self) -> str:
        """Get concise log message for missing Modal credentials"""
        return ExcMsg.MODAL_CREDENTIALS_LOG.value.format(
            missing=ExcMsg.MISSING_SEPARATOR.value.join(self.missing)
        )


class ScalewayCredentialsError(ServiceException):
    """Exception raised when a service URL is a private Scaleway serverless
    endpoint but its per-service auth token (e.g. OBSTRUCTION_TOKEN) is not
    configured."""

    def __init__(self, missing: list[str]):
        self.missing = missing

        message = ExcMsg.SCALEWAY_CREDENTIALS.value.format(
            missing=ExcMsg.MISSING_SEPARATOR.value.join(missing)
        )
        super().__init__(message)

    def get_log_message(self) -> str:
        """Get concise log message for missing Scaleway credentials"""
        return ExcMsg.SCALEWAY_CREDENTIALS_LOG.value.format(
            missing=ExcMsg.MISSING_SEPARATOR.value.join(self.missing)
        )


class MergeValidationError(ServiceException):
    """Exception raised when the per-window data assembled for the merge step is
    inconsistent (e.g. a window is missing its simulation, or a mask has an
    unexpected shape such as a 4-channel encoder image instead of a 2D mask).

    Indicates corrupted intermediate state (e.g. from a concurrency defect) -
    we fail loudly instead of silently producing a wrong daylight field.
    """

    def __init__(self, message: str):
        super().__init__(message, service_name="main")

    def get_log_message(self) -> str:
        return ExcMsg.MERGE_VALIDATION_LOG.value.format(message=self.message)


class ServiceAuthorizationError(ServiceException):
    """Exception raised when service returns 403 Forbidden (missing or invalid authorization)"""

    def __init__(self, service_name: str, endpoint: str, error_message: str):
        self.endpoint = endpoint
        self.error_message = error_message

        message = ExcMsg.AUTHORIZATION.value.format(service=service_name)
        super().__init__(message, service_name)

    def get_log_message(self) -> str:
        """Get concise log message for authorization errors"""
        return ExcMsg.AUTHORIZATION_LOG.value.format(
            service=self.service_name, endpoint=self.endpoint, error=self.error_message
        )

    def get_user_message(self) -> str:
        """Get user-friendly authorization error message"""
        return ExcMsg.AUTHORIZATION_USER.value
