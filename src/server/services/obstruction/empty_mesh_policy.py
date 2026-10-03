"""Policy for obstruction requests that carry no context geometry.

An absent or empty mesh means "nothing shades this window", which is an
unobstructed sky — obstruction angles of 0° in every direction. That answer is
known without any geometry, so the remote obstruction service is not called at
all: no HTTP round trip, no semaphore slot, no fan-out per window.
"""

import logging
from typing import Any, Dict, List, Union

from ...constants import ObstructionAngleDefaults, ObstructionRequestDefaults
from ...enums import ResponseKey

logger = logging.getLogger("logger")


class EmptyMeshPolicy:
    """Decides whether a mesh is empty and builds the unobstructed-sky answer.

    Stateless: the decision depends only on the mesh passed in, so every method
    is a classmethod and no instance is ever needed.
    """

    # Keys of the split mesh form ({"horizon": [...], "zenith": [...]}), which
    # is empty only when neither half carries geometry.
    _SPLIT_KEYS: tuple = (ResponseKey.HORIZON.value, ResponseKey.ZENITH.value)

    @classmethod
    def is_empty(cls, mesh: Any) -> bool:
        """True when a mesh carries no geometry and obstruction can be skipped.

        Covers every shape the mesh field accepts: missing (``None``), an empty
        JSON list, an empty split dict, and a zero-length binary payload.

        A non-empty binary mesh is never inspected — lux does not parse .npy /
        gzip payloads, so a valid file containing zero vertices cannot be
        recognised here. The obstruction service answers those correctly on its
        own (full sky when no geometry remains), so they take the remote path.
        """
        if mesh is None:
            return True
        if isinstance(mesh, (bytes, bytearray)):
            return len(mesh) == 0
        if isinstance(mesh, dict):
            return not any(mesh.get(key) for key in cls._SPLIT_KEYS)
        return not mesh

    @classmethod
    def unobstructed_angles(
        cls,
        window_name: str = ObstructionRequestDefaults.WINDOW_NAME,
        count: int = ObstructionAngleDefaults.EXPECTED_ANGLE_COUNT,
    ) -> Dict[str, Union[List[float], Dict[str, List[float]]]]:
        """Build the horizon/zenith response for an unobstructed window.

        Mirrors ObstructionService.run's output shape: flat lists for the
        default single-window name, ``{window_name: angles}`` otherwise.

        Args:
            window_name: Window the angles belong to
            count: Number of directions, matching the remote service's output

        Returns:
            Dict with ``horizon`` and ``zenith`` angle lists of ``count`` zeros
        """
        logger.info(
            "Empty mesh for window '%s': unobstructed sky, skipping obstruction service",
            window_name,
        )
        angles = [ObstructionRequestDefaults.UNOBSTRUCTED_ANGLE_DEGREES] * count

        if window_name == ObstructionRequestDefaults.WINDOW_NAME:
            return {
                ResponseKey.HORIZON.value: angles,
                ResponseKey.ZENITH.value: list(angles),
            }

        return {
            ResponseKey.HORIZON.value: {window_name: angles},
            ResponseKey.ZENITH.value: {window_name: list(angles)},
        }
