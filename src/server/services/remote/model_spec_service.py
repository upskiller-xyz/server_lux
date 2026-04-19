from typing import Any, Dict
import logging

from .contracts import ModelSpecRequest, ModelSpecResponse
from .base import RemoteService
from ...enums import ServiceName, EndpointType
from ...exceptions import ServiceResponseError

logger = logging.getLogger("logger")


class ModelSpecService(RemoteService):
    """Fetches model spec (encoding_scheme, encoder_model_type) from model-service /spec.

    Caches responses by model name — spec.json is immutable for a given UUID.
    """
    name: ServiceName = ServiceName.MODEL
    _cache: Dict[str, ModelSpecResponse] = {}

    @classmethod
    def _get_request(cls, endpoint: EndpointType) -> type[ModelSpecRequest]:
        return ModelSpecRequest

    @classmethod
    def run(cls, endpoint: EndpointType, request: ModelSpecRequest, file: Any = None, response_class=None) -> ModelSpecResponse:
        if request.model_name in cls._cache:
            logger.info("Model spec cache hit for '%s'", request.model_name)
            return cls._cache[request.model_name]

        url = cls._get_url(endpoint)
        cls._log_request(endpoint, url)
        try:
            response_dict = cls._http_client.get(url, params=request.to_dict)
        except ServiceResponseError as e:
            if e.status_code == 404:
                logger.warning("spec.json not found for model '%s' — encoding_scheme and encoder_model_type will not be set.", request.model_name)
            else:
                logger.exception("Failed to fetch model spec from %s; falling back to empty spec.", url)
            response_dict = {}
        except Exception:
            logger.exception("Failed to fetch model spec from %s; falling back to empty spec.", url)
            response_dict = {}

        result = ModelSpecResponse.parse(response_dict or {})
        if request.model_name and result.encoding_scheme:
            cls._cache[request.model_name] = result
        return result
