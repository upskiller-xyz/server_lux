# from typing import Dict, Any

# from src.server.config import SessionConfig
# from src.server.interfaces.remote_interfaces import RemoteServiceRequest, RemoteServiceResponse
# from ...enums import ServiceName, EndpointType
# from ...maps import BaseUrlMap
# from .base import RemoteService
# from ..http_client import HTTPClient


# class DaylightService(RemoteService):
#     """Service for daylight data operations"""
#     name: ServiceName = ServiceName.DAYLIGHT

#     @classmethod
#     def run(
#         cls,
#         endpoint: EndpointType,
#         request: RemoteServiceRequest,
#         response_class: type[RemoteServiceResponse], 
#         file:Any=None
#     ) -> Any:
#         """Template method for standard request/response flow

#         Args:
#             endpoint: Endpoint to call
#             request: Typed request object
#             response_class: Response class to parse with
#             http_client: HTTP client instance
#             base_url: Base URL for service

#         Returns:
#             Parsed response data
#         """
        
#         url = cls._get_url(endpoint)
#         cls._log_request(endpoint, url)
#         files = {"file": (file.filename, file.stream, file.content_type)}

#         response_dict = HTTPClient.post_multipart(url, files, request.to_dict)
#         # response_dict = HTTPClient.post(url, request.to_dict)
#         response = response_class(response_dict)
#         return response.parse()
    
