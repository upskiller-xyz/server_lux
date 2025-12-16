import time
import numpy as np
from PIL import Image as PILImage
from ....interfaces import ILogger
from ....enums import ResponseStatus, ResponseKey, RequestField
from ...remote import ModelService
from .base_handler import ProcessingHandler, WindowContext


class SimulationHandler(ProcessingHandler):
    """Handles model simulation step

    Runs model inference on encoded image.
    Updates context with simulation_result.
    Resizes and applies mask if available.
    """

    def __init__(self, model_service: ModelService, logger: ILogger):
        super().__init__(logger)
        self._model = model_service

    def _process(self, context: WindowContext) -> dict:
        """Run model inference on encoded image"""
        start_time = time.time()
        self._logger.info(f"[{context.window_name}] ⏱️  Starting model inference at {time.time():.3f}")

        # Execute model inference
        model_result = self._run_model(context)

        if model_result.get(ResponseKey.STATUS.value) == ResponseStatus.ERROR.value:
            return self._error(f"Model inference failed: {model_result.get(ResponseKey.ERROR.value)}")

        elapsed = time.time() - start_time
        self._logger.info(f"[{context.window_name}] ⏱️  Model inference completed in {elapsed:.2f}s")
        self._logger.info(f"[{context.window_name}] 🔍 Model result keys: {list(model_result.keys())}")

        # Process mask if available
        self._process_mask(context, model_result)

        # Store result
        context.simulation_result = model_result

        return self._success()

    def _run_model(self, context: WindowContext) -> dict:
        """Execute model inference"""
        return self._model.run(
            image_bytes=context.encoded_image_bytes,
            filename=f"encoded_{context.window_name}.png",
            invert_channels=context.invert_channels
        )

    def _process_mask(self, context: WindowContext, model_result: dict) -> None:
        """Process and resize mask to match prediction shape"""
        prediction = model_result.get(ResponseKey.PREDICTION.value)
        if prediction is None or not isinstance(prediction, list):
            return

        pred_array = np.array(prediction)
        pred_shape = pred_array.shape
        self._logger.info(f"[{context.window_name}] Prediction shape: {pred_shape}")

        # Resize mask if available
        if context.mask_array is not None:
            mask_array = self._resize_mask_to_prediction(
                context.mask_array,
                pred_shape,
                context.window_name
            )
            model_result[RequestField.MASK.value] = mask_array.tolist()
        else:
            model_result[RequestField.MASK.value] = None

    def _resize_mask_to_prediction(
        self,
        mask_array: np.ndarray,
        target_shape: tuple,
        window_name: str
    ) -> np.ndarray:
        """Resize mask to match prediction shape"""
        mask_shape = mask_array.shape
        self._logger.info(f"[{window_name}] Mask shape before resize: {mask_shape}")

        if mask_shape == target_shape:
            return mask_array

        # Resize mask using nearest neighbor interpolation
        mask_img = PILImage.fromarray(mask_array.astype(np.uint8))
        mask_resized = mask_img.resize((target_shape[1], target_shape[0]), PILImage.NEAREST)
        resized_array = np.array(mask_resized)

        self._logger.info(f"[{window_name}] Resized mask from {mask_shape} to {resized_array.shape}")
        return resized_array
