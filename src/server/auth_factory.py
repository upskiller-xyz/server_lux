from typing import Dict, Type
from .enums import AuthType
from .auth_config import AuthConfig
from .auth_strategies import (
    AuthenticationStrategy,
    TokenAuthenticationStrategy,
    Auth0AuthenticationStrategy,
    NoAuthenticationStrategy
)


class AuthenticationStrategyFactory:
    """Factory for creating authentication strategies using Factory pattern"""

    def __init__(self):
        self._strategy_map: Dict[AuthType, Type[AuthenticationStrategy]] = {
            AuthType.TOKEN: TokenAuthenticationStrategy,
            AuthType.AUTH0: Auth0AuthenticationStrategy,
            AuthType.NONE: NoAuthenticationStrategy,
        }

    def create_strategy(self, config: AuthConfig) -> AuthenticationStrategy:
        """Create authentication strategy based on configuration

        Args:
            config: Authentication configuration

        Returns:
            AuthenticationStrategy instance

        Raises:
            ValueError: If auth type is not supported
        """
        auth_type = config.auth_type
        strategy_class = self._strategy_map.get(auth_type)

        if strategy_class is None:
            raise ValueError(f"Unsupported authentication type: {auth_type}")

        # Use Strategy pattern to instantiate appropriate strategy
        if auth_type == AuthType.TOKEN:
            return strategy_class(config.token)
        elif auth_type == AuthType.AUTH0:
            if config.auth0_config is None:
                raise ValueError("Auth0 configuration is missing")
            return strategy_class(config.auth0_config)
        elif auth_type == AuthType.NONE:
            return strategy_class()

        raise ValueError(f"Unable to create strategy for auth type: {auth_type}")
