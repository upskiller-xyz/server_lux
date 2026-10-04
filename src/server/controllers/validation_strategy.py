from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional

from ..enums import RequestField, ValidationMessage
from ..exceptions import RequestValidationError


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
            return ValidationMessage.MISSING_FIELD.value.format(field=field.value)
        return None


class DictTypeValidator(IFieldValidator):
    """Validates that a field is a dictionary"""

    def validate(self, request_data: Dict[str, Any], field: RequestField) -> Optional[str]:
        value = request_data.get(field.value)
        if value is not None and not isinstance(value, dict):
            return ValidationMessage.MUST_BE_DICT.value.format(field=field.value)
        return None


class ListTypeValidator(IFieldValidator):
    """Validates that a field is a list"""

    def validate(self, request_data: Dict[str, Any], field: RequestField) -> Optional[str]:
        value = request_data.get(field.value)
        if value is not None and not isinstance(value, list):
            return ValidationMessage.MUST_BE_LIST.value.format(field=field.value)
        return None


class MeshTypeValidator(IFieldValidator):
    """Validates the mesh field.

    The mesh may arrive as a JSON list of ``[x, y, z]`` vertices, as a split
    dict (``{"horizon": [...], "zenith": [...]}``, the form
    ObstructionMultiRequest sends), or as a raw binary payload (.npy / gzip)
    that lux forwards untouched to obstruction's binary endpoint without ever
    parsing it. All three are accepted here.
    """

    _ACCEPTED_TYPES: tuple = (list, dict, bytes, bytearray)

    def validate(self, request_data: Dict[str, Any], field: RequestField) -> Optional[str]:
        value = request_data.get(field.value)
        if value is not None and not isinstance(value, self._ACCEPTED_TYPES):
            return ValidationMessage.MUST_BE_MESH.value.format(field=field.value)
        return None


class ValidationStrategy:
    """Strategy for validating request fields using validator chain"""

    # Map fields to their validator chain. A field listed here is validated by
    # its chain alone, so whether it may be omitted is expressed by including
    # PresenceValidator or not — mesh is optional (an absent mesh means an
    # unobstructed sky, see EmptyMeshPolicy) but still type-checked when sent.
    # Fields without a chain fall back to requiring presence.
    FIELD_VALIDATORS: Dict[RequestField, List[IFieldValidator]] = {
        RequestField.PARAMETERS: [PresenceValidator(), DictTypeValidator()],
        RequestField.MESH: [MeshTypeValidator()],
    }

    @classmethod
    def validate_fields(cls, request_data: Dict[str, Any], required_fields: List[RequestField]) -> None:
        """Validate all required fields using appropriate strategies

        Args:
            request_data: Request data dictionary
            required_fields: List of fields to validate

        Raises:
            RequestValidationError: if a required field is missing or malformed.
                The exception path maps client-input errors to HTTP 400.
        """
        for field in required_fields:
            validators = cls.FIELD_VALIDATORS.get(field)

            # No chain configured: presence is the whole contract for this field.
            if not validators:
                if field.value not in request_data:
                    raise RequestValidationError(
                        ValidationMessage.MISSING_FIELD.value.format(field=field.value)
                    )
                continue

            for validator in validators:
                error_msg = validator.validate(request_data, field)
                if error_msg:
                    raise RequestValidationError(error_msg)
