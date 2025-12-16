from typing import Dict, Any, Optional
import json
import logging
logger = logging.getLogger("logger")
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from urllib.parse import urlparse
from ..exceptions import ServiceConnectionError, ServiceTimeoutError, ServiceResponseError, ServiceAuthorizationError


class HTTPClient:
    """HTTP client for making external requests with connection pooling and retries"""
    timeout: int = 300
    max_retries: int = 3
    backoff_factor: float = 0.3
    _session: requests.Session | None = None

    @classmethod
    def _create_session(cls, max_retries: int, backoff_factor: float) -> requests.Session:
        """Create session with retry strategy and connection pooling"""
        session = requests.Session()

        retry_strategy = Retry(
            total=max_retries,
            backoff_factor=backoff_factor,
            status_forcelist=[429, 500, 502, 503, 504],
            allowed_methods=["POST", "GET"]
        )

        adapter = HTTPAdapter(
            max_retries=retry_strategy,
            pool_connections=10,
            pool_maxsize=10
        )

        session.mount("http://", adapter)
        session.mount("https://", adapter)

        return session
    

    @classmethod
    def _parse_service_name(cls, url: str) -> str:
        """Extract service name from URL"""
        parsed = urlparse(url)
        path_parts = parsed.path.strip('/').split('/')
        # Try to extract service name from path or use hostname
        if path_parts:
            return path_parts[0]
        return parsed.hostname or "unknown"
    @classmethod
    def _parse_endpoint(cls, url: str) -> str:
        """Extract endpoint from URL"""
        parsed = urlparse(url)
        return parsed.path or "/"
    @classmethod
    def _handle_request_error(cls, e: Exception, url: str) -> None:
        """Handle request errors with appropriate custom exceptions"""
        service_name = cls._parse_service_name(url)
        endpoint = cls._parse_endpoint(url)

        if isinstance(e, requests.exceptions.Timeout):
            error = ServiceTimeoutError(service_name, endpoint, cls._timeout)
            logger.error(error.get_log_message())
            raise error
        elif isinstance(e, requests.exceptions.ConnectionError):
            error = ServiceConnectionError(service_name, endpoint, url, e)
            logger.error(error.get_log_message())
            raise error
        elif isinstance(e, requests.exceptions.HTTPError):
            status_code = e.response.status_code if e.response else 0
            error_msg = e.response.text[:200] if e.response else str(e)

            # Special handling for 403 Forbidden (authorization errors)
            if status_code == 403:
                error = ServiceAuthorizationError(service_name, endpoint, error_msg)
                logger.error(error.get_log_message())
                raise error
            else:
                error = ServiceResponseError(service_name, endpoint, status_code, error_msg)
                logger.error(error.get_log_message())
                raise error
        else:
            # Generic fallback for other request exceptions
            error = ServiceConnectionError(service_name, endpoint, url, e)
            logger.error(error.get_log_message())
            raise error
    
    @classmethod
    def post(cls, url: str, data: Dict[str, Any]) -> Dict[str, Any]:
        """Make POST request to URL with JSON data"""
        try:
            logger.info(f"POST request to {url} (timeout: {cls.timeout}s)")
            logger.debug(f"Request data keys: {list(data.keys())}")

            if cls._session is None:
                cls._session = cls._create_session(cls.max_retries, cls.backoff_factor)
            response = cls._session.post(
                url,
                json=data,
                headers={"Content-Type": "application/json"},
                timeout=(10, cls.timeout)  # (connect timeout, read timeout)
            )
            response.raise_for_status()

            logger.info(f"Response received from {url} (status: {response.status_code})")
            return response.json()

        except requests.exceptions.RequestException as e:
            # Log response body if available (for debugging 400 errors)
            if hasattr(e, 'response') and e.response is not None:
                logger.error(f"Response status: {e.response.status_code}")
                logger.error(f"Response body: {e.response.text[:500]}")
            cls._handle_request_error(e, url)
            

    @classmethod
    def post_multipart(
        cls,
        url: str,
        files: Dict[str, Any],
        data: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Make POST request with multipart/form-data"""
        try:
            logger.info(f"POST multipart request to {url} (timeout: {cls.timeout}s)")
            logger.debug(f"Files: {list(files.keys())}")
            if data:
                logger.debug(f"Form data keys: {list(data.keys())}")

            if cls._session is None:
                cls._session = cls._create_session(cls.max_retries, cls.backoff_factor)

            response = cls._session.post(
                url,
                files=files,
                data=data,
                timeout=(10, cls.timeout)
            )
            response.raise_for_status()

            logger.info(f"Response received from {url} (status: {response.status_code})")
            return response.json()

        except requests.exceptions.RequestException as e:
            cls._handle_request_error(e, url)

    @classmethod
    def post_binary(cls, url: str, data: Dict[str, Any]) -> bytes:
        """Make POST request expecting binary response (e.g., images)"""
        try:
            logger.info(f"POST request to {url} expecting binary response (timeout: {cls.timeout}s)")
            logger.debug(f"Request data keys: {list(data.keys())}")
            
            if cls._session is None:
                cls._session = cls._create_session(cls.max_retries, cls.backoff_factor)
            response = cls._session.post(
                url,
                json=data,
                headers={"Content-Type": "application/json"},
                timeout=(10, cls.timeout)
            )
            response.raise_for_status()

            # Check if response is JSON error (content-type application/json)
            content_type = response.headers.get('Content-Type', '').lower()
            if 'application/json' in content_type:
                try:
                    error_data = response.json()
                    if error_data.get('status') == 'error':
                        error_msg = error_data.get('error', 'Unknown error from encoder service')
                        logger.error(f"Encoder service returned error: {error_msg}")
                        service_name = cls._parse_service_name(url)
                        endpoint = cls._parse_endpoint(url)
                        raise ServiceResponseError(service_name, endpoint, response.status_code, error_msg)
                except ValueError:
                    pass  # Not valid JSON, treat as binary

            logger.info(f"Binary response received from {url} (status: {response.status_code}, size: {len(response.content)} bytes)")
            return response.content

        except requests.exceptions.RequestException as e:
            cls._handle_request_error(e, url)
