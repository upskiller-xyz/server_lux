# Microservices Documentation

This document provides a comprehensive overview of all external microservices called by the server.

---

## 1. Color Management Service

**URL:** `https://colormanage-server-182483330095.europe-north2.run.app`

### Endpoints

#### `/to_rgb`
Converts numerical values to RGB representation using a specified colorscale.

**Input:**
```json
{
  "data": [[float, ...], ...],  // 2D array of numerical values
  "colorscale": "df"             // Colorscale identifier
}
```

**Output:**
```json
{
  "status": "success",
  "data": [[[r, g, b], ...], ...]  // 2D array of RGB triplets
}
```

#### `/to_values`
Converts RGB representation back to numerical values using a specified colorscale.

**Input:**
```json
{
  "data": [[[r, g, b], ...], ...],  // 2D array of RGB triplets
  "colorscale": "df"                 // Colorscale identifier
}
```

**Output:**
```json
{
  "status": "success",
  "data": [[float, ...], ...]  // 2D array of numerical values
}
```

---

## 2. Daylight Simulation Service

**URL:** `https://daylight-factor-182483330095.europe-north2.run.app`

### Endpoints

#### `/simulate` (alias: `/get_df`)
Performs daylight factor simulation on an encoded room image.

**Input:**
- **Content-Type:** `multipart/form-data`
- **file:** PNG image (encoded room representation)
- **translation:** JSON string `{"x": float, "y": float}`
- **rotation:** JSON string `[float]`

**Output:**
```json
{
  "status": "success",
  "content": "base64_encoded_numpy_array",
  "shape": [height, width]
}
```

Or:
```json
{
  "status": "success",
  "data": [[float, ...], ...],
  "metadata": {...}
}
```

---

## 3. DF Evaluation Service

**URL:** `https://df-eval-server-182483330095.europe-north2.run.app`

### Endpoints

#### `/get_stats`
Calculates statistics from daylight factor data.

**Input:**
```json
{
  "data": [[float, ...], ...]  // 2D array of daylight factor values
}
```

**Output:**
```json
{
  "status": "success",
  "mean": float,
  "median": float,
  "min": float,
  "max": float,
  "std": float
}
```

---

## 4. Obstruction Service

**URL:** `https://obstruction-server-182483330095.europe-north2.run.app`

### Endpoints

#### `/horizon_angle`
Calculates horizon obstruction angles from a 3D mesh.

**Input:**
```json
{
  "x": float,           // Position x-coordinate
  "y": float,           // Position y-coordinate
  "z": float,           // Position z-coordinate
  "rad_x": float,       // X-radius for sampling
  "rad_y": float,       // Y-radius for sampling
  "mesh": [[x, y, z], ...]  // 3D mesh points
}
```

**Output:**
```json
{
  "status": "success",
  "angles": [float, float, ...]  // 64 horizon angle values
}
```

#### `/zenith_angle`
Calculates zenith obstruction angles from a 3D mesh.

**Input:**
```json
{
  "x": float,
  "y": float,
  "z": float,
  "rad_x": float,
  "rad_y": float,
  "mesh": [[x, y, z], ...]
}
```

**Output:**
```json
{
  "status": "success",
  "angles": [float, float, ...]  // 64 zenith angle values
}
```

#### `/obstruction`
Calculates both horizon and zenith obstruction angles (legacy endpoint).

**Input:** Same as `/horizon_angle`

**Output:**
```json
{
  "status": "success",
  "horizon_angles": [float, ...],  // 64 values
  "zenith_angles": [float, ...]    // 64 values
}
```

#### `/obstruction_all`
Calculates both horizon and zenith obstruction angles (current endpoint).

**Input:**
```json
{
  "x": float,
  "y": float,
  "z": float,
  "rad_x": float,
  "rad_y": float,
  "mesh": [[x, y, z], ...]
}
```

**Output:**
```json
{
  "status": "success",
  "horizon_angles": [float, ...],  // 64 values
  "zenith_angles": [float, ...]    // 64 values
}
```

---

## 5. Encoder Service

**URL:** `https://encoder-server-182483330095.europe-north2.run.app`

### Endpoints

#### `/encode`
Encodes room parameters into a PNG image representation.

**Input:**
```json
{
  "model_type": "df_default",
  "parameters": {
    "height_roof_over_floor": float,
    "floor_height_above_terrain": float,
    "room_polygon": [[x, y], ...],
    "windows": {
      "window_name": {
        "x1": float, "y1": float, "z1": float,
        "x2": float, "y2": float, "z2": float,
        "window_sill_height": float,
        "window_frame_ratio": float,
        "window_height": float,
        "obstruction_angle_horizon": [float, ...],  // 64 values
        "obstruction_angle_zenith": [float, ...]    // 64 values
      }
    }
  }
}
```

**Output:**
- **Content-Type:** `image/png`
- **Body:** Binary PNG image data

---

## 6. Postprocessing Service

**URL:** `https://daylight-processing-182483330095.europe-north2.run.app`

### Endpoints

#### `/postprocess`
Combines multiple window simulation results into a single output matrix.

**Input:**
```json
{
  "windows": {
    "window_name": {
      "x1": float, "y1": float, "z1": float,
      "x2": float, "y2": float, "z2": float
    }
  },
  "results": {
    "window_name": {
      "status": "success",
      "content": "base64_encoded_numpy_array",
      "shape": [height, width]
    }
  },
  "room_polygon": [[x, y], ...]
}
```

**Output:**
```json
{
  "status": "success",
  "content": "base64_encoded_numpy_array",
  "shape": [height, width]
}
```

Or:
```json
{
  "status": "success",
  "data": [[float, ...], ...],
  "metadata": {...}
}
```

**Note:** Output dimensions can vary based on room_polygon and window configurations.

---

## Service Workflow in `/run` Endpoint

The `/run` endpoint orchestrates calls to multiple services in the following sequence:

```
For each window:
  1. Obstruction Service (/obstruction_all)
     └─> Calculate horizon and zenith angles

  2. Encoder Service (/encode)
     └─> Encode room with obstruction angles to PNG

  3. Daylight Service (/simulate)
     └─> Simulate daylight factor from encoded PNG

After all windows processed:
  4. Postprocessing Service (/postprocess)
     └─> Combine all window results into final matrix
```

### Data Flow

```
Request
  ├─> model_type, parameters, mesh
  │
  └─> For each window in parameters.windows:
      │
      ├─> [Obstruction] mesh + window center position
      │   └─> horizon_angles[64], zenith_angles[64]
      │
      ├─> [Encoder] parameters + obstruction angles
      │   └─> encoded PNG image
      │
      └─> [Daylight] PNG image + translation/rotation
          └─> daylight factor matrix

  └─> [Postprocess] all window results + room_polygon
      └─> Final combined matrix
```

---

## Error Handling

All services return error responses in the following format:

```json
{
  "status": "error",
  "error": "Error description"
}
```

The orchestration service will:
- Stop processing if a window fails at any step
- Return the error with partial results if available
- Skip postprocessing if any window simulation failed
