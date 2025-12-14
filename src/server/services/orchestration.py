from typing import Dict, Any, List
import concurrent.futures
import time
import math
import os
import base64
import numpy as np
from io import BytesIO
import io
from PIL import Image
from ..interfaces import ILogger
from .remote_service import ColorManageService, DaylightService, ObstructionService, EncoderService, PostprocessService, ModelService
from .obstruction_calculation import ObstructionCalculationService
from ..exceptions import ServiceConnectionError, ServiceTimeoutError, ServiceResponseError, ServiceAuthorizationError
from ..enums import ResponseStatus, ResponseKey


class ParameterValidator:
    """Validator for request parameters following Strategy pattern"""

    @staticmethod
    def validate_window_fields(window_name: str, window_data: Dict[str, Any]) -> Dict[str, Any]:
        """Validate required fields for a window"""
        # Updated for encoder v2.0.1 - only requires position and window_frame_ratio
        required_fields = ["x1", "y1", "z1", "x2", "y2", "z2", "window_frame_ratio"]
        for field in required_fields:
            if field not in window_data:
                return {
                    ResponseKey.STATUS.value: ResponseStatus.ERROR.value,
                    ResponseKey.ERROR.value: f"Window '{window_name}' missing required field: {field}"
                }
        return {ResponseKey.STATUS.value: ResponseStatus.SUCCESS.value}

    @staticmethod
    def validate_mesh(mesh: Any) -> Dict[str, Any]:
        """Validate mesh data"""
        if not mesh:
            return {
                ResponseKey.STATUS.value: ResponseStatus.ERROR.value,
                ResponseKey.ERROR.value: "Missing required field: mesh"
            }
        if not isinstance(mesh, list) or len(mesh) < 3:
            return {
                ResponseKey.STATUS.value: ResponseStatus.ERROR.value,
                ResponseKey.ERROR.value: "Mesh must contain at least 3 points"
            }
        return {ResponseKey.STATUS.value: ResponseStatus.SUCCESS.value}

    @staticmethod
    def validate_windows(windows: Any) -> Dict[str, Any]:
        """Validate windows structure"""
        if not windows:
            return {
                ResponseKey.STATUS.value: ResponseStatus.ERROR.value,
                ResponseKey.ERROR.value: "Missing required field: parameters.windows"
            }
        if not isinstance(windows, dict):
            return {
                ResponseKey.STATUS.value: ResponseStatus.ERROR.value,
                ResponseKey.ERROR.value: "Windows must be a dictionary"
            }
        return {ResponseKey.STATUS.value: ResponseStatus.SUCCESS.value}

    @staticmethod
    def validate_parameters(parameters: Any) -> Dict[str, Any]:
        """Validate parameters structure"""
        if not parameters:
            return {
                ResponseKey.STATUS.value: ResponseStatus.ERROR.value,
                ResponseKey.ERROR.value: "Missing required field: parameters"
            }
        if not isinstance(parameters, dict):
            return {
                ResponseKey.STATUS.value: ResponseStatus.ERROR.value,
                ResponseKey.ERROR.value: "Parameters must be a dictionary"
            }
        return {ResponseKey.STATUS.value: ResponseStatus.SUCCESS.value}

    @staticmethod
    def validate_model_type(model_type: Any) -> Dict[str, Any]:
        """Validate model_type"""
        if not model_type:
            return {
                ResponseKey.STATUS.value: ResponseStatus.ERROR.value,
                ResponseKey.ERROR.value: "Missing required field: model_type"
            }
        return {ResponseKey.STATUS.value: ResponseStatus.SUCCESS.value}


class OrchestrationService:
    """Service for orchestrating multiple remote service calls"""

    def __init__(
        self,
        colormanage_service: ColorManageService,
        daylight_service: DaylightService,
        logger: ILogger
    ):
        self._colormanage = colormanage_service
        self._daylight = daylight_service
        self._logger = logger

    def get_df_rgb(self, file: Any, form_data: Dict[str, Any]) -> Dict[str, Any]:
        """Get dataframe and convert to RGB (get_df + to_rgb) with file upload"""
        self._logger.info("Orchestrating get_df_rgb operation")

        # Step 1: Get dataframe from daylight service
        df_result = self._daylight.get_df(file, form_data)

        if df_result.get("status") == "error":
            self._logger.error("get_df call failed")
            return df_result

        # Step 2: Convert result to RGB
        # Assuming df_result contains the data to convert
        data_to_convert = df_result.get("data")
        if not data_to_convert:
            self._logger.error("No data received from get_df")
            return {"status": "error", "error": "No data from get_df"}

        colorscale = form_data.get("colorscale", "df")
        rgb_result = self._colormanage.to_rgb(data_to_convert, colorscale)

        return rgb_result


