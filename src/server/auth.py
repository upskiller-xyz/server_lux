import os
from functools import wraps
from typing import Callable, Any
from flask import request
from .enums import ErrorType
from .response_builder import ErrorResponseBuilder


class TokenAuthenticator:

    def __init__(self, token_env_var: str = "API_TOKEN"):
        self._token_env_var = token_env_var
        self._token = os.getenv(token_env_var)
        self._error_builder = ErrorResponseBuilder()

    @property
    def is_configured(self) -> bool:
        return self._token is not None and len(self._token) > 0

    def validate_token(self, provided_token: str) -> bool:
        if not self.is_configured:
            return True
        return provided_token == self._token

    def require_token(self, f: Callable) -> Callable:
        @wraps(f)
        def decorated_function(*args: Any, **kwargs: Any) -> Any:
            auth_header = request.headers.get('Authorization')

            if not auth_header:
                return self._error_builder.build(ErrorType.MISSING_AUTHORIZATION)

            parts = auth_header.split()
            if len(parts) != 2 or parts[0].lower() != 'bearer':
                return self._error_builder.build(ErrorType.INVALID_AUTH_FORMAT)

            token = parts[1]

            if not self.validate_token(token):
                return self._error_builder.build(ErrorType.INVALID_TOKEN)

            return f(*args, **kwargs)

        return decorated_function
