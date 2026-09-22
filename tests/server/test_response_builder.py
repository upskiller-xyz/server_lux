"""Unit tests for the error-response status mapping"""

import pytest
from src.server.enums import ErrorType, HTTPStatus
from src.server.response_builder import ErrorResponseBuilder, ErrorTypeStatusMap


class TestAuthErrorStatusCodes:
    """Authentication failures must not be reported as malformed requests.

    A client can only tell "sign in again" apart from "your payload is wrong"
    by the status code: web-daylight-tool maps 401/403 to its AuthRequiredError
    and shows a localised login prompt. While a missing header answered 400,
    the user was shown the raw backend message instead.
    """

    @pytest.mark.parametrize(
        "error_type",
        [ErrorType.MISSING_AUTHORIZATION, ErrorType.INVALID_AUTH_FORMAT],
    )
    def test_missing_or_malformed_header_is_unauthorized(self, error_type):
        # Arrange / Act
        status = ErrorTypeStatusMap.get(error_type)

        # Assert
        assert status == HTTPStatus.UNAUTHORIZED.value

    @pytest.mark.parametrize(
        "error_type",
        [
            ErrorType.INVALID_TOKEN,
            ErrorType.INVALID_JWT,
            ErrorType.EXPIRED_JWT,
            ErrorType.INSUFFICIENT_PERMISSIONS,
        ],
    )
    def test_rejected_credentials_stay_forbidden(self, error_type):
        # Arrange / Act
        status = ErrorTypeStatusMap.get(error_type)

        # Assert
        assert status == HTTPStatus.FORBIDDEN.value

    def test_payload_errors_stay_bad_request(self):
        # Arrange / Act
        status = ErrorTypeStatusMap.get(ErrorType.MISSING_JSON)

        # Assert
        assert status == HTTPStatus.BAD_REQUEST.value


class TestErrorResponseBuilder:

    def test_builds_the_mapped_status_for_a_missing_header(self, app_context):
        # Arrange
        builder = ErrorResponseBuilder()

        # Act
        _, status = builder.build(ErrorType.MISSING_AUTHORIZATION)

        # Assert
        assert status == HTTPStatus.UNAUTHORIZED.value

    def test_an_explicit_status_still_wins(self, app_context):
        # Arrange
        builder = ErrorResponseBuilder()

        # Act
        _, status = builder.build(ErrorType.MISSING_AUTHORIZATION, status_code=418)

        # Assert
        assert status == 418


@pytest.fixture
def app_context():
    """`ErrorResponseBuilder.build` calls `jsonify`, which needs an app context."""
    from flask import Flask

    with Flask(__name__).app_context():
        yield
