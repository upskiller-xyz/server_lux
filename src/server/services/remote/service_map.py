from __future__ import annotations
from typing import Dict

from .contracts import RemoteServiceRequest, ObstructionRequest, MergerRequest, StatsRequest, MainRequest, ModelRequest
from ...maps import StandardMap
from src.server.enums import ServiceName, EndpointType
from .base import RemoteService
from . import MergerService, EncoderService, DirectionAngleService, ReferencePointService, ObstructionService, ModelService, StatsService



class ServiceRegistryMap(StandardMap):
    """Maps service names to their corresponding service classes"""
    _content:Dict[ServiceName, type[RemoteService]] = {
        ServiceName.MERGER: MergerService,
        ServiceName.ENCODER: EncoderService,
        ServiceName.OBSTRUCTION: ObstructionService,
        ServiceName.MODEL: ModelService,
        ServiceName.STATS: StatsService
    }
    _default:type[RemoteService] = RemoteService

class EndpointServiceMap(StandardMap):
    """Maps endpoints to the sequence of services that should process them"""
    _content:Dict[EndpointType, list[type[RemoteService]]] = {
        EndpointType.RUN: [ReferencePointService, DirectionAngleService, ObstructionService, EncoderService, ModelService],
        EndpointType.MERGE : [MergerService],
        EndpointType.ENCODE: [ReferencePointService, DirectionAngleService, ObstructionService, EncoderService],
        EndpointType.ENCODE_RAW: [EncoderService],

        EndpointType.OBSTRUCTION: [ObstructionService],
        EndpointType.OBSTRUCTION_PARALLEL: [ObstructionService],
        EndpointType.OBSTRUCTION_MULTI: [ObstructionService],
        EndpointType.OBSTRUCTION_ALL: [ReferencePointService, DirectionAngleService, ObstructionService],
        EndpointType.HORIZON: [ObstructionService],
        EndpointType.ZENITH: [ObstructionService],
        EndpointType.SIMULATE: [ModelService],
        EndpointType.CALCULATE_DIRECTION: [DirectionAngleService],
        EndpointType.REFERENCE_POINT: [ReferencePointService],
        EndpointType.STATS_CALCULATE: [StatsService]

    }
    _default:list[type[RemoteService]] = [RemoteService]

class ServiceRequestMap(StandardMap):
    """Maps service names to their default request types"""
    _content:Dict[ServiceName, type[RemoteServiceRequest]] = {
        ServiceName.MERGER : MergerRequest,
        ServiceName.ENCODER: MainRequest,
        ServiceName.OBSTRUCTION: ObstructionRequest,
        ServiceName.MODEL: ModelRequest,
        ServiceName.STATS: StatsRequest

    }
    _default:type[RemoteServiceRequest] = MainRequest

class ServiceEndpointMap(StandardMap):
    """Maps service classes to their actual remote endpoint

    When a service is called during orchestration (e.g., ReferencePointService during /encode),
    this map determines which actual endpoint to call on the remote service.
    """
    _content: Dict[type[RemoteService], EndpointType] = {
        ReferencePointService: EndpointType.REFERENCE_POINT,
        DirectionAngleService: EndpointType.CALCULATE_DIRECTION,
        ObstructionService: EndpointType.OBSTRUCTION_PARALLEL,
        EncoderService: EndpointType.ENCODE,
        MergerService: EndpointType.MERGE,
        ModelService: EndpointType.RUN,
        StatsService: EndpointType.RUN
    }
    _default: EndpointType = EndpointType.RUN

