from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

ROOT_DIR = Path(__file__).resolve().parents[1]
SYSTEM_ENV_FILE = Path("/etc/yolov11-rtsp.env")
LEGACY_SYSTEM_ENV_FILE = Path("/etc/yolo11-rtsp.env")


def _load_environment() -> None:
    # Prioridad:
    # 1) ENV_FILE explícito
    # 2) /etc/yolov11-rtsp.env
    # 3) compatibilidad: /etc/yolo11-rtsp.env
    # 4) .env local del proyecto
    explicit_env = os.getenv("ENV_FILE")
    if explicit_env:
        load_dotenv(explicit_env, override=False)
        return

    if SYSTEM_ENV_FILE.exists():
        load_dotenv(SYSTEM_ENV_FILE, override=False)
    elif LEGACY_SYSTEM_ENV_FILE.exists():
        load_dotenv(LEGACY_SYSTEM_ENV_FILE, override=False)

    load_dotenv(ROOT_DIR / ".env", override=False)


_load_environment()


DEFAULT_RTSP = "rtsp://usuario:password@192.168.1.100:554/stream1"


def _get_required_rtsp_url() -> str:
    value = os.getenv("RTSP_URL", "").strip()
    if not value or value == DEFAULT_RTSP:
        raise ValueError(
            "RTSP_URL no configurada correctamente. Define RTSP_URL en "
            "/etc/yolov11-rtsp.env (o usa ENV_FILE=/ruta/al/archivo)."
        )
    return value


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
        rtsp_url=_get_required_rtsp_url(),
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
