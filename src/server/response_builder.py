from typing import Optional, Dict, Any, Tuple
from abc import ABC, abstractmethod
from flask import jsonify
from .enums import ErrorType, ErrorMessage, HTTPStatus, ResponseKey, ResponseStatus
from .maps import StandardMap
from .exceptions import ServiceException, ServiceResponseError, ServiceAuthorizationError, ServiceConnectionError, ServiceTimeoutError


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
        if isinstance(exception, ServiceResponseError):
            # Determine error type based on status code
            error_type = (
                ErrorType.VALIDATION_ERROR
                if exception.status_code == HTTPStatus.BAD_REQUEST.value
                else ErrorType.INTERNAL_ERROR
            )

            response_body = {
                ResponseKey.STATUS.value: ResponseStatus.ERROR.value,
                ResponseKey.ERROR.value: exception.error_message,
                ResponseKey.ERROR_TYPE.value: error_type.value
            }
            return jsonify(response_body), exception.status_code

        elif isinstance(exception, ServiceAuthorizationError):
            response_body = {
                ResponseKey.STATUS.value: ResponseStatus.ERROR.value,
                ResponseKey.ERROR.value: exception.error_message,
                ResponseKey.ERROR_TYPE.value: ErrorType.INVALID_TOKEN.value
            }
            return jsonify(response_body), HTTPStatus.FORBIDDEN.value

        elif isinstance(exception, ServiceConnectionError):
            response_body = {
                ResponseKey.STATUS.value: ResponseStatus.ERROR.value,
                ResponseKey.ERROR.value: f"{exception.service_name} service unavailable",
                ResponseKey.ERROR_TYPE.value: ErrorType.INTERNAL_ERROR.value
            }
            return jsonify(response_body), HTTPStatus.SERVICE_UNAVAILABLE.value

        elif isinstance(exception, ServiceTimeoutError):
            response_body = {
                ResponseKey.STATUS.value: ResponseStatus.ERROR.value,
                ResponseKey.ERROR.value: f"{exception.service_name} service timeout",
                ResponseKey.ERROR_TYPE.value: ErrorType.INTERNAL_ERROR.value
            }
            return jsonify(response_body), HTTPStatus.GATEWAY_TIMEOUT.value

        elif isinstance(exception, ServiceException):
            response_body = {
                ResponseKey.STATUS.value: ResponseStatus.ERROR.value,
                ResponseKey.ERROR.value: str(exception),
                ResponseKey.ERROR_TYPE.value: ErrorType.INTERNAL_ERROR.value
            }
            return jsonify(response_body), default_status_code

        else:
            response_body = {
                ResponseKey.STATUS.value: ResponseStatus.ERROR.value,
                ResponseKey.ERROR.value: str(exception),
                ResponseKey.ERROR_TYPE.value: ErrorType.INTERNAL_ERROR.value
            }
            return jsonify(response_body), default_status_code
