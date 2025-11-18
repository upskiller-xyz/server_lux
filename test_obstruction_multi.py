#!/usr/bin/env python3
"""Test script for obstruction_multi endpoint"""

import requests
import json
import math

# Test data
url = "http://localhost:8081/obstruction_multi"

# Example mesh data (vertical wall and horizontal roof)
mesh = [
    # Vertical wall triangles
    [10.0, -5.0, 0.0],
    [10.0, -5.0, 8.0],
    [10.0, 5.0, 0.0],
    [10.0, 5.0, 0.0],
    [10.0, -5.0, 8.0],
    [10.0, 5.0, 8.0],
    # Horizontal roof triangles
    [2.0, -5.0, 5.0],
    [2.0, 5.0, 5.0],
    [8.0, -5.0, 5.0],
    [2.0, 5.0, 5.0],
    [8.0, 5.0, 5.0],
    [8.0, -5.0, 5.0]
]

# Window at origin, facing East (0 radians)
payload = {
    "x": 0.0,
    "y": 0.0,
    "z": 3.0,
    "direction_angle": 0.0,  # Facing +X (East)
    "mesh": mesh,
    "start_angle": 17.5,     # Optional, default
    "end_angle": 162.5,      # Optional, default
    "num_directions": 64     # Optional, default
}

print("Testing /obstruction_multi endpoint...")
print(f"Request payload: {json.dumps(payload, indent=2)}")
print("\nNote: Server must be running on port 8081")
print("Start server with: python src/main.py\n")

try:
    response = requests.post(url, json=payload, timeout=600)

    print(f"Status code: {response.status_code}")

    if response.status_code == 200:
        result = response.json()
        print(f"\nResponse status: {result.get('status')}")

        if result.get('status') == 'success':
            data = result['data']
            print(f"Number of directions: {data['num_directions']}")
            print(f"Start angle: {data['start_angle']}°")
            print(f"End angle: {data['end_angle']}°")
            print(f"\nFirst 5 horizon angles: {data['horizon_angles'][:5]}")
            print(f"First 5 zenith angles: {data['zenith_angles'][:5]}")
            print(f"First 5 direction angles: {data['direction_angles'][:5]}")
            print(f"\nLast 5 horizon angles: {data['horizon_angles'][-5:]}")
            print(f"Last 5 zenith angles: {data['zenith_angles'][-5:]}")
            print(f"Last 5 direction angles: {data['direction_angles'][-5:]}")
            print(f"\nTotal horizon angles: {len(data['horizon_angles'])}")
            print(f"Total zenith angles: {len(data['zenith_angles'])}")
            print("\n✅ Test passed!")
        else:
            print(f"\n❌ Error: {result.get('error')}")
    else:
        print(f"\n❌ Request failed with status {response.status_code}")
        print(f"Response: {response.text}")

except requests.exceptions.ConnectionError:
    print("❌ Could not connect to server. Make sure the server is running on port 8081")
except requests.exceptions.Timeout:
    print("❌ Request timed out after 600 seconds")
except Exception as e:
    print(f"❌ Error: {str(e)}")
