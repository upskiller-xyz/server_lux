# API Endpoints

Base URL: `http://localhost:8080`

All endpoints use `POST` method with `Content-Type: application/json` unless specified otherwise.

## Health Check

### `GET /`
Check server status.

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

## Endpoints (API v1)

### `/v1/run`
End-to-end simulation: calculates obstruction angles, encodes room, runs ML model, and returns daylight factor matrix.

**Request:**
```json
{
  "model_type": "df_default",
  "parameters": {
    "height_roof_over_floor": 19.7,
    "floor_height_above_terrain": 2.71,
    "room_polygon": [[0, 0], [0, 7], [-3, 7], [-3, 0]],
    "windows": {
      "window_1": {
        "x1": -0.4, "y1": 7, "z1": 2.8,
        "x2": -2, "y2": 7.3, "z2": 5.4,
        "window_frame_ratio": 0.41
      }
    }
  },
  "mesh": [[x1, y1, z1], [x2, y2, z2], ...]
}
```

**Response:**
```json
{
  "status": "success",
  "result": [[0.5, 0.3, ...], [0.2, 0.8, ...]]
}
```

---

### `/v1/stats`
Calculate statistics for daylight factor results.

**Request:**
```json
{
  "result": [[0.5, 0.3], [0.2, 0.8]],
  "mask": [[1, 1], [1, 1]]
}
```

**Response:**
```json
{
  "status": "success",
  "metrics": {
    "min": 0.1,
    "max": 9.2,
    "mean": 3.39,
    "median": 1.5,
    "valid_area": 50.0
  }
}
```

---

### `/v1/obstruction_all`
Calculate obstruction angles for a single window point in all directions.

**Request:**
```json
{
  "mesh": [[x1, y1, z1], [x2, y2, z2], ...],
  "x": 39.98,
  "y": 48.78,
  "z": 18.65
}
```

**Response:**
```json
{
  "status": "success",
  "horizon": [0.0, 1.2, ...],
  "zenith": [45.0, 43.2, ...]
}
```

---

### `/v1/encode`
Encode room geometry and windows into image representation.

**Request:**
```json
{
  "parameters": {
    "height_roof_over_floor": 19.7,
    "floor_height_above_terrain": 2.71,
    "room_polygon": [[0, 0], [0, 7], [-3, 7], [-3, 0]],
    "windows": {
      "window_1": {
        "x1": -0.4, "y1": 7, "z1": 2.8,
        "x2": -2, "y2": 7.3, "z2": 5.4,
        "window_frame_ratio": 0.41
      }
    }
  },
  "mesh": [[x1, y1, z1], [x2, y2, z2], ...]
}
```

**Response:**
Binary ZIP file containing `image.npy` (numpy array) and `mask.npy`.

---

### `/v1/get-reference-point`
Calculate reference point for windows.

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
  "results": {
    "test_window": {
      "reference_point": {"x": -1.2, "y": 7.1, "z": 4.1}
    }
  }
}
```

---

### `/v1/calculate-direction`
Calculate direction angles for windows.

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
  "results": {
    "test_window": {
      "direction_angle": 1.5708
    }
  }
}
```

---

## Other Endpoints

- `/v1/simulate` - Alias for `/v1/run`
- `/v1/horizon` - Calculate horizon obstruction angle only
- `/v1/zenith` - Calculate zenith obstruction angle only
- `/v1/obstruction` - Alias for `/v1/obstruction_all`
- `/v1/obstruction_multi` - Calculate obstruction for multiple points
- `/v1/obstruction_parallel` - Parallel obstruction calculation
- `/v1/encode_raw` - Raw encoding without preprocessing
- `/v1/merge` - Merge multiple window results

---

## Error Response Format

```json
{
  "status": "error",
  "error": "Error description",
  "error_type": "validation_error"
}
```
