from typing import Dict, Any, Optional
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from ..interfaces import IHTTPClient, ILogger


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

            response = self._session.post(
                url,
                json=data,
                headers={"Content-Type": "application/json"},
                timeout=(10, self._timeout)  # (connect timeout, read timeout)
            )
            response.raise_for_status()

            self._logger.info(f"Response received from {url} (status: {response.status_code})")
            return response.json()

        except requests.exceptions.Timeout as e:
            error_msg = f"Request to {url} timed out after {self._timeout}s"
            self._logger.error(error_msg)
            self._logger.error(f"Timeout details: {str(e)}")
            raise
        except requests.exceptions.ConnectionError as e:
            error_msg = f"Connection error to {url}"
            self._logger.error(error_msg)
            self._logger.error(f"Connection details: {str(e)}")
            raise
        except requests.exceptions.RequestException as e:
            self._logger.error(f"Request to {url} failed: {str(e)}")
            if hasattr(e, 'response') and e.response is not None:
                self._logger.error(f"Response status: {e.response.status_code}")
                self._logger.error(f"Response body: {e.response.text}")
            raise

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

        except requests.exceptions.Timeout as e:
            error_msg = f"Request to {url} timed out after {self._timeout}s"
            self._logger.error(error_msg)
            self._logger.error(f"Timeout details: {str(e)}")
            raise
        except requests.exceptions.ConnectionError as e:
            error_msg = f"Connection error to {url}"
            self._logger.error(error_msg)
            self._logger.error(f"Connection details: {str(e)}")
            raise
        except requests.exceptions.RequestException as e:
            self._logger.error(f"Request to {url} failed: {str(e)}")
            if hasattr(e, 'response') and e.response is not None:
                self._logger.error(f"Response status: {e.response.status_code}")
                self._logger.error(f"Response body: {e.response.text}")
            raise
