from dataclasses import dataclass
from typing import Dict, Any, List

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
    mesh: list
    result: Any = None

    @property
    def to_dict(self) -> Dict[str, Any]:
        return {
            RequestField.MODEL_TYPE.value: self.model_type,
            RequestField.PARAMETERS.value: self.params.to_dict,
            RequestField.MESH.value: self.mesh
        }

    @classmethod
    def parse(cls, content: Dict[str, Any]) -> List['MainRequest']:
        model_type = content.get(RequestField.MODEL_TYPE.value, "df_default")
        params_dict = content.get(RequestField.PARAMETERS.value, {})

        # Merge accumulated orchestration data (from top-level) with parameters
        # This allows Parameters.parse() to access reference_point, direction_angle, obstruction_angle_*, etc.
        merged_params = params_dict.copy()
        for key in [RequestField.REFERENCE_POINT.value, RequestField.DIRECTION_ANGLE.value,
                   RequestField.OBSTRUCTION_ANGLE_HORIZON.value, RequestField.OBSTRUCTION_ANGLE_ZENITH.value]:
            if key in content:
                merged_params[key] = content[key]

        prms = Parameters.parse(merged_params)
        mesh = content.get(RequestField.MESH.value, [])
        return [cls(model_type, p, mesh) for p in prms]
