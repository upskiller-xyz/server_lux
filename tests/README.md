# Test Directory Structure

## Overview

The test directory mirrors the `src/` directory structure for easy navigation and maintainability.

## Directory Structure

```
tests/
├── __init__.py
├── server/                          # Mirrors src/server/
│   ├── __init__.py
│   └── test_auth.py                 # Tests for src/server/auth*.py
└── test_local_endpoint.py           # Root-level tests
```

This should mirror:

```
src/
├── __init__.py
├── main.py
├── server/
│   ├── __init__.py
│   ├── auth.py
│   ├── auth_config.py
│   ├── auth_factory.py
│   ├── auth_strategies.py
│   ├── config.py
│   ├── controllers/
│   ├── services/
│   └── ...
└── utils/
```

## Test Naming Convention

Tests should follow the naming pattern:
- **File naming**: `test_<module_name>.py`
- **Class naming**: `Test<ClassName>` or `Test<Feature>`
- **Method naming**: `test_<what_is_being_tested>`

### Examples

| Source File | Test File | Test Class |
|-------------|-----------|------------|
| `src/server/auth.py` | `tests/server/test_auth.py` | `TestAuthenticator` |
| `src/server/auth_config.py` | `tests/server/test_auth.py` | `TestAuthConfig` |
| `src/server/auth_strategies.py` | `tests/server/test_auth.py` | `TestTokenAuthenticationStrategy` |
| `src/server/enums.py` | `tests/server/test_enums.py` | `TestEnums` |
| `src/server/services/remote/base.py` | `tests/server/services/remote/test_base.py` | `TestRemoteBase` |

## Running Tests

### Run All Tests
```bash
pytest tests/
```

### Run Specific Test File
```bash
pytest tests/server/test_auth.py
```

### Run Specific Test Class
```bash
pytest tests/server/test_auth.py::TestAuthConfig
```

### Run Specific Test Method
```bash
pytest tests/server/test_auth.py::TestAuthConfig::test_token_auth_type
```

### Run with Verbose Output
```bash
pytest tests/ -v
```

### Run with Coverage
```bash
pytest tests/ --cov=src --cov-report=html
```

## Test Structure Guidelines

### 1. Mirror Source Structure

For every module in `src/`, create a corresponding test file in `tests/`:

```
src/server/auth.py          → tests/server/test_auth.py
src/server/config.py        → tests/server/test_config.py
src/server/enums.py         → tests/server/test_enums.py
src/utils/extended_enum.py  → tests/utils/test_extended_enum.py
```

### 2. Group Related Tests

Group tests for related classes in the same file:

```python
# tests/server/test_auth.py
class TestAuthConfig:
    """Tests for AuthConfig class"""
    def test_default_auth_type_is_token(self): ...
    def test_token_auth_type(self): ...

class TestAuth0Config:
    """Tests for Auth0Config class"""
    def test_from_environment_success(self): ...
    def test_jwks_url_property(self): ...

class TestAuthenticator:
    """Tests for Authenticator class"""
    def test_authenticator_with_token(self): ...
    def test_authenticator_with_auth0(self): ...
```

### 3. Use Fixtures for Common Setup

```python
import pytest

@pytest.fixture
def auth_config():
    """Create mock AuthConfig"""
    return AuthConfig(...)

class TestAuthenticator:
    def test_authenticator(self, auth_config):
        authenticator = Authenticator(auth_config)
        assert authenticator.is_configured
```

### 4. Test File Template

```python
"""Tests for <module_name>"""

import pytest
from unittest.mock import Mock, patch, MagicMock

from src.server.<module_name> import ClassName


class TestClassName:
    """Tests for ClassName"""

    @pytest.fixture
    def instance(self):
        """Create instance for testing"""
        return ClassName()

    def test_method_name_success_case(self, instance):
        """Test method_name with valid input"""
        result = instance.method_name()
        assert result == expected_value

    def test_method_name_error_case(self, instance):
        """Test method_name with invalid input"""
        with pytest.raises(ValueError):
            instance.method_name(invalid_input)
```

