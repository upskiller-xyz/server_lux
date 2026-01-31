import logging
import time
import numpy as np
from PIL import Image as PILImage
from ...remote.contracts import ModelResponse, ModelRequest
from ....enums import ResponseStatus, ResponseKey, RequestField, EndpointType
from ...remote import ModelService
from .base_handler import ProcessingHandler, WindowContext


class SimulationHandler(ProcessingHandler):
    """Handles model simulation step

    Runs model inference on encoded image.
    Updates context with simulation_result.
    Resizes and applies mask if available.
    """

    def __init__(self, model_service: ModelService):
        super().__init__()
        self._model = model_service

    def _process(self, context: WindowContext) -> dict:
        """Run model inference on encoded image

        Uses encoder_response.image as input and creates ModelResponse with result.
        """
        start_time = time.time()
        self._logger.info(f"[{context.window_name}] ⏱️  Starting model inference at {time.time():.3f}")

        # Execute model inference (using encoded image from encoder response)
        model_result = self._run_model(context)

        if model_result.get(ResponseKey.STATUS.value) == ResponseStatus.ERROR.value:
            return self._error(f"Model inference failed: {model_result.get(ResponseKey.ERROR.value)}")

        elapsed = time.time() - start_time
        self._logger.info(f"[{context.window_name}] ⏱️  Model inference completed in {elapsed:.2f}s")
        self._logger.info(f"[{context.window_name}] 🔍 Model result keys: {list(model_result.keys())}")

        # Parse model result into ModelResponse object
        try:
            model_response = ModelResponse.parse(model_result)
            context.model_response = model_response
            self._logger.info(f"[{context.window_name}] Created ModelResponse: shape={model_response.content.shape}")
        except Exception as e:
            self._logger.warning(f"[{context.window_name}] Failed to parse ModelResponse: {e}, using raw dict")
            context.model_response = None

        # Process mask if available (from encoder response)
        self._process_mask(context, model_result)

        # Store result (legacy compatibility)
        context.simulation_result = model_result

        return self._success()

    def _run_model(self, context: WindowContext) -> dict:
        """Execute model inference"""
        # Create ModelRequest with encoded image bytes
        request = ModelRequest(
            image=context.encoded_image_bytes,
            filename=f"encoded_{context.window_name}.png",
            invert_channels=context.invert_channels
        )

        # Call ModelService with proper interface
        return self._model.run(
            endpoint=EndpointType.RUN,
            request=request
        )

    def _process_mask(self, context: WindowContext, model_result: dict) -> None:
        """Process and resize mask to match simulation shape"""
        simulation = model_result.get(ResponseKey.RESULT.value)
        if simulation is None or not isinstance(simulation, list):
            return

        pred_array = np.array(simulation)
        pred_shape = pred_array.shape
        self._logger.info(f"[{context.window_name}] Prediction shape: {pred_shape}")

        # Resize mask if available
        if context.mask_array is not None:
            mask_array = self._resize_mask_to_simulation(
                context.mask_array,
                pred_shape,
                context.window_name
            )
            model_result[RequestField.MASK.value] = mask_array.tolist()
        else:
            model_result[RequestField.MASK.value] = None

    def _resize_mask_to_simulation(
        self,
        mask_array: np.ndarray,
        target_shape: tuple,
        window_name: str
    ) -> np.ndarray:
        """Resize mask to match simulation shape"""
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
