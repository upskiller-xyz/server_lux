# API Documentation

Server Lux provides a REST API for daylight simulation, obstruction analysis, and room encoding. All endpoints are prefixed with `/v1`.

## Base URL

- **Local**: `http://localhost:8080/v1`
- **Production**: `https://api.upskiller.xyz/v1`

## Endpoints

### Health Check

#### `GET /`

Check server status and service availability.

**Response:**
```json
{
  "status": "running",
  "services": {
    "encoder": "ready",
    "merger": "ready",
    "model": "ready",
    "obstruction": "ready",
    "stats": "ready"
  }
}
```

---

### Simulation & Analysis

#### `POST /v1/run`

End-to-end daylight simulation including obstruction calculation, encoding, and model prediction.

**Request:**
```json
{
  "model_type": "df_default",
  "parameters": {
    "height_roof_over_floor": 19.7,
    "floor_height_above_terrain": 2.71,
    "room_polygon": [[0, 0], [0, 7], [-3, 7], [-3, 0]],
    "windows": {
      "main_window": {
        "x1": -0.4, "y1": 7, "z1": 2.8,
        "x2": -2, "y2": 7.3, "z2": 5.4,
        "window_frame_ratio": 0.41
      }
    }
  },
  "mesh": [/* array of mesh triangles */]
}
```

**Response:**
```json
{
  "status": "success",
  "result": [/* 128x128 RGB image array */]
}
```

---

### Obstruction Analysis

#### `POST /v1/obstruction_all`

Calculate horizon and zenith obstruction angles for all 64 directions around a window.

**Request:**
```json
{
  "x": 39.98,
  "y": 48.78,
  "z": 18.65,
  "mesh": [/* array of mesh triangles */]
}
```

**Response:**
```json
{
  "status": "success",
  "horizon_angles": [/* 64 angles in degrees */],
  "zenith_angles": [/* 64 angles in degrees */]
}
```

#### `POST /v1/horizon_angle`

Calculate single horizon obstruction angle for a specific direction.

**Request:**
```json
{
  "x": 39.98,
  "y": 48.78,
  "z": 18.65,
  "direction_angle": 45.0,
  "mesh": [/* array of mesh triangles */]
}
```

**Response:**
```json
{
  "status": "success",
  "horizon_angle": 15.5
}
```

#### `POST /v1/zenith_angle`

Calculate single zenith obstruction angle for a specific direction.

**Request:** Same as `/horizon_angle`

**Response:**
```json
{
  "status": "success",
  "zenith_angle": 10.2
}
```

---

### Window Geometry

#### `POST /v1/get-reference-point`

Get the reference point (center) of each window for obstruction calculations.

**Request:**
```json
{
  "room_polygon": [[0, 0], [0, 7], [-3, 7], [-3, 0]],
  "windows": {
    "test_window": {
      "x1": -2, "y1": 7, "z1": 2.8,
      "x2": -0.4, "y2": 7.2, "z2": 5.4
    }
  }
}
```

**Response:**
```json
{
  "status": "success",
  "windows": {
    "test_window": {
      "reference_point": {"x": -1.2, "y": 7.1, "z": 4.1}
    }
  }
}
```

#### `POST /v1/calculate-direction`

Calculate the outward normal direction angle for each window.

**Request:** Same as `/get-reference-point`

**Response:**
```json
{
  "status": "success",
  "windows": {
    "test_window": {
      "direction_angle": 90.5
    }
  }
}
```

---

### Encoding

#### `POST /v1/encode`

Encode room and window parameters into model input format (ZIP file with NPY arrays).

**Request:**
```json
{
  "model_type": "df_default",
  "parameters": {
    "height_roof_over_floor": 19.7,
    "floor_height_above_terrain": 2.71,
    "room_polygon": [[0, 0], [0, 7], [-3, 7], [-3, 0]],
    "windows": {
      "main_window": {
        "x1": -0.4, "y1": 7, "z1": 2.8,
        "x2": -2, "y2": 7.3, "z2": 5.4,
        "window_frame_ratio": 0.41
      }
    }
  },
  "mesh": [/* array of mesh triangles */]
}
```

**Response:** Binary ZIP file containing `image.npy` (128x128 encoded image array)

**Python example:**
```python
import zipfile
from io import BytesIO
import numpy as np

response = requests.post(f"{SERVER_URL}/encode", json=payload)
zip_buffer = BytesIO(response.content)

with zipfile.ZipFile(zip_buffer, 'r') as zip_file:
    with zip_file.open('image.npy') as npy_file:
        image_array = np.load(npy_file)
```

#### `POST /v1/encode_raw`

Encode room parameters with pre-calculated obstruction angles.

**Request:**
```json
{
  "model_type": "df_default",
  "parameters": {
    "height_roof_over_floor": 19.7,
    "floor_height_above_terrain": 2.71,
    "room_polygon": [[0, 0], [0, 7], [-3, 7], [-3, 0]],
    "windows": {
      "main_window": {
        "x1": -0.4, "y1": 7, "z1": 2.8,
        "x2": -2, "y2": 7.3, "z2": 5.4,
        "window_frame_ratio": 0.41,
        "direction_angle": 90.0,
        "obstruction_angle_horizon": [/* 64 angles */],
        "obstruction_angle_zenith": [/* 64 angles */]
      }
    }
  }
}
```

**Response:** Binary ZIP file (same format as `/encode`)

---

### Statistics

#### `POST /v1/stats`

Calculate statistical metrics for daylight simulation results.

**Request:**
```json
{
  "df_matrix": [/* 2D array of daylight factor values */],
  "room_mask": [/* 2D boolean array marking room area */]
}
```

**Response:**
```json
{
  "status": "success",
  "mean": 2.5,
  "median": 2.3,
  "min": 0.1,
  "max": 5.8,
  "std": 1.2
}
```

#### `POST /v1/merge`

Merge multiple window simulation results into a single combined image.

**Request:**
```json
{
  "window_results": {
    "window_1": {
      "df_matrix": [/* 2D array */],
      "room_mask": [/* 2D array */]
    },
    "window_2": {
      "df_matrix": [/* 2D array */],
      "room_mask": [/* 2D array */]
    }
  }
}
```

**Response:**
```json
{
  "status": "success",
  "merged_result": {
    "df_matrix": [/* merged 2D array */],
    "room_mask": [/* merged 2D array */]
  }
}
```

---

## Error Responses

All endpoints return errors in the following format:

```json
{
  "status": "error",
  "error": "Description of what went wrong",
  "error_type": "validation_error"
}
```

**Common HTTP Status Codes:**
- `200` - Success
- `400` - Bad Request (invalid parameters)
- `403` - Forbidden (authentication required)
- `500` - Internal Server Error
- `503` - Service Unavailable
- `504` - Gateway Timeout

---

## Examples

See [example/demo.ipynb](../example/demo.ipynb) for complete working examples of all endpoints.
