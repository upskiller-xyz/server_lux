from dataclasses import dataclass, field
from typing import Dict, Any, List, Optional

from .base_contracts import RemoteServiceRequest
from .encoder_contracts import Parameters
from ....enums import RequestField


@dataclass
class MainRequest(RemoteServiceRequest):
    """Request for main /simulate endpoint

    The primary external request that initiates the full simulation pipeline.
    """
    model_type: str
    params: Parameters
    mesh: List[List[float]]
    result: Any = None
    encoding_scheme: Optional[str] = field(default=None)

    @property
    def to_dict(self) -> Dict[str, Any]:
        result = {
            RequestField.MODEL_TYPE.value: self.model_type,
            RequestField.PARAMETERS.value: self.params.to_dict,
            RequestField.MESH.value: self.mesh,
        }
        if self.encoding_scheme:
            result[RequestField.ENCODING_SCHEME.value] = self.encoding_scheme
        return result

    @classmethod
    def parse(cls, content: Dict[str, Any]) -> List['MainRequest']:
        # Prefer encoder_model_type (resolved from spec.json) over the raw UUID model_type
        model_type = (
            content.get(RequestField.ENCODER_MODEL_TYPE.value)
            or content.get(RequestField.MODEL_TYPE.value, "df_default")
        )
        encoding_scheme = content.get(RequestField.ENCODING_SCHEME.value)

        params_dict = content.get(RequestField.PARAMETERS.value, {})

        # Merge accumulated orchestration data (from top-level) with parameters
        # This allows Parameters.parse() to access reference_point, direction_angle, horizon, zenith, etc.
        merged_params = params_dict.copy()
        for key in [RequestField.REFERENCE_POINT.value, RequestField.DIRECTION_ANGLE.value,
                   RequestField.HORIZON.value, RequestField.ZENITH.value]:
            if key in content:
                merged_params[key] = content[key]

        prms = Parameters.parse(merged_params)
        mesh = content.get(RequestField.MESH.value, [])
        return [cls(model_type, p, mesh, encoding_scheme=encoding_scheme) for p in prms]
