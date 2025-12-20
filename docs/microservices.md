# Microservices Documentation

Server Lux orchestrates requests across multiple specialized microservices. This document describes each service and its endpoints.

---

## Service Architecture

Server Lux acts as a gateway that:
- Receives client requests via REST API
- Orchestrates calls to specialized microservices
- Combines results from multiple services
- Returns unified responses to clients

**Default Port:** 8080
**API Version:** v1
**Base Path:** `/v1`

---

## Microservices

### 1. Obstruction Service

**Port:** 8081
**URL:** `http://localhost:8081`

Calculates horizon and zenith obstruction angles from 3D mesh data.

#### `/obstruction_all`
Calculate both horizon and zenith angles for all 64 directions.

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

#### `/horizon_angle`
Calculate single horizon angle for specific direction.

#### `/zenith_angle`
Calculate single zenith angle for specific direction.

---

### 2. Encoder Service

**Port:** 8082
**URL:** `http://localhost:8082`

Encodes room parameters and obstruction data into model input format.

#### `/encode`
Encode room geometry with obstruction angles.

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
        "window_frame_ratio": float,
        "obstruction_angle_horizon": [float, ...],
        "obstruction_angle_zenith": [float, ...]
      }
    }
  }
}
```

**Output:** Binary NPZ file containing encoded image arrays

---

### 3. Model Service

**Port:** 8083
**URL:** `http://localhost:8083`

Runs daylight simulation model on encoded room data.

#### `/simulate`
Perform daylight factor simulation.

**Input:** NPZ file (multipart/form-data)

**Output:**
```json
{
  "status": "success",
  "df_matrix": [[float, ...]],
  "room_mask": [[bool, ...]]
}
```

---

### 4. Merger Service

**Port:** 8084
**URL:** `http://localhost:8084`

Merges simulation results from multiple windows.

#### `/merge`
Combine multiple window results.

**Input:**
```json
{
  "window_results": {
    "window_name": {
      "df_matrix": [[float, ...]],
      "room_mask": [[bool, ...]]
    }
  }
}
```

**Output:**
```json
{
  "status": "success",
  "merged_result": {
    "df_matrix": [[float, ...]],
    "room_mask": [[bool, ...]]
  }
}
```

---

### 5. Stats Service

**Port:** 8085
**URL:** `http://localhost:8085`

Calculates statistical metrics and converts to RGB visualization.

#### `/calculate`
Calculate statistics and convert to RGB.

**Input:**
```json
{
  "df_matrix": [[float, ...]],
  "room_mask": [[bool, ...]]
}
```

**Output:**
```json
{
  "status": "success",
  "result": [[[r, g, b], ...]],
  "stats": {
    "mean": float,
    "median": float,
    "min": float,
    "max": float
  }
}
```

## Service Workflow

The `/v1/run` endpoint orchestrates these services in sequence:

```
For each window:
  1. Obstruction Service
     └─> Calculate horizon and zenith angles from mesh

  2. Encoder Service
     └─> Encode room + obstruction data to NPZ

  3. Model Service
     └─> Simulate daylight factor from encoded data

After all windows:
  4. Merger Service
     └─> Combine all window results

  5. Stats Service (separate)
     └─> Calculate statistics and convert to RGB
```

---

## Data Flow

```
Client Request
  │
  ├─> model_type, parameters, mesh
  │
  └─> For each window:
      │
      ├─> [Obstruction] mesh + window position
      │   └─> horizon_angles[64], zenith_angles[64]
      │
      ├─> [Encoder] parameters + obstruction angles
      │   └─> NPZ file (encoded arrays)
      │
      └─> [Model] NPZ file
          └─> df_matrix, room_mask
  │
  ├─> [Merger] all window results
      └─> merged df_matrix, room_mask
  ```

---

## Deployment Configuration

Configure service endpoints via environment variable:

- **`DEPLOYMENT_MODE=local`** - Uses `http://localhost:PORT` (development/testing)
- **`DEPLOYMENT_MODE=production`** - Uses configured production endpoints (default)

---

## Error Handling

All services return errors in this format:

```json
{
  "status": "error",
  "error": "Error description"
}
```

Server Lux orchestration behavior:
- Stops processing if any service fails
- Returns partial results when available
- Includes error details in response
