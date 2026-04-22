from __future__ import annotations

import time
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from app.config import load_settings
from app.detector import RealtimeDetector

settings = load_settings()
detector = RealtimeDetector(settings)

BASE_DIR = Path(__file__).resolve().parent
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))


@asynccontextmanager
async def lifespan(_: FastAPI):
    detector.start()
    try:
        yield
    finally:
        detector.stop()


app = FastAPI(
    title="Jetson YOLOv5 Monitor",
    version="2.0.0",
    lifespan=lifespan,
)
app.mount("/static", StaticFiles(directory=str(BASE_DIR / "static")), name="static")


@app.get("/")
def index(request: Request):
    return templates.TemplateResponse(
        "index.html",
        {
            "request": request,
            "model": settings.model_path,
            "vehicle_classes": settings.vehicle_class_ids,
        },
    )


def frame_generator():
    last_frame_id = -1
    boundary = b"--frame\r\nContent-Type: image/jpeg\r\n\r\n"

    while True:
        snapshot = detector.get_snapshot()

        if snapshot.connected and snapshot.jpeg and snapshot.frame_id != last_frame_id:
            last_frame_id = snapshot.frame_id
            yield boundary + snapshot.jpeg + b"\r\n"
        else:
            time.sleep(0.01)


@app.get("/video_feed")
def video_feed():
    detector.request_restart()
    return StreamingResponse(
        frame_generator(),
        media_type="multipart/x-mixed-replace; boundary=frame",
    )


@app.get("/api/counts")
def get_counts():
    snapshot = detector.get_snapshot()
    return JSONResponse(
        {
            "frame_id": snapshot.frame_id,
            "timestamp": snapshot.timestamp,
            "connected": snapshot.connected,
            "people": snapshot.people,
            "vehicles": snapshot.vehicles,
            "fps": round(snapshot.fps, 2),
            "model": settings.model_path,
        }
    )


@app.get("/api/health")
def healthcheck():
    snapshot = detector.get_snapshot()
    return JSONResponse(
        {
            "status": "ok",
            "connected": snapshot.connected,
            "last_frame_id": snapshot.frame_id,
        }
    )
