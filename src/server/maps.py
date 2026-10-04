from __future__ import annotations

from typing import Any, Dict

from .enums import (
    AuthType,
    DeploymentMode,
    LogMessage,
    ServiceHost,
    ServiceName,
    ServicePort,
)


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


    

class AuthTypeMessageMap(StandardMap):
    """Startup log line describing the active authentication mode."""
    _content: Dict[AuthType, str] = {
        AuthType.NONE: LogMessage.AUTH_NONE.value,
        AuthType.TOKEN: LogMessage.AUTH_TOKEN.value,
        AuthType.AUTH0: LogMessage.AUTH_AUTH0.value,
    }
    _default: str = LogMessage.AUTH_UNKNOWN.value