## Current Test Coverage

### ✅ Implemented
- **Authentication** (`tests/server/test_auth.py`)
  - 27 test cases covering all auth strategies
  - Auth0Config, AuthConfig, Authenticator
  - Token, Auth0, and No authentication strategies
  - Factory pattern implementation
  - Backward compatibility

### 📋 TODO: Add Tests For

Create the following test files to match the src structure:

```
tests/
├── server/
│   ├── test_config.py                    # Tests for src/server/config.py
│   ├── test_enums.py                     # Tests for src/server/enums.py
│   ├── test_exceptions.py                # Tests for src/server/exceptions.py
│   ├── test_response_builder.py          # Tests for src/server/response_builder.py
│   ├── test_request_handler.py           # Tests for src/server/request_handler.py
│   ├── test_endpoint_handlers.py         # Tests for src/server/endpoint_handlers.py
│   ├── test_route_configurator.py        # Tests for src/server/route_configurator.py
│   ├── test_swagger_config.py            # Tests for src/server/swagger_config.py
│   ├── controllers/
│   │   ├── __init__.py
│   │   ├── test_base_controller.py       # Tests for controllers/base_controller.py
│   │   └── test_endpoint_controller.py   # Tests for controllers/endpoint_controller.py
│   └── services/
│       ├── __init__.py
│       ├── test_http_client.py           # Tests for services/http_client.py
│       ├── remote/
│       │   ├── __init__.py
│       │   ├── test_base.py
│       │   ├── test_obstruction_service.py
│       │   ├── test_encoder_service.py
│       │   └── test_model_service.py
│       └── orchestration/
│           ├── __init__.py
│           └── test_orchestrator.py
└── utils/
    ├── __init__.py
    └── test_extended_enum.py             # Tests for utils/extended_enum.py
```

## Example: Creating New Test File

To add tests for `src/server/config.py`:

### 1. Create Directory Structure
```bash
# Directory already exists
mkdir -p tests/server
```

### 2. Create Test File
```bash
touch tests/server/test_config.py
```

### 3. Write Tests
```python
"""Tests for server configuration"""

import pytest
from src.server.config import ServerConfig


class TestServerConfig:
    """Tests for ServerConfig class"""

    def test_config_loads_from_environment(self):
        """Test config loads from environment variables"""
        config = ServerConfig.from_environment()
        assert config.port == 8080

    def test_config_validates_port(self):
        """Test config validates port number"""
        with pytest.raises(ValueError):
            ServerConfig(port=-1)
```

### 4. Run Tests
```bash
pytest tests/server/test_config.py -v
```

## Best Practices

### ✅ DO
- Mirror the src directory structure
- Use descriptive test names
- Group related tests in classes
- Use fixtures for common setup
- Test both success and error cases
- Use mocks for external dependencies
- Add docstrings to test classes and methods

### ❌ DON'T
- Put all tests in a single file
- Use generic test names like `test_1`, `test_2`
- Test implementation details
- Write tests without assertions
- Ignore test failures
- Skip writing tests for edge cases

## Continuous Integration

Tests should be run automatically on:
- Every commit (pre-commit hook)
- Every pull request (CI/CD)
- Before deployment

## Test Coverage Goals

Target coverage percentages:
- **Overall**: 80%+
- **Critical paths** (auth, controllers): 90%+
- **Utilities**: 70%+

Check coverage:
```bash
pytest tests/ --cov=src --cov-report=term-missing
```

## Contributing

When adding new features:
1. Create corresponding test file in `tests/`
2. Mirror the source directory structure
3. Write tests for all public methods
4. Include both success and error cases
5. Update this README if needed

## Resources

- [pytest documentation](https://docs.pytest.org/)
- [pytest fixtures](https://docs.pytest.org/en/stable/fixture.html)
- [unittest.mock](https://docs.python.org/3/library/unittest.mock.html)
- Python testing best practices: Follow TDD principles

---

**Remember**: Tests should mirror the source structure for easy navigation and maintenance!
