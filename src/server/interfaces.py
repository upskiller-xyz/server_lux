from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional


class IModelLoader(ABC):
    """Interface for model loading strategies"""

    @abstractmethod
    def load(self) -> Any:
        """Load and return the model"""
        pass


class IImageProcessor(ABC):
    """Interface for image processing strategies"""

    @abstractmethod
    def preprocess(self, image_bytes: bytes) -> Any:
        """Preprocess image bytes into tensor"""
        pass


class IDownloadStrategy(ABC):
    """Interface for download strategies"""

    @abstractmethod
    def download(self, url: str, local_path: str) -> str:
        """Download file from URL to local path"""
        pass


class ILogger(ABC):
    """Interface for logging strategies"""

    @abstractmethod
    def debug(self, message: str) -> None:
        pass

    @abstractmethod
    def info(self, message: str) -> None:
        pass

    @abstractmethod
    def warning(self, message: str) -> None:
        pass

    @abstractmethod
    def error(self, message: str) -> None:
        pass


class IPredictionService(ABC):
    """Interface for prediction services"""

    @abstractmethod
    def predict(self, image_bytes: bytes) -> Dict[str, Any]:
        """Make prediction on image and return result"""
        pass


class IServerController(ABC):
    """Interface for server controllers"""

    @abstractmethod
    def initialize(self) -> None:
        """Initialize the server"""
        pass

    @abstractmethod
    def get_status(self) -> Dict[str, Any]:
        """Get server status"""
        pass


class IHTTPClient(ABC):
    """Interface for HTTP client strategies"""

    @abstractmethod
    def post(self, url: str, data: Dict[str, Any]) -> Dict[str, Any]:
        """Make POST request to URL with JSON data"""
        pass

    @abstractmethod
    def post_multipart(
        self,
        url: str,
        files: Dict[str, Any],
        data: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Make POST request with multipart/form-data"""
        pass


class IRemoteService(ABC):
    """Interface for remote service callers"""

    @abstractmethod
    def call(self, endpoint: str, data: Dict[str, Any]) -> Dict[str, Any]:
        """Call remote service endpoint with data"""
        pass