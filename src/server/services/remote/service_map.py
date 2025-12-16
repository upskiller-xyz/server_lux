from __future__ import annotations
from typing import Dict
from ...maps import StandardMap
from src.server.enums import ServiceName
from . import RemoteService, MergerService, EncoderService, ObstructionService, ModelService, StatsService



class EndpointServiceMap(StandardMap):
    _content:Dict[ServiceName, RemoteService] = {
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
    _default:RemoteService = RemoteService
