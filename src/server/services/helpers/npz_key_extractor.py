from typing import List
from ...enums import NPZKey


class NPZKeyExtractor:

    @staticmethod
    def extract_keys(window_name: str, npz_keys: List[str]) -> tuple[str | None, str | None]:
        window_image_key = f"{window_name}{NPZKey.IMAGE_SUFFIX.value}"
        window_mask_key = f"{window_name}{NPZKey.MASK_SUFFIX.value}"
        if window_image_key in npz_keys:
            return (window_image_key, window_mask_key)

        if NPZKey.IMAGE.value in npz_keys:
            mask_key = NPZKey.MASK.value if NPZKey.MASK.value in npz_keys else None
            return (NPZKey.IMAGE.value, mask_key)

        image_keys = [
            k for k in npz_keys
            if k.endswith(NPZKey.IMAGE_SUFFIX.value) or k == NPZKey.IMAGE.value
        ]
        if image_keys:
            image_key = image_keys[0]
            mask_key = image_key.replace(NPZKey.IMAGE_SUFFIX.value, NPZKey.MASK_SUFFIX.value)
            return (image_key, mask_key)

        return (None, None)