class RunOrchestrationService:
    """Service for orchestrating the complete run workflow:
    obstruction angles → encoding → daylight simulation → postprocessing"""

    def __init__(
        self,
        obstruction_service: ObstructionService,
        obstruction_calculation_service: ObstructionCalculationService,
        encoder_service: EncoderService,
        daylight_service: DaylightService,
        model_service: ModelService,
        postprocess_service: PostprocessService,
        merger_service: 'MergerService',
        logger: ILogger
    ):
        self._obstruction = obstruction_service  # Legacy remote service (kept for compatibility)
        self._obstruction_calculation = obstruction_calculation_service  # New parallel service
        self._encoder = encoder_service
        self._daylight = daylight_service
        self._model = model_service
        self._postprocess = postprocess_service
        self._merger = merger_service
        self._logger = logger

    def _is_local_deployment(self) -> bool:
        """Check if running in local deployment mode"""
        deployment_mode = os.getenv("DEPLOYMENT_MODE", "local")
        return deployment_mode == "local"

    def _process_single_window(
        self,
        window_name: str,
        window_data: Dict[str, Any],
        model_type: str,
        parameters: Dict[str, Any],
        mesh: List,
        translation: Dict[str, float],
        rotation: List[float]
    ) -> Dict[str, Any]:
        """Process a single window: obstruction → encoding → simulation

        Args:
            window_name: Name/identifier of the window
            window_data: Window parameters
            model_type: Model type for encoding
            parameters: Room parameters
            mesh: Obstruction mesh
            translation: Translation parameters
            rotation: Rotation parameters

        Returns:
            Result dictionary with window_name and simulation result or error
        """
        self._logger.info(f"Processing window: {window_name}")

        try:
            # Step 1: Calculate window center position
            x = (window_data.get("x1", 0) + window_data.get("x2", 0)) / 2
            y = (window_data.get("y1", 0) + window_data.get("y2", 0)) / 2
            z = (window_data.get("z1", 0) + window_data.get("z2", 0)) / 2

            # Step 2: Calculate obstruction angles for this window using parallel service
            obstruction_start = time.time()
            self._logger.info(f"[{window_name}] Calculating obstruction angles at ({x:.2f}, {y:.2f}, {z:.2f}) with parallel service")
            self._logger.info(f"[{window_name}] Mesh size: {len(mesh)} triangles")

            # Determine direction_angle: use provided value or calculate from encoder service
            # Priority 1: Check if direction_angle is in window_data
            if "direction_angle" in window_data:
                direction_angle = window_data.get("direction_angle")
                self._logger.info(f"[{window_name}] Using direction_angle from window_data: {direction_angle:.4f} rad ({math.degrees(direction_angle):.2f}°)")
            # Priority 2: Check if direction_angle is in parameters (top-level)
            elif "direction_angle" in parameters:
                direction_angle = parameters.get("direction_angle")
                self._logger.info(f"[{window_name}] Using direction_angle from parameters: {direction_angle:.4f} rad ({math.degrees(direction_angle):.2f}°)")
            else:
                # Priority 3: Calculate direction angle using encoder service's calculate-direction endpoint
                self._logger.info(f"[{window_name}] direction_angle not provided, calling encoder service to calculate it")
                calc_params = {
                    "room_polygon": parameters.get("room_polygon"),
                    "windows": {
                        window_name: {
                            "x1": window_data.get("x1"),
                            "y1": window_data.get("y1"),
                            "x2": window_data.get("x2"),
                            "y2": window_data.get("y2")
                        }
                    }
                }
                direction_result = self._encoder.calculate_direction_angles(calc_params)
                direction_angle = direction_result.get("direction_angles", {}).get(window_name)

                if direction_angle is None:
                    self._logger.error(f"[{window_name}] Failed to calculate direction_angle from encoder service")
                    return {
                        ResponseKey.WINDOW_NAME.value: window_name,
                        ResponseKey.STATUS.value: ResponseStatus.ERROR.value,
                        ResponseKey.ERROR.value: "Failed to calculate direction_angle"
                    }

                self._logger.info(f"[{window_name}] Calculated direction_angle from encoder service: {direction_angle:.4f} rad ({math.degrees(direction_angle):.2f}°)")

            # Use parallel obstruction calculation service
            self._logger.info(f"[{window_name}] ⏱️  Starting obstruction calculation at {time.time():.3f}")

            # Save obstruction request
            import json
            import os
            from datetime import datetime
            os.makedirs("./tmp", exist_ok=True)
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")[:-3]  # Include milliseconds
            obstruction_request = {
                "x": x, "y": y, "z": z,
                "direction_angle": direction_angle,
                "mesh": mesh,
                "start_angle": 17.5,
                "end_angle": 162.5,
                "num_directions": 64
            }
            with open(f"./tmp/obstruction_request_{window_name}_{timestamp}.json", "w") as f:
                json.dump(obstruction_request, f, indent=2)

            obstruction_result = self._obstruction_calculation.calculate_multi_direction(
                x=x, y=y, z=z,
                direction_angle=direction_angle,
                mesh=mesh,
                start_angle=17.5,
                end_angle=162.5,
                num_directions=64
            )

            # Save obstruction response
            with open(f"./tmp/obstruction_response_{window_name}_{timestamp}.json", "w") as f:
                json.dump(obstruction_result, f, indent=2)

            obstruction_time = time.time() - obstruction_start
            self._logger.info(f"[{window_name}] ⏱️  Obstruction calculation completed in {obstruction_time:.2f}s")

            if obstruction_result.get("status") == "error":
                self._logger.error(f"[{window_name}] Obstruction calculation failed")
                return {
                    "window_name": window_name,
                    "status": "error",
                    "error": f"Obstruction calculation failed: {obstruction_result.get('error')}"
                }

            # Extract angles from the result data
            result_data = obstruction_result.get("data", {})
            horizon_angles = result_data.get("horizon_angles", [])
            zenith_angles = result_data.get("zenith_angles", [])

            if len(horizon_angles) != 64 or len(zenith_angles) != 64:
                error_msg = f"Expected 64 angles each, got horizon: {len(horizon_angles)}, zenith: {len(zenith_angles)}"
                self._logger.error(f"[{window_name}] {error_msg}")
                return {
                    "window_name": window_name,
                    "status": "error",
                    "error": error_msg
                }

            # Step 3: Create parameters with single window enhanced with obstruction angles
            single_window_params = parameters.copy()

            # Prepare window data for encoder v2.0.1
            # Only send required fields: position (x1,y1,z1,x2,y2,z2), window_frame_ratio, direction_angle, and obstruction angles
            encoder_window_data = {
                "x1": window_data.get("x1"),
                "y1": window_data.get("y1"),
                "z1": window_data.get("z1"),
                "x2": window_data.get("x2"),
                "y2": window_data.get("y2"),
                "z2": window_data.get("z2"),
                "window_frame_ratio": window_data.get("window_frame_ratio"),
                "direction_angle": direction_angle,
                "obstruction_angle_horizon": horizon_angles,
                "obstruction_angle_zenith": zenith_angles
            }

            single_window_params["windows"] = {
                window_name: encoder_window_data
            }

            # Step 4: Encode with obstruction angles
            encode_start = time.time()
            self._logger.info(f"[{window_name}] ⏱️  Starting encoding at {time.time():.3f}")
            self._logger.info(f"[{window_name}] Encoding room with obstruction angles (direction_angle={direction_angle:.4f} rad)")
            self._logger.info(f"[{window_name}] Sending to encoder: horizon_angles type={type(horizon_angles)}, length={len(horizon_angles)}")
            self._logger.info(f"[{window_name}] Sending to encoder: zenith_angles type={type(zenith_angles)}, length={len(zenith_angles)}")
            self._logger.info(f"[{window_name}] Sample horizon values: {horizon_angles[:3]}")

            # Save encoder request
            encoder_request = {
                "model_type": model_type,
                "parameters": single_window_params
            }
            with open(f"./tmp/encoder_request_{window_name}_{timestamp}.json", "w") as f:
                json.dump(encoder_request, f, indent=2)

            encoded_image_bytes = self._encoder.encode(
                model_type=model_type,
                parameters=single_window_params
            )

            encode_time = time.time() - encode_start
            self._logger.info(f"[{window_name}] ⏱️  Encoding completed in {encode_time:.2f}s, response size: {len(encoded_image_bytes)} bytes")

            # Log what we received from encoder
            self._logger.info(f"[{window_name}] 🔍 Encoder response type: {type(encoded_image_bytes)}")
            self._logger.info(f"[{window_name}] 🔍 First 8 bytes: {encoded_image_bytes[:8].hex() if len(encoded_image_bytes) >= 8 else 'N/A'}")

            # Check if response is NPZ format (NumPy compressed archive)
            # NPZ files start with 'PK' (0x504b) - ZIP file signature
            if encoded_image_bytes[:2] == b'PK':
                self._logger.info(f"[{window_name}] 📦 Detected NPZ format from encoder (new format)")

                npz_data = np.load(io.BytesIO(encoded_image_bytes))
                keys = list(npz_data.keys())
                self._logger.info(f"[{window_name}] NPZ keys: {keys}")

                # Find image and mask keys for this window
                # Try different key patterns in order of preference:
                # 1. window_name_image / window_name_mask
                # 2. Generic "image" / "mask"
                # 3. Any key ending with _image / _mask

                image_key = None
                mask_key = None

                # Pattern 1: window-specific keys
                if f"{window_name}_image" in keys:
                    image_key = f"{window_name}_image"
                    mask_key = f"{window_name}_mask"
                    self._logger.info(f"[{window_name}] Using window-specific keys")
                # Pattern 2: generic keys (single window encoding)
                elif "image" in keys:
                    image_key = "image"
                    mask_key = "mask" if "mask" in keys else None
                    self._logger.info(f"[{window_name}] Using generic keys (single window)")
                # Pattern 3: first available with _image suffix
                else:
                    image_keys = [k for k in keys if k.endswith('_image') or k == 'image']
                    if image_keys:
                        image_key = image_keys[0]
                        mask_key = image_key.replace('_image', '_mask')
                        self._logger.info(f"[{window_name}] Using first available image key: {image_key}")

                if not image_key:
                    self._logger.error(f"[{window_name}] No image key found in NPZ")
                    return {
                        "window_name": window_name,
                        "status": "error",
                        "error": f"No image found in encoder NPZ response. Available keys: {keys}"
                    }

                # Extract image array
                image_array = npz_data[image_key]
                self._logger.info(f"[{window_name}] Extracted image from NPZ: shape={image_array.shape}, dtype={image_array.dtype}")

                # Extract and save mask if available (temporary debugging)
                mask_array = None
                if mask_key and mask_key in npz_data:
                    mask_array = npz_data[mask_key]
                    self._logger.info(f"[{window_name}] Extracted mask from NPZ: shape={mask_array.shape}, dtype={mask_array.dtype}")
                    # Save mask temporarily for debugging
                    from PIL import Image as PILImage
                    mask_img = PILImage.fromarray(mask_array.astype(np.uint8) * 255)
                    mask_filename = f"./tmp/mask_{window_name}.png"
                    mask_img.save(mask_filename)
                    self._logger.info(f"[{window_name}] 💾 Saved mask to {mask_filename}")
                else:
                    self._logger.warning(f"[{window_name}] No mask found in NPZ")

                # Convert numpy array to PNG bytes for model service
                

                # Ensure uint8 format
                if image_array.dtype != np.uint8:
                    if image_array.max() <= 1.0:
                        image_array = (image_array * 255).astype(np.uint8)
                    else:
                        image_array = image_array.astype(np.uint8)

                img = Image.fromarray(image_array)
                buffer = BytesIO()
                img.save(buffer, format='PNG')
                encoded_image_bytes = buffer.getvalue()
                self._logger.info(f"[{window_name}] Converted NPZ image to PNG: {len(encoded_image_bytes)} bytes")

                # Save encoded image to tmp folder
                import os
                from datetime import datetime
                os.makedirs("./tmp", exist_ok=True)
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                encoded_file = f"./tmp/encoded_{window_name}_{timestamp}.png"
                with open(encoded_file, "wb") as f:
                    f.write(encoded_image_bytes)
                self._logger.info(f"[{window_name}] 💾 Saved encoded image to {encoded_file}")
            elif encoded_image_bytes[:8] == b'\x89PNG\r\n\x1a\n':
                self._logger.info(f"[{window_name}] 🖼️  Detected PNG format from encoder (legacy format)")

                os.makedirs("./tmp", exist_ok=True)
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                encoded_file = f"./tmp/encoded_{window_name}_{timestamp}.png"
                with open(encoded_file, "wb") as f:
                    f.write(encoded_image_bytes)
                self._logger.info(f"[{window_name}] 💾 Saved encoded image to {encoded_file}")
                mask_array = None  # No mask in PNG format
            else:
                self._logger.warning(f"[{window_name}] ⚠️  Unknown encoder response format")
                mask_array = None  # No mask available

            # Step 5: Run model inference on encoded image
            simulation_start = time.time()
            self._logger.info(f"[{window_name}] ⏱️  Starting model inference at {time.time():.3f}")

            # Send encoded image to model server
            # Get invert_channels parameter from request data (default: False)
            invert_channels = parameters.get("invert_channels", False)

            model_result = self._model.run(
                image_bytes=encoded_image_bytes,
                filename=f"encoded_{window_name}.png",
                invert_channels=invert_channels
            )

            simulation_time = time.time() - simulation_start
            self._logger.info(f"[{window_name}] ⏱️  Model inference completed in {simulation_time:.2f}s")
            self._logger.info(f"[{window_name}] 🔍 Model result keys: {list(model_result.keys())}")
            self._logger.info(f"[{window_name}] 🔍 Model result structure: {str(model_result)[:500]}")

            os.makedirs("./tmp", exist_ok=True)
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            simulation_file = f"./tmp/simulation_{window_name}_{timestamp}.json"
            with open(simulation_file, "w") as f:
                json.dump(model_result, f, indent=2)
            self._logger.info(f"[{window_name}] 💾 Saved simulation result to {simulation_file}")

            # Save prediction as image
            if "prediction" in model_result and isinstance(model_result["prediction"], list):
                prediction_array = np.array(model_result["prediction"])
                if prediction_array.ndim == 2:
                    # Normalize to 0-255 range
                    pred_min = prediction_array.min()
                    pred_max = prediction_array.max()
                    if pred_max > pred_min:
                        prediction_normalized = ((prediction_array - pred_min) / (pred_max - pred_min) * 255).astype(np.uint8)
                    else:
                        prediction_normalized = prediction_array.astype(np.uint8)
                        
                    pred_img = PILImage.fromarray(prediction_normalized)
                    pred_file = f"./tmp/prediction_{window_name}_{timestamp}.png"
                    pred_img.save(pred_file)
                    self._logger.info(f"[{window_name}] 💾 Saved prediction image to {pred_file}")

            if model_result.get("status") == "error":
                self._logger.error(f"[{window_name}] Model inference failed")
                return {
                    "window_name": window_name,
                    "status": "error",
                    "error": f"Model inference failed: {model_result.get('error')}"
                }

            # Get prediction shape to resize mask if needed
            prediction = model_result.get("prediction")
            if prediction is not None and isinstance(prediction, list):
                pred_array = np.array(prediction)
                pred_shape = pred_array.shape
                self._logger.info(f"[{window_name}] Prediction shape: {pred_shape}")

                # Resize mask to match prediction shape if needed
                if mask_array is not None:
                    mask_shape = mask_array.shape
                    self._logger.info(f"[{window_name}] Mask shape before resize: {mask_shape}")

                    if mask_shape != pred_shape:
                        from PIL import Image as PILImage
                        # Resize mask to match prediction
                        mask_img = PILImage.fromarray(mask_array.astype(np.uint8))
                        mask_resized = mask_img.resize((pred_shape[1], pred_shape[0]), PILImage.NEAREST)
                        mask_array = np.array(mask_resized)
                        self._logger.info(f"[{window_name}] Resized mask from {mask_shape} to {mask_array.shape}")

            # Convert mask to list for JSON serialization
            model_result["mask"] = mask_array.tolist() if mask_array is not None else None

            total_time = time.time() - obstruction_start
            self._logger.info(f"[{window_name}] ⏱️  Total processing time: {total_time:.2f}s (obstruction: {obstruction_time:.2f}s, encode: {encode_time:.2f}s, simulation: {simulation_time:.2f}s)")
            self._logger.info(f"[{window_name}] Processing completed successfully")
            return {
                "window_name": window_name,
                "status": "success",
                "result": model_result,
                "x1": window_data.get("x1"),
                "y1": window_data.get("y1"),
                "z1": window_data.get("z1"),
                "x2": window_data.get("x2"),
                "y2": window_data.get("y2"),
                "z2": window_data.get("z2")
            }

        except ServiceAuthorizationError as e:
            # Handle 403 authorization errors with specific message
            self._logger.error(f"[{window_name}] {e.get_log_message()}")
            return {
                "window_name": window_name,
                "status": "error",
                "error": e.get_user_message(),
                "error_type": "authorization_error"
            }

        except ServiceConnectionError as e:
            # Handle connection errors with user-friendly message
            is_local = self._is_local_deployment()
            user_message = e.get_user_message(is_local)
            self._logger.error(f"[{window_name}] {e.get_log_message()}")

            return {
                "window_name": window_name,
                "status": "error",
                "error": user_message,
                "error_type": "connection_error"
            }

        except ServiceTimeoutError as e:
            self._logger.error(f"[{window_name}] {e.get_log_message()}")
            return {
                "window_name": window_name,
                "status": "error",
                "error": f"Request timeout: {e.service_name} service did not respond within {e.timeout_seconds} seconds",
                "error_type": "timeout_error"
            }

        except ServiceResponseError as e:
            self._logger.error(f"[{window_name}] {e.get_log_message()}")
            return {
                "window_name": window_name,
                "status": "error",
                "error": f"Service error: {e.service_name} returned status {e.status_code} - {e.error_message}",
                "error_type": "response_error"
            }

        except Exception as e:
            self._logger.error(f"[{window_name}] Processing failed: {str(e)}")
            return {
                "window_name": window_name,
                "status": "error",
                "error": str(e)
            }

    def run_simulation(self, request_data: Dict[str, Any]) -> Dict[str, Any]:
        """Execute complete simulation workflow for each window

        Args:
            request_data: Contains model_type, parameters with windows, and mesh

        Returns:
            Dictionary with results for each window
        """
        self._logger.info("Starting run_simulation orchestration")

        # Step 1: Extract parameters
        model_type = request_data.get("model_type")
        parameters = request_data.get("parameters", {})
        windows = parameters.get("windows", {})
        mesh = request_data.get("mesh")

        # Use default values for translation and rotation (will be integrated later)
        translation = {"x": 0, "y": 0}
        rotation = [0]

        # Validate required fields
        if not model_type:
            return {
                ResponseKey.STATUS.value: ResponseStatus.ERROR.value,
                ResponseKey.ERROR.value: "Missing required field: model_type"
            }
        if not parameters:
            return {
                ResponseKey.STATUS.value: ResponseStatus.ERROR.value,
                ResponseKey.ERROR.value: "Missing required field: parameters"
            }
        if not windows:
            return {
                ResponseKey.STATUS.value: ResponseStatus.ERROR.value,
                ResponseKey.ERROR.value: "Missing required field: parameters.windows"
            }
        if not isinstance(windows, dict):
            return {
                ResponseKey.STATUS.value: ResponseStatus.ERROR.value,
                ResponseKey.ERROR.value: "Windows must be a dictionary"
            }
        if not mesh:
            return {
                ResponseKey.STATUS.value: ResponseStatus.ERROR.value,
                ResponseKey.ERROR.value: "Missing required field: mesh"
            }
        if not isinstance(mesh, list) or len(mesh) < 3:
            return {
                ResponseKey.STATUS.value: ResponseStatus.ERROR.value,
                ResponseKey.ERROR.value: "Mesh must contain at least 3 points"
            }

        # Validate each window - updated for encoder v2.0.1
        required_window_fields = ["x1", "y1", "z1", "x2", "y2", "z2", "window_frame_ratio"]
        for window_name, window_data in windows.items():
            for field in required_window_fields:
                if field not in window_data:
                    return {
                        ResponseKey.STATUS.value: ResponseStatus.ERROR.value,
                        ResponseKey.ERROR.value: f"Window '{window_name}' missing required field: {field}"
                    }

        # Process each window through complete workflow
        results = {}
        for window_name, window_data in windows.items():
            result = self._process_single_window(
                window_name=window_name,
                window_data=window_data,
                model_type=model_type,
                parameters=parameters,
                mesh=mesh,
                translation=translation,
                rotation=rotation
            )
            results[window_name] = result

        # Check if any window processing failed
        for window_name, result in results.items():
            if result.get("status") == "error":
                self._logger.error(f"Window '{window_name}' processing failed, skipping merger")
                return {
                    "status": "error",
                    "error": f"Window '{window_name}' processing failed: {result.get('error')}",
                    "partial_results": results
                }

        # Step 4: Merge all window simulations using merger service
        self._logger.info("Starting merger service to combine all window results")
        room_polygon = parameters.get("room_polygon")

        # Prepare windows data for merger (extract direction_angle for each window)
        windows_for_merger = {}
        for window_name, window_data in windows.items():
            # Get direction_angle from window_data or calculate it
            if "direction_angle" in window_data:
                direction_angle = window_data["direction_angle"]
            else:
                # Calculate from encoder service if not provided
                calc_params = {
                    "room_polygon": room_polygon,
                    "windows": {
                        window_name: {
                            "x1": window_data.get("x1"),
                            "y1": window_data.get("y1"),
                            "x2": window_data.get("x2"),
                            "y2": window_data.get("y2")
                        }
                    }
                }
                direction_result = self._encoder.calculate_direction_angles(calc_params)
                direction_angle = direction_result.get("direction_angles", {}).get(window_name, 0)

            windows_for_merger[window_name] = {
                "x1": window_data.get("x1"),
                "y1": window_data.get("y1"),
                "z1": window_data.get("z1"),
                "x2": window_data.get("x2"),
                "y2": window_data.get("y2"),
                "z2": window_data.get("z2"),
                "direction_angle": direction_angle
            }

        # Prepare simulations data for merger (extract df_values and mask from each window result)
        simulations_for_merger = {}
        for window_name, result in results.items():
            # Extract the simulation result data
            simulation_result = result.get("result", {})

            # The model service returns prediction field with the actual data
            if "prediction" in simulation_result:
                df_values = simulation_result["prediction"]
                mask = simulation_result.get("mask", None)
            elif "data" in simulation_result:
                # Legacy format: data field (could be nested in "data" or at root level)
                data_field = simulation_result["data"]
                if isinstance(data_field, dict):
                    df_values = data_field.get("df_values", data_field)
                    mask = data_field.get("mask", None)
                else:
                    # data is the df_values directly (list/array)
                    df_values = data_field
                    mask = None
            else:
                # Fallback: use direct fields
                df_values = simulation_result.get("df_values", [])
                mask = simulation_result.get("mask", None)

            # Create a simple mask if not provided
            if mask is None:
                if isinstance(df_values, list) and len(df_values) > 0:
                    mask = [[1 for _ in row] for row in df_values]
                else:
                    mask = []

            self._logger.info(f"[{window_name}] Prepared for merger: df_values type={type(df_values)}, mask type={type(mask)}")
            if isinstance(df_values, list) and len(df_values) > 0:
                self._logger.info(f"[{window_name}] df_values shape: {len(df_values)}x{len(df_values[0]) if len(df_values) > 0 else 0}")
                self._logger.info(f"[{window_name}] mask shape: {len(mask)}x{len(mask[0]) if len(mask) > 0 else 0}")
                
            simulations_for_merger[window_name] = {
                "df_values": df_values,
                "mask": mask
            }

        # Log merger request details for debugging
        self._logger.info(f"Merger request - room_polygon: {room_polygon}")
        self._logger.info(f"Merger request - windows count: {len(windows_for_merger)}")
        self._logger.info(f"Merger request - simulations count: {len(simulations_for_merger)}")

        # Validate that all required fields are present
        for window_name in windows_for_merger.keys():
            if window_name not in simulations_for_merger:
                self._logger.error(f"Window '{window_name}' in windows but not in simulations")
                return {
                    "status": "error",
                    "error": f"Window '{window_name}' missing simulation data",
                    "window_results": results
                }

        # Save merger request to file for debugging
        import json
        import os
        from datetime import datetime

        merger_request = {
            "room_polygon": room_polygon,
            "windows": windows_for_merger,
            "simulations": simulations_for_merger
        }

        os.makedirs("./tmp", exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        merger_request_file = f"./tmp/merger_request_{timestamp}.json"
        with open(merger_request_file, "w") as f:
            json.dump(merger_request, f, indent=2)
        self._logger.info(f"💾 Saved merger request to {merger_request_file}")

        try:
            merger_result = self._merger.merge(
                room_polygon=room_polygon,
                windows=windows_for_merger,
                simulations=simulations_for_merger
            )

            # Save merger response
            merger_timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            with open(f"./tmp/merger_response_{merger_timestamp}.json", "w") as f:
                json.dump(merger_result, f, indent=2)
            self._logger.info(f"💾 Saved merger response to ./tmp/merger_response_{merger_timestamp}.json")

            # Save merged result as image
            if "result" in merger_result and isinstance(merger_result["result"], list):
                merged_array = np.array(merger_result["result"])
                if merged_array.ndim == 2:
                    # Normalize to 0-255 range
                    merged_min = merged_array.min()
                    merged_max = merged_array.max()
                    if merged_max > merged_min:
                        merged_normalized = ((merged_array - merged_min) / (merged_max - merged_min) * 255).astype(np.uint8)
                    else:
                        merged_normalized = merged_array.astype(np.uint8)

                    from PIL import Image as PILImage
                    merged_img = PILImage.fromarray(merged_normalized)
                    merged_file = f"./tmp/merged_result_{merger_timestamp}.png"
                    merged_img.save(merged_file)
                    self._logger.info(f"💾 Saved merged result image to {merged_file}")

            # Save merged mask as image
            if "mask" in merger_result and isinstance(merger_result["mask"], list):
                mask_array = np.array(merger_result["mask"])
                if mask_array.ndim == 2:
                    from PIL import Image as PILImage
                    mask_img = PILImage.fromarray((mask_array * 255).astype(np.uint8))
                    mask_file = f"./tmp/merged_mask_{merger_timestamp}.png"
                    mask_img.save(mask_file)
                    self._logger.info(f"💾 Saved merged mask image to {mask_file}")

            if merger_result.get("status") == "error":
                self._logger.error("Merger service failed")
                return {
                    "status": "error",
                    "error": f"Merger failed: {merger_result.get('error')}",
                    "window_results": results
                }

            self._logger.info("Complete workflow finished successfully with merger")
            self._logger.info(f"🔍 Merger result keys: {list(merger_result.keys())}")

            # Return merged result along with individual window results
            # Merger service returns "result" and "mask" fields
            return {
                "status": "success",
                "window_results": results,
                "merged_result": {
                    "df_matrix": merger_result.get("result", merger_result.get("df_matrix")),
                    "room_mask": merger_result.get("mask", merger_result.get("room_mask"))
                }
            }

        except Exception as e:
            self._logger.error(f"Merger service error: {str(e)}")
            # Return window results even if merger fails
            return {
                "status": "success",
                "window_results": results,
                "merger_error": str(e)
            }


class EncodeOrchestrationService:
    """Service for orchestrating the encode workflow:
    obstruction angles → encoding (no simulation, no postprocessing)"""

    def __init__(
        self,
        obstruction_calculation_service: ObstructionCalculationService,
        encoder_service: EncoderService,
        logger: ILogger
    ):
        self._obstruction_calculation = obstruction_calculation_service
        self._encoder = encoder_service
        self._logger = logger
        self._validator = ParameterValidator()

    def _is_local_deployment(self) -> bool:
        """Check if running in local deployment mode"""
        deployment_mode = os.getenv("DEPLOYMENT_MODE", "local")
        return deployment_mode == "local"

    def _process_single_window_encode(
        self,
        window_name: str,
        window_data: Dict[str, Any],
        model_type: str,
        parameters: Dict[str, Any],
        mesh: List
    ) -> Dict[str, Any]:
        """Process a single window: obstruction → encoding (no simulation)

        Args:
            window_name: Name/identifier of the window
            window_data: Window parameters
            model_type: Model type for encoding
            parameters: Room parameters
            mesh: Obstruction mesh

        Returns:
            Result dictionary with window_name and encoded image bytes or error
        """
        self._logger.info(f"[Encode] Processing window: {window_name}")

        try:
            # Step 1: Calculate window center position
            x = (window_data.get("x1", 0) + window_data.get("x2", 0)) / 2
            y = (window_data.get("y1", 0) + window_data.get("y2", 0)) / 2
            z = (window_data.get("z1", 0) + window_data.get("z2", 0)) / 2

            # Step 2: Calculate obstruction angles for this window
            obstruction_start = time.time()
            self._logger.info(f"[{window_name}] Calculating obstruction angles at ({x}, {y}, {z})")

            # Determine direction_angle: use provided value or calculate from encoder service
            # Priority 1: Check if direction_angle is in window_data
            if "direction_angle" in window_data:
                direction_angle = window_data.get("direction_angle")
                self._logger.info(f"[{window_name}] Using direction_angle from window_data: {direction_angle:.4f} rad ({math.degrees(direction_angle):.2f}°)")
            # Priority 2: Check if direction_angle is in parameters (top-level)
            elif "direction_angle" in parameters:
                direction_angle = parameters.get("direction_angle")
                self._logger.info(f"[{window_name}] Using direction_angle from parameters: {direction_angle:.4f} rad ({math.degrees(direction_angle):.2f}°)")
            else:
                # Priority 3: Calculate direction angle using encoder service's calculate-direction endpoint
                self._logger.info(f"[{window_name}] direction_angle not provided, calling encoder service to calculate it")
                calc_params = {
                    "room_polygon": parameters.get("room_polygon"),
                    "windows": {
                        window_name: {
                            "x1": window_data.get("x1"),
                            "y1": window_data.get("y1"),
                            "x2": window_data.get("x2"),
                            "y2": window_data.get("y2")
                        }
                    }
                }
                direction_result = self._encoder.calculate_direction_angles(calc_params)
                direction_angle = direction_result.get("direction_angles", {}).get(window_name)

                if direction_angle is None:
                    self._logger.error(f"[{window_name}] Failed to calculate direction_angle from encoder service")
                    return {
                        ResponseKey.WINDOW_NAME.value: window_name,
                        ResponseKey.STATUS.value: ResponseStatus.ERROR.value,
                        ResponseKey.ERROR.value: "Failed to calculate direction_angle"
                    }

                self._logger.info(f"[{window_name}] Calculated direction_angle from encoder service: {direction_angle:.4f} rad ({math.degrees(direction_angle):.2f}°)")

            # Use parallel obstruction calculation service
            obstruction_result = self._obstruction_calculation.calculate_multi_direction(
                x=x, y=y, z=z,
                direction_angle=direction_angle,
                mesh=mesh,
                start_angle=17.5,
                end_angle=162.5,
                num_directions=64
            )

            obstruction_time = time.time() - obstruction_start
            self._logger.info(f"[{window_name}] Obstruction calculation completed in {obstruction_time:.2f}s")

            if obstruction_result.get("status") == "error":
                self._logger.error(f"[{window_name}] Obstruction calculation failed")
                return {
                    "window_name": window_name,
                    "status": "error",
                    "error": f"Obstruction calculation failed: {obstruction_result.get('error')}"
                }

            # Extract angles from the result data
            result_data = obstruction_result.get("data", {})
            horizon_angles = result_data.get("horizon_angles", [])
            zenith_angles = result_data.get("zenith_angles", [])

            if len(horizon_angles) != 64 or len(zenith_angles) != 64:
                error_msg = f"Expected 64 angles each, got horizon: {len(horizon_angles)}, zenith: {len(zenith_angles)}"
                self._logger.error(f"[{window_name}] {error_msg}")
                return {
                    "window_name": window_name,
                    "status": "error",
                    "error": error_msg
                }

            # Step 3: Create parameters with single window enhanced with obstruction angles
            single_window_params = parameters.copy()

            # Prepare window data for encoder v2.0.1
            # Only send required fields: position (x1,y1,z1,x2,y2,z2), window_frame_ratio, direction_angle, and obstruction angles
            encoder_window_data = {
                "x1": window_data.get("x1"),
                "y1": window_data.get("y1"),
                "z1": window_data.get("z1"),
                "x2": window_data.get("x2"),
                "y2": window_data.get("y2"),
                "z2": window_data.get("z2"),
                "window_frame_ratio": window_data.get("window_frame_ratio"),
                "direction_angle": direction_angle,
                "obstruction_angle_horizon": horizon_angles,
                "obstruction_angle_zenith": zenith_angles
            }

            single_window_params["windows"] = {
                window_name: encoder_window_data
            }

            # Step 4: Encode with obstruction angles
            self._logger.info(f"[{window_name}] Encoding room with obstruction angles (direction_angle={direction_angle:.4f} rad)")

            encoded_image_bytes = self._encoder.encode(
                model_type=model_type,
                parameters=single_window_params
            )

            self._logger.info(f"[{window_name}] Encoding completed successfully ({len(encoded_image_bytes)} bytes)")

            # Base64-encode the image so it can be JSON-serialized
            encoded_image_b64 = base64.b64encode(encoded_image_bytes).decode('utf-8')

            return {
                "window_name": window_name,
                "status": "success",
                "encoded_image": encoded_image_b64,  # Base64-encoded string
                "image_size": len(encoded_image_bytes),
                "x1": window_data.get("x1"),
                "y1": window_data.get("y1"),
                "z1": window_data.get("z1"),
                "x2": window_data.get("x2"),
                "y2": window_data.get("y2"),
                "z2": window_data.get("z2")
            }

        except ServiceAuthorizationError as e:
            self._logger.error(f"[{window_name}] {e.get_log_message()}")
            return {
                "window_name": window_name,
                "status": "error",
                "error": e.get_user_message(),
                "error_type": "authorization_error"
            }

        except ServiceConnectionError as e:
            is_local = self._is_local_deployment()
            user_message = e.get_user_message(is_local)
            self._logger.error(f"[{window_name}] {e.get_log_message()}")

            return {
                "window_name": window_name,
                "status": "error",
                "error": user_message,
                "error_type": "connection_error"
            }

        except ServiceTimeoutError as e:
            self._logger.error(f"[{window_name}] {e.get_log_message()}")
            return {
                "window_name": window_name,
                "status": "error",
                "error": f"Request timeout: {e.service_name} service did not respond within {e.timeout_seconds} seconds",
                "error_type": "timeout_error"
            }

        except ServiceResponseError as e:
            self._logger.error(f"[{window_name}] {e.get_log_message()}")
            return {
                "window_name": window_name,
                "status": "error",
                "error": f"Service error: {e.service_name} returned status {e.status_code} - {e.error_message}",
                "error_type": "response_error"
            }

        except Exception as e:
            self._logger.error(f"[{window_name}] Processing failed: {str(e)}")
            return {
                "window_name": window_name,
                "status": "error",
                "error": str(e)
            }

    def encode_with_obstruction(self, request_data: Dict[str, Any]) -> Dict[str, Any]:
        """Execute encode workflow for each window: obstruction → encoding

        Args:
            request_data: Contains model_type, parameters with windows, and mesh

        Returns:
            Dictionary with encoded images for each window
        """
        self._logger.info("Starting encode_with_obstruction orchestration")

        # Extract parameters
        model_type = request_data.get("model_type")
        parameters = request_data.get("parameters", {})
        windows = parameters.get("windows", {})
        mesh = request_data.get("mesh")

        # Validate using ParameterValidator
        validation_result = self._validator.validate_model_type(model_type)
        if validation_result.get("status") == "error":
            return validation_result

        validation_result = self._validator.validate_parameters(parameters)
        if validation_result.get("status") == "error":
            return validation_result

        validation_result = self._validator.validate_windows(windows)
        if validation_result.get("status") == "error":
            return validation_result

        validation_result = self._validator.validate_mesh(mesh)
        if validation_result.get("status") == "error":
            return validation_result

        # Validate each window
        for window_name, window_data in windows.items():
            validation_result = self._validator.validate_window_fields(window_name, window_data)
            if validation_result.get("status") == "error":
                return validation_result

        # Process each window through obstruction → encoding workflow
        results = {}
        for window_name, window_data in windows.items():
            result = self._process_single_window_encode(
                window_name=window_name,
                window_data=window_data,
                model_type=model_type,
                parameters=parameters,
                mesh=mesh
            )
            results[window_name] = result

        # Check if any window processing failed
        for window_name, result in results.items():
            if result.get("status") == "error":
                self._logger.error(f"Window '{window_name}' encoding failed")
                return {
                    "status": "error",
                    "error": f"Window '{window_name}' encoding failed: {result.get('error')}",
                    "partial_results": results
                }

        self._logger.info("Encode workflow finished successfully")

        # Return results with encoded images
        return {
            "status": "success",
            "results": results
        }
