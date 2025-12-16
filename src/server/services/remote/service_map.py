from __future__ import annotations
from typing import Dict

from ....server.interfaces.remote_interfaces import RemoteServiceRequest, ObstructionRequest, MergerRequest, EncoderRequest, DirectionAngleRequest, StatsRequest, RemoteServiceResponse, ObstructionResponse, MergerResponse, EncoderResponse, DirectionAngleResponse, StatsResponse
from ...maps import StandardMap
from src.server.enums import ServiceName, EndpointType
from . import RemoteService, MergerService, EncoderService, ObstructionService, ModelService, StatsService



class ServiceServiceMap(StandardMap):
    _content:Dict[ServiceName, type[RemoteService]] = {
        ServiceName.MERGER : MergerService,
        ServiceName.ENCODER: EncoderService,
        ServiceName.ENCODER: EncoderService,
        ServiceName.OBSTRUCTION: ObstructionService,
        ServiceName.OBSTRUCTION: ObstructionService,
        ServiceName.OBSTRUCTION: ObstructionService,
        ServiceName.OBSTRUCTION: ObstructionService,
        ServiceName.MODEL: ModelService,
        ServiceName.STATS: StatsService
        
    }
    _default:type[RemoteService] = RemoteService

class EndpointServiceMap(StandardMap):
    _content:Dict[EndpointType, list[type[RemoteService]]] = {
        EndpointType.RUN: [ObstructionService, EncoderService, ModelService, MergerService],
        EndpointType.MERGE : [MergerService],
        EndpointType.ENCODE: [ObstructionService, EncoderService],
        EndpointType.ENCODE_RAW: [EncoderService],

        EndpointType.OBSTRUCTION: [ObstructionService],
        EndpointType.OBSTRUCTION_PARALLEL: [ObstructionService],
        EndpointType.OBSTRUCTION_MULTI: [ObstructionService],
        EndpointType.OBSTRUCTION_ALL: [ObstructionService],
        EndpointType.HORIZON_ANGLE: [ObstructionService],
        EndpointType.ZENITH_ANGLE: [ObstructionService],
        EndpointType.SIMULATE: [ModelService],
        EndpointType.CALCULATE_DIRECTION: [EncoderService],
        EndpointType.STATS_CALCULATE: [StatsService]
        
    }
    _default:list[type[RemoteService]] = [RemoteService]

class ServiceRequestMap(StandardMap):
    _content:Dict[type[RemoteService], type[RemoteServiceRequest]] = {
        ServiceName.MERGER : MergerRequest,
        ServiceName.ENCODER: EncoderRequest,
        ServiceName.OBSTRUCTION: ObstructionRequest,
        ServiceName.MODEL: ModelRequest,
        ServiceName.STATS: StatsRequest
        
    }
    _default:RemoteServiceRequest = RemoteServiceRequest

class ServiceResponseMap(StandardMap):
    _content:Dict[type[RemoteService], type[RemoteServiceResponse]] = {
        ServiceName.MERGER : MergerResponse,
        ServiceName.ENCODER: EncoderResponse,
        ServiceName.OBSTRUCTION: ObstructionResponse,
        ServiceName.MODEL: ModelResponse,
        ServiceName.STATS: StatsResponse
        
    }
    _default:RemoteServiceResponse = RemoteServiceResponse