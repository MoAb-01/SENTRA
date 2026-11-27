#!/usr/bin/env python3
"""
SENTRA - Geofence Prototype
===========================
Interactive polygonal geofencing module using OpenCV, NumPy, and YOLOv8.
Enables real-time perimeter configuration via mouse clicks, live physical
person detection via webcam (tracking bottom-center foot coordinates),
spatial breach testing with cv2.pointPolygonTest, tactical visual HUD overlays,
and normalized JSON configuration export.
"""

import cv2
import json
import numpy as np
import os
import sys
import time
from typing import List, Tuple, Optional, Dict, Any

try:
    from ultralytics import YOLO
    YOLO_AVAILABLE = True
except ImportError:
    YOLO_AVAILABLE = False


class GeofenceApp:
    """
    Manages video capture, live AI person detection, interactive polygon definition,
    spatial collision testing (pointPolygonTest), and tactical HUD rendering.
    """

    WINDOW_TITLE = "SENTRA - Geofence Prototype"
    CONFIG_FILENAME = "zone_config.json"

    # Color Palette (BGR)
    COLOR_CLEAR_OUTLINE = (230, 216, 0)      # Cyan / Teal
    COLOR_CLEAR_FILL = (120, 200, 0)         # Translucent Green-Cyan
    COLOR_BREACH_FILL = (40, 40, 230)        # Vibrant Red
    COLOR_BREACH_OUTLINE = (30, 30, 255)     # Deep Red
    COLOR_DRAFT_LINE = (255, 180, 0)         # Amber / Yellow
    COLOR_VERTEX = (0, 255, 255)             # Bright Yellow
    COLOR_CROSSHAIR = (0, 255, 120)          # Green
    COLOR_CROSSHAIR_ALERT = (50, 50, 255)    # Red
    COLOR_TEXT_GREEN = (50, 240, 50)
    COLOR_TEXT_RED = (60, 60, 255)
    COLOR_WHITE = (255, 255, 255)
    COLOR_HUD_BG = (15, 15, 20)

    def __init__(self, camera_index: int = 0):
        self.camera_index = camera_index
        self.cap: Optional[cv2.VideoCapture] = None
        self.using_synthetic_feed = False

        # Geofence State
        self.polygon_points: List[Tuple[int, int]] = []
        self.is_zone_active = False  # True when closed and locked

        # Detection Mode: "ai" (real person detection via webcam) or "mouse" (simulation)
        self.mode = "ai" if YOLO_AVAILABLE else "mouse"
        self.yolo_model: Optional[Any] = None
        self.detected_persons: List[Dict[str, Any]] = []

        # Simulated Target (Foot position for mouse mode)
        self.target_pos: Optional[Tuple[int, int]] = None
        self.is_breached = False

        # Alert debouncing & notification banner
        self.last_alert_time = 0.0
        self.alert_cooldown = 1.0  # seconds between terminal alert prints
        self.status_message = "Click to set perimeter vertices."
        self.status_message_expiry = 0.0

        # Frame telemetry
        self.frame_width = 1280
        self.frame_height = 720
        self.frame_count = 0

        # Performance monitoring
        self.fps = 0.0
        self._last_fps_time = time.time()
        self._fps_counter = 0

    def initialize_ai(self) -> None:
        """Initializes YOLOv8n model for real-time person tracking."""
        if not YOLO_AVAILABLE:
            print("[AI] Ultralytics is not available. Falling back to mouse simulation mode.")
            self.mode = "mouse"
            return

        model_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "yolov8n.pt")
        if not os.path.exists(model_path):
            model_path = "yolov8n.pt"

        try:
            print("[AI] Loading YOLOv8n human detection model...")
            self.yolo_model = YOLO(model_path)
            print("[AI] YOLOv8n initialized successfully! Real person tracking is active.")
            self.mode = "ai"
        except Exception as e:
            print(f"[AI] Failed to load YOLO: {e}. Defaulting to mouse simulation mode.")
            self.yolo_model = None
            self.mode = "mouse"

    def initialize_camera(self) -> None:
        """Initializes webcam or falls back to synthetic feed if camera unavailable."""
        print(f"[INIT] Attempting to open camera index {self.camera_index}...")
        self.cap = cv2.VideoCapture(self.camera_index)

        if self.cap is not None and self.cap.isOpened():
            ret, test_frame = self.cap.read()
            if ret and test_frame is not None:
                self.frame_height, self.frame_width = test_frame.shape[:2]
                print(f"[INIT] Camera opened successfully ({self.frame_width}x{self.frame_height}).")
                return

        print(f"[WARNING] Camera index {self.camera_index} could not be read.")
        print("[INIT] Switching to synthetic CCTV simulation feed.")
        self.using_synthetic_feed = True
        if self.cap is not None:
            self.cap.release()
            self.cap = None

    def generate_synthetic_frame(self) -> np.ndarray:
        """Generates a synthetic surveillance camera frame with timestamp and grid."""
        frame = np.zeros((self.frame_height, self.frame_width, 3), dtype=np.uint8)

        # Surveillance grid
        grid_color = (25, 30, 35)
        step = 80
        for x in range(0, self.frame_width, step):
            cv2.line(frame, (x, 0), (x, self.frame_height), grid_color, 1)
        for y in range(0, self.frame_height, step):
            cv2.line(frame, (0, y), (self.frame_width, y), grid_color, 1)

        # Animated sweep line
        sweep_y = int((self.frame_count * 3) % self.frame_height)
        cv2.line(frame, (0, sweep_y), (self.frame_width, sweep_y), (40, 50, 60), 1)

        timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
        cv2.putText(
            frame,
            f"CAM-01 [SIMULATED FEED] | {timestamp} | LIVE",
            (20, self.frame_height - 60),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.5,
            (100, 120, 140),
            1,
            cv2.LINE_AA,
        )
        return frame

    def mouse_callback(self, event: int, x: int, y: int, flags: int, param: any) -> None:
        """Handles user mouse input for drawing the perimeter and simulated targeting."""
        self.target_pos = (x, y)

        if event == cv2.EVENT_LBUTTONDOWN:
            if not self.is_zone_active:
                self.polygon_points.append((x, y))
                print(f"[GEOFENCE] Added vertex #{len(self.polygon_points)}: ({x}, {y})")
                self.set_banner(f"Added vertex #{len(self.polygon_points)} at ({x}, {y})", 2.0)
            else:
                self.set_banner("Zone is locked. Press 'c' to redraw.", 2.0)

        elif event == cv2.EVENT_RBUTTONDOWN:
            if not self.is_zone_active:
                if len(self.polygon_points) >= 3:
                    self.is_zone_active = True
                    print(f"[GEOFENCE] Polygon closed with {len(self.polygon_points)} vertices. Zone ACTIVE.")
                    self.set_banner(f"Zone LOCKED ({len(self.polygon_points)} vertices). Monitoring started!", 3.0)
                else:
                    print("[GEOFENCE] Cannot close zone: At least 3 vertices required.")
                    self.set_banner("Error: Need >= 3 vertices to close polygon.", 2.5)

    def set_banner(self, message: str, duration_sec: float = 2.0) -> None:
        """Sets temporary status message on HUD."""
        self.status_message = message
        self.status_message_expiry = time.time() + duration_sec

    def clear_zone(self) -> None:
        """Resets polygon definition and unlocks zone."""
        self.polygon_points.clear()
        self.is_zone_active = False
        self.is_breached = False
        for p in self.detected_persons:
            p["breached"] = False
        print("[GEOFENCE] Zone cleared. Ready for new configuration.")
        self.set_banner("Zone cleared. Click to define new perimeter.", 2.0)

    def export_config(self) -> None:
        """Exports active polygon normalized coordinates (0.0 to 1.0) to zone_config.json."""
        if not self.is_zone_active or len(self.polygon_points) < 3:
            print("[EXPORT] Cannot export: Zone must be closed and active first.")
            self.set_banner("Cannot export: Complete polygon first (Right-Click).", 2.5)
            return

        normalized_points = [
            {
                "x": round(x / float(self.frame_width), 5),
                "y": round(y / float(self.frame_height), 5)
            }
            for (x, y) in self.polygon_points
        ]

        config_data = {
            "version": "1.0.0",
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
            "resolution": {
                "width": self.frame_width,
                "height": self.frame_height
            },
            "polygon_type": "restricted_perimeter",
            "num_vertices": len(normalized_points),
            "normalized_vertices": normalized_points,
            "absolute_vertices": [{"x": x, "y": y} for (x, y) in self.polygon_points]
        }

        output_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), self.CONFIG_FILENAME)
        try:
            with open(output_path, "w", encoding="utf-8") as f:
                json.dump(config_data, f, indent=2)
            print(f"[EXPORT] Successfully saved zone configuration to: {output_path}")
            self.set_banner(f"SAVED: {self.CONFIG_FILENAME} (normalized)", 3.0)
        except Exception as e:
            print(f"[ERROR] Failed to save configuration: {e}")
            self.set_banner(f"Export failed: {e}", 3.0)

    def detect_real_people(self, frame: np.ndarray) -> None:
        """Runs YOLOv8 person detection on the frame to find human bounding boxes and foot points."""
        if self.mode != "ai" or self.yolo_model is None:
            self.detected_persons = []
            return

        # Inference: class 0 is 'person' in COCO dataset
        results = self.yolo_model(frame, classes=[0], conf=0.45, verbose=False)
        self.detected_persons = []

        for r in results:
            boxes = r.boxes
            for box in boxes:
                coords = box.xyxy[0].tolist()
                x1, y1, x2, y2 = int(coords[0]), int(coords[1]), int(coords[2]), int(coords[3])
                conf = float(box.conf[0])

                # Foot coordinate: bottom-center of the bounding box
                foot_x = int((x1 + x2) / 2)
                foot_y = int(y2)

                self.detected_persons.append({
                    "box": (x1, y1, x2, y2),
                    "foot": (foot_x, foot_y),
                    "breached": False,
                    "conf": conf
                })

    def evaluate_spatial_status(self) -> None:
        """
        Runs cv2.pointPolygonTest to evaluate whether detected person(s) or
        the simulated target is inside or outside the active polygon.
        """
        if not self.is_zone_active or len(self.polygon_points) < 3:
            self.is_breached = False
            for p in self.detected_persons:
                p["breached"] = False
            return

        poly_array = np.array(self.polygon_points, dtype=np.int32)

        # 1. AI Real Person Tracking Mode
        if self.mode == "ai" and self.detected_persons:
            breach_count = 0
            for person in self.detected_persons:
                fx, fy = person["foot"]
                dist = cv2.pointPolygonTest(poly_array, (float(fx), float(fy)), measureDist=False)
                if dist >= 0:
                    person["breached"] = True
                    breach_count += 1
                else:
                    person["breached"] = False

            self.is_breached = (breach_count > 0)

            if self.is_breached:
                current_time = time.time()
                if current_time - self.last_alert_time >= self.alert_cooldown:
                    print(f"[ALERT] INTRUSION DETECTED! {breach_count} person(s) physically inside restricted perimeter!")
                    self.last_alert_time = current_time

        # 2. Mouse Simulation Mode (or Fallback if no real person in frame)
        else:
            if self.target_pos is not None:
                dist = cv2.pointPolygonTest(poly_array, (float(self.target_pos[0]), float(self.target_pos[1])), measureDist=False)
                self.is_breached = (dist >= 0)

                if self.is_breached:
                    current_time = time.time()
                    if current_time - self.last_alert_time >= self.alert_cooldown:
                        print(f"[ALERT] Spatial breach at coordinate ({self.target_pos[0]}, {self.target_pos[1]})")
                        self.last_alert_time = current_time
            else:
                self.is_breached = False

    def render_geofence(self, frame: np.ndarray) -> np.ndarray:
        """Renders polygon vertices, perimeter outlines, and intrusion color fills."""
        if not self.polygon_points:
            return frame

        overlay = frame.copy()
        pts = np.array(self.polygon_points, dtype=np.int32)

        if self.is_zone_active:
            if self.is_breached:
                # Semi-transparent RED fill for intrusion
                cv2.fillPoly(overlay, [pts], self.COLOR_BREACH_FILL)
                alpha = 0.38
                cv2.addWeighted(overlay, alpha, frame, 1 - alpha, 0, frame)
                # Crisp Red outline
                cv2.polylines(frame, [pts], isClosed=True, color=self.COLOR_BREACH_OUTLINE, thickness=3, lineType=cv2.LINE_AA)
            else:
                # Semi-transparent Cyan/Green fill for clear status
                cv2.fillPoly(overlay, [pts], self.COLOR_CLEAR_FILL)
                alpha = 0.18
                cv2.addWeighted(overlay, alpha, frame, 1 - alpha, 0, frame)
                # Cyan/Green outline
                cv2.polylines(frame, [pts], isClosed=True, color=self.COLOR_CLEAR_OUTLINE, thickness=2, lineType=cv2.LINE_AA)

            # Draw vertices
            for pt in self.polygon_points:
                cv2.circle(frame, pt, 4, self.COLOR_VERTEX, -1, lineType=cv2.LINE_AA)
        else:
            # Drafting mode: Draw connected lines and numbered vertices
            for i in range(len(self.polygon_points)):
                pt1 = self.polygon_points[i]
                cv2.circle(frame, pt1, 5, self.COLOR_VERTEX, -1, lineType=cv2.LINE_AA)
                cv2.circle(frame, pt1, 7, (0, 0, 0), 1, lineType=cv2.LINE_AA)
                cv2.putText(
                    frame,
                    f"P{i+1}",
                    (pt1[0] + 8, pt1[1] - 8),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.4,
                    self.COLOR_VERTEX,
                    1,
                    cv2.LINE_AA,
                )
                if i > 0:
                    pt0 = self.polygon_points[i - 1]
                    cv2.line(frame, pt0, pt1, self.COLOR_DRAFT_LINE, 2, lineType=cv2.LINE_AA)

            # Line to cursor while drafting
            if self.target_pos is not None and len(self.polygon_points) > 0:
                cv2.line(frame, self.polygon_points[-1], self.target_pos, (180, 180, 180), 1, lineType=cv2.LINE_AA)

        return frame

    def render_detected_people(self, frame: np.ndarray) -> None:
        """Renders bounding boxes, foot contact markers, and status tags for all detected persons."""
        if self.mode != "ai":
            return

        for idx, person in enumerate(self.detected_persons):
            x1, y1, x2, y2 = person["box"]
            fx, fy = person["foot"]
            breached = person["breached"]
            conf = int(person["conf"] * 100)

            if breached:
                box_color = (30, 30, 255)       # Red
                text_label = f"INTRUDER [{conf}%]"
                bg_color = (30, 30, 220)
            else:
                box_color = (230, 216, 0)      # Cyan
                text_label = f"PERSON [{conf}%]"
                bg_color = (30, 120, 30)

            # Draw person bounding box
            cv2.rectangle(frame, (x1, y1), (x2, y2), box_color, 2, lineType=cv2.LINE_AA)

            # Corner accents
            c_len = min(20, (x2 - x1) // 3)
            thick = 3
            cv2.line(frame, (x1, y1), (x1 + c_len, y1), box_color, thick)
            cv2.line(frame, (x1, y1), (x1, y1 + c_len), box_color, thick)
            cv2.line(frame, (x2, y1), (x2 - c_len, y1), box_color, thick)
            cv2.line(frame, (x2, y1), (x2, y1 + c_len), box_color, thick)
            cv2.line(frame, (x1, y2), (x1 + c_len, y2), box_color, thick)
            cv2.line(frame, (x1, y2), (x1, y2 - c_len), box_color, thick)
            cv2.line(frame, (x2, y2), (x2 - c_len, y2), box_color, thick)
            cv2.line(frame, (x2, y2), (x2, y2 - c_len), box_color, thick)

            # Label badge above person
            (tw, th), _ = cv2.getTextSize(text_label, cv2.FONT_HERSHEY_SIMPLEX, 0.45, 1)
            cv2.rectangle(frame, (x1, max(0, y1 - 22)), (x1 + tw + 10, max(22, y1)), bg_color, -1)
            cv2.putText(
                frame,
                text_label,
                (x1 + 5, max(16, y1 - 5)),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.45,
                (255, 255, 255),
                1,
                cv2.LINE_AA,
            )

            # Foot Coordinate Tracking Indicator
            cv2.circle(frame, (fx, fy), 5, box_color, -1, lineType=cv2.LINE_AA)
            cv2.circle(frame, (fx, fy), 11, box_color, 1, lineType=cv2.LINE_AA)
            cv2.putText(
                frame,
                f"FOOT ({fx}, {fy})",
                (fx - 40, fy + 18),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.36,
                box_color,
                1,
                cv2.LINE_AA,
            )

    def render_crosshair(self, frame: np.ndarray) -> None:
        """Renders tactical crosshair for mouse simulation mode or drafting."""
        if self.target_pos is None:
            return

        x, y = self.target_pos

        # If in AI mode and zone is active, we don't need the mouse crosshair cluttering the camera
        if self.mode == "ai" and self.is_zone_active:
            return

        color = self.COLOR_CROSSHAIR_ALERT if (self.is_breached and self.mode == "mouse") else self.COLOR_CROSSHAIR

        ch_len = 15
        gap = 5
        cv2.line(frame, (x - ch_len, y), (x - gap, y), color, 1, lineType=cv2.LINE_AA)
        cv2.line(frame, (x + gap, y), (x + ch_len, y), color, 1, lineType=cv2.LINE_AA)
        cv2.line(frame, (x, y - ch_len), (x, y - gap), color, 1, lineType=cv2.LINE_AA)
        cv2.line(frame, (x, y + gap), (x, y + ch_len), color, 1, lineType=cv2.LINE_AA)
        cv2.circle(frame, (x, y), 3, color, -1, lineType=cv2.LINE_AA)
        cv2.circle(frame, (x, y), 10, color, 1, lineType=cv2.LINE_AA)

        if not self.is_zone_active:
            label = f"CURSOR ({x}, {y})"
            cv2.putText(frame, label, (x + 14, y + 18), cv2.FONT_HERSHEY_SIMPLEX, 0.40, color, 1, cv2.LINE_AA)

    def render_hud(self, frame: np.ndarray) -> None:
        """Draws tactical telemetry HUD bars."""
        h, w = frame.shape[:2]

        # 1. Top HUD Bar
        top_bar_height = 52
        top_overlay = frame.copy()
        cv2.rectangle(top_overlay, (0, 0), (w, top_bar_height), self.COLOR_HUD_BG, -1)
        cv2.addWeighted(top_overlay, 0.85, frame, 0.15, 0, frame)
        cv2.line(frame, (0, top_bar_height), (w, top_bar_height), (50, 55, 65), 1)

        # Title
        cv2.putText(
            frame,
            "SENTRA :: GEOFENCE",
            (16, 32),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.65,
            self.COLOR_WHITE,
            2,
            cv2.LINE_AA,
        )

        # Spatial Status Badge
        if not self.is_zone_active:
            status_text = "MODE: CONFIGURING PERIMETER"
            status_color = (0, 200, 255)
        elif self.is_breached:
            status_text = "STATUS: INTRUSION DETECTED"
            status_color = self.COLOR_TEXT_RED
        else:
            status_text = "STATUS: PERIMETER CLEAR"
            status_color = self.COLOR_TEXT_GREEN

        cv2.putText(
            frame,
            status_text,
            (w // 2 - 150, 32),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.68,
            status_color,
            2,
            cv2.LINE_AA,
        )

        # Telemetry & Mode Info (Right side)
        mode_str = "[AI: YOLOv8 PERSON TRACKING]" if self.mode == "ai" else "[MOUSE SIMULATION]"
        person_count_str = f"PEOPLE: {len(self.detected_persons)}" if self.mode == "ai" else "SIM: MOUSE"
        telemetry_str = f"{mode_str} | {person_count_str} | FPS: {self.fps:.1f}"
        cv2.putText(
            frame,
            telemetry_str,
            (w - 430, 31),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.40,
            (190, 200, 210),
            1,
            cv2.LINE_AA,
        )

        # 2. Bottom HUD Bar
        bot_bar_height = 42
        bot_overlay = frame.copy()
        cv2.rectangle(bot_overlay, (0, h - bot_bar_height), (w, h), self.COLOR_HUD_BG, -1)
        cv2.addWeighted(bot_overlay, 0.85, frame, 0.15, 0, frame)
        cv2.line(frame, (0, h - bot_bar_height), (w, h - bot_bar_height), (50, 55, 65), 1)

        # Controls cheat-sheet
        controls_text = "[L-CLICK] Add Point  |  [R-CLICK] Close Zone  |  [M] AI/Mouse Mode  |  [C] Clear  |  [S] Save  |  [Q] Quit"
        cv2.putText(
            frame,
            controls_text,
            (16, h - 14),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.42,
            (210, 210, 210),
            1,
            cv2.LINE_AA,
        )

        # Status notification banner
        if time.time() < self.status_message_expiry:
            banner_text = f">>> {self.status_message}"
            cv2.putText(
                frame,
                banner_text,
                (w - 440, h - 14),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.45,
                (0, 255, 255),
                1,
                cv2.LINE_AA,
            )

    def run(self) -> None:
        """Main operational loop."""
        self.initialize_camera()
        self.initialize_ai()

        cv2.namedWindow(self.WINDOW_TITLE, cv2.WINDOW_AUTOSIZE)
        cv2.setMouseCallback(self.WINDOW_TITLE, self.mouse_callback)

        print("\n" + "=" * 68)
        print(" SENTRA - Live Polygonal Geofence Engine Initialized")
        print(f" Current Tracking Mode: {self.mode.upper()}")
        print(" Controls:")
        print("   - Left-Click : Add perimeter vertex (x, y)")
        print("   - Right-Click: Close polygon and activate geofencing")
        print("   - 'm' key    : Toggle between Live AI Person Tracking and Mouse Mode")
        print("   - 'c' key    : Clear polygon to redraw")
        print("   - 's' key    : Export zone to zone_config.json")
        print("   - 'q' or ESC : Quit application")
        print("=" * 68 + "\n")

        try:
            while True:
                self.frame_count += 1
                self._fps_counter += 1

                # Calculate live FPS
                now = time.time()
                elapsed = now - self._last_fps_time
                if elapsed >= 1.0:
                    self.fps = self._fps_counter / elapsed
                    self._fps_counter = 0
                    self._last_fps_time = now

                # Frame acquisition
                if self.using_synthetic_feed or self.cap is None:
                    frame = self.generate_synthetic_frame()
                else:
                    ret, frame = self.cap.read()
                    if not ret or frame is None:
                        print("[ERROR] Camera stream interrupted. Switching to synthetic feed.")
                        self.using_synthetic_feed = True
                        frame = self.generate_synthetic_frame()

                self.frame_height, self.frame_width = frame.shape[:2]

                # 1. Detect Real People via AI
                if self.mode == "ai":
                    self.detect_real_people(frame)

                # 2. Evaluate Spatial Geofence Collision (pointPolygonTest)
                self.evaluate_spatial_status()

                # 3. Render Geofence (fills and outlines)
                frame = self.render_geofence(frame)

                # 4. Render Detected People (boxes + foot tracking)
                if self.mode == "ai":
                    self.render_detected_people(frame)

                # 5. Render Crosshair (in mouse mode or drafting)
                self.render_crosshair(frame)

                # 6. Render Tactical HUD
                self.render_hud(frame)

                # Display frame
                cv2.imshow(self.WINDOW_TITLE, frame)

                # Key handling
                key = cv2.waitKey(1) & 0xFF
                if key in [ord('q'), ord('Q'), 27]:
                    print("[EXIT] Shutting down SENTRA Geofence Prototype...")
                    break
                elif key in [ord('c'), ord('C')]:
                    self.clear_zone()
                elif key in [ord('s'), ord('S')]:
                    self.export_config()
                elif key in [ord('m'), ord('M')]:
                    if self.yolo_model is not None:
                        self.mode = "mouse" if self.mode == "ai" else "ai"
                        mode_name = "LIVE AI (YOLOv8)" if self.mode == "ai" else "MOUSE SIMULATION"
                        self.set_banner(f"Switched mode to: {mode_name}", 2.5)
                        print(f"[MODE] Mode switched to: {mode_name}")
                    else:
                        self.set_banner("YOLO model not loaded. AI mode unavailable.", 2.5)

        except KeyboardInterrupt:
            print("\n[EXIT] Interrupted by user.")

        finally:
            self.cleanup()

    def cleanup(self) -> None:
        """Releases video capture and closes OpenCV windows cleanly."""
        if self.cap is not None:
            self.cap.release()
            self.cap = None
        cv2.destroyAllWindows()
        print("[CLEANUP] Video capture released and all windows closed.")


if __name__ == "__main__":
    cam_id = 0
    if len(sys.argv) > 1 and sys.argv[1].isdigit():
        cam_id = int(sys.argv[1])

    app = GeofenceApp(camera_index=cam_id)
    app.run()
