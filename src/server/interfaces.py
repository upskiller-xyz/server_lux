from abc import ABC, abstractmethod
from typing import Any, Dict, Optional


class IModelLoader(ABC):

    @abstractmethod
    def load(self) -> Any:
        pass


class IImageProcessor(ABC):

    @abstractmethod
    def preprocess(self, image_bytes: bytes) -> Any:
        pass


class IDownloadStrategy(ABC):

    @abstractmethod
    def download(self, url: str, local_path: str) -> str:
        pass


class ILogger(ABC):

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

    @abstractmethod
    def predict(self, image_bytes: bytes) -> Dict[str, Any]:
        pass


class IServerController(ABC):

    @abstractmethod
    def initialize(self) -> None:
        pass

    @abstractmethod
    def get_status(self) -> Dict[str, Any]:
        pass


class IRemoteService(ABC):

    @abstractmethod
    def call(self, endpoint: str, data: Dict[str, Any]) -> Dict[str, Any]:
        pass


class IErrorResponseBuilder(ABC):

    @abstractmethod
    def build(self, error_type: Any, message: Optional[str] = None, status_code: Optional[int] = None) -> tuple:
        pass

    @abstractmethod
    def build_from_exception(self, exception: Exception, status_code: Optional[int] = None) -> tuple:
        pass