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


    