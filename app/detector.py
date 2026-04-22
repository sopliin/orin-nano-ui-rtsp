from __future__ import annotations

import os
import threading
import time
from dataclasses import dataclass
from datetime import datetime, timezone

import cv2
import torch
import yolov5

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
        self._model = None
        self._device = self._resolve_device(settings.device)
        self._stop_event = threading.Event()
        self._restart_event = threading.Event()
        self._thread: threading.Thread | None = None
        self._lock = threading.Lock()
        self._snapshot = DetectionSnapshot()
        self.target_class_ids = tuple(
            dict.fromkeys((settings.person_class_id, *settings.vehicle_class_ids))
        )
        self._gpu_failed = False

    @property
    def _is_file(self) -> bool:
        return self.settings.source_type == "file"

    def request_restart(self) -> None:
        """Señaliza al worker que reinicie la fuente desde el principio.
        Para RTSP no tiene efecto (la reconexión es automática).
        """
        if self._is_file:
            self._restart_event.set()

    def _resolve_device(self, raw_device: str) -> str:
        value = raw_device.strip().lower()
        if value == "auto":
            return "0" if torch.cuda.is_available() else "cpu"
        if value == "cpu":
            return "cpu"
        if value.isdigit():
            if not torch.cuda.is_available():
                print("[YOLOv5] CUDA no disponible; usando CPU.")
                return "cpu"
            return value
        return raw_device

    def _load_model(self, device: str):
        model = yolov5.load(self.settings.model_path, device=device)
        model.conf = self.settings.conf_threshold
        model.iou = self.settings.iou_threshold
        model.classes = list(self.target_class_ids)
        return model

    def _ensure_model(self) -> None:
        if self._model is None:
            self._model = self._load_model(self._device)

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._ensure_model()
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._worker, name="detector-worker")
        self._thread.start()

    def stop(self) -> None:
        self._stop_event.set()
        self._restart_event.set()  # desbloquea wait() si estaba esperando
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

    # ------------------------------------------------------------------ RTSP

    def _transport_candidates(self) -> tuple[str, ...]:
        if self.settings.rtsp_transport in {"udp", "tcp"}:
            return (self.settings.rtsp_transport,)
        return ("udp", "tcp")

    def _backend_candidates(self) -> tuple[int, ...]:
        return (cv2.CAP_FFMPEG, cv2.CAP_ANY)

    def _set_ffmpeg_rtsp_options(self, transport: str) -> None:
        os.environ["OPENCV_FFMPEG_CAPTURE_OPTIONS"] = (
            f"rtsp_transport;{transport}|max_delay;500000"
        )

    # ------------------------------------------------------------------ captura

    def _open_capture(self) -> cv2.VideoCapture | None:
        if self._is_file:
            cap = cv2.VideoCapture(self.settings.video_source)
            if cap.isOpened():
                print(f"[VIDEO] archivo abierto: {self.settings.video_source}")
                return cap
            print(f"[VIDEO] no se pudo abrir: {self.settings.video_source}")
            return None

        for transport in self._transport_candidates():
            self._set_ffmpeg_rtsp_options(transport)
            for backend in self._backend_candidates():
                cap = cv2.VideoCapture(self.settings.video_source, backend)
                cap.set(cv2.CAP_PROP_BUFFERSIZE, 2)
                if cap.isOpened():
                    print(f"[RTSP] conectado con transport={transport}, backend={backend}")
                    return cap
                cap.release()
        return None

    # ------------------------------------------------------------------ worker

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

            self._restart_event.clear()

            while not self._stop_event.is_set():
                # Restart solicitado mientras el video estaba en reproducción
                if self._is_file and self._restart_event.is_set():
                    self._restart_event.clear()
                    break

                ok, frame = capture.read()
                if not ok:
                    if self._is_file:
                        # Archivo terminado: esperar a que el browser refresque
                        self._set_snapshot(
                            DetectionSnapshot(
                                frame_id=frame_id,
                                timestamp=datetime.now(timezone.utc).isoformat(),
                                connected=False,
                            )
                        )
                        while not self._stop_event.is_set():
                            if self._restart_event.wait(timeout=0.5):
                                self._restart_event.clear()
                                break
                        break  # reabrir el archivo desde el principio
                    else:
                        self._set_snapshot(
                            DetectionSnapshot(
                                frame_id=frame_id,
                                timestamp=datetime.now(timezone.utc).isoformat(),
                                connected=False,
                            )
                        )
                        break

                start = time.perf_counter()
                try:
                    results = self._model(frame, size=self.settings.img_size)
                except RuntimeError as exc:
                    msg = str(exc).lower()
                    if (
                        "unable to find an engine" in msg
                        and self._device != "cpu"
                        and not self._gpu_failed
                    ):
                        print(
                            "[YOLOv5] Error de engine CUDA/cuDNN; cambiando a CPU para mantener el servicio activo."
                        )
                        self._gpu_failed = True
                        self._device = "cpu"
                        self._model = self._load_model("cpu")
                        time.sleep(0.2)
                        continue
                    print(f"[YOLOv5] RuntimeError en inferencia: {exc}")
                    time.sleep(0.2)
                    continue
                except Exception as exc:  # noqa: BLE001
                    print(f"[YOLOv5] Error inesperado en inferencia: {exc}")
                    time.sleep(0.2)
                    continue

                # results.pred[0]: tensor [N, 6] — x1, y1, x2, y2, conf, cls
                detections = results.pred[0]
                people = 0
                vehicles = 0
                if detections is not None and len(detections):
                    for *_, cls_id in detections.tolist():
                        cls_id = int(cls_id)
                        if cls_id == self.settings.person_class_id:
                            people += 1
                        elif cls_id in self.settings.vehicle_class_ids:
                            vehicles += 1

                annotated = results.render()[0]
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
            if not self._is_file:
                time.sleep(self.settings.reconnect_delay_sec)
