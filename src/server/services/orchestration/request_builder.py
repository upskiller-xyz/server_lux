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
        """Set mesh data (nested format: {"horizon": [...], "zenith": [...]})."""
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

        Extracts horizon and zenith from window_data if present and adds them at the top level
        so the orchestrator can detect and skip obstruction calculation.
        """
        params = request_data.get(RequestField.PARAMETERS.value, {})

        builder = (WindowRequestBuilder()
                .with_model_type(request_data.get(RequestField.MODEL_TYPE.value))
                .with_mesh(request_data.get(RequestField.MESH.value))
                .with_window(window_name, window_data)
                .with_room_polygon(params.get(RequestField.ROOM_POLYGON.value))
                .with_roof_height(params.get(RequestField.ROOF_HEIGHT.value))
                .with_floor_height(params.get(RequestField.FLOOR_HEIGHT.value)))
        built_request = builder.build()

        # Extract horizon and zenith from window_data if they exist
        # This allows per-window obstruction data to skip the obstruction service
        if isinstance(window_data, dict):
            if 'horizon' in window_data:
                built_request['horizon'] = window_data['horizon']
            if 'zenith' in window_data:
                built_request['zenith'] = window_data['zenith']

        return built_request
