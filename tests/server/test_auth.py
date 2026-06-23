"""Unit tests for authentication system"""

import os
import time
import json
import pytest
from unittest.mock import Mock, patch, MagicMock
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.backends import default_backend
from jose import jwt
from jose.utils import base64url_encode
import struct
from src.server.enums import AuthType, ErrorType
from src.server.auth_config import AuthConfig, Auth0Config
from src.server.auth_strategies import (
    TokenAuthenticationStrategy,
    Auth0AuthenticationStrategy,
    NoAuthenticationStrategy
)
from src.server.auth_factory import AuthenticationStrategyFactory
from src.server.auth import Authenticator, TokenAuthenticator


def _generate_rsa_key_pair():
    """Generate an RSA key pair for test JWT signing."""
    private_key = rsa.generate_private_key(
        public_exponent=65537,
        key_size=2048,
        backend=default_backend()
    )
    return private_key, private_key.public_key()


def _public_key_to_jwk(public_key, kid: str = "test-key-id") -> dict:
    """Convert RSA public key to JWK dict for mocking JWKS endpoint."""
    pub_numbers = public_key.public_numbers()

    def _int_to_base64url(n: int) -> str:
        byte_length = (n.bit_length() + 7) // 8
        n_bytes = n.to_bytes(byte_length, byteorder='big')
        return base64url_encode(n_bytes).decode('ascii')

    return {
        "kty": "RSA",
        "use": "sig",
        "alg": "RS256",
        "kid": kid,
        "n": _int_to_base64url(pub_numbers.n),
        "e": _int_to_base64url(pub_numbers.e),
    }


def _make_jwt(
    private_key,
    audience: str,
    issuer: str,
    kid: str = "test-key-id",
    exp_offset: int = 3600,
) -> str:
    """Sign a test JWT with the given RSA private key."""
    now = int(time.time())
    payload = {
        "sub": "test-user",
        "aud": audience,
        "iss": issuer,
        "iat": now,
        "exp": now + exp_offset,
    }
    headers = {"kid": kid}
    return jwt.encode(payload, private_key, algorithm="RS256", headers=headers)


class TestAuth0Config:
    """Tests for Auth0Config"""

    def test_from_environment_success(self):
        """Test Auth0Config creation from environment variables"""
        with patch.dict(os.environ, {
            'AUTH0_DOMAIN': 'test.auth0.com',
            'AUTH0_AUDIENCE': 'https://api.test.com',
            'AUTH0_ALGORITHMS': 'RS256'
        }):
            config = Auth0Config.from_environment()
            assert config.domain == 'test.auth0.com'
            assert config.audience == 'https://api.test.com'
            assert config.algorithms == ['RS256']
            assert config.issuer == 'https://test.auth0.com/'

    def test_from_environment_missing_domain(self):
        """Test Auth0Config fails when domain is missing"""
        with patch.dict(os.environ, {
            'AUTH0_AUDIENCE': 'https://api.test.com'
        }, clear=True):
            with pytest.raises(ValueError, match="AUTH0_DOMAIN"):
                Auth0Config.from_environment()

    def test_from_environment_multiple_algorithms(self):
        """Test Auth0Config with multiple algorithms"""
        with patch.dict(os.environ, {
            'AUTH0_DOMAIN': 'test.auth0.com',
            'AUTH0_AUDIENCE': 'https://api.test.com',
            'AUTH0_ALGORITHMS': 'RS256,HS256'
        }):
            config = Auth0Config.from_environment()
            assert config.algorithms == ['RS256', 'HS256']

    def test_jwks_url_property(self):
        """Test JWKS URL generation"""
        config = Auth0Config(
            domain='test.auth0.com',
            audience='https://api.test.com',
            algorithms=['RS256'],
            issuer='https://test.auth0.com/'
        )
        assert config.jwks_url == 'https://test.auth0.com/.well-known/jwks.json'


