from typing import Dict, Any
from ...enums import ResponseStatus, ResponseKey


class ValidationResponseBuilder:

    @staticmethod
    def error(message: str) -> Dict[str, Any]:
        return {
            ResponseKey.STATUS.value: ResponseStatus.ERROR.value,
            ResponseKey.ERROR.value: message
        }

    @staticmethod
    def success() -> Dict[str, Any]:
        return {ResponseKey.STATUS.value: ResponseStatus.SUCCESS.value}
