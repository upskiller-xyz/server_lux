from typing import Any, Dict, Union

from src.server.interfaces.remote_interfaces import RemoteServiceRequest, RemoteServiceResponse
from ...interfaces.remote_interfaces import EncoderRequest, DirectionAngleRequest, DirectionAngleResponse, BinaryResponse, EncoderParameters
from ...enums import ServiceName, EndpointType
from .base import RemoteService


class EncoderService(RemoteService):
    """Service for encoding room data to images"""
    name: ServiceName = ServiceName.ENCODER

    @classmethod
    def _get_request(cls, endpoint:EndpointType):
        _map = {
            EndpointType.ENCODE: EncoderRequest,
            EndpointType.CALCULATE_DIRECTION: DirectionAngleRequest
        }
        return _map.get(endpoint, EncoderRequest)
    
    @classmethod
    def _get_response(cls, endpoint:EndpointType):
        _map = {
            EndpointType.ENCODE: BinaryResponse,
            EndpointType.CALCULATE_DIRECTION: DirectionAngleResponse
        }
        return _map.get(endpoint, BinaryResponse)

    @classmethod
    def run(cls, endpoint: EndpointType, request: RemoteServiceRequest, response_class: RemoteServiceResponse, file:Any=None) -> Union[bytes, Dict[str, float]]:
        """Run encoder service operation"""
        _rq = cls._get_request(endpoint)
        _rsp = cls._get_response(endpoint)
        request = _rq(**request.to_dict)

        if endpoint == EndpointType.ENCODE:
            return super().run_binary(endpoint, request, _rsp)
            
        return super().run(endpoint, request, _rsp)
