"""CARLA simulation bridge.

Connects Neo to a CARLA simulator running remotely (typically Colab). Uses
the cloud vision backend for perception and a rule-based policy for control,
so it works even before you train an RL policy.

If CARLA isn't running, every method returns a structured "not connected"
result rather than crashing.
"""
from __future__ import annotations
import base64
import io
import logging
import os
from typing import Any, Dict, List, Optional

log = logging.getLogger("driving.sim_bridge")


class SimBridge:
    def __init__(self, carla_url: Optional[str] = None):
        self.carla_url = carla_url or os.getenv("CARLA_URL", "")
        self.client = None
        self.world = None
        self.ego = None
        self._camera = None

    # ---------- connectivity ----------
    def connect(self) -> Dict[str, Any]:
        if not self.carla_url:
            return {
                "ok": False,
                "reason": "no_carla_url",
                "message": ("Set CARLA_URL in .env to a running CARLA instance. "
                            "See docs/DRIVING_SIM.md for the Colab recipe."),
            }
        try:
            import carla  # type: ignore
        except ImportError:
            return {
                "ok": False,
                "reason": "carla_python_missing",
                "message": "pip install carla==0.9.15",
            }
        try:
            self.client = carla.Client(self.carla_url.replace("wss://", "")
                                       .replace("https://", ""), 2000)
            self.client.set_timeout(10.0)
            self.world = self.client.get_world()
            return {"ok": True, "map": str(self.world.get_map().name)}
        except Exception as e:
            return {"ok": False, "reason": "connect_failed", "error": str(e)}

    # ---------- spawn ----------
    def spawn_ego_vehicle(self) -> Dict[str, Any]:
        if not self.world:
            return {"ok": False, "reason": "not_connected"}
        try:
            import carla  # type: ignore
            bp = self.world.get_blueprint_library().filter("vehicle.*")[0]
            spawn = self.world.get_map().get_spawn_points()[0]
            self.ego = self.world.spawn_actor(bp, spawn)
            # camera
            cam_bp = self.world.get_blueprint_library().find("sensor.camera.rgb")
            cam_bp.set_attribute("image_size_x", "800")
            cam_bp.set_attribute("image_size_y", "600")
            self._camera = self.world.spawn_actor(
                cam_bp, carla.Transform(carla.Location(x=1.5, z=2.4)),
                attach_to=self.ego,
            )
            return {"ok": True, "id": self.ego.id}
        except Exception as e:
            return {"ok": False, "error": str(e)}

    # ---------- perception ----------
    def get_camera_frame(self) -> Optional[bytes]:
        """Return latest camera frame as JPEG bytes."""
        if not self._camera:
            return None
        import queue
        q: "queue.Queue" = queue.Queue()
        self._camera.listen(q.put)
        try:
            image = q.get(timeout=2)
        finally:
            self._camera.stop()
        # image.raw_data is BGRA; convert to jpeg
        try:
            from PIL import Image
            arr = image.raw_data
            img = Image.frombytes("RGBA", (image.width, image.height), arr)
            buf = io.BytesIO()
            img.convert("RGB").save(buf, format="JPEG", quality=80)
            return buf.getvalue()
        except Exception as e:
            log.debug("[sim] frame conversion failed: %s", e)
            return None

    def detect_obstacles(self, frame: bytes,
                         prompt: str = "person, car, bike, obstacle") -> Dict[str, Any]:
        """Run cloud vision on a single frame."""
        try:
            from core.vision import cloud_detect
            return cloud_detect.detect_bytes(
                frame, prompt=prompt, save_as_observation=False)
        except Exception as e:
            return {"ok": False, "error": str(e)}

    # ---------- decision ----------
    def decide(self, detections: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Rule-based policy: stop if obstacle close ahead, else go."""
        # Without distance, use a heuristic: any large bbox of person/vehicle
        # means brake, smaller ones mean slow down.
        stop_labels = {"person", "pedestrian", "bike", "bicycle", "motorcycle"}
        for d in detections:
            label = str(d.get("label", "")).lower()
            box = d.get("box") or {}
            h = (box.get("ymax", 0) or 0) - (box.get("ymin", 0) or 0)
            if label in stop_labels and h > 200:
                return {"action": "brake", "throttle": 0.0, "brake": 1.0,
                        "reason": f"{label} large in frame"}
            if label in ("car", "vehicle", "truck") and h > 250:
                return {"action": "slow", "throttle": 0.2, "brake": 0.3,
                        "reason": f"{label} ahead"}
        return {"action": "go", "throttle": 0.5, "brake": 0.0, "steer": 0.0}

    def apply(self, action: Dict[str, Any]) -> Dict[str, Any]:
        if not self.ego:
            return {"ok": False, "reason": "no_ego"}
        try:
            import carla  # type: ignore
            ctrl = carla.VehicleControl()
            ctrl.throttle = float(action.get("throttle", 0))
            ctrl.brake = float(action.get("brake", 0))
            ctrl.steer = float(action.get("steer", 0))
            self.ego.apply_control(ctrl)
            return {"ok": True, "action": action["action"]}
        except Exception as e:
            return {"ok": False, "error": str(e)}

    # ---------- high-level ----------
    def drive(self, seconds: int = 10) -> Dict[str, Any]:
        """Run the perception-decision-act loop for N seconds."""
        import time
        if not self.ego:
            return {"ok": False, "reason": "no_ego"}
        t0 = time.time()
        steps = 0
        actions: List[str] = []
        while time.time() - t0 < seconds:
            frame = self.get_camera_frame()
            if not frame:
                break
            det = self.detect_obstacles(frame)
            dets = det.get("detections", []) if det.get("ok") else []
            action = self.decide(dets)
            self.apply(action)
            actions.append(action["action"])
            steps += 1
            time.sleep(0.2)
        return {
            "ok": True,
            "steps": steps,
            "duration": round(time.time() - t0, 1),
            "action_histogram": {a: actions.count(a) for a in set(actions)},
        }

    def destroy(self) -> Dict[str, Any]:
        try:
            if self._camera: self._camera.destroy()
            if self.ego: self.ego.destroy()
            return {"ok": True}
        except Exception as e:
            return {"ok": False, "error": str(e)}


def handle(text: str) -> str:
    """Dispatch a 'sim: <cmd>' line from the CLI or chat."""
    b = SimBridge()
    cmd = (text or "").strip().lower()
    if cmd == "connect":
        return str(b.connect())
    if cmd == "spawn":
        b.connect(); return str(b.spawn_ego_vehicle())
    if cmd.startswith("drive"):
        parts = cmd.split()
        secs = int(parts[1]) if len(parts) > 1 and parts[1].isdigit() else 10
        return str(b.drive(seconds=secs))
    if cmd == "stop":
        return str(b.destroy())
    return ("Usage: sim: connect | spawn | drive <sec> | stop\n"
            "See docs/DRIVING_SIM.md for the Colab CARLA recipe.")