class TestAuthConfig:
    """Tests for AuthConfig"""

    def test_default_auth_type_is_token(self):
        """Test that default auth type is token"""
        with patch.dict(os.environ, {}, clear=True):
            config = AuthConfig()
            assert config.auth_type == AuthType.TOKEN

    def test_token_auth_type(self):
        """Test token authentication configuration"""
        with patch.dict(os.environ, {
            'AUTH_TYPE': 'token',
            'API_TOKEN': 'test_token'
        }):
            config = AuthConfig()
            assert config.auth_type == AuthType.TOKEN
            assert config.token == 'test_token'
            assert config.is_auth_enabled is True

    def test_auth0_auth_type(self):
        """Test Auth0 authentication configuration"""
        with patch.dict(os.environ, {
            'AUTH_TYPE': 'auth0',
            'AUTH0_DOMAIN': 'test.auth0.com',
            'AUTH0_AUDIENCE': 'https://api.test.com'
        }):
            config = AuthConfig()
            assert config.auth_type == AuthType.AUTH0
            assert config.auth0_config is not None
            assert config.auth0_config.domain == 'test.auth0.com'

    def test_none_auth_type(self):
        """Test no authentication configuration"""
        with patch.dict(os.environ, {'AUTH_TYPE': 'none'}, clear=True):
            config = AuthConfig()
            assert config.auth_type == AuthType.NONE
            assert config.is_auth_enabled is False


class TestTokenAuthenticationStrategy:
    """Tests for TokenAuthenticationStrategy"""

    def test_is_configured_with_token(self):
        """Test is_configured returns True when token is set"""
        strategy = TokenAuthenticationStrategy('test_token')
        assert strategy.is_configured() is True

    def test_is_configured_without_token(self):
        """Test is_configured returns False when token is None"""
        strategy = TokenAuthenticationStrategy(None)
        assert strategy.is_configured() is False

    def test_validate_request_success(self):
        """Test successful token validation"""
        strategy = TokenAuthenticationStrategy('test_token')
        is_valid, error = strategy.validate_request('Bearer test_token')
        assert is_valid is True
        assert error is None

    def test_validate_request_invalid_token(self):
        """Test invalid token validation"""
        strategy = TokenAuthenticationStrategy('test_token')
        is_valid, error = strategy.validate_request('Bearer wrong_token')
        assert is_valid is False
        assert error == ErrorType.INVALID_TOKEN

    def test_validate_request_missing_header(self):
        """Test validation with missing auth header"""
        strategy = TokenAuthenticationStrategy('test_token')
        is_valid, error = strategy.validate_request(None)
        assert is_valid is False
        assert error == ErrorType.MISSING_AUTHORIZATION

    def test_validate_request_invalid_format(self):
        """Test validation with invalid header format"""
        strategy = TokenAuthenticationStrategy('test_token')
        is_valid, error = strategy.validate_request('InvalidFormat test_token')
        assert is_valid is False
        assert error == ErrorType.INVALID_AUTH_FORMAT

    def test_validate_request_no_token_configured(self):
        """Test validation allows all when no token is configured"""
        strategy = TokenAuthenticationStrategy(None)
        is_valid, error = strategy.validate_request('Bearer any_token')
        assert is_valid is True
        assert error is None


class TestAuth0AuthenticationStrategy:
    """Tests for Auth0AuthenticationStrategy"""

    @pytest.fixture
    def auth0_config(self):
        return Auth0Config(
            domain='test.auth0.com',
            audience='https://api.test.com',
            algorithms=['RS256'],
            issuer='https://test.auth0.com/'
        )

    @pytest.fixture
    def rsa_key_pair(self):
        return _generate_rsa_key_pair()

    @pytest.fixture
    def strategy_with_jwks(self, auth0_config, rsa_key_pair):
        """Auth0 strategy with mocked JWKS (no network calls)."""
        private_key, public_key = rsa_key_pair
        jwk = _public_key_to_jwk(public_key)
        jwks = {"keys": [jwk]}
        strategy = Auth0AuthenticationStrategy(auth0_config)
        strategy._jwks_cache = jwks
        return strategy, private_key

    def test_is_configured(self, auth0_config):
        strategy = Auth0AuthenticationStrategy(auth0_config)
        assert strategy.is_configured() is True

    def test_validate_request_missing_header(self, auth0_config):
        strategy = Auth0AuthenticationStrategy(auth0_config)
        is_valid, error = strategy.validate_request(None)
        assert is_valid is False
        assert error == ErrorType.MISSING_AUTHORIZATION

    def test_validate_request_invalid_format(self, auth0_config):
        strategy = Auth0AuthenticationStrategy(auth0_config)
        is_valid, error = strategy.validate_request('InvalidFormat token')
        assert is_valid is False
        assert error == ErrorType.INVALID_AUTH_FORMAT

    def test_validate_request_valid_jwt(self, strategy_with_jwks, auth0_config):
        """Valid JWT signed with matching key is accepted."""
        strategy, private_key = strategy_with_jwks
        token = _make_jwt(private_key, auth0_config.audience, auth0_config.issuer)
        is_valid, error = strategy.validate_request(f'Bearer {token}')
        assert is_valid is True
        assert error is None

    def test_validate_request_expired_jwt(self, strategy_with_jwks, auth0_config):
        """Expired JWT is rejected with EXPIRED_JWT error."""
        strategy, private_key = strategy_with_jwks
        token = _make_jwt(private_key, auth0_config.audience, auth0_config.issuer, exp_offset=-3600)
        is_valid, error = strategy.validate_request(f'Bearer {token}')
        assert is_valid is False
        assert error == ErrorType.EXPIRED_JWT

    def test_validate_request_wrong_audience(self, strategy_with_jwks, auth0_config):
        """JWT with wrong audience is rejected."""
        strategy, private_key = strategy_with_jwks
        token = _make_jwt(private_key, 'https://wrong-audience.com', auth0_config.issuer)
        is_valid, error = strategy.validate_request(f'Bearer {token}')
        assert is_valid is False
        assert error == ErrorType.INVALID_JWT

    def test_validate_request_wrong_issuer(self, strategy_with_jwks, auth0_config):
        """JWT with wrong issuer is rejected."""
        strategy, private_key = strategy_with_jwks
        token = _make_jwt(private_key, auth0_config.audience, 'https://wrong-issuer.com/')
        is_valid, error = strategy.validate_request(f'Bearer {token}')
        assert is_valid is False
        assert error == ErrorType.INVALID_JWT

    def test_validate_request_unknown_kid(self, auth0_config, rsa_key_pair):
        """JWT signed with a key whose kid is not in JWKS is rejected."""
        private_key, _ = rsa_key_pair
        other_private, other_public = _generate_rsa_key_pair()
        jwks = {"keys": [_public_key_to_jwk(other_public, kid="other-key")]}
        strategy = Auth0AuthenticationStrategy(auth0_config)
        strategy._jwks_cache = jwks
        token = _make_jwt(private_key, auth0_config.audience, auth0_config.issuer, kid="test-key-id")
        is_valid, error = strategy.validate_request(f'Bearer {token}')
        assert is_valid is False
        assert error == ErrorType.INVALID_JWT

    def test_validate_request_garbage_token(self, auth0_config):
        """Completely invalid token string is rejected."""
        strategy = Auth0AuthenticationStrategy(auth0_config)
        strategy._jwks_cache = {"keys": []}
        is_valid, error = strategy.validate_request('Bearer not.a.real.jwt')
        assert is_valid is False
        assert error == ErrorType.INVALID_JWT

    def test_jwks_cache_is_populated_on_first_call(self, auth0_config, rsa_key_pair):
        """JWKS is fetched from Auth0 on first validation and then cached."""
        private_key, public_key = rsa_key_pair
        jwks = {"keys": [_public_key_to_jwk(public_key)]}
        strategy = Auth0AuthenticationStrategy(auth0_config)
        assert strategy._jwks_cache is None
        with patch('requests.get') as mock_get:
            mock_response = Mock()
            mock_response.json.return_value = jwks
            mock_response.raise_for_status = Mock()
            mock_get.return_value = mock_response
            token = _make_jwt(private_key, auth0_config.audience, auth0_config.issuer)
            strategy.validate_request(f'Bearer {token}')
            assert mock_get.call_count == 1
            strategy.validate_request(f'Bearer {token}')
            assert mock_get.call_count == 1  # still 1 — cache hit

    def test_jwks_fetch_failure_returns_invalid_jwt(self, auth0_config):
        """Network error fetching JWKS results in INVALID_JWT, not a crash."""
        import requests as req
        strategy = Auth0AuthenticationStrategy(auth0_config)
        private_key, _ = _generate_rsa_key_pair()
        token = _make_jwt(private_key, auth0_config.audience, auth0_config.issuer)
        with patch('requests.get', side_effect=req.RequestException("timeout")):
            is_valid, error = strategy.validate_request(f'Bearer {token}')
        assert is_valid is False
        assert error == ErrorType.INVALID_JWT


