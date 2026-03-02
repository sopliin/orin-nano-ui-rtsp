from __future__ import annotations

import os
import threading
import time
from dataclasses import dataclass
from datetime import datetime, timezone

import cv2
from ultralytics import YOLO

from app.config import Settings


@dataclass
class DetectionSnapshot:
    frame_id: int = 0
    timestamp: str = ""
    people: int = 0
    vehicles: int = 0
    fps: float = 0.0
    connected: bool = False
    jpeg: bytes = b""


class RealtimeDetector:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self._model: YOLO | None = None
        self._device = self._resolve_device(settings.device)
        self._stop_event = threading.Event()
        self._thread: threading.Thread | None = None
        self._lock = threading.Lock()
        self._snapshot = DetectionSnapshot()
        self.target_class_ids = tuple(
            dict.fromkeys((settings.person_class_id, *settings.vehicle_class_ids))
        )

        # Fuerza RTSP sobre TCP para evitar cortes frecuentes en redes inestables.
        os.environ.setdefault(
            "OPENCV_FFMPEG_CAPTURE_OPTIONS", "rtsp_transport;tcp|max_delay;500000"
        )

    def _resolve_device(self, raw_device: str) -> int | str:
        value = raw_device.strip().lower()
        if value == "cpu":
            return "cpu"
        if value.isdigit():
            return int(value)
        return raw_device

    def _ensure_model(self) -> None:
        if self._model is None:
            self._model = YOLO(self.settings.model_path)

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return

        self._ensure_model()
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._worker, name="detector-worker")
        self._thread.start()

    def stop(self) -> None:
        self._stop_event.set()
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=5)

    def get_snapshot(self) -> DetectionSnapshot:
        with self._lock:
            return DetectionSnapshot(
                frame_id=self._snapshot.frame_id,
                timestamp=self._snapshot.timestamp,
                people=self._snapshot.people,
                vehicles=self._snapshot.vehicles,
                fps=self._snapshot.fps,
                connected=self._snapshot.connected,
                jpeg=self._snapshot.jpeg,
            )

    def _set_snapshot(self, snapshot: DetectionSnapshot) -> None:
        with self._lock:
            self._snapshot = snapshot

    def _open_capture(self) -> cv2.VideoCapture | None:
        cap = cv2.VideoCapture(self.settings.rtsp_url, cv2.CAP_FFMPEG)
        cap.set(cv2.CAP_PROP_BUFFERSIZE, 2)
        if not cap.isOpened():
            cap.release()
            return None
        return cap

    def _worker(self) -> None:
        frame_id = 0

        while not self._stop_event.is_set():
            capture = self._open_capture()
            if capture is None:
                self._set_snapshot(
                    DetectionSnapshot(
                        frame_id=frame_id,
                        timestamp=datetime.now(timezone.utc).isoformat(),
                        connected=False,
                    )
                )
                time.sleep(self.settings.reconnect_delay_sec)
                continue

            while not self._stop_event.is_set():
                ok, frame = capture.read()
                if not ok:
                    self._set_snapshot(
                        DetectionSnapshot(
                            frame_id=frame_id,
                            timestamp=datetime.now(timezone.utc).isoformat(),
                            connected=False,
                        )
                    )
                    break

                start = time.perf_counter()
                results = self._model.predict(
                    source=frame,
                    conf=self.settings.conf_threshold,
                    iou=self.settings.iou_threshold,
                    imgsz=self.settings.img_size,
                    classes=list(self.target_class_ids),
                    device=self._device,
                    verbose=False,
                )
                result = results[0]

                people = 0
                vehicles = 0
                if result.boxes is not None and result.boxes.cls is not None:
                    for cls_id in result.boxes.cls.int().tolist():
                        if cls_id == self.settings.person_class_id:
                            people += 1
                        elif cls_id in self.settings.vehicle_class_ids:
                            vehicles += 1

                annotated = result.plot(conf=True, labels=True)
                elapsed = max(time.perf_counter() - start, 1e-6)
                fps = 1.0 / elapsed

                timestamp = datetime.now(timezone.utc).isoformat()
                cv2.putText(
                    annotated,
                    f"Peatones: {people} | Vehiculos: {vehicles} | FPS: {fps:.1f}",
                    (20, 35),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.9,
                    (0, 255, 0),
                    2,
                    cv2.LINE_AA,
                )

                ok_jpg, jpeg = cv2.imencode(
                    ".jpg",
                    annotated,
                    [int(cv2.IMWRITE_JPEG_QUALITY), self.settings.jpeg_quality],
                )
                if not ok_jpg:
                    continue

                frame_id += 1
                self._set_snapshot(
                    DetectionSnapshot(
                        frame_id=frame_id,
                        timestamp=timestamp,
                        people=people,
                        vehicles=vehicles,
                        fps=fps,
                        connected=True,
                        jpeg=jpeg.tobytes(),
                    )
                )

            capture.release()
            time.sleep(self.settings.reconnect_delay_sec)
