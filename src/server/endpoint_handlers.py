from typing import Tuple
from flask import Request, Response, jsonify, request

from .request_handler import EndpointRequestHandler


class EndpointHandlers:
    """Individual handler methods for each endpoint with Swagger documentation"""

    def __init__(self, request_handler: EndpointRequestHandler):
        self._request_handler = request_handler

    def handle_simulate(self) -> Tuple[Response, int]:
        """End-to-end daylight simulation

        Calculates obstruction angles, encodes room, runs ML model, and returns daylight factor matrix as 128x128 RGB image.
        ---
        tags:
          - Simulation
        parameters:
          - in: body
            name: body
            required: true
            schema:
              type: object
              required:
                - model_type
                - parameters
                - mesh
              properties:
                model_type:
                  type: string
                  description: Model identifier
                  example: "df_default"
                parameters:
                  type: object
                  required:
                    - height_roof_over_floor
                    - floor_height_above_terrain
                    - room_polygon
                    - windows
                  properties:
                    height_roof_over_floor:
                      type: number
                      description: Height of roof above floor in meters
                      example: 19.7
                    floor_height_above_terrain:
                      type: number
                      description: Floor height above terrain in meters
                      example: 2.71
                    room_polygon:
                      $ref: '#/definitions/RoomPolygon'
                    windows:
                      type: object
                      description: Dictionary of window configurations by name
                      example: {"window_1": {"x1": -0.4, "y1": 7, "z1": 2.8, "x2": -2, "y2": 7.3, "z2": 5.4, "window_frame_ratio": 0.41}}
                mesh:
                  $ref: '#/definitions/Mesh'
        responses:
          200:
            description: Daylight factor simulation result as 128x128 RGB image
            schema:
              type: object
              properties:
                status:
                  type: string
                  example: "success"
                result:
                  type: array
                  description: 128x128 RGB image array
          400:
            description: Bad request
          500:
            description: Internal server error
        """
        return self._request_handler.handle(request)

    def handle_stats(self) -> Tuple[Response, int]:
        """Calculate statistical metrics from daylight simulation results

        Computes min, max, mean, median, and valid area percentage from daylight factor values.
        ---
        tags:
          - Statistics
        parameters:
          - in: body
            name: body
            required: true
            schema:
              type: object
              required:
                - result
                - mask
              properties:
                result:
                  type: array
                  description: 2D array of daylight factor values
                  example: [[0.5, 0.3, 0.7, 0.1], [0.2, 0.8, 0.1, 0.9], [7.9, 8.4, 9.2, 3.5], [2.1, 5.5, 6.8, 7.3]]
                  items:
                    type: array
                    items:
                      type: number
                mask:
                  type: array
                  description: 2D boolean array marking valid room area (1=valid, 0=invalid)
                  example: [[1, 1, 1, 1], [1, 1, 1, 1], [1, 1, 1, 1], [1, 1, 1, 1]]
                  items:
                    type: array
                    items:
                      type: integer
        responses:
          200:
            description: Statistical metrics
            schema:
              type: object
              properties:
                status:
                  type: string
                  example: "success"
                metrics:
                  type: object
                  properties:
                    min:
                      type: number
                      example: 0.1
                    max:
                      type: number
                      example: 9.2
                    mean:
                      type: number
                      example: 3.39
                    median:
                      type: number
                      example: 1.5
                    valid_area:
                      type: number
                      description: Percentage of valid area
                      example: 50.0
          400:
            description: Bad request
          500:
            description: Internal server error
        """
        return self._request_handler.handle(request)

    def handle_horizon(self) -> Tuple[Response, int]:
        """Calculate single horizon obstruction angle

        Computes horizon angle for a specific direction from a window point.
        ---
        tags:
          - Obstruction
        parameters:
          - in: body
            name: body
            required: true
            schema:
              type: object
              required:
                - x
                - y
                - z
                - direction_angle
                - mesh
              properties:
                x:
                  $ref: '#/definitions/CoordinateX'
                y:
                  $ref: '#/definitions/CoordinateY'
                z:
                  $ref: '#/definitions/CoordinateZ'
                direction_angle:
                  $ref: '#/definitions/DirectionAngle'
                mesh:
                  $ref: '#/definitions/Mesh'
        responses:
          200:
            description: Horizon angle result
            schema:
              type: object
              properties:
                status:
                  type: string
                  example: "success"
                horizon:
                  type: number
                  description: Horizon angle in degrees
                  example: 15.5
          400:
            description: Bad request
          500:
            description: Internal server error
        """
        return self._request_handler.handle(request)

    def handle_zenith(self) -> Tuple[Response, int]:
        """Calculate single zenith obstruction angle

        Computes zenith angle for a specific direction from a window point.
        ---
        tags:
          - Obstruction
        parameters:
          - in: body
            name: body
            required: true
            schema:
              type: object
              required:
                - x
                - y
                - z
                - direction_angle
                - mesh
              properties:
                x:
                  $ref: '#/definitions/CoordinateX'
                y:
                  $ref: '#/definitions/CoordinateY'
                z:
                  $ref: '#/definitions/CoordinateZ'
                direction_angle:
                  $ref: '#/definitions/DirectionAngle'
                mesh:
                  $ref: '#/definitions/Mesh'
                  example: [[0,0,0], [1,0,0], [0,1,0]]
        responses:
          200:
            description: Zenith angle result
            schema:
              type: object
              properties:
                status:
                  type: string
                  example: "success"
                zenith:
                  type: number
                  description: Zenith angle in degrees
                  example: 10.2
          400:
            description: Bad request
          500:
            description: Internal server error
        """
        return self._request_handler.handle(request)

    def handle_obstruction(self) -> Tuple[Response, int]:
        """Calculate both horizon and zenith angles for a single direction

        Returns both obstruction angles for one specific direction from a window point.
        ---
        tags:
          - Obstruction
        parameters:
          - in: body
            name: body
            required: true
            schema:
              type: object
              required:
                - x
                - y
                - z
                - direction_angle
                - mesh
              properties:
                x:
                  $ref: '#/definitions/CoordinateX'
                y:
                  $ref: '#/definitions/CoordinateY'
                z:
                  $ref: '#/definitions/CoordinateZ'
                direction_angle:
                  $ref: '#/definitions/DirectionAngle'
                mesh:
                  $ref: '#/definitions/Mesh'
        responses:
          200:
            description: Horizon and zenith angles for the specified direction
            schema:
              allOf:
                - $ref: '#/definitions/SuccessResponse'
                - type: object
                  properties:
                    horizon:
                      type: number
                      description: Horizon angle in degrees
                      example: 15.5
                    zenith:
                      type: number
                      description: Zenith angle in degrees
                      example: 10.2
          400:
            description: Bad request
            schema:
              $ref: '#/definitions/ErrorResponse'
          500:
            description: Internal server error
            schema:
              $ref: '#/definitions/ErrorResponse'
        """
        return self._request_handler.handle(request)

    def handle_obstruction_all(self) -> Tuple[Response, int]:
        """Calculate obstruction angles for all 64 directions from window geometry

        Computes horizon and zenith angles for 64 directions around window points.
        Automatically calculates reference points and direction angles from room polygon and window positions.
        ---
        tags:
          - Obstruction
        parameters:
          - in: body
            name: body
            required: true
            schema:
              type: object
              required:
                - room_polygon
                - windows
                - mesh
              properties:
                room_polygon:
                  $ref: '#/definitions/RoomPolygon'
                windows:
                  $ref: '#/definitions/WindowConfig'
                mesh:
                  $ref: '#/definitions/Mesh'
        responses:
          200:
            description: Obstruction angles for all directions for each window
            schema:
              allOf:
                - $ref: '#/definitions/SuccessResponse'
                - type: object
                  properties:
                    horizon:
                      type: array
                      description: Array of 64 horizon angles in degrees
                      items:
                        type: number
                      example: [15.5, 16.2, 14.8, 17.1, 15.9, 16.5, 14.2, 18.3, 15.7, 16.8, 14.5, 17.9, 15.3, 16.1, 14.9, 17.5, 15.6, 16.3, 14.7, 17.2, 15.8, 16.4, 14.3, 18.1, 15.4, 16.9, 14.6, 17.8, 15.2, 16.0, 14.8, 17.4, 15.5, 16.2, 14.8, 17.1, 15.9, 16.5, 14.2, 18.3, 15.7, 16.8, 14.5, 17.9, 15.3, 16.1, 14.9, 17.5, 15.6, 16.3, 14.7, 17.2, 15.8, 16.4, 14.3, 18.1, 15.4, 16.9, 14.6, 17.8, 15.2, 16.0, 14.8, 17.4]
                    zenith:
                      type: array
                      description: Array of 64 zenith angles in degrees
                      items:
                        type: number
                      example: [10.2, 11.1, 9.8, 12.3, 10.5, 11.4, 9.5, 13.1, 10.8, 11.7, 9.7, 12.9, 10.3, 11.2, 9.9, 12.5, 10.6, 11.5, 9.6, 12.4, 10.9, 11.8, 9.4, 13.2, 10.4, 12.0, 9.8, 12.8, 10.1, 11.0, 9.7, 12.2, 10.2, 11.1, 9.8, 12.3, 10.5, 11.4, 9.5, 13.1, 10.8, 11.7, 9.7, 12.9, 10.3, 11.2, 9.9, 12.5, 10.6, 11.5, 9.6, 12.4, 10.9, 11.8, 9.4, 13.2, 10.4, 12.0, 9.8, 12.8, 10.1, 11.0, 9.7, 12.2]
          400:
            description: Bad request
            schema:
              $ref: '#/definitions/ErrorResponse'
          500:
            description: Internal server error
            schema:
              $ref: '#/definitions/ErrorResponse'
        """
        return self._request_handler.handle(request)

    def handle_obstruction_multi(self) -> Tuple[Response, int]:
        """Calculate obstruction angles for multiple window points
        ---
        tags:
          - Obstruction
        parameters:
          - in: body
            name: body
            required: true
            schema:
              type: object
        responses:
          200:
            description: Obstruction results for multiple windows
            schema:
              type: object
          400:
            description: Bad request
          500:
            description: Internal server error
        """
        return self._request_handler.handle(request)

    def handle_obstruction_parallel(self) -> Tuple[Response, int]:
        """Calculate obstruction angles in parallel for all directions (optimized)

        Same as /obstruction_all but uses optimized parallel processing. Returns 64 horizon and zenith angles.
        ---
        tags:
          - Obstruction
        parameters:
          - in: body
            name: body
            required: true
            schema:
              type: object
              required:
                - x
                - y
                - z
                - mesh
              properties:
                x:
                  $ref: '#/definitions/CoordinateX'
                y:
                  $ref: '#/definitions/CoordinateY'
                z:
                  $ref: '#/definitions/CoordinateZ'
                mesh:
                  $ref: '#/definitions/Mesh'
                direction_angle:
                  type: number
                  description: Direction angle in degrees (optional, defaults to window normal)
                  example: 90.0
        responses:
          200:
            description: Obstruction angles for all 64 directions (parallel calculation)
            schema:
              allOf:
                - $ref: '#/definitions/SuccessResponse'
                - type: object
                  properties:
                    horizon:
                      type: array
                      description: Array of 64 horizon angles in degrees
                      items:
                        type: number
                    zenith:
                      type: array
                      description: Array of 64 zenith angles in degrees
                      items:
                        type: number
          400:
            description: Bad request
            schema:
              $ref: '#/definitions/ErrorResponse'
          500:
            description: Internal server error
            schema:
              $ref: '#/definitions/ErrorResponse'
        """
        return self._request_handler.handle(request)

    def handle_encode_raw(self) -> Tuple[Response, int]:
        """Encode room with pre-calculated obstruction angles

        Encodes room parameters with provided horizon and zenith angles into NPZ format.
        Returns binary ZIP file containing image.npy (128x128 encoded image array).
        ---
        tags:
          - Encoder
        parameters:
          - in: body
            name: body
            required: true
            schema:
              type: object
              required:
                - model_type
                - parameters
              properties:
                model_type:
                  type: string
                  example: "df_default"
                parameters:
                  type: object
                  required:
                    - height_roof_over_floor
                    - floor_height_above_terrain
                    - room_polygon
                    - windows
                  properties:
                    height_roof_over_floor:
                      type: number
                      example: 19.7
                    floor_height_above_terrain:
                      type: number
                      example: 2.71
                    room_polygon:
                      $ref: '#/definitions/RoomPolygon'
                    windows:
                      type: object
                      description: Windows with pre-calculated obstruction angles (arrays of 64 values, or [0] for default)
                      example: {"window_1": {"x1": -0.4, "y1": 7, "z1": 2.8, "x2": -2, "y2": 7.3, "z2": 5.4, "window_frame_ratio": 0.41, "direction_angle": 90.0, "horizon": [0], "zenith": [0]}}
        responses:
          200:
            description: Binary ZIP file containing image.npy and mask.npy (application/octet-stream)
          400:
            description: Bad request
          500:
            description: Internal server error
        """
        return self._request_handler.handle(request)

    def handle_encode(self) -> Tuple[Response, int]:
        """Encode room geometry and windows

        Encodes room and window parameters into model input format. Calculates obstruction angles automatically.
        Returns binary ZIP file containing image.npy (128x128 encoded image array).
        ---
        tags:
          - Encoder
        parameters:
          - in: body
            name: body
            required: true
            schema:
              type: object
              required:
                - parameters
                - mesh
              properties:
                model_type:
                  type: string
                  example: "df_default"
                parameters:
                  type: object
                  required:
                    - height_roof_over_floor
                    - floor_height_above_terrain
                    - room_polygon
                    - windows
                  properties:
                    height_roof_over_floor:
                      type: number
                      example: 19.7
                    floor_height_above_terrain:
                      type: number
                      example: 2.71
                    room_polygon:
                      $ref: '#/definitions/RoomPolygon'
                    windows:
                      type: object
                      example: {"window_1": {"x1": -0.4, "y1": 7, "z1": 2.8, "x2": -2, "y2": 7.3, "z2": 5.4, "window_frame_ratio": 0.41}}
                mesh:
                  $ref: '#/definitions/Mesh'
        responses:
          200:
            description: Binary ZIP file containing image.npy (application/octet-stream)
          400:
            description: Bad request
          500:
            description: Internal server error
        """
        return self._request_handler.handle(request)

    def handle_calculate_direction(self) -> Tuple[Response, int]:
        """Calculate outward normal direction angle for windows

        Computes the direction angle (outward normal) for each window based on room polygon and window coordinates.
        ---
        tags:
          - Geometry
        parameters:
          - in: body
            name: body
            required: true
            schema:
              type: object
              required:
                - room_polygon
                - windows
              properties:
                room_polygon:
                  $ref: '#/definitions/RoomPolygon'
                windows:
                  type: object
                  description: Window configurations
                  example: {"test_window": {"x1": -2, "y1": 7, "z1": 2.8, "x2": -0.4, "y2": 7.2, "z2": 5.4}}
        responses:
          200:
            description: Direction angles in radians for each window
            schema:
              type: object
              properties:
                status:
                  type: string
                  example: "success"
                direction_angle:
                  type: object
                  description: Direction angles by window name
                  example: {"test_window": 1.5708}
                room_polygon:
                  type: array
                windows:
                  type: object
          400:
            description: Bad request
          500:
            description: Internal server error
        """
        return self._request_handler.handle(request)

    def handle_reference_point(self) -> Tuple[Response, int]:
        """Calculate reference point (center) for windows

        Computes the center point of each window for obstruction calculations.
        ---
        tags:
          - Geometry
        parameters:
          - in: body
            name: body
            required: true
            schema:
              type: object
              required:
                - room_polygon
                - windows
              properties:
                room_polygon:
                  $ref: '#/definitions/RoomPolygon'
                windows:
                  type: object
                  description: Window configurations
                  example: {"test_window": {"x1": -2, "y1": 7, "z1": 2.8, "x2": -0.4, "y2": 7.2, "z2": 5.4}}
        responses:
          200:
            description: Reference point coordinates for each window
            schema:
              type: object
              properties:
                status:
                  type: string
                  example: "success"
                reference_point:
                  type: object
                  description: Reference points by window name
                  example: {"test_window": {"x": -1.2, "y": 7.0, "z": 4.1}}
                room_polygon:
                  type: array
                windows:
                  type: object
          400:
            description: Bad request
          500:
            description: Internal server error
        """
        return self._request_handler.handle(request)

    def handle_run(self) -> Tuple[Response, int]:
        """Run ML model inference for daylight simulation

        Same as /simulate endpoint. End-to-end daylight simulation.
        Optionally accepts pre-calculated horizon and zenith angles to skip obstruction calculation.
        ---
        tags:
          - Model
        parameters:
          - in: body
            name: body
            required: true
            schema:
              type: object
              required:
                - model_type
                - parameters
                - mesh
              properties:
                model_type:
                  type: string
                  example: "df_default"
                parameters:
                  type: object
                  properties:
                    height_roof_over_floor:
                      type: number
                      format: float
                      example: 19.7
                    floor_height_above_terrain:
                      type: number
                      format: float
                      example: 2.71
                    room_polygon:
                      type: array
                      items:
                        type: array
                        items:
                          type: number
                      example:
                        - [0, 0]
                        - [0, 7]
                        - [-3, 7]
                        - [-3, 0]
                    windows:
                      type: object
                      description: A map of window identifiers to window definitions
                      additionalProperties:
                        type: object
                        properties:
                          x1:
                            type: number
                            format: float
                          y1:
                            type: number
                            format: float
                          z1:
                            type: number
                            format: float
                          x2:
                            type: number
                            format: float
                          y2:
                            type: number
                            format: float
                          z2:
                            type: number
                            format: float
                          window_frame_ratio:
                            type: number
                            format: float
                          horizon:
                            type: array
                            description: Optional pre-calculated horizon angles for this window (64 values). Skips obstruction calculation for this window.
                            items:
                              type: number
                          zenith:
                            type: array
                            description: Optional pre-calculated zenith angles for this window (64 values). Skips obstruction calculation for this window.
                            items:
                              type: number
                        required:
                          - x1
                          - y1
                          - z1
                          - x2
                          - y2
                          - z2
                          - window_frame_ratio
                      example:
                        test_window_1:
                          x1: -2.0
                          y1: 7
                          z1: 2.8
                          x2: -0.4
                          y2: 7.2
                          z2: 5.4
                          window_frame_ratio: 0.41
                          horizon: [30, 30, 30, 30, 30, 30, 30, 30, 30, 30, 30, 30, 30, 30, 30, 30, 30, 30, 30, 30, 30, 30, 30, 30, 30, 30, 30, 30, 30, 30, 30, 30, 30, 30, 30, 30, 30, 30, 30, 30, 30, 30, 30, 30, 30, 30, 30, 30, 30, 30, 30, 30, 30, 30, 30, 30, 30, 30, 30, 30, 30, 30, 30, 30]
                          zenith: [30, 30, 30, 30, 30, 30, 30, 30, 30, 30, 30, 30, 30, 30, 30, 30, 30, 30, 30, 30, 30, 30, 30, 30, 30, 30, 30, 30, 30, 30, 30, 30, 30, 30, 30, 30, 30, 30, 30, 30, 30, 30, 30, 30, 30, 30, 30, 30, 30, 30, 30, 30, 30, 30, 30, 30, 30, 30, 30, 30, 30, 30, 30, 30]
                  required:
                    - height_roof_over_floor
                    - floor_height_above_terrain
                    - room_polygon
                    - windows
                mesh:
                  $ref: '#/definitions/Mesh'
                horizon:
                  type: array
                  description: Optional pre-calculated horizon angles (64 values). If provided along with zenith, obstruction calculation will be skipped.
                  items:
                    type: number
                  example: [15.5, 16.2, 14.8, 17.1, 15.9, 16.5, 14.2, 18.3, 15.7, 16.8, 14.5, 17.9, 15.3, 16.1, 14.9, 17.5, 15.6, 16.3, 14.7, 17.2, 15.8, 16.4, 14.3, 18.1, 15.4, 16.9, 14.6, 17.8, 15.2, 16.0, 14.8, 17.4, 15.5, 16.2, 14.8, 17.1, 15.9, 16.5, 14.2, 18.3, 15.7, 16.8, 14.5, 17.9, 15.3, 16.1, 14.9, 17.5, 15.6, 16.3, 14.7, 17.2, 15.8, 16.4, 14.3, 18.1, 15.4, 16.9, 14.6, 17.8, 15.2, 16.0, 14.8, 17.4]
                zenith:
                  type: array
                  description: Optional pre-calculated zenith angles (64 values). If provided along with horizon, obstruction calculation will be skipped.
                  items:
                    type: number
                  example: [10.2, 11.1, 9.8, 12.3, 10.5, 11.4, 9.5, 13.1, 10.8, 11.7, 9.7, 12.9, 10.3, 11.2, 9.9, 12.5, 10.6, 11.5, 9.6, 12.4, 10.9, 11.8, 9.4, 13.2, 10.4, 12.0, 9.8, 12.8, 10.1, 11.0, 9.7, 12.2, 10.2, 11.1, 9.8, 12.3, 10.5, 11.4, 9.5, 13.1, 10.8, 11.7, 9.7, 12.9, 10.3, 11.2, 9.9, 12.5, 10.6, 11.5, 9.6, 12.4, 10.9, 11.8, 9.4, 13.2, 10.4, 12.0, 9.8, 12.8, 10.1, 11.0, 9.7, 12.2]
        responses:
          200:
            description: Daylight factor result as 128x128 RGB image
            schema:
              type: object
              properties:
                status:
                  type: string
                  example: "success"
                result:
                  type: array
                  description: 128x128 RGB image array
          400:
            description: Bad request
          500:
            description: Internal server error
        """
        return self._request_handler.handle(request)

    def handle_merge(self) -> Tuple[Response, int]:
        """Merge multiple window simulation results

        Combines simulation results from multiple windows into a single merged daylight factor matrix and mask.
        ---
        tags:
          - Merger
        parameters:
          - in: body
            name: body
            required: true
            schema:
              type: object
              required:
                - simulation
                - room_polygon
                - windows
              properties:
                simulation:
                  type: object
                  description: Dictionary of simulation results by window name
                  example: {"window_1": {"df_values": [[0.5, 0.3], [0.7, 0.2]], "mask": [[1, 1], [1, 1]]}, "window_2": {"df_values": [[0.4, 0.6], [0.8, 0.1]], "mask": [[1, 1], [1, 1]]}}
                room_polygon:
                  $ref: '#/definitions/RoomPolygon'
                windows:
                  type: object
                  description: Window configurations with direction angles
                  example: {"window_1": {"x1": -0.4, "y1": 7, "z1": 2.8, "x2": -2, "y2": 7.3, "z2": 5.4, "window_frame_ratio": 0.41, "direction_angle": 90}, "window_2": {"x1": 0.4, "y1": 7, "z1": 2.8, "x2": 2, "y2": 7.3, "z2": 5.4, "window_frame_ratio": 0.41, "direction_angle": 90}}
        responses:
          200:
            description: Merged simulation results
            schema:
              allOf:
                - $ref: '#/definitions/SuccessResponse'
                - type: object
                  properties:
                    result:
                      type: array
                      description: Merged daylight factor matrix (128x128 RGB image)
                      items:
                        type: array
                        items:
                          type: number
                    mask:
                      type: array
                      description: Merged room mask
                      items:
                        type: array
                        items:
                          type: integer
          400:
            description: Bad request
            schema:
              $ref: '#/definitions/ErrorResponse'
          500:
            description: Internal server error
            schema:
              $ref: '#/definitions/ErrorResponse'
        """
        return self._request_handler.handle(request)
