from __future__ import annotations
from typing import Any, Dict
from .enums import ServiceName, ServicePort, EndpointType, DeploymentMode, ServiceHost


class StandardMap:
    _content:Dict[Any, Any] = {}
    _default: Any
    @classmethod
    def get(cls, key:Any)->Any:
        return cls._content.get(key, cls._default)
    
class BaseUrlMap(StandardMap):
    _content:Dict[DeploymentMode, ServiceHost] = {
        DeploymentMode.PRODUCTION: ServiceHost.PRODUCTION_SERVER,
        DeploymentMode.LOCAL: ServiceHost.LOCALHOST
    }
    _default:ServicePort = ServicePort.MAIN_SERVER

class PortMap(StandardMap):
    _content:Dict[ServiceName, ServicePort] = {
        ServiceName.MERGER: ServicePort.MERGER,
        ServiceName.ENCODER: ServicePort.ENCODER,
        ServiceName.OBSTRUCTION: ServicePort.OBSTRUCTION,
        ServiceName.MODEL: ServicePort.MODEL,
        ServiceName.STATS: ServicePort.STATS
    }
    _default:ServicePort = ServicePort.MAIN_SERVER

class EndpointServiceMap(StandardMap):
    _content:Dict[EndpointType, ServiceName] = {
        EndpointType.MERGE: ServiceName.MERGER,
        EndpointType.ENCODE: ServiceName.ENCODER,
        EndpointType.CALCULATE_DIRECTION: ServiceName.ENCODER,
        EndpointType.OBSTRUCTION: ServiceName.OBSTRUCTION,
        EndpointType.OBSTRUCTION_ALL: ServiceName.OBSTRUCTION,
        EndpointType.OBSTRUCTION_MULTI: ServiceName.OBSTRUCTION,
        EndpointType.OBSTRUCTION_PARALLEL: ServiceName.OBSTRUCTION,
        EndpointType.SIMULATE: ServiceName.MODEL,
        EndpointType.STATS_CALCULATE: ServiceName.STATS
        
    }
    _default:Any = ServiceName.ENCODER
    