from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

ROOT_DIR = Path(__file__).resolve().parents[1]
load_dotenv(ROOT_DIR / ".env")


DEFAULT_RTSP = "rtsp://usuario:password@192.168.1.100:554/stream1"


def _get_int(name: str, default: int) -> int:
    value = os.getenv(name)
    if value is None:
        return default
    try:
        return int(value)
    except ValueError:
        return default


def _get_float(name: str, default: float) -> float:
    value = os.getenv(name)
    if value is None:
        return default
    try:
        return float(value)
    except ValueError:
        return default


def _get_class_list(name: str, default: tuple[int, ...]) -> tuple[int, ...]:
    raw = os.getenv(name)
    if not raw:
        return default
    class_ids: list[int] = []
    for part in raw.split(","):
        part = part.strip()
        if not part:
            continue
        try:
            class_ids.append(int(part))
        except ValueError:
            continue
    return tuple(class_ids) if class_ids else default


@dataclass(frozen=True)
class Settings:
    host: str
    port: int
    rtsp_url: str
    model_path: str
    conf_threshold: float
    iou_threshold: float
    img_size: int
    jpeg_quality: int
    reconnect_delay_sec: float
    device: str
    person_class_id: int
    vehicle_class_ids: tuple[int, ...]


def load_settings() -> Settings:
    return Settings(
        host=os.getenv("HOST", "0.0.0.0"),
        port=_get_int("PORT", 8000),
        rtsp_url=os.getenv("RTSP_URL", DEFAULT_RTSP),
        model_path=os.getenv("MODEL_PATH", "yolo11n.pt"),
        conf_threshold=_get_float("CONF_THRESHOLD", 0.35),
        iou_threshold=_get_float("IOU_THRESHOLD", 0.45),
        img_size=_get_int("IMG_SIZE", 640),
        jpeg_quality=_get_int("JPEG_QUALITY", 80),
        reconnect_delay_sec=_get_float("RECONNECT_DELAY_SEC", 2.0),
        device=os.getenv("DEVICE", "0"),
        person_class_id=_get_int("PERSON_CLASS_ID", 0),
        vehicle_class_ids=_get_class_list("VEHICLE_CLASS_IDS", (2, 5, 7, 6)),
    )
