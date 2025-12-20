# `/run` Endpoint Request Schema

## Overview

The `/v1/run` endpoint executes a complete daylight simulation workflow that:
1. Calculates obstruction angles (horizon and zenith) from the provided mesh
2. Encodes room parameters with obstruction data
3. Runs daylight simulation on the encoded data
4. Merges results from multiple windows
5. Returns the final simulation results

## Request Format

**Endpoint:** `POST /v1/run`

**Content-Type:** `application/json`

## Request Body Schema

```json
{
  "model_type": "string (required)",
  "parameters": {
    "height_roof_over_floor": "float (required)",
    "floor_height_above_terrain": "float (required)",
    "room_polygon": "array of [x, y] coordinates (required)",
    "windows": {
      "window_name": {
        "x1": "float (required)",
        "y1": "float (required)",
        "z1": "float (required)",
        "x2": "float (required)",
        "y2": "float (required)",
        "z2": "float (required)",
        "window_frame_ratio": "float (required, 0-1)",
        "direction_angle": "float (optional, radians, auto-calculated if not provided)"
      }
    }
  },
  "mesh": "array of [x, y, z] coordinates (required, min 3 points)"
}
```

## Field Descriptions

### Root Level

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `model_type` | string | Yes | Model type identifier (e.g., "df_default") |
| `parameters` | object | Yes | Room parameters including windows |
| `mesh` | array | Yes | 3D mesh data for obstruction angle calculation |

### Parameters Object

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `height_roof_over_floor` | float | Yes | Height from floor to roof in meters |
| `floor_height_above_terrain` | float | Yes | Floor height above terrain in meters |
| `room_polygon` | array | Yes | Array of [x, y] coordinates defining room boundary |
| `windows` | object | Yes | Dictionary of window definitions (key: window name, value: window object) |

### Window Object

Each window in the `windows` dictionary contains:

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `x1`, `y1`, `z1` | float | Yes | First corner coordinates (absolute, same coordinate system as room) |
| `x2`, `y2`, `z2` | float | Yes | Second corner coordinates (absolute, same coordinate system as room) |
| `window_frame_ratio` | float | Yes | Frame ratio (0-1), portion of window occupied by frame |
| `direction_angle` | float | No | Window direction angle in radians (auto-calculated if not provided) |

**Note:** The `obstruction_angle_horizon` and `obstruction_angle_zenith` fields are automatically calculated from the mesh for each window and do not need to be provided in the request. Each window is processed through the complete workflow: obstruction calculation → encoding → simulation.

### Mesh Array

3D mesh representing obstructing geometry:
- Each element is an [x, y, z] coordinate
- Represents buildings, terrain, or other obstructions

**Note:** Translation and rotation parameters are currently set to default values (translation: {x: 0, y: 0}, rotation: [0]) and will be integrated in a future update.

## Example Request

```json
{
  "model_type": "df_default",
  "parameters": {
    "height_roof_over_floor": 2.7,
    "floor_height_above_terrain": 3.0,
    "room_polygon": [[0, 0], [5, 0], [5, 4], [0, 4]],
    "windows": {
      "main_window": {
        "x1": -0.6,
        "y1": 0.0,
        "z1": 0.9,
        "x2": 0.6,
        "y2": 0.0,
        "z2": 2.4,
        "window_frame_ratio": 0.15
      }
    }
  },
  "mesh": [
    [10, 0, 0],
    [10, 0, 5],
    [10, 10, 5],
    [10, 10, 0]
  ]
}
```

## Response Format

### Success Response (200 OK)

Returns the final merged result as an RGB image array:

```json
{
  "status": "success",
  "result": [[[r, g, b], ...], ...]  // 2D array of RGB triplets
}
```

**Note:** The response dimensions can vary based on the room_polygon and window configurations.

### Error Response (400 Bad Request)

```json
{
  "status": "error",
  "error": "Missing required field: model_type"
}
```

```json
{
  "status": "error",
  "error": "Mesh must contain at least 3 points"
}
```

### Error Response (500 Internal Server Error)

```json
{
  "status": "error",
  "error": "Obstruction calculation failed: <error details>"
}
```

```json
{
  "status": "error",
  "error": "Encoding failed: <error details>"
}
```

## Validation Rules

1. **Required Fields:**
   - `model_type` must be present and non-empty
   - `parameters` must be a valid object with required fields
   - `parameters.windows` must be a dictionary with at least one window
   - `mesh` must be an array with at least 3 points

2. **Window Validation:**
   - All required window fields must be present for each window (x1, y1, z1, x2, y2, z2, window_frame_ratio)
   - Window coordinates must be in absolute coordinates (same system as room_polygon)
   - All numeric fields must be valid floats
   - `window_frame_ratio` must be between 0 and 1

3. **Mesh Validation:**
   - Must be an array of arrays
   - Each point must have [x, y, z] coordinates

## Python Example

```python
import requests
import json

url = "http://localhost:8080/v1/run"

payload = {
    "model_type": "df_default",
    "parameters": {
        "height_roof_over_floor": 2.7,
        "floor_height_above_terrain": 3.0,
        "room_polygon": [[0, 0], [5, 0], [5, 4], [0, 4]],
        "windows": {
            "main_window": {
                "x1": -0.6, "y1": 0.0, "z1": 0.9,
                "x2": 0.6, "y2": 0.0, "z2": 2.4,
                "window_frame_ratio": 0.15
            }
        }
    },
    "mesh": [
        [10, 0, 0], [10, 0, 5],
        [10, 10, 5], [10, 10, 0]
    ]
}

response = requests.post(url, json=payload)

if response.status_code == 200:
    result = response.json()
    print("Simulation successful!")
    print(f"Result shape: {result.get('shape')}")
else:
    error = response.json()
    print(f"Error: {error.get('error')}")
```

## TypeScript Example

```typescript
const url = "http://localhost:8080/v1/run";

const payload = {
  model_type: "df_default",
  parameters: {
    height_roof_over_floor: 2.7,
    floor_height_above_terrain: 3.0,
    room_polygon: [[0, 0], [5, 0], [5, 4], [0, 4]],
    windows: {
      main_window: {
        x1: -0.6, y1: 0.0, z1: 0.9,
        x2: 0.6, y2: 0.0, z2: 2.4,
        window_frame_ratio: 0.15
      }
    }
  },
  mesh: [
    [10, 0, 0], [10, 0, 5],
    [10, 10, 5], [10, 10, 0]
  ]
};

fetch(url, {
  method: "POST",
  headers: { "Content-Type": "application/json" },
  body: JSON.stringify(payload)
})
  .then(res => res.json())
  .then(data => {
    if (data.status === "success") {
      console.log("Simulation successful!");
      console.log("Result:", data);
    } else {
      console.error("Error:", data.error);
    }
  })
  .catch(err => console.error("Request failed:", err));
```

## Notes

- The window center position for obstruction calculation is automatically computed as the midpoint between (x1, y1, z1) and (x2, y2, z2)
- You can include multiple windows in a single request - each will be processed independently and combined in the final result
- The final output matrix dimensions can vary based on room geometry and window configurations
