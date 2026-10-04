from typing import Any, Dict

from ...enums import ResponseKey, ResponseStatus


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
