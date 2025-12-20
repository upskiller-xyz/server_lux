from typing import Dict, Any
import io
import numpy as np
import logging

from ...enums import NPZKey, RequestField

logger = logging.getLogger("logger")


class MaskExtractor:
    """Extracts mask data from NPZ encoder responses"""

    @staticmethod
    def extract_from_npz(npz_bytes: bytes, params: Dict[str, Any]) -> Dict[str, Any]:
        """Extract mask dictionary from NPZ bytes

        Args:
            npz_bytes: NPZ file as bytes
            params: Request parameters containing window information

        Returns:
            Dictionary mapping window names to mask arrays
        """
        try:
            npz_data = np.load(io.BytesIO(npz_bytes))
            keys = list(npz_data.keys())
            mask_keys = [k for k in keys if k.endswith(NPZKey.MASK_SUFFIX.value)]

            if not mask_keys:
                return {}

            masks = {}
            for mask_key in mask_keys:
                if mask_key == RequestField.MASK.value:
                    masks.update(MaskExtractor._extract_generic_mask(npz_data, mask_key, params))
                else:
                    window_name = mask_key.replace(NPZKey.MASK_SUFFIX.value, '')
                    masks[window_name] = npz_data[mask_key].tolist()

            return masks

        except Exception as e:
            logger.error(f"Failed to extract mask from encoder NPZ: {str(e)}")
            return {}

    @staticmethod
    def _extract_generic_mask(npz_data: Any, mask_key: str, params: Dict[str, Any]) -> Dict[str, Any]:
        """Extract generic mask and apply to all windows"""
        windows_dict = params.get(RequestField.PARAMETERS.value, {}).get(RequestField.WINDOWS.value, {})
        if not windows_dict:
            windows_dict = params.get(RequestField.WINDOWS.value, {})

        mask_data = npz_data[mask_key].tolist()
        return {window_name: mask_data for window_name in windows_dict.keys()}
