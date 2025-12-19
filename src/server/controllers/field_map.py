from ..maps import StandardMap
from ..enums import EndpointType, RequestField
from ..services.orchestration.encode_orchestration_service import Orchestrator, SimulationOrchestrator, EncodeOrchestrator

class FieldMap(StandardMap):

    _content = {
        EndpointType.SIMULATE: [],
        EndpointType.RUN: [RequestField.MODEL_TYPE, RequestField.MESH, RequestField.PARAMETERS],
        EndpointType.OBSTRUCTION: [RequestField.X, RequestField.Y, RequestField.Z, RequestField.DIRECTION_ANGLE],
        EndpointType.OBSTRUCTION_ALL: [RequestField.X, RequestField.Y, RequestField.Z, RequestField.DIRECTION_ANGLE],
        EndpointType.OBSTRUCTION_MULTI: [RequestField.X, RequestField.Y, RequestField.Z, RequestField.DIRECTION_ANGLE],
        EndpointType.OBSTRUCTION_PARALLEL: [RequestField.X, RequestField.Y, RequestField.Z, RequestField.DIRECTION_ANGLE],
        EndpointType.CALCULATE_DIRECTION: [RequestField.ROOM_POLYGON, RequestField.WINDOWS],
        EndpointType.REFERENCE_POINT: [RequestField.ROOM_POLYGON, RequestField.WINDOWS],
        EndpointType.ENCODE: [RequestField.MODEL_TYPE, RequestField.MESH, RequestField.PARAMETERS],
        EndpointType.ENCODE_RAW: [RequestField.MODEL_TYPE, RequestField.PARAMETERS],
        EndpointType.HORIZON_ANGLE: [],
        EndpointType.ZENITH_ANGLE: [],
        EndpointType.MERGE: [RequestField.SIMULATION, RequestField.ROOM_POLYGON, RequestField.WINDOWS],
        EndpointType.STATS_CALCULATE: [RequestField.DF_VALUES, RequestField.MASK],
        EndpointType.STATUS: []
    }
    _default = []

class EndpointOrchestratorMap(StandardMap):
    _content = {
        EndpointType.SIMULATE: SimulationOrchestrator,
        EndpointType.RUN: SimulationOrchestrator,
        EndpointType.ENCODE: EncodeOrchestrator
    }
    _default = Orchestrator