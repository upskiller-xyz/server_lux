# API Documentation

This document describes the main API endpoints for the Model Server.
Example requests are provided in both **Python** (using `requests`) and **TypeScript** (using `fetch`). Use [the playground notebook](../playground.ipynb) for hands-on examples with the API.

---

## `/`
**GET** `/`
Health check endpoint that returns the current server status and information.

### Request
- **Content-Type:** Not required (GET request)
- **Body:** None

### Response
- **200 OK**
  ```json
  {
    "name": "Upskiller Model Server",
    "version": "2.0.0",
    "status": "running"
  }
  ```

### Python Example
```python
import requests

response = requests.get("http://localhost:8000/")
print(response.json())
# Output: {"name": "Upskiller Model Server", "version": "2.0.0", "status": "running"}
```

### TypeScript Example
```typescript
fetch("http://localhost:8000/")
  .then(res => res.json())
  .then(data => console.log(data));
```

---

## `/run`
**POST** `/run`
Executes complete daylight simulation workflow: obstruction angle calculation → room encoding → daylight simulation → postprocessing.

**For detailed schema documentation, see [run_schema.md](run_schema.md)**

### Request
- **Content-Type:** `application/json`
- **Body:** See [run_schema.md](run_schema.md) for complete schema

### Quick Reference
```json
{
  "model_type": "df_default",
  "parameters": {
    "height_roof_over_floor": 2.7,
    "floor_height_above_terrain": 3.0,
    "room_polygon": [[0, 0], [5, 0], [5, 4], [0, 4]],
    "windows": {
      "window_name": { /* window definition */ }
    }
  },
  "mesh": [[x, y, z], ...]  // Min 3 points
}
```

**Note:** Translation and rotation are currently set to defaults ({x: 0, y: 0} and [0]) and will be configurable in a future update.

### Response
- **200 OK** (Success)
  ```json
  {
    "status": "success",
    "content": "base64_encoded_numpy_array",
    "shape": [height, width]
  }
  ```
- **400 Bad Request** (Invalid input)
  ```json
  {
    "status": "error",
    "error": "Missing required field: model_type"
  }
  ```
- **500 Internal Server Error** (Processing error)
  ```json
  {
    "status": "error",
    "error": "Obstruction calculation failed: <details>"
  }
  ```

### Python Example
```python
import requests

url = "http://localhost:8081/run"

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
                "window_sill_height": 0.9,
                "window_frame_ratio": 0.15,
                "window_height": 1.5
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
else:
    print(f"Error: {response.json().get('error')}")
```

### TypeScript Example
```typescript
const url = "http://localhost:8081/run";

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
        window_sill_height: 0.9,
        window_frame_ratio: 0.15,
        window_height: 1.5
      }
    }
  },
  mesh: [[10, 0, 0], [10, 0, 5], [10, 10, 5], [10, 10, 0]]
};

fetch(url, {
  method: "POST",
  headers: { "Content-Type": "application/json" },
  body: JSON.stringify(payload)
})
  .then(res => res.json())
  .then(data => {
    if (data.status === "success") {
      console.log("Simulation successful!", data);
    } else {
      console.error("Error:", data.error);
    }
  });
```


---

## `/simulate`
**POST** `/simulate`
Runs daylight simulation on an uploaded encoded room image. This is the new name for the `/get_df` endpoint (which is kept for backwards compatibility).

### Request
- **Content-Type:** `multipart/form-data`
- **Body:**
  - `file`: Encoded room image (PNG/JPG)
  - `translation`: JSON string with `{"x": float, "y": float}` (optional)
  - `rotation`: JSON string with `[angle]` array (optional)

### Response
- **200 OK** (Success)
  ```json
  {
    "status": "success",
    "content": "base64_encoded_numpy_array",
    "shape": [height, width]
  }
  ```
- **400 Bad Request**
  ```json
  {
    "status": "error",
    "error": "No file provided in request"
  }
  ```
- **500 Internal Server Error**
  ```json
  {
    "status": "error",
    "error": "<error message>"
  }
  ```

### Python Example
```python
import requests
import json

with open("encoded_room.png", "rb") as f:
    files = {"file": ("encoded_room.png", f)}
    response = requests.post(
        "http://localhost:8081/simulate",
        files=files,
        data={
            "translation": json.dumps({"x": 750, "y": 0}),
            "rotation": json.dumps([0])
        }
    )

result = response.json()
if result.get("status") == "success":
    print(f"Simulation complete! Shape: {result['shape']}")
```

### TypeScript Example
```typescript
const formData = new FormData();
const fileInput = document.getElementById('imageFile') as HTMLInputElement;
if (fileInput.files?.[0]) {
  formData.append('file', fileInput.files[0]);
  formData.append('translation', JSON.stringify({x: 750, y: 0}));
  formData.append('rotation', JSON.stringify([0]));
}

fetch("http://localhost:8081/simulate", {
  method: "POST",
  body: formData
})
  .then(res => res.json())
  .then(data => console.log(data));
```

---

## Error Handling

### Client Errors (4xx)
- **400 Bad Request**: Missing file upload or invalid file format
- **422 Unprocessable Entity**: File processing errors

### Server Errors (5xx)
- **500 Internal Server Error**: Model inference failures, memory issues, or server crashes

### Error Response Format
```json
{
  "error": "Descriptive error message",
  "status": "error"  // May be present
}
```

---

## Usage Notes

- **Server Port**: Default port is 8000 (configurable via `PORT` environment variable)
- **File Upload**: Always use `multipart/form-data` for file uploads
- **Content Types**: Server validates uploaded files are images
- **Model Loading**: Model is loaded on first prediction request (may cause initial delay)
- **Response Format**: All endpoints return JSON responses
- **Logging**: Server provides structured logging for monitoring and debugging

---

## `/encode`
**POST** `/encode`
Encodes room data and parameters into a PNG image representation. **Protected by token authentication.**

### Authentication
This endpoint requires Bearer token authentication:
```
Authorization: Bearer <your_token>
```

Configure the token by setting the `API_TOKEN` environment variable on the server.

### Request
- **Content-Type:** `application/json`
- **Headers:**
  - `Authorization: Bearer <token>` (required)
- **Body:**
  - `model_type`: The model type to use for encoding (e.g., "df_default")
  - `parameters`: Object containing room and window parameters
    - `height_roof_over_floor`: Height from floor to roof (float)
    - `floor_height_above_terrain`: Floor height above terrain (float)
    - `room_polygon`: Array of [x, y] coordinates defining the room shape
    - `windows`: Object containing window definitions
      - Each window is keyed by name and contains:
        - `x1`, `y1`, `z1`: First corner coordinates
        - `x2`, `y2`, `z2`: Second corner coordinates
        - `window_sill_height`: Height of window sill
        - `window_frame_ratio`: Frame ratio (0-1)
        - `window_height`: Height of window
        - `obstruction_angle_horizon`: Horizon obstruction angle (degrees)
        - `obstruction_angle_zenith`: Zenith obstruction angle (degrees)

### Response
- **200 OK** (Success)
  - Returns PNG image binary data
  - Content-Type: `image/png`
- **400 Bad Request** (Invalid input or missing authentication)
  ```json
  {
    "status": "error",
    "error": "Missing Authorization header"
  }
  ```
  ```json
  {
    "status": "error",
    "error": "Invalid authentication token"
  }
  ```
  ```json
  {
    "status": "error",
    "error": "Missing required field: model_type"
  }
  ```
- **500 Internal Server Error** (Processing error)
  ```json
  {
    "status": "error",
    "error": "<error message>"
  }
  ```

### Python Example
```python
import requests

url = "http://localhost:8081/encode"
token = "your_api_token_here"

headers = {
    "Authorization": f"Bearer {token}",
    "Content-Type": "application/json"
}

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
                "window_sill_height": 0.9,
                "window_frame_ratio": 0.15,
                "window_height": 1.5,
                "obstruction_angle_horizon": 15.0,
                "obstruction_angle_zenith": 10.0
            }
        }
    }
}

response = requests.post(url, headers=headers, json=payload)

if response.status_code == 200:
    with open("encoded_room.png", "wb") as f:
        f.write(response.content)
    print("Image saved successfully!")
else:
    print(f"Error: {response.json()}")
```

### TypeScript Example
```typescript
const url = "http://localhost:8081/encode";
const token = "your_api_token_here";

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
        window_sill_height: 0.9,
        window_frame_ratio: 0.15,
        window_height: 1.5,
        obstruction_angle_horizon: 15.0,
        obstruction_angle_zenith: 10.0
      }
    }
  }
};

fetch(url, {
  method: "POST",
  headers: {
    "Authorization": `Bearer ${token}`,
    "Content-Type": "application/json"
  },
  body: JSON.stringify(payload)
})
  .then(res => {
    if (res.ok) {
      return res.blob();
    }
    throw new Error(`HTTP error! status: ${res.status}`);
  })
  .then(blob => {
    const url = window.URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = 'encoded_room.png';
    a.click();
  })
  .catch(err => console.error('Request failed:', err));
```

### cURL Example
```bash
curl -X POST \
  -H "Authorization: Bearer your_api_token_here" \
  -H "Content-Type: application/json" \
  -d '{
    "model_type": "df_default",
    "parameters": {
      "height_roof_over_floor": 2.7,
      "floor_height_above_terrain": 3.0,
      "room_polygon": [[0, 0], [5, 0], [5, 4], [0, 4]],
      "windows": {
        "main_window": {
          "x1": -0.6, "y1": 0.0, "z1": 0.9,
          "x2": 0.6, "y2": 0.0, "z2": 2.4,
          "window_sill_height": 0.9,
          "window_frame_ratio": 0.15,
          "window_height": 1.5,
          "obstruction_angle_horizon": 15.0,
          "obstruction_angle_zenith": 10.0
        }
      }
    }
  }' \
  --output encoded_room.png \
  http://localhost:8081/encode
```

---

## Development & Testing

### Local Development
```bash
# Start the server
python main.py

# Test health check
curl http://localhost:8000/

# Test prediction with sample image
curl -X POST -F "file=@sample.jpg" http://localhost:8000/run
```

### Environment Variables
- `MODEL`: Model checkpoint name (default: "df_default_2.0.0")
- `PORT`: Server port (default: 8000)
- `API_TOKEN`: Authentication token for protected endpoints (required for `/encode`)

---