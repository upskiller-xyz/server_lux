from typing import Dict, Any, Optional
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from urllib.parse import urlparse
from ..interfaces import IHTTPClient, ILogger
from ..exceptions import ServiceConnectionError, ServiceTimeoutError, ServiceResponseError, ServiceAuthorizationError


class HTTPClient(IHTTPClient):
    """HTTP client for making external requests with connection pooling and retries"""

    def __init__(
        self,
        logger: ILogger,
        timeout: int = 300,
        max_retries: int = 3,
        backoff_factor: float = 0.3
    ):
        self._logger = logger
        self._timeout = timeout
        self._session = self._create_session(max_retries, backoff_factor)

    def _parse_service_name(self, url: str) -> str:
        """Extract service name from URL"""
        parsed = urlparse(url)
        path_parts = parsed.path.strip('/').split('/')
        # Try to extract service name from path or use hostname
        if path_parts:
            return path_parts[0]
        return parsed.hostname or "unknown"

    def _parse_endpoint(self, url: str) -> str:
        """Extract endpoint from URL"""
        parsed = urlparse(url)
        return parsed.path or "/"

    def _handle_request_error(self, e: Exception, url: str) -> None:
        """Handle request errors with appropriate custom exceptions"""
        service_name = self._parse_service_name(url)
        endpoint = self._parse_endpoint(url)

        if isinstance(e, requests.exceptions.Timeout):
            error = ServiceTimeoutError(service_name, endpoint, self._timeout)
            self._logger.error(error.get_log_message())
            raise error
        elif isinstance(e, requests.exceptions.ConnectionError):
            error = ServiceConnectionError(service_name, endpoint, url, e)
            self._logger.error(error.get_log_message())
            raise error
        elif isinstance(e, requests.exceptions.HTTPError):
            status_code = e.response.status_code if e.response else 0
            error_msg = e.response.text[:200] if e.response else str(e)

            # Special handling for 403 Forbidden (authorization errors)
            if status_code == 403:
                error = ServiceAuthorizationError(service_name, endpoint, error_msg)
                self._logger.error(error.get_log_message())
                raise error
            else:
                error = ServiceResponseError(service_name, endpoint, status_code, error_msg)
                self._logger.error(error.get_log_message())
                raise error
        else:
            # Generic fallback for other request exceptions
            error = ServiceConnectionError(service_name, endpoint, url, e)
            self._logger.error(error.get_log_message())
            raise error

    def _create_session(self, max_retries: int, backoff_factor: float) -> requests.Session:
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

    def post(self, url: str, data: Dict[str, Any]) -> Dict[str, Any]:
        """Make POST request to URL with JSON data"""
        try:
            self._logger.info(f"POST request to {url} (timeout: {self._timeout}s)")
            self._logger.debug(f"Request data keys: {list(data.keys())}")

            # Additional logging for merger service
            if "/merge" in url:
                self._logger.info(f"📤 Merger service request:")
                self._logger.info(f"   room_polygon: {data.get('room_polygon')}")
                if "windows" in data:
                    self._logger.info(f"   windows count: {len(data['windows'])}")
                    for win_name, win_data in data['windows'].items():
                        self._logger.info(f"      {win_name}: {list(win_data.keys())}")
                if "simulations" in data:
                    self._logger.info(f"   simulations count: {len(data['simulations'])}")
                    for win_name, sim_data in data['simulations'].items():
                        df_vals = sim_data.get('df_values', [])
                        mask_vals = sim_data.get('mask', [])
                        df_shape = f"{len(df_vals)}x{len(df_vals[0]) if df_vals and len(df_vals) > 0 else 0}" if isinstance(df_vals, list) else type(df_vals).__name__
                        mask_shape = f"{len(mask_vals)}x{len(mask_vals[0]) if mask_vals and len(mask_vals) > 0 else 0}" if isinstance(mask_vals, list) else type(mask_vals).__name__
                        self._logger.info(f"      {win_name}: df_values={df_shape}, mask={mask_shape}")

            response = self._session.post(
                url,
                json=data,
                headers={"Content-Type": "application/json"},
                timeout=(10, self._timeout)  # (connect timeout, read timeout)
            )
            response.raise_for_status()

            self._logger.info(f"Response received from {url} (status: {response.status_code})")
            return response.json()

        except requests.exceptions.RequestException as e:
            # Log response body if available (for debugging 400 errors)
            if hasattr(e, 'response') and e.response is not None:
                self._logger.error(f"Response status: {e.response.status_code}")
                self._logger.error(f"Response body: {e.response.text[:500]}")
            self._handle_request_error(e, url)

    def post_multipart(
        self,
        url: str,
        files: Dict[str, Any],
        data: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Make POST request with multipart/form-data"""
        try:
            self._logger.info(f"POST multipart request to {url} (timeout: {self._timeout}s)")
            self._logger.debug(f"Files: {list(files.keys())}")
            if data:
                self._logger.debug(f"Form data keys: {list(data.keys())}")

            response = self._session.post(
                url,
                files=files,
                data=data,
                timeout=(10, self._timeout)
            )
            response.raise_for_status()

            self._logger.info(f"Response received from {url} (status: {response.status_code})")
            return response.json()

        except requests.exceptions.RequestException as e:
            self._handle_request_error(e, url)

    def post_binary(self, url: str, data: Dict[str, Any]) -> bytes:
        """Make POST request expecting binary response (e.g., images)"""
        try:
            self._logger.info(f"POST request to {url} expecting binary response (timeout: {self._timeout}s)")
            self._logger.debug(f"Request data keys: {list(data.keys())}")

            # Log detailed payload structure for debugging
            import json
            if "parameters" in data:
                params = data["parameters"]
                self._logger.info(f"📤 Encoder payload structure:")
                self._logger.info(f"   model_type: {data.get('model_type')}")
                self._logger.info(f"   parameters keys: {list(params.keys())}")
                if "windows" in params:
                    for window_name, window_data in params["windows"].items():
                        self._logger.info(f"   window '{window_name}' fields: {list(window_data.keys())}")
                        for key, value in window_data.items():
                            if isinstance(value, list):
                                self._logger.info(f"      {key}: list[{len(value)}] = {value[:3] if len(value) > 3 else value}...")
                            else:
                                self._logger.info(f"      {key}: {value}")

            response = self._session.post(
                url,
                json=data,
                headers={"Content-Type": "application/json"},
                timeout=(10, self._timeout)
            )
            response.raise_for_status()

            # Check if response is JSON error (content-type application/json)
            content_type = response.headers.get('Content-Type', '').lower()
            if 'application/json' in content_type:
                try:
                    error_data = response.json()
                    if error_data.get('status') == 'error':
                        error_msg = error_data.get('error', 'Unknown error from encoder service')
                        self._logger.error(f"Encoder service returned error: {error_msg}")
                        service_name = self._parse_service_name(url)
                        endpoint = self._parse_endpoint(url)
                        raise ServiceResponseError(service_name, endpoint, response.status_code, error_msg)
                except ValueError:
                    pass  # Not valid JSON, treat as binary

            self._logger.info(f"Binary response received from {url} (status: {response.status_code}, size: {len(response.content)} bytes)")
            return response.content

        except requests.exceptions.RequestException as e:
            self._handle_request_error(e, url)
