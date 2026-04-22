# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Real-time pedestrian and vehicle detection web app for the **NVIDIA Jetson Orin Nano** (JetPack 6.2.2). Reads an RTSP camera stream, runs YOLOv11 inference, and serves annotated MJPEG video + JSON metrics via FastAPI.

## Setup & Run

```bash
# Initial setup (creates .venv, installs deps, copies .env.example → .env)
./scripts/setup.sh

# Edit .env with your RTSP_URL and desired settings
# Then run:
source .venv/bin/activate
./run.sh

# Or point to a system-level secrets file:
ENV_FILE=/etc/yolov11-rtsp.env ./run.sh
```

Web UI: `http://<JETSON_IP>:8000/`  
API: `http://<JETSON_IP>:8000/api/counts`  
Health: `http://<JETSON_IP>:8000/api/health`  

## Key Configuration (`.env` / `.env.example`)

| Variable | Default | Notes |
|---|---|---|
| `RTSP_URL` | *(required)* | Camera stream URL |
| `RTSP_TRANSPORT` | `auto` | `udp`, `tcp`, or `auto` |
| `MODEL_PATH` | `yolo11n.pt` | YOLO model variant (n/s/m) |
| `DEVICE` | `auto` | `cpu`, `0` (CUDA), or `auto` |
| `CONF_THRESHOLD` | `0.35` | Detection confidence |
| `IMG_SIZE` | `640` | Lower = faster (e.g. 416) |
| `JPEG_QUALITY` | `80` | Lower = faster stream |

Config loading priority: `ENV_FILE` env var → `/etc/yolov11-rtsp.env` → `/etc/yolo11-rtsp.env` → `.env`.

## Architecture

**Threading model:** A single background worker thread (`detector._worker`) continuously reads RTSP frames, runs YOLO inference, and writes results into a `DetectionSnapshot` dataclass protected by `threading.Lock`. FastAPI handlers read from this snapshot — they never touch OpenCV or the model directly.

**Key modules:**
- `app/config.py` — Loads and validates all settings; exports `Settings` dataclass
- `app/detector.py` — RTSP capture + YOLO inference worker; exposes `get_snapshot()` and `get_frame()`
- `app/main.py` — FastAPI app with lifespan (starts/stops detector); four endpoints: `/`, `/video_feed`, `/api/counts`, `/api/health`

**Data flow:**
```
RTSP → detector._worker() → DetectionSnapshot (lock-protected)
                                   ├── /video_feed  → MJPEG stream
                                   └── /api/counts  → JSON
                                         ↑ polled every 300ms by app.js
```

**RTSP resilience:** On connection failure, the worker retries with protocol fallback (UDP → TCP) and backend fallback (FFMPEG → ANY), then reconnects with configurable delay.

**GPU/CPU fallback:** CUDA is auto-detected at model load. If a `RuntimeError` occurs during GPU inference, the worker falls back to CPU transparently and continues running.

**Frontend:** `app/static/app.js` polls `/api/counts` every 300ms to update metrics. Video is rendered as a plain `<img>` tag consuming the MJPEG `/video_feed` endpoint.

## Detection Classes

Only COCO class IDs for **person** (`PERSON_CLASS_ID=0`) and **vehicles** (`VEHICLE_CLASS_IDS=2,3,5,7` — car, motorcycle excluded by design, bus, truck) are counted. Bicycles and motorcycles/scooters are intentionally excluded.

## Dependencies

Five pinned direct dependencies in `requirements.txt`: `fastapi`, `uvicorn[standard]`, `jinja2`, `python-dotenv`, `ultralytics`. PyTorch and OpenCV are expected to be pre-installed on the Jetson via JetPack.

## No Test Suite

There are no automated tests or linters configured in this project.
