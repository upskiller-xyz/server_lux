from typing import Dict, Any

from ...enums import RequestField


class WindowRequestBuilder:
    """Builder for constructing single window requests"""

    def __init__(self):
        self._request = {}

    def with_model_type(self, model_type: Any) -> 'WindowRequestBuilder':
        if model_type is not None:
            self._request[RequestField.MODEL_TYPE.value] = model_type
        return self

    def with_mesh(self, mesh: Any) -> 'WindowRequestBuilder':
        """Set mesh data as a flat list of triangle vertices [[x,y,z], ...]."""
        if mesh is not None:
            self._request[RequestField.MESH.value] = mesh
        return self

    def with_window(self, window_name: str, window_data: Any) -> 'WindowRequestBuilder':
        if RequestField.PARAMETERS.value not in self._request:
            self._request[RequestField.PARAMETERS.value] = {}

        self._request[RequestField.PARAMETERS.value][RequestField.WINDOWS.value] = {
            window_name: window_data
        }
        return self

    def with_room_polygon(self, room_polygon: Any) -> 'WindowRequestBuilder':
        if RequestField.PARAMETERS.value not in self._request:
            self._request[RequestField.PARAMETERS.value] = {}

        if room_polygon is not None:
            self._request[RequestField.PARAMETERS.value][RequestField.ROOM_POLYGON.value] = room_polygon
        return self

    def with_roof_height(self, roof_height: Any) -> 'WindowRequestBuilder':
        if RequestField.PARAMETERS.value not in self._request:
            self._request[RequestField.PARAMETERS.value] = {}

        if roof_height is not None:
            self._request[RequestField.PARAMETERS.value][RequestField.ROOF_HEIGHT.value] = roof_height
        return self

    def with_floor_height(self, floor_height: Any) -> 'WindowRequestBuilder':
        if RequestField.PARAMETERS.value not in self._request:
            self._request[RequestField.PARAMETERS.value] = {}

        if floor_height is not None:
            self._request[RequestField.PARAMETERS.value][RequestField.FLOOR_HEIGHT.value] = floor_height
        return self

    def build(self) -> Dict[str, Any]:
        return self._request

    @staticmethod
    def from_request_data(request_data: Dict[str, Any], window_name: str, window_data: Any) -> Dict[str, Any]:
        """Convenience method to build a window request from existing request data

        Extracts horizon, zenith, and direction_angle from window_data if present 
        and adds them at the top level so the orchestrator can use them and skip 
        unnecessary service calls.
        
        Uses Enumerator Pattern - all string keys use RequestField/ResponseKey enums.
        """
        params = request_data.get(RequestField.PARAMETERS.value, {})

        built_request = (WindowRequestBuilder()
                .with_model_type(request_data.get(RequestField.MODEL_TYPE.value))
                .with_mesh(request_data.get(RequestField.MESH.value))
                .with_window(window_name, window_data)
                .with_room_polygon(params.get(RequestField.ROOM_POLYGON.value))
                .with_roof_height(params.get(RequestField.ROOF_HEIGHT.value))
                .with_floor_height(params.get(RequestField.FLOOR_HEIGHT.value))).build()

        # Extract horizon, zenith and direction_angle from window_data if present.
        # horizon/zenith are wrapped in {window_name: value} so Parameters._normalize_to_dict()
        # can look up angles by window name. direction_angle is kept as a flat value.
        if isinstance(window_data, dict):
            if RequestField.HORIZON.value in window_data:
                built_request[RequestField.HORIZON.value] = {window_name: window_data[RequestField.HORIZON.value]}
            if RequestField.ZENITH.value in window_data:
                built_request[RequestField.ZENITH.value] = {window_name: window_data[RequestField.ZENITH.value]}
            direction_angle = window_data.get(RequestField.DIRECTION_ANGLE.value)
            if direction_angle is not None:
                built_request[RequestField.DIRECTION_ANGLE.value] = direction_angle

        return built_request
