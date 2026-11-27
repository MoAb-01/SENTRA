"""
Test suite for geofence spatial logic and configuration export.
"""

import json
import os
import sys
import numpy as np

# Add parent directory
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from geofence_test import GeofenceApp


def run_tests():
    print("[TEST] Running Geofence Logic Unit Tests...")
    app = GeofenceApp()
    app.frame_width = 1000
    app.frame_height = 800

    # 1. Define a rectangular polygon: (200, 200) to (800, 600)
    test_points = [(200, 200), (800, 200), (800, 600), (200, 600)]
    app.polygon_points = list(test_points)
    app.is_zone_active = True

    # 2. Test spatial point inside: (500, 400)
    app.target_pos = (500, 400)
    app.evaluate_spatial_status()
    assert app.is_breached is True, "Target inside polygon should trigger breach!"
    print("  [OK] Point inside detection: PASS")

    # 3. Test spatial point outside: (100, 100)
    app.target_pos = (100, 100)
    app.evaluate_spatial_status()
    assert app.is_breached is False, "Target outside polygon should be clear!"
    print("  [OK] Point outside detection: PASS")

    # 4. Test spatial point on boundary: (200, 400)
    app.target_pos = (200, 400)
    app.evaluate_spatial_status()
    assert app.is_breached is True, "Target on boundary (dist=0) should be considered inside/breached!"
    print("  [OK] Point on boundary detection: PASS")

    # 5. Test JSON Export
    config_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), "zone_config.json")
    if os.path.exists(config_file):
        os.remove(config_file)

    app.export_config()
    assert os.path.exists(config_file), "zone_config.json should be created!"
    
    with open(config_file, "r", encoding="utf-8") as f:
        data = json.load(f)

    assert data["resolution"]["width"] == 1000
    assert data["resolution"]["height"] == 800
    assert data["num_vertices"] == 4
    # First normalized point: 200/1000 = 0.2, 200/800 = 0.25
    assert data["normalized_vertices"][0]["x"] == 0.2
    assert data["normalized_vertices"][0]["y"] == 0.25
    print("  [OK] JSON normalization & schema export: PASS")

    # Clean up test export
    if os.path.exists(config_file):
        os.remove(config_file)

    print("\n[SUCCESS] All geofence logic tests passed successfully!")


if __name__ == "__main__":
    run_tests()
