from abc import ABC, abstractmethod
from typing import Callable, Any, Optional
from functools import wraps
from flask import request
import requests
from jose import jwt, JWTError
from .enums import ErrorType, AuthType
from .response_builder import ErrorResponseBuilder
from .auth_config import AuthConfig, Auth0Config


class AuthenticationStrategy(ABC):
    """Abstract base class for authentication strategies using Adapter pattern"""

    def __init__(self):
        self._error_builder = ErrorResponseBuilder()

    @abstractmethod
    def validate_request(self, auth_header: Optional[str]) -> tuple[bool, Optional[ErrorType]]:
        """Validate the authentication header

        Args:
            auth_header: Authorization header value

        Returns:
            Tuple of (is_valid, error_type)
        """
        pass

    @abstractmethod
    def is_configured(self) -> bool:
        """Check if authentication is properly configured"""
        pass

    def require_auth(self, f: Callable) -> Callable:
        """Decorator to require authentication for a route

        Args:
            f: The route function to protect

        Returns:
            Decorated function with authentication
        """
        @wraps(f)
        def decorated_function(*args: Any, **kwargs: Any) -> Any:
            auth_header = request.headers.get('Authorization')

            if not auth_header:
                return self._error_builder.build(ErrorType.MISSING_AUTHORIZATION)

            is_valid, error_type = self.validate_request(auth_header)

            if not is_valid:
                return self._error_builder.build(error_type)

            return f(*args, **kwargs)

        return decorated_function


class TokenAuthenticationStrategy(AuthenticationStrategy):
    """Token-based authentication strategy"""

    def __init__(self, token: Optional[str]):
        super().__init__()
        self._token = token

    def is_configured(self) -> bool:
        """Check if token authentication is configured"""
        return self._token is not None and len(self._token) > 0

    def validate_request(self, auth_header: Optional[str]) -> tuple[bool, Optional[ErrorType]]:
        """Validate token-based authentication

        Args:
            auth_header: Authorization header value

        Returns:
            Tuple of (is_valid, error_type)
        """
        if not auth_header:
            return False, ErrorType.MISSING_AUTHORIZATION

        parts = auth_header.split()
        if len(parts) != 2 or parts[0].lower() != 'bearer':
            return False, ErrorType.INVALID_AUTH_FORMAT

        token = parts[1]

        if not self.is_configured():
            # If no token is configured, allow all requests
            return True, None

        if token == self._token:
            return True, None

        return False, ErrorType.INVALID_TOKEN


class Auth0AuthenticationStrategy(AuthenticationStrategy):
    """Auth0 JWT-based authentication strategy using Adapter pattern"""

    def __init__(self, config: Auth0Config):
        super().__init__()
        self._config = config
        self._jwks_cache: Optional[dict] = None

    def is_configured(self) -> bool:
        """Check if Auth0 is properly configured"""
        return self._config is not None

    def _get_jwks(self) -> dict:
        """Fetch JWKS from Auth0 (cached)

        Returns:
            JWKS dictionary

        Raises:
            RuntimeError: If JWKS cannot be fetched
        """
        if self._jwks_cache is None:
            try:
                response = requests.get(self._config.jwks_url, timeout=10)
                response.raise_for_status()
                self._jwks_cache = response.json()
            except requests.RequestException as e:
                raise RuntimeError(f"Failed to fetch JWKS: {e}")

        return self._jwks_cache

    def _get_signing_key(self, token: str) -> str:
        """Get the signing key for token verification

        Args:
            token: JWT token

        Returns:
            Signing key

        Raises:
            ValueError: If signing key cannot be found
        """
        try:
            unverified_header = jwt.get_unverified_header(token)
        except JWTError as e:
            raise ValueError(f"Invalid token header: {e}")

        jwks = self._get_jwks()

        # Find the key with matching kid
        kid = unverified_header.get('kid')
        for key in jwks.get('keys', []):
            if key.get('kid') == kid:
                return key

        raise ValueError(f"Unable to find signing key for kid: {kid}")

    def validate_request(self, auth_header: Optional[str]) -> tuple[bool, Optional[ErrorType]]:
        """Validate Auth0 JWT token

        Args:
            auth_header: Authorization header value

        Returns:
            Tuple of (is_valid, error_type)
        """
        if not auth_header:
            return False, ErrorType.MISSING_AUTHORIZATION

        parts = auth_header.split()
        if len(parts) != 2 or parts[0].lower() != 'bearer':
            return False, ErrorType.INVALID_AUTH_FORMAT

        token = parts[1]

        try:
            signing_key = self._get_signing_key(token)

            # Verify and decode the token
            payload = jwt.decode(
                token,
                signing_key,
                algorithms=self._config.algorithms,
                audience=self._config.audience,
                issuer=self._config.issuer
            )

            # Token is valid
            return True, None

        except jwt.ExpiredSignatureError:
            return False, ErrorType.EXPIRED_JWT
        except jwt.JWTClaimsError:
            return False, ErrorType.INVALID_JWT
        except Exception:
            return False, ErrorType.INVALID_JWT


class NoAuthenticationStrategy(AuthenticationStrategy):
    """No authentication strategy (allows all requests)"""

    def is_configured(self) -> bool:
        """Always returns True as no configuration is needed"""
        return True

    def validate_request(self, auth_header: Optional[str]) -> tuple[bool, Optional[ErrorType]]:
        """Always returns valid (no authentication)

        Args:
            auth_header: Authorization header value (ignored)

        Returns:
            Tuple of (True, None)
        """
        return True, None
