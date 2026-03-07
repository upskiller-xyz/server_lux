from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, List

from ..enums import RequestField, ResponseKey, ResponseStatus


class IFieldValidator(ABC):
    """Interface for field validation strategies"""

    @abstractmethod
    def validate(self, request_data: Dict[str, Any], field: RequestField) -> Optional[str]:
        """Validate a specific field

        Args:
            request_data: Request data dictionary
            field: Field to validate

        Returns:
            Error message if validation fails, None if success
        """
        pass


class PresenceValidator(IFieldValidator):
    """Validates that a field is present in the request"""

    def validate(self, request_data: Dict[str, Any], field: RequestField) -> Optional[str]:
        if field.value not in request_data:
            return f"Missing required field: {field.value}"
        return None


class DictTypeValidator(IFieldValidator):
    """Validates that a field is a dictionary"""

    def validate(self, request_data: Dict[str, Any], field: RequestField) -> Optional[str]:
        value = request_data.get(field.value)
        if value is not None and not isinstance(value, dict):
            return f"Field '{field.value}' must be a dictionary"
        return None


class ListTypeValidator(IFieldValidator):
    """Validates that a field is a list"""

    def validate(self, request_data: Dict[str, Any], field: RequestField) -> Optional[str]:
        value = request_data.get(field.value)
        if value is not None and not isinstance(value, list):
            return f"Field '{field.value}' must be a list"
        return None


class ValidationStrategy:
    """Strategy for validating request fields using validator chain"""

    # Map fields to their specific validators
    FIELD_VALIDATORS: Dict[RequestField, List[IFieldValidator]] = {
        RequestField.PARAMETERS: [PresenceValidator(), DictTypeValidator()],
        RequestField.MESH: [PresenceValidator(), ListTypeValidator()],
    }

    @classmethod
    def validate_fields(cls, request_data: Dict[str, Any], required_fields: List[RequestField]) -> Optional[Dict[str, Any]]:
        """Validate all required fields using appropriate strategies

        Args:
            request_data: Request data dictionary
            required_fields: List of fields to validate

        Returns:
            Error response dict if validation fails, None if success
        """
        for field in required_fields:
            # Check presence first
            if field.value not in request_data:
                return cls._build_error_response(f"Missing required field: {field.value}")

            # Apply specific validators if configured
            validators = cls.FIELD_VALIDATORS.get(field, [])
            for validator in validators:
                error_msg = validator.validate(request_data, field)
                if error_msg:
                    return cls._build_error_response(error_msg)

        return None

    @staticmethod
    def _build_error_response(error_message: str) -> Dict[str, Any]:
        """Build standardized error response"""
        return {
            ResponseKey.STATUS.value: ResponseStatus.ERROR.value,
            ResponseKey.ERROR.value: error_message
        }
