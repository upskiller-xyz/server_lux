# from .base import  RemoteService
from .obstruction_service import ObstructionService
from .encoder_service import EncoderService
from .direction_angle_service import DirectionAngleService
from .reference_point_service import ReferencePointService
from .model_service import ModelService
from .merger_service import MergerService
from .stats_service import StatsService
from .image_converters import ImageDataConverter


# Domain models
from .contracts import (
    WindowGeometry,
    RoomPolygon,
    Simulation,
    EncoderParameters,
)

# Request classes
from .contracts import (
    # RemoteServiceRequest,
    MainRequest,
    Parameters,
    ObstructionRequest,
    ObstructionMultiRequest,
    ObstructionParallelRequest,
    DirectionAngleRequest,
    ReferencePointRequest,
    MergerRequest,
    StatsRequest,
    ModelRequest,
)

# Response classes
from .contracts import (
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

    # 'RemoteService',
    'ObstructionService',
    'EncoderService',
    'DirectionAngleService',
    'ReferencePointService',
    'ModelService',
    'MergerService',
    'StatsService',
    'ImageDataConverter',

    "WindowGeometry",
    "RoomPolygon",
    "Simulation",
    "EncoderParameters",
    # Request classes
    # "RemoteServiceRequest",
    "MainRequest",
    "Parameters",
    "ObstructionRequest",
    "ObstructionMultiRequest",
    "ObstructionParallelRequest",
    "DirectionAngleRequest",
    "ReferencePointRequest",
    "MergerRequest",
    "StatsRequest",
    "ModelRequest",
    # Response classes
    # "RemoteServiceResponse",
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
