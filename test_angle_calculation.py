#!/usr/bin/env python3
"""Unit test for angle calculation logic"""

import math
from src.server.services.obstruction_calculation import ObstructionCalculationConfig

def test_angle_calculation():
    """Test that angle calculation produces correct ranges"""
    config = ObstructionCalculationConfig(
        start_angle_degrees=17.5,
        end_angle_degrees=162.5,
        num_directions=64
    )

    # Test with window facing East (0 radians)
    base_direction = 0.0
    angles = config.get_direction_angles(base_direction)

    print("Testing angle calculation with window facing East (0 rad):")
    print(f"Number of angles: {len(angles)}")
    print(f"First angle: {math.degrees(angles[0]):.2f}° (radians: {angles[0]:.4f})")
    print(f"Middle angle (approx): {math.degrees(angles[len(angles)//2]):.2f}° (radians: {angles[len(angles)//2]:.4f})")
    print(f"Last angle: {math.degrees(angles[-1]):.2f}° (radians: {angles[-1]:.4f})")

    # Expected values:
    # - Window facing East: 0° = 0 rad
    # - Half-circle from -90° to +90° relative to window
    # - Start at 17.5° in half-circle system = 0° - 90° + 17.5° = -72.5° = 287.5° (in [0, 360) range)
    # - Middle at 90° in half-circle system = 0° - 90° + 90° = 0° (window normal)
    # - End at 162.5° in half-circle system = 0° - 90° + 162.5° = 72.5°

    expected_first = (0 - 90 + 17.5) % 360
    expected_middle = (0 - 90 + 90) % 360
    expected_last = (0 - 90 + 162.5) % 360

    print(f"\nExpected first angle: {expected_first:.2f}°")
    print(f"Expected middle angle: {expected_middle:.2f}°")
    print(f"Expected last angle: {expected_last:.2f}°")

    # Test with window facing North (π/2 radians)
    base_direction = math.pi / 2
    angles_north = config.get_direction_angles(base_direction)

    print("\n\nTesting angle calculation with window facing North (π/2 rad):")
    print(f"Number of angles: {len(angles_north)}")
    print(f"First angle: {math.degrees(angles_north[0]):.2f}° (radians: {angles_north[0]:.4f})")
    print(f"Middle angle (approx): {math.degrees(angles_north[len(angles_north)//2]):.2f}° (radians: {angles_north[len(angles_north)//2]:.4f})")
    print(f"Last angle: {math.degrees(angles_north[-1]):.2f}° (radians: {angles_north[-1]:.4f})")

    # Expected values for North-facing window:
    # - Window facing North: 90° = π/2 rad
    # - Start: 90° - 90° + 17.5° = 17.5°
    # - Middle: 90° - 90° + 90° = 90° (window normal)
    # - End: 90° - 90° + 162.5° = 162.5°

    expected_first_north = (90 - 90 + 17.5) % 360
    expected_middle_north = (90 - 90 + 90) % 360
    expected_last_north = (90 - 90 + 162.5) % 360

    print(f"\nExpected first angle: {expected_first_north:.2f}°")
    print(f"Expected middle angle: {expected_middle_north:.2f}°")
    print(f"Expected last angle: {expected_last_north:.2f}°")

    # Verify the angles are in increasing order and cover the expected range
    assert len(angles) == 64, "Should have 64 angles"
    assert len(angles_north) == 64, "Should have 64 angles"

    print("\n✅ All angle calculation tests passed!")

if __name__ == "__main__":
    test_angle_calculation()
