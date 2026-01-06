from typing import Dict, Any, Optional
import logging
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from urllib.parse import urlparse
from ..exceptions import ServiceConnectionError, ServiceTimeoutError, ServiceResponseError, ServiceAuthorizationError

logger = logging.getLogger("logger")


class HTTPClient:

    def __init__(self, timeout: int = 300, max_retries: int = 3, backoff_factor: float = 0.3):
        self._timeout = timeout
        self._max_retries = max_retries
        self._backoff_factor = backoff_factor
        self._session: requests.Session | None = None

    def _create_session(self) -> requests.Session:
        session = requests.Session()

        retry_strategy = Retry(
            total=self._max_retries,
            backoff_factor=self._backoff_factor,
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

    @staticmethod
    def _parse_service_name(url: str) -> str:
        parsed = urlparse(url)
        path_parts = parsed.path.strip('/').split('/')
        if path_parts:
            return path_parts[0]
        return parsed.hostname or "unknown"

    @staticmethod
    def _parse_endpoint(url: str) -> str:
        parsed = urlparse(url)
        return parsed.path or "/"

    @staticmethod
    def _extract_error_message(response: requests.Response) -> str:
        """Extract error message from service response.

        Tries to parse JSON response first to get structured error message,
        falls back to raw text if parsing fails.
        """
        try:
            content_type = response.headers.get('Content-Type', '').lower()
            if 'application/json' in content_type:
                error_data = response.json()
                if isinstance(error_data, dict):
                    # Try to get error message from common keys
                    error_msg = error_data.get('error') or error_data.get('message') or error_data.get('detail')
                    if error_msg:
                        return f"Service responded with a message: {error_msg}"
        except (ValueError, KeyError):
            pass

        # Fallback to raw response text
        return f"Service responded with a message: {response.text[:200]}"

    def _handle_request_error(self, e: Exception, url: str) -> None:
        service_name = self._parse_service_name(url)
        endpoint = self._parse_endpoint(url)

        if isinstance(e, requests.exceptions.Timeout):
            error = ServiceTimeoutError(service_name, endpoint, self._timeout)
            logger.error(error.get_log_message())
            raise error
        elif isinstance(e, requests.exceptions.ConnectionError):
            error = ServiceConnectionError(service_name, endpoint, url, e)
            logger.error(error.get_log_message())
            raise error
        elif isinstance(e, requests.exceptions.HTTPError):
            status_code = e.response.status_code if e.response else 0
            error_msg = self._extract_error_message(e.response) if e.response else str(e)

            if status_code == 403:
                error = ServiceAuthorizationError(service_name, endpoint, error_msg)
                logger.error(error.get_log_message())
                raise error
            else:
                error = ServiceResponseError(service_name, endpoint, status_code, error_msg)
                logger.error(error.get_log_message())
                raise error
        else:
            error = ServiceConnectionError(service_name, endpoint, url, e)
            logger.error(error.get_log_message())
            raise error

    def post(self, url: str, data: Dict[str, Any]) -> Dict[str, Any]:
        try:
            if self._session is None:
                self._session = self._create_session()
            response = self._session.post(
                url,
                json=data,
                headers={"Content-Type": "application/json"},
                timeout=(10, self._timeout)
            )
            response.raise_for_status()
            logger.info(f"Response received from {url} (status: {response.status_code})")
            return response.json()

        except requests.exceptions.RequestException as e:
            if hasattr(e, 'response') and e.response is not None:
                logger.error(f"Response status: {e.response.status_code}")
                logger.error(f"Response body: {e.response.text[:500]}")
            self._handle_request_error(e, url)

    def post_multipart(
        self,
        url: str,
        files: Dict[str, Any],
        data: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        try:
            logger.info(f"POST multipart request to {url} (timeout: {self._timeout}s)")

            if self._session is None:
                self._session = self._create_session()

            response = self._session.post(
                url,
                files=files,
                data=data,
                timeout=(10, self._timeout)
            )
            response.raise_for_status()
            logger.info(f"Response received from {url} (status: {response.status_code})")
            return response.json()

        except requests.exceptions.RequestException as e:
            self._handle_request_error(e, url)

    def post_binary(self, url: str, data: Dict[str, Any]) -> bytes:
        try:
            if self._session is None:
                self._session = self._create_session()
            response = self._session.post(
                url,
                json=data,
                headers={"Content-Type": "application/json"},
                timeout=(10, self._timeout)
            )
            response.raise_for_status()

            content_type = response.headers.get('Content-Type', '').lower()
            if 'application/json' in content_type:
                try:
                    error_data = response.json()
                    if error_data.get('status') == 'error':
                        error_msg = error_data.get('error', 'Unknown error from service')
                        service_name = self._parse_service_name(url)
                        endpoint = self._parse_endpoint(url)
                        full_error_msg = f"Service responded with a message: {error_msg}"
                        logger.error(full_error_msg)
                        raise ServiceResponseError(service_name, endpoint, response.status_code, full_error_msg)
                except ValueError:
                    pass

            return response.content

        except requests.exceptions.RequestException as e:
            self._handle_request_error(e, url)
