import requests
import json

# Test the local server endpoint
assets_folder = "..assets"
imgname = "sample.png"

with open(f"{assets_folder}/{imgname}", "rb") as f:
    print(f"📂 Loading image: {assets_folder}/{imgname}")
    files = {"file": (imgname, f)}
    resp = requests.post(
        "http://127.0.0.1:8081/get_df",
        files=files,
        data={
            "translation": json.dumps({"x": 15 * 50, "y": 0 * 50}),
            "rotation": json.dumps([0])
        }
    )
    print(f"📊 Response status: {resp.status_code}")
    print(json.dumps(resp.json(), indent=2))
