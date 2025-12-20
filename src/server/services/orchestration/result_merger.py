from typing import Dict, Any, List, Tuple

from ...enums import RequestField


class ResultMerger:
    """Merges results from multiple window processing operations"""

    MERGEABLE_KEYS = [
        RequestField.DIRECTION_ANGLE.value,
        RequestField.REFERENCE_POINT.value,
        RequestField.OBSTRUCTION_ANGLE_HORIZON.value,
        RequestField.OBSTRUCTION_ANGLE_ZENITH.value
    ]

    def __init__(self, base_request: Dict[str, Any]):
        self._base_request = base_request
        self._merged_data = self._initialize_merged_data()

    def _initialize_merged_data(self) -> Dict[str, Any]:
        """Initialize merged data structure"""
        params = self._base_request.get(RequestField.PARAMETERS.value, {})
        merged = self._base_request.copy()
        merged[RequestField.PARAMETERS.value] = params.copy()

        for key in self.MERGEABLE_KEYS:
            merged[key] = {}

        merged[RequestField.MASK.value] = {}
        return merged

    def merge_window_results(self, window_results: List[Tuple[str, Dict[str, Any]]]) -> Dict[str, Any]:
        """Merge results from multiple windows

        Args:
            window_results: List of (window_name, result_dict) tuples

        Returns:
            Merged data dictionary
        """
        simulations = {}

        for window_name, result in window_results:
            if not isinstance(result, dict):
                continue

            self._merge_dict_fields(result)
            self._merge_mask(result)
            self._merge_simulation(window_name, result, simulations)

        if simulations:
            self._merged_data['simulations'] = simulations

        if RequestField.IMAGE.value in self._merged_data:
            del self._merged_data[RequestField.IMAGE.value]

        return self._merged_data

    def _merge_dict_fields(self, result: Dict[str, Any]) -> None:
        """Merge dictionary fields from a single result"""
        for key in self.MERGEABLE_KEYS:
            if key in result and isinstance(result[key], dict):
                self._merged_data[key].update(result[key])

    def _merge_mask(self, result: Dict[str, Any]) -> None:
        """Merge mask data from a single result"""
        if RequestField.MASK.value in result and isinstance(result[RequestField.MASK.value], dict):
            self._merged_data[RequestField.MASK.value].update(result[RequestField.MASK.value])

    def _merge_simulation(self, window_name: str, result: Dict[str, Any], simulations: Dict[str, Any]) -> None:
        """Merge simulation data from a single result"""
        if RequestField.SIMULATION.value in result:
            simulations[window_name] = result[RequestField.SIMULATION.value]
