from typing import Dict, Any
from ...enums import ResponseStatus, ResponseKey


class ValidationResponseBuilder:
    """Builder for validation responses using Builder pattern - DRY principle

    Provides consistent validation response format across all validation operations.
    Follows Single Responsibility Principle - only builds validation responses.
    """

    @staticmethod
    def error(message: str) -> Dict[str, Any]:
        """Build validation error response

        Args:
            message: Error message

        Returns:
            Error response dictionary
        """
        return {
            ResponseKey.STATUS.value: ResponseStatus.ERROR.value,
            ResponseKey.ERROR.value: message
        }

    @staticmethod
    def success() -> Dict[str, Any]:
        """Build validation success response

        Returns:
            Success response dictionary
        """
        return {ResponseKey.STATUS.value: ResponseStatus.SUCCESS.value}
