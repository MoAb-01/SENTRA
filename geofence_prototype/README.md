# SENTRA - Interactive Polygonal Geofencing Prototype

Standalone prototype built with **OpenCV (`opencv-python`)** and **NumPy** to verify interactive polygonal geofencing logic, real-time spatial breach detection, visual HUD telemetry, and normalized coordinate export without heavy AI dependencies.

---

## 🚀 Features

- **Real-Time Physical AI Person Detection**: Powered by **YOLOv8n** to physically detect people walking in front of the camera, tracking their ground contact foot coordinates `(foot_x, foot_y)` with visual bounding boxes and intrusion markers.
- **Dual-Mode Tracking**: Press **'m'** to seamlessly switch between **Live AI Person Tracking** (walk in front of your webcam) and **Mouse Simulation Mode** (use mouse cursor as simulated foot).
- **Interactive Polygon Configuration**:
  - **Left-Click**: Add vertices to draw a custom perimeter zone. Real-time drafting lines connect points with vertex badges.
  - **Right-Click**: Closes the polygon (requires $\ge 3$ vertices) and locks the zone as **ACTIVE**.
  - **'c' Key**: Clears the current polygon so you can redraw a new zone.
  - **'s' Key**: Exports the active zone coordinates to `zone_config.json` normalized to $[0.0, 1.0]$ based on frame resolution.
- **Tactical Visual HUD**:
  - **Perimeter Clear**: Polygon outline rendered in Cyan/Green with semi-transparent tint. Detected persons outside perimeter marked in Cyan `[PERSON (SAFE)]`. Status displays `STATUS: PERIMETER CLEAR`.
  - **Intrusion Detected**: Polygon filled with a vibrant semi-transparent Red overlay. Detected persons inside perimeter marked in bold Red with `[INTRUDER DETECTED]`. Top HUD flashes `STATUS: INTRUSION DETECTED`.
  - **Terminal Alert**: Prints `[ALERT] INTRUSION DETECTED! X person(s) physically inside restricted perimeter!` (debounced).
  - **Glassmorphism HUD**: Top header with status, live FPS, active tracking mode, and detected person count; bottom bar with keyboard shortcuts and toasts.

---

## 📦 Requirements

- Python 3.8+
- `opencv-python`
- `numpy`
- `ultralytics` (YOLOv8)

---

## 🎮 How to Run

From the project root or prototype directory:

```bash
# Run with default webcam (index 0)
python e:\SENTRA\geofence_prototype\geofence_test.py

# Or specify a different camera index (e.g. index 1)
python e:\SENTRA\geofence_prototype\geofence_test.py 1
```

### Controls Cheat-Sheet

| Action | Control | Description |
| :--- | :--- | :--- |
| **Add Vertex** | `Left-Click` | Places a vertex point $(x, y)$ |
| **Close Zone** | `Right-Click` | Closes polygon and locks perimeter for live monitoring |
| **Toggle Mode** | `m` / `M` | Switches between **Live AI Person Tracking** and **Mouse Simulator** |
| **Clear Zone** | `c` / `C` | Clears current perimeter and unlocks editing |
| **Save Zone** | `s` / `S` | Saves normalized coordinates to `zone_config.json` |
| **Exit** | `q` / `Q` / `ESC` | Cleanly releases camera and closes window |

---

## 📄 Exported JSON Schema (`zone_config.json`)

When you press `s`, the perimeter is saved with normalized coordinates relative to frame width and height:

```json
{
  "version": "1.0.0",
  "timestamp": "2026-09-21T12:00:00",
  "resolution": {
    "width": 1280,
    "height": 720
  },
  "polygon_type": "restricted_perimeter",
  "num_vertices": 4,
  "normalized_vertices": [
    { "x": 0.215, "y": 0.312 },
    { "x": 0.785, "y": 0.312 },
    { "x": 0.850, "y": 0.750 },
    { "x": 0.150, "y": 0.750 }
  ],
  "absolute_vertices": [
    { "x": 275, "y": 225 },
    { "x": 1005, "y": 225 },
    { "x": 1088, "y": 540 },
    { "x": 192, "y": 540 }
  ]
}
```
