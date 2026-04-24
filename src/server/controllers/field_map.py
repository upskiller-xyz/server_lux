from ..maps import StandardMap
from ..enums import EndpointType, RequestField
from ..services.orchestration.encode_orchestration_service import Orchestrator, SimulationOrchestrator, EncodeOrchestrator

class FieldMap(StandardMap):

    _content = {
        EndpointType.SIMULATE: [],
        EndpointType.RUN: [RequestField.MODEL_TYPE, RequestField.PARAMETERS, RequestField.MESH],
        EndpointType.RUN_DETAILED: [RequestField.MODEL_TYPE, RequestField.PARAMETERS, RequestField.MESH],
        EndpointType.RUN_DIRECT: [RequestField.MODEL_TYPE, RequestField.ENCODER_MODEL_TYPE, RequestField.PARAMETERS, RequestField.MESH, RequestField.ENCODING_SCHEME],
        EndpointType.OBSTRUCTION: [RequestField.X, RequestField.Y, RequestField.Z, RequestField.DIRECTION_ANGLE, RequestField.MESH],
        EndpointType.OBSTRUCTION_ALL: [RequestField.ROOM_POLYGON, RequestField.WINDOWS, RequestField.MESH],
        EndpointType.OBSTRUCTION_MULTI: [RequestField.X, RequestField.Y, RequestField.Z, RequestField.MESH],
        EndpointType.OBSTRUCTION_PARALLEL: [RequestField.X, RequestField.Y, RequestField.Z, RequestField.MESH],
        EndpointType.CALCULATE_DIRECTION: [RequestField.ROOM_POLYGON, RequestField.WINDOWS],
        EndpointType.REFERENCE_POINT: [RequestField.ROOM_POLYGON, RequestField.WINDOWS],
        EndpointType.ENCODE: [RequestField.MODEL_TYPE, RequestField.PARAMETERS],
        EndpointType.ENCODE_RAW: [RequestField.MODEL_TYPE, RequestField.PARAMETERS],
        EndpointType.HORIZON: [],
        EndpointType.ZENITH: [],
        EndpointType.MERGE: [RequestField.SIMULATION, RequestField.ROOM_POLYGON, RequestField.WINDOWS],
        EndpointType.STATS_CALCULATE: [RequestField.RESULT, RequestField.MASK],
        EndpointType.STATUS: []
    }
    _default = []

class EndpointOrchestratorMap(StandardMap):
    _content = {
        EndpointType.SIMULATE: SimulationOrchestrator,
        EndpointType.RUN: SimulationOrchestrator,
        EndpointType.RUN_DETAILED: SimulationOrchestrator,
        EndpointType.RUN_DIRECT: SimulationOrchestrator,
        EndpointType.ENCODE: EncodeOrchestrator,
        EndpointType.ENCODE_RAW: EncodeOrchestrator
    }
    _default = Orchestrator