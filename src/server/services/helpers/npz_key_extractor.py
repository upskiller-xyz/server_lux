from typing import List
from ...enums import NPZKey


class NPZKeyExtractor:
    """Extracts image and mask keys from NPZ data using Strategy pattern

    Handles 3 key patterns:
    1. Window-specific: {window_name}_image, {window_name}_mask
    2. Generic: image, mask
    3. First available: any key ending with _image, _mask

    Follows Single Responsibility Principle - only extracts NPZ keys.
    """

    @staticmethod
    def extract_keys(window_name: str, npz_keys: List[str]) -> tuple[str | None, str | None]:
        """Extract image and mask keys using adapter-map pattern

        Args:
            window_name: Name of the window
            npz_keys: List of available keys in NPZ file

        Returns:
            Tuple of (image_key, mask_key) or (None, None) if not found
        """
        # Pattern 1: Window-specific keys
        window_image_key = f"{window_name}{NPZKey.IMAGE_SUFFIX.value}"
        window_mask_key = f"{window_name}{NPZKey.MASK_SUFFIX.value}"
        if window_image_key in npz_keys:
            return (window_image_key, window_mask_key)

        # Pattern 2: Generic keys (single window)
        if NPZKey.IMAGE.value in npz_keys:
            mask_key = NPZKey.MASK.value if NPZKey.MASK.value in npz_keys else None
            return (NPZKey.IMAGE.value, mask_key)

        # Pattern 3: First available with _image suffix
        image_keys = [
            k for k in npz_keys
            if k.endswith(NPZKey.IMAGE_SUFFIX.value) or k == NPZKey.IMAGE.value
        ]
        if image_keys:
            image_key = image_keys[0]
            mask_key = image_key.replace(NPZKey.IMAGE_SUFFIX.value, NPZKey.MASK_SUFFIX.value)
            return (image_key, mask_key)

        # No valid key found
        return (None, None)
