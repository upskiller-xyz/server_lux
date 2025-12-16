from typing import Dict, Any
from ...enums import RequestField, ResponseStatus, ResponseKey
from ...constants import MeshValidation
from .validation_response_builder import ValidationResponseBuilder


class ParameterValidator:
    """Validator for request parameters following Strategy pattern

    Uses Adapter-Map-Enum pattern for field validation.
    Follows Single Responsibility Principle - only validates parameters.
    """

    # Required window fields as class constant
    REQUIRED_WINDOW_FIELDS = [
        RequestField.X1,
        RequestField.Y1,
        RequestField.Z1,
        RequestField.X2,
        RequestField.Y2,
        RequestField.Z2,
        RequestField.WINDOW_FRAME_RATIO
    ]

    # Type validation map using Strategy pattern
    TYPE_VALIDATORS = {
        RequestField.WINDOWS: (dict, "Windows must be a dictionary"),
        RequestField.PARAMETERS: (dict, "Parameters must be a dictionary"),
    }

    @staticmethod
    def validate_required_field(
        value: Any,
        field: RequestField | str,
        expected_type: type = None,
        type_error_msg: str = None
    ) -> Dict[str, Any]:
        """Generic validator for required fields using Strategy pattern

        Args:
            value: Value to validate
            field: Field name (RequestField enum or string)
            expected_type: Expected type (e.g., dict, list)
            type_error_msg: Custom error message for type mismatch

        Returns:
            Validation response (success or error)
        """
        field_name = field.value if isinstance(field, RequestField) else field

        # Check if field exists
        if not value:
            return ValidationResponseBuilder.error(f"Missing required field: {field_name}")

        # Check type if specified
        if expected_type and not isinstance(value, expected_type):
            error_msg = type_error_msg or f"{field_name} must be a {expected_type.__name__}"
            return ValidationResponseBuilder.error(error_msg)

        return ValidationResponseBuilder.success()

    @staticmethod
    def validate_window_fields(window_name: str, window_data: Dict[str, Any]) -> Dict[str, Any]:
        """Validate required fields for a window

        Args:
            window_name: Name of the window
            window_data: Window data to validate

        Returns:
            Validation response (success or error)
        """
        for field_enum in ParameterValidator.REQUIRED_WINDOW_FIELDS:
            field = field_enum.value
            if field not in window_data:
                return ValidationResponseBuilder.error(
                    f"Window '{window_name}' missing required field: {field}"
                )
        return ValidationResponseBuilder.success()

    @staticmethod
    def validate_mesh(mesh: Any) -> Dict[str, Any]:
        """Validate mesh data

        Args:
            mesh: Mesh data to validate

        Returns:
            Validation response (success or error)
        """
        # Check existence
        result = ParameterValidator.validate_required_field(mesh, RequestField.MESH)
        if result.get(ResponseKey.STATUS.value) == ResponseStatus.ERROR.value:
            return result

        # Check specific mesh requirements - empty mesh is allowed
        if not isinstance(mesh, list) or len(mesh) < MeshValidation.MIN_TRIANGLES:
            return ValidationResponseBuilder.error(f"Mesh must be a list with at least {MeshValidation.MIN_TRIANGLES} points")

        return ValidationResponseBuilder.success()

    @staticmethod
    def validate_windows(windows: Any) -> Dict[str, Any]:
        """Validate windows structure

        Args:
            windows: Windows data to validate

        Returns:
            Validation response (success or error)
        """
        expected_type, type_error_msg = ParameterValidator.TYPE_VALIDATORS[RequestField.WINDOWS]
        return ParameterValidator.validate_required_field(
            windows,
            f"{RequestField.PARAMETERS.value}.{RequestField.WINDOWS.value}",
            expected_type,
            type_error_msg
        )

    @staticmethod
    def validate_parameters(parameters: Any) -> Dict[str, Any]:
        """Validate parameters structure

        Args:
            parameters: Parameters data to validate

        Returns:
            Validation response (success or error)
        """
        expected_type, type_error_msg = ParameterValidator.TYPE_VALIDATORS[RequestField.PARAMETERS]
        return ParameterValidator.validate_required_field(
            parameters,
            RequestField.PARAMETERS,
            expected_type,
            type_error_msg
        )

    @staticmethod
    def validate_model_type(model_type: Any) -> Dict[str, Any]:
        """Validate model_type

        Args:
            model_type: Model type to validate

        Returns:
            Validation response (success or error)
        """
        return ParameterValidator.validate_required_field(model_type, RequestField.MODEL_TYPE)
