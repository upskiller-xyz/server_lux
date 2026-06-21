"""Manual smoke check against a *running* local server — not a unit test.

Run it explicitly against a live server::

    python tests/test_local_endpoint.py
    SERVER_URL=http://127.0.0.1:8081 SAMPLE_IMAGE=assets/sample.png python tests/test_local_endpoint.py

The request logic lives under ``if __name__ == "__main__"`` so pytest can import
this module without opening files or firing a live HTTP call at collection time.
"""
import json
import os
from pathlib import Path

import requests

# Repo root = parent of tests/. Paths resolve from here regardless of cwd.
_REPO_ROOT = Path(__file__).resolve().parent.parent
_DEFAULT_IMAGE = _REPO_ROOT / "assets" / "sample.png"
_DEFAULT_URL = "http://127.0.0.1:8081/get_df"


def main() -> None:
    image_path = Path(os.environ.get("SAMPLE_IMAGE", _DEFAULT_IMAGE))
    url = os.environ.get("SERVER_URL", _DEFAULT_URL)

    if not image_path.is_file():
        raise SystemExit(f"❌ Sample image not found: {image_path}")

    with open(image_path, "rb") as f:
        print(f"📂 Loading image: {image_path}")
        files = {"file": (image_path.name, f)}
        resp = requests.post(
            url,
            files=files,
            data={
                "translation": json.dumps({"x": 15 * 50, "y": 0 * 50}),
                "rotation": json.dumps([0]),
            },
        )

    print(f"📊 Response status: {resp.status_code}")
    print(json.dumps(resp.json(), indent=2))


if __name__ == "__main__":
    main()
