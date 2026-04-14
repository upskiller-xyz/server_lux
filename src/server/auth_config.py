import os
from typing import Optional
from dataclasses import dataclass
from .enums import AuthType


@dataclass(frozen=True)
class Auth0Config:
    """Auth0 configuration using dataclass for immutability"""

    domain: str
    audience: str
    algorithms: list[str]
    issuer: str

    @classmethod
    def from_environment(cls) -> 'Auth0Config':
        """Factory method to create Auth0Config from environment variables

        Returns:
            Auth0Config instance

        Raises:
            ValueError: If required environment variables are missing
        """
        domain = os.getenv('AUTH0_DOMAIN')
        audience = os.getenv('AUTH0_AUDIENCE')
        algorithms_str = os.getenv('AUTH0_ALGORITHMS', 'RS256')

        if not domain:
            raise ValueError("AUTH0_DOMAIN environment variable is required")
        if not audience:
            raise ValueError("AUTH0_AUDIENCE environment variable is required")

        algorithms = [alg.strip() for alg in algorithms_str.split(',')]
        issuer = f"https://{domain}/"

        return cls(
            domain=domain,
            audience=audience,
            algorithms=algorithms,
            issuer=issuer
        )

    @property
    def jwks_url(self) -> str:
        """Get the JWKS URL for token verification"""
        return f"https://{self.domain}/.well-known/jwks.json"


class AuthConfig:
    """Central authentication configuration using Strategy pattern"""

    def __init__(self):
        self._auth_type = self._determine_auth_type()
        self._token: Optional[str] = None
        self._auth0_config: Optional[Auth0Config] = None

        self._initialize_config()

    def _determine_auth_type(self) -> AuthType:
        """Determine authentication type from environment

        Returns:
            AuthType enum value
        """
        auth_type_str = os.getenv('AUTH_TYPE', 'token').lower()

        auth_type_map = {
            AuthType.TOKEN.value: AuthType.TOKEN,
            AuthType.AUTH0.value: AuthType.AUTH0,
            AuthType.NONE.value: AuthType.NONE,
        }

        return auth_type_map.get(auth_type_str, AuthType.TOKEN)

    def _initialize_config(self) -> None:
        """Initialize configuration based on auth type"""
        if self._auth_type == AuthType.TOKEN:
            self._token = os.getenv('API_TOKEN')
        elif self._auth_type == AuthType.AUTH0:
            try:
                self._auth0_config = Auth0Config.from_environment()
            except ValueError as e:
                raise ValueError(f"Auth0 configuration error: {e}")

    @property
    def auth_type(self) -> AuthType:
        """Get the configured authentication type"""
        return self._auth_type

    @property
    def token(self) -> Optional[str]:
        """Get the API token (for token-based auth)"""
        return self._token

    @property
    def auth0_config(self) -> Optional[Auth0Config]:
        """Get Auth0 configuration (for Auth0-based auth)"""
        return self._auth0_config

    @property
    def is_auth_enabled(self) -> bool:
        """Check if any authentication is enabled"""
        return self._auth_type != AuthType.NONE
