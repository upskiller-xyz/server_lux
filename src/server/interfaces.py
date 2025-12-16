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




class IRemoteService(ABC):
    """Interface for remote service callers"""

    @abstractmethod
    def call(self, endpoint: str, data: Dict[str, Any]) -> Dict[str, Any]:
        """Call remote service endpoint with data"""
        pass


class IErrorResponseBuilder(ABC):
    """Interface for building error responses using Adapter-Map pattern"""

    @abstractmethod
    def build(self, error_type: Any, message: Optional[str] = None, status_code: Optional[int] = None) -> tuple:
        """Build error response tuple (json_response, http_status_code)

        Args:
            error_type: ErrorType enum or error type identifier
            message: Optional custom error message (overrides default)
            status_code: Optional HTTP status code (overrides default)

        Returns:
            Tuple of (jsonify response, status code)
        """
        pass

    @abstractmethod
    def build_from_exception(self, exception: Exception, status_code: Optional[int] = None) -> tuple:
        """Build error response from exception

        Args:
            exception: Exception to build response from
            status_code: Optional HTTP status code (overrides default)

        Returns:
            Tuple of (jsonify response, status code)
        """
        pass