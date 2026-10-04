from abc import ABC, abstractmethod
from typing import List

from .config import ObstructionCalculationConfig, ObstructionResult, WindowGeometry


class IObstructionCalculator(ABC):
    """Interface for obstruction calculation strategies

    Defines contract for different calculation implementations.
    Follows Strategy pattern - allows switching between single-request and parallel approaches.
    """

    @abstractmethod
    async def calculate(
        self,
        window: WindowGeometry,
        mesh: List[List[float]],
        config: ObstructionCalculationConfig
    ) -> List[ObstructionResult]:
        """Calculate obstruction angles for all directions

        Args:
            window: Window geometry (position and orientation)
            mesh: Obstruction mesh data
            config: Calculation configuration

        Returns:
            List of obstruction results for each direction
        """
        pass
