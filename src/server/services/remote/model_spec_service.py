from typing import Any
import logging

from .contracts import ModelSpecRequest, ModelSpecResponse
from .base import RemoteService
from ...enums import ServiceName, EndpointType

logger = logging.getLogger("logger")


class ModelSpecService(RemoteService):
    """Fetches model spec (encoding_scheme, encoder_model_type) from model-service /spec."""
    name: ServiceName = ServiceName.MODEL

    @classmethod
    def _get_request(cls, endpoint: EndpointType) -> type[ModelSpecRequest]:
        return ModelSpecRequest

    @classmethod
    def run(cls, endpoint: EndpointType, request: ModelSpecRequest, file: Any = None, response_class=None) -> ModelSpecResponse:
        url = cls._get_url(endpoint)
        cls._log_request(endpoint, url)
        try:
            response_dict = cls._http_client.get(url, params=request.to_dict)
        except Exception:
            logger.exception("Failed to fetch model spec from %s; falling back to empty spec.", url)
            response_dict = {}
        return ModelSpecResponse.parse(response_dict or {})
