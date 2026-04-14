"""Unit tests for authentication system"""

import os
import pytest
from unittest.mock import Mock, patch, MagicMock
from src.server.enums import AuthType, ErrorType
from src.server.auth_config import AuthConfig, Auth0Config
from src.server.auth_strategies import (
    TokenAuthenticationStrategy,
    Auth0AuthenticationStrategy,
    NoAuthenticationStrategy
)
from src.server.auth_factory import AuthenticationStrategyFactory
from src.server.auth import Authenticator, TokenAuthenticator


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
        """Create mock Auth0Config"""
        return Auth0Config(
            domain='test.auth0.com',
            audience='https://api.test.com',
            algorithms=['RS256'],
            issuer='https://test.auth0.com/'
        )

    def test_is_configured(self, auth0_config):
        """Test is_configured returns True with config"""
        strategy = Auth0AuthenticationStrategy(auth0_config)
        assert strategy.is_configured() is True

    def test_validate_request_missing_header(self, auth0_config):
        """Test validation with missing auth header"""
        strategy = Auth0AuthenticationStrategy(auth0_config)
        is_valid, error = strategy.validate_request(None)
        assert is_valid is False
        assert error == ErrorType.MISSING_AUTHORIZATION

    def test_validate_request_invalid_format(self, auth0_config):
        """Test validation with invalid header format"""
        strategy = Auth0AuthenticationStrategy(auth0_config)
        is_valid, error = strategy.validate_request('InvalidFormat token')
        assert is_valid is False
        assert error == ErrorType.INVALID_AUTH_FORMAT


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
