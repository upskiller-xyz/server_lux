import os
from functools import wraps
from typing import Callable, Any
from flask import request
from .enums import ErrorType
from .response_builder import ErrorResponseBuilder
from .auth_config import AuthConfig
from .auth_factory import AuthenticationStrategyFactory
from .auth_strategies import AuthenticationStrategy


class Authenticator:
    """Main authenticator class using Strategy and Factory patterns

    This class provides a unified interface for authentication regardless
    of the underlying strategy (Token, Auth0, or None).
    """

    def __init__(self, config: AuthConfig = None):
        """Initialize authenticator with configuration

        Args:
            config: Authentication configuration. If None, creates from environment
        """
        self._config = config or AuthConfig()
        self._factory = AuthenticationStrategyFactory()
        self._strategy: AuthenticationStrategy = self._factory.create_strategy(self._config)
        self._error_builder = ErrorResponseBuilder()

    @property
    def is_configured(self) -> bool:
        """Check if authentication is properly configured"""
        return self._strategy.is_configured()

    @property
    def strategy(self) -> AuthenticationStrategy:
        """Get the current authentication strategy"""
        return self._strategy

    def require_auth(self, f: Callable) -> Callable:
        """Decorator to require authentication for a route

        Args:
            f: The route function to protect

        Returns:
            Decorated function with authentication
        """
        return self._strategy.require_auth(f)


# Backward compatibility alias
class TokenAuthenticator(Authenticator):
    """Backward compatibility class for TokenAuthenticator

    This maintains the same interface as the old TokenAuthenticator
    while using the new Strategy pattern implementation.
    """

    def __init__(self, token_env_var: str = "API_TOKEN"):
        # Force token-based authentication
        os.environ['AUTH_TYPE'] = 'token'
        super().__init__()

    def validate_token(self, provided_token: str) -> bool:
        """Validate a token (backward compatibility method)

        Args:
            provided_token: Token to validate

        Returns:
            True if valid, False otherwise
        """
        auth_header = f"Bearer {provided_token}"
        is_valid, _ = self._strategy.validate_request(auth_header)
        return is_valid

    def require_token(self, f: Callable) -> Callable:
        """Decorator to require token authentication (backward compatibility)

        Args:
            f: The route function to protect

        Returns:
            Decorated function with authentication
        """
        return self.require_auth(f)