class TestNoAuthenticationStrategy:
    """Tests for NoAuthenticationStrategy"""

    def test_is_configured(self):
        """Test is_configured always returns True"""
        strategy = NoAuthenticationStrategy()
        assert strategy.is_configured() is True

    def test_validate_request_always_valid(self):
        """Test validation always succeeds"""
        strategy = NoAuthenticationStrategy()
        is_valid, error = strategy.validate_request(None)
        assert is_valid is True
        assert error is None

        is_valid, error = strategy.validate_request('Bearer token')
        assert is_valid is True
        assert error is None


class TestAuthenticationStrategyFactory:
    """Tests for AuthenticationStrategyFactory"""

    def test_create_token_strategy(self):
        """Test creating token authentication strategy"""
        with patch.dict(os.environ, {
            'AUTH_TYPE': 'token',
            'API_TOKEN': 'test_token'
        }):
            config = AuthConfig()
            factory = AuthenticationStrategyFactory()
            strategy = factory.create_strategy(config)
            assert isinstance(strategy, TokenAuthenticationStrategy)

    def test_create_auth0_strategy(self):
        """Test creating Auth0 authentication strategy"""
        with patch.dict(os.environ, {
            'AUTH_TYPE': 'auth0',
            'AUTH0_DOMAIN': 'test.auth0.com',
            'AUTH0_AUDIENCE': 'https://api.test.com'
        }):
            config = AuthConfig()
            factory = AuthenticationStrategyFactory()
            strategy = factory.create_strategy(config)
            assert isinstance(strategy, Auth0AuthenticationStrategy)

    def test_create_none_strategy(self):
        """Test creating no authentication strategy"""
        with patch.dict(os.environ, {'AUTH_TYPE': 'none'}, clear=True):
            config = AuthConfig()
            factory = AuthenticationStrategyFactory()
            strategy = factory.create_strategy(config)
            assert isinstance(strategy, NoAuthenticationStrategy)


class TestAuthenticator:
    """Tests for Authenticator"""

    def test_authenticator_with_token(self):
        """Test Authenticator with token configuration"""
        with patch.dict(os.environ, {
            'AUTH_TYPE': 'token',
            'API_TOKEN': 'test_token'
        }):
            authenticator = Authenticator()
            assert authenticator.is_configured is True
            assert isinstance(authenticator.strategy, TokenAuthenticationStrategy)

    def test_authenticator_with_auth0(self):
        """Test Authenticator with Auth0 configuration"""
        with patch.dict(os.environ, {
            'AUTH_TYPE': 'auth0',
            'AUTH0_DOMAIN': 'test.auth0.com',
            'AUTH0_AUDIENCE': 'https://api.test.com'
        }):
            authenticator = Authenticator()
            assert authenticator.is_configured is True
            assert isinstance(authenticator.strategy, Auth0AuthenticationStrategy)


class TestTokenAuthenticatorBackwardCompatibility:
    """Tests for TokenAuthenticator backward compatibility"""

    def test_token_authenticator_creates_token_strategy(self):
        """Test TokenAuthenticator creates token strategy"""
        with patch.dict(os.environ, {'API_TOKEN': 'test_token'}):
            authenticator = TokenAuthenticator()
            assert isinstance(authenticator.strategy, TokenAuthenticationStrategy)

    def test_validate_token_method(self):
        """Test backward compatibility validate_token method"""
        with patch.dict(os.environ, {'API_TOKEN': 'test_token'}):
            authenticator = TokenAuthenticator()
            assert authenticator.validate_token('test_token') is True
            assert authenticator.validate_token('wrong_token') is False
