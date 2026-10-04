import os
from dataclasses import dataclass
from typing import Optional

from .enums import AuthType, JwtAlgorithm
from .env_keys import EnvKey


class Auth0UrlBuilder:
    """Builds the Auth0 URLs derived from the tenant domain."""
    ISSUER: str = "https://{domain}/"
    JWKS: str = "https://{domain}/.well-known/jwks.json"

    @classmethod
    def issuer(cls, domain: str) -> str:
        return cls.ISSUER.format(domain=domain)

    @classmethod
    def jwks(cls, domain: str) -> str:
        return cls.JWKS.format(domain=domain)


class AuthConfigError:
    """Templates for the configuration errors raised in this module."""
    ASYMMETRIC_ONLY: str = (
        "AUTH0_ALGORITHMS must list asymmetric algorithms only ({allowed}); rejected: {rejected}"
    )
    UNSUPPORTED_AUTH_TYPE: str = "Unsupported AUTH_TYPE '{actual}'; expected one of {expected}"
    AUTH0_CONFIG: str = "Auth0 configuration error: {error}"
    ALGORITHM_SEPARATOR: str = ", "


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
        domain = os.getenv(EnvKey.AUTH0_DOMAIN.value)
        audience = os.getenv(EnvKey.AUTH0_AUDIENCE.value)
        algorithms_str = os.getenv(EnvKey.AUTH0_ALGORITHMS.value, JwtAlgorithm.RS256.value)

        if not domain:
            raise ValueError("AUTH0_DOMAIN environment variable is required")
        if not audience:
            raise ValueError("AUTH0_AUDIENCE environment variable is required")

        algorithms = cls._parse_algorithms(algorithms_str)
        issuer = Auth0UrlBuilder.issuer(domain)

        return cls(
            domain=domain,
            audience=audience,
            algorithms=algorithms,
            issuer=issuer
        )

    @staticmethod
    def _parse_algorithms(algorithms_str: str) -> list[str]:
        """Parse AUTH0_ALGORITHMS, accepting only asymmetric algorithms.

        Raises:
            ValueError: If the list is empty or names a non-asymmetric algorithm
        """
        algorithms = [alg.strip() for alg in algorithms_str.split(',') if alg.strip()]
        allowed = {alg.value for alg in JwtAlgorithm}
        rejected = [alg for alg in algorithms if alg not in allowed]
        if not algorithms or rejected:
            raise ValueError(
                AuthConfigError.ASYMMETRIC_ONLY.format(
                    allowed=AuthConfigError.ALGORITHM_SEPARATOR.join(
                        a.value for a in JwtAlgorithm
                    ),
                    rejected=rejected,
                )
            )
        return algorithms

    @property
    def jwks_url(self) -> str:
        """Get the JWKS URL for token verification"""
        return Auth0UrlBuilder.jwks(self.domain)


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
        auth_type_str = os.getenv(EnvKey.AUTH_TYPE.value, AuthType.TOKEN.value).strip().lower()

        auth_type_map = {auth_type.value: auth_type for auth_type in AuthType}

        auth_type = auth_type_map.get(auth_type_str)
        if auth_type is None:
            # Fail closed: a typo must not silently pick a weaker mode.
            raise ValueError(
                AuthConfigError.UNSUPPORTED_AUTH_TYPE.format(
                    actual=auth_type_str, expected=sorted(auth_type_map)
                )
            )
        return auth_type

    def _initialize_config(self) -> None:
        """Initialize configuration based on auth type"""
        if self._auth_type == AuthType.TOKEN:
            self._token = os.getenv(EnvKey.API_TOKEN.value)
            if not self._token:
                # Fail closed: token auth without a token would accept any bearer.
                raise ValueError("AUTH_TYPE=token requires a non-empty API_TOKEN")
        elif self._auth_type == AuthType.AUTH0:
            try:
                self._auth0_config = Auth0Config.from_environment()
            except ValueError as e:
                raise ValueError(AuthConfigError.AUTH0_CONFIG.format(error=e))

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
