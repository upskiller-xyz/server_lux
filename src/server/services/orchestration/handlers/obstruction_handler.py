import time
from ....interfaces import ILogger
from ....enums import ResponseStatus, ResponseKey
from ....constants import ObstructionAngleDefaults
from ...obstruction import ObstructionCalculationService
from ...remote import EncoderService
from ...helpers.direction_angle_resolver import DirectionAngleResolver, WindowPosition, RoomGeometry
from .base_handler import ProcessingHandler, WindowContext


class ObstructionHandler(ProcessingHandler):
    """Handles obstruction angle calculation step

    Calculates horizon and zenith angles for window.
    Updates context with direction_angle, horizon_angles, zenith_angles.
    """

    def __init__(
        self,
        obstruction_service: ObstructionCalculationService,
        encoder_service: EncoderService,
        logger: ILogger
    ):
        super().__init__(logger)
        self._obstruction = obstruction_service
        self._encoder = encoder_service

    def _process(self, context: WindowContext) -> dict:
        """Calculate obstruction angles"""
        start_time = time.time()
        self._logger.info(f"[{context.window_name}] Calculating obstruction angles at ({context.center_x:.2f}, {context.center_y:.2f}, {context.center_z:.2f})")
        self._logger.info(f"[{context.window_name}] Mesh size: {len(context.mesh)} triangles")

        # Resolve direction angle
        direction_angle = self._resolve_direction_angle(context)
        if direction_angle is None:
            return self._error("Failed to calculate direction_angle")

        context.direction_angle = direction_angle

        # Calculate obstruction angles
        obstruction_result = self._calculate_angles(context)
        if obstruction_result.get(ResponseKey.STATUS.value) == ResponseStatus.ERROR.value:
            return self._error(
                f"Obstruction calculation failed: {obstruction_result.get(ResponseKey.ERROR.value)}"
            )

        # Extract and validate angles
        result_data = obstruction_result.get(ResponseKey.DATA.value, {})
        horizon_angles = result_data.get(ResponseKey.HORIZON_ANGLES.value, [])
        zenith_angles = result_data.get(ResponseKey.ZENITH_ANGLES.value, [])

        if not self._validate_angle_counts(horizon_angles, zenith_angles, context.window_name):
            error_msg = f"Expected {ObstructionAngleDefaults.EXPECTED_ANGLE_COUNT} angles each, got horizon: {len(horizon_angles)}, zenith: {len(zenith_angles)}"
            return self._error(error_msg)

        # Store results in context
        context.horizon_angles = horizon_angles
        context.zenith_angles = zenith_angles

        elapsed = time.time() - start_time
        self._logger.info(f"[{context.window_name}] ⏱️  Obstruction calculation completed in {elapsed:.2f}s")

        return self._success()

    def _resolve_direction_angle(self, context: WindowContext) -> float:
        """Resolve direction angle for window"""
        window_pos = WindowPosition(
            x1=context.x1,
            y1=context.y1,
            x2=context.x2,
            y2=context.y2,
            direction_angle=context.direction_angle
        )
        room_geom = RoomGeometry(
            room_polygon=context.room_polygon,
            windows={}
        )
        return DirectionAngleResolver.resolve(
            context.window_name,
            window_pos,
            room_geom,
            self._encoder,
            self._logger
        )

    def _calculate_angles(self, context: WindowContext) -> dict:
        """Execute obstruction calculation"""
        self._logger.info(f"[{context.window_name}] ⏱️  Starting obstruction calculation at {time.time():.3f}")

        return self._obstruction.calculate_multi_direction(
            x=context.center_x,
            y=context.center_y,
            z=context.center_z,
            direction_angle=context.direction_angle,
            mesh=context.mesh,
            start_angle=ObstructionAngleDefaults.START_ANGLE_DEGREES,
            end_angle=ObstructionAngleDefaults.END_ANGLE_DEGREES,
            num_directions=ObstructionAngleDefaults.NUM_DIRECTIONS
        )

    def _validate_angle_counts(self, horizon: list, zenith: list, window_name: str) -> bool:
        """Validate angle array lengths"""
        expected = ObstructionAngleDefaults.EXPECTED_ANGLE_COUNT
        if len(horizon) != expected or len(zenith) != expected:
            self._logger.error(f"[{window_name}] Invalid angle counts")
            return False
        return True
