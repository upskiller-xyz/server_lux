from typing import Callable, Optional, Dict, Any, Tuple, Type
from abc import ABC, abstractmethod
from flask import jsonify
from .enums import ErrorType, ErrorMessage, HTTPStatus, ResponseKey, ResponseStatus
from .maps import StandardMap
from .exceptions import (
    RequestValidationError,
    ServiceResponseError,
    ServiceAuthorizationError,
    ServiceConnectionError,
    ServiceTimeoutError,
)

# Upstream statuses whose body is our own services' input validation and is
# meaningful to the caller. Anything else (incl. 401/403: our service
# credentials, not the caller's) is summarised as a gateway error.
_PASS_THROUGH_STATUSES = frozenset({400, 404, 413, 422})


class IErrorResponseBuilder(ABC):

    @abstractmethod
    def build(self, error_type: Any, message: Optional[str] = None, status_code: Optional[int] = None) -> tuple:
        pass


class ErrorTypeMessageMap(StandardMap):
    _content: Dict[ErrorType, str] = {
        ErrorType.MISSING_AUTHORIZATION: ErrorMessage.MISSING_AUTHORIZATION.value,
        ErrorType.INVALID_AUTH_FORMAT: ErrorMessage.INVALID_AUTH_FORMAT.value,
        ErrorType.INVALID_TOKEN: ErrorMessage.INVALID_TOKEN.value,
        ErrorType.INVALID_JWT: ErrorMessage.INVALID_JWT.value,
        ErrorType.EXPIRED_JWT: ErrorMessage.EXPIRED_JWT.value,
        ErrorType.INSUFFICIENT_PERMISSIONS: ErrorMessage.INSUFFICIENT_PERMISSIONS.value,
        ErrorType.RATE_LIMIT_EXCEEDED: ErrorMessage.RATE_LIMIT_EXCEEDED.value,
        ErrorType.MISSING_JSON: ErrorMessage.MISSING_JSON.value,
        ErrorType.MISSING_FILE: ErrorMessage.MISSING_FILE.value,
    }
    _default: str = "An error occurred"


class ErrorTypeStatusMap(StandardMap):
    _content: Dict[ErrorType, int] = {
        ErrorType.MISSING_AUTHORIZATION: HTTPStatus.BAD_REQUEST.value,
        ErrorType.INVALID_AUTH_FORMAT: HTTPStatus.BAD_REQUEST.value,
        ErrorType.INVALID_TOKEN: HTTPStatus.FORBIDDEN.value,
        ErrorType.INVALID_JWT: HTTPStatus.FORBIDDEN.value,
        ErrorType.EXPIRED_JWT: HTTPStatus.FORBIDDEN.value,
        ErrorType.INSUFFICIENT_PERMISSIONS: HTTPStatus.FORBIDDEN.value,
        ErrorType.RATE_LIMIT_EXCEEDED: HTTPStatus.TOO_MANY_REQUESTS.value,
        ErrorType.MISSING_JSON: HTTPStatus.BAD_REQUEST.value,
        ErrorType.MISSING_FILE: HTTPStatus.BAD_REQUEST.value,
        ErrorType.VALIDATION_ERROR: HTTPStatus.BAD_REQUEST.value,
        ErrorType.INTERNAL_ERROR: HTTPStatus.INTERNAL_SERVER_ERROR.value,
    }
    _default: int = HTTPStatus.BAD_REQUEST.value


class ErrorResponseBuilder(IErrorResponseBuilder):

    def build(
        self,
        error_type: ErrorType,
        message: Optional[str] = None,
        status_code: Optional[int] = None
    ) -> Tuple[Any, int]:
        error_message = message or ErrorTypeMessageMap.get(error_type)
        http_status = status_code or ErrorTypeStatusMap.get(error_type)

        response_body = {
            ResponseKey.STATUS.value: ResponseStatus.ERROR.value,
            ResponseKey.ERROR.value: error_message,
            ResponseKey.ERROR_TYPE.value: error_type.value
        }

        return jsonify(response_body), http_status

    def build_from_exception(
        self,
        exception: Exception,
        default_status_code: int = HTTPStatus.INTERNAL_SERVER_ERROR.value
    ) -> Tuple[Any, int]:
        """Map an exception to a client-safe response.

        Only messages known to be client-facing (input validation) are echoed;
        internal details stay in the server log.
        """
        handler = self._handler_for(type(exception))
        if handler is None:
            return self._body(ErrorMessage.INTERNAL_ERROR.value, ErrorType.INTERNAL_ERROR), default_status_code
        return handler(exception)

    def _handler_for(self, exception_type: Type[BaseException]) -> Optional[Callable[[Any], Tuple[Any, int]]]:
        handlers: Dict[Type[BaseException], Callable[[Any], Tuple[Any, int]]] = {
            RequestValidationError: self._from_validation,
            ServiceResponseError: self._from_upstream_response,
            ServiceAuthorizationError: self._from_upstream_authorization,
            ServiceConnectionError: self._from_upstream_connection,
            ServiceTimeoutError: self._from_upstream_timeout,
        }
        # Most specific registered class wins (walk the MRO).
        for cls in exception_type.__mro__:
            if cls in handlers:
                return handlers[cls]
        return None

    @staticmethod
    def _body(message: str, error_type: ErrorType) -> Any:
        return jsonify({
            ResponseKey.STATUS.value: ResponseStatus.ERROR.value,
            ResponseKey.ERROR.value: message,
            ResponseKey.ERROR_TYPE.value: error_type.value
        })

    def _from_validation(self, exception: RequestValidationError) -> Tuple[Any, int]:
        return self._body(str(exception), ErrorType.VALIDATION_ERROR), HTTPStatus.BAD_REQUEST.value

    def _from_upstream_response(self, exception: ServiceResponseError) -> Tuple[Any, int]:
        if exception.status_code in _PASS_THROUGH_STATUSES:
            return self._body(exception.error_message, ErrorType.VALIDATION_ERROR), exception.status_code
        message = ErrorMessage.UPSTREAM_ERROR.value.format(service=exception.service_name)
        return self._body(message, ErrorType.INTERNAL_ERROR), HTTPStatus.BAD_GATEWAY.value

    def _from_upstream_authorization(self, exception: ServiceAuthorizationError) -> Tuple[Any, int]:
        # Our service-to-service credentials were refused — not the caller's token,
        # so never answer 403 (clients treat that as "log in again").
        message = ErrorMessage.UPSTREAM_UNAVAILABLE.value.format(service=exception.service_name)
        return self._body(message, ErrorType.INTERNAL_ERROR), HTTPStatus.BAD_GATEWAY.value

    def _from_upstream_connection(self, exception: ServiceConnectionError) -> Tuple[Any, int]:
        message = ErrorMessage.UPSTREAM_UNAVAILABLE.value.format(service=exception.service_name)
        return self._body(message, ErrorType.INTERNAL_ERROR), HTTPStatus.SERVICE_UNAVAILABLE.value

    def _from_upstream_timeout(self, exception: ServiceTimeoutError) -> Tuple[Any, int]:
        message = ErrorMessage.UPSTREAM_TIMEOUT.value.format(service=exception.service_name)
        return self._body(message, ErrorType.INTERNAL_ERROR), HTTPStatus.GATEWAY_TIMEOUT.value
