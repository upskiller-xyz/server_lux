from dataclasses import dataclass
from typing import Dict, Any, List, Optional

from .base_contracts import RemoteServiceRequest, StandardResponse
from ....enums import RequestField


@dataclass
class ModelSpecRequest(RemoteServiceRequest):
    """Request for model spec lookup — GET /spec?model=<name>"""
    model_name: str

    @classmethod
    def parse(cls, content: Dict[str, Any]) -> List['ModelSpecRequest']:
        model_name = content.get(RequestField.MODEL_TYPE.value, "")
        return [cls(model_name=model_name)]

    @property
    def to_dict(self) -> Dict[str, Any]:
        return {"model": self.model_name}


class ModelSpecResponse(StandardResponse):
    """Response from /spec — carries encoding_scheme and encoder_model_type."""

    def __init__(self, encoding_scheme: Optional[str], encoder_model_type: Optional[str],
                 raw_response: Optional[Dict[str, Any]] = None):
        super().__init__(raw_response or {})
        self.encoding_scheme = encoding_scheme
        self.encoder_model_type = encoder_model_type

    @classmethod
    def parse(cls, content: Dict[str, Any]) -> 'ModelSpecResponse':
        return cls(
            encoding_scheme=content.get(RequestField.ENCODING_SCHEME.value),
            encoder_model_type=content.get(RequestField.ENCODER_MODEL_TYPE.value),
            raw_response=content,
        )

    @property
    def to_dict(self) -> Dict[str, Any]:
        result = {}
        if self.encoding_scheme:
            result[RequestField.ENCODING_SCHEME.value] = self.encoding_scheme
        if self.encoder_model_type:
            result[RequestField.ENCODER_MODEL_TYPE.value] = self.encoder_model_type
        return result
