"""Remote service interfaces for request/response handling"""

# Domain models
from .remote_interfaces import (
    WindowGeometry,
    RoomPolygon,
    Simulation,
    EncoderParameters,
)

# Request classes
from .remote_interfaces import (
    RemoteServiceRequest,
    MainRequest,
    Parameters,
    ObstructionRequest,
    ObstructionMultiRequest,
    ObstructionParallelRequest,
    DirectionAngleRequest,
    MergerRequest,
    StatsRequest,
    ModelRequest,
)

# Response classes
from .remote_responses import (
    RemoteServiceResponse,
    StandardResponse,
    BinaryResponse,
    ObstructionResponse,
    DirectionAngleResponse,
    ReferencePointResponse,
    EncoderResponse,
    ModelResponse,
    MergerResponse,
    StatsResponse,
)

__all__ = [
    # Domain models
    "WindowGeometry",
    "RoomPolygon",
    "Simulation",
    "EncoderParameters",
    # Request classes
    "RemoteServiceRequest",
    "MainRequest",
    "Parameters",
    "ObstructionRequest",
    "ObstructionMultiRequest",
    "ObstructionParallelRequest",
    "DirectionAngleRequest",
    "MergerRequest",
    "StatsRequest",
    "ModelRequest",
    # Response classes
    "RemoteServiceResponse",
    "StandardResponse",
    "BinaryResponse",
    "ObstructionResponse",
    "DirectionAngleResponse",
    "ReferencePointResponse",
    "EncoderResponse",
    "ModelResponse",
    "MergerResponse",
    "StatsResponse",
]
