# API + Interfaz YOLO11 para Jetson Orin Nano (JetPack 6.2.2)

Proyecto en Python para:
- Procesar una fuente RTSP en tiempo real.
- Detectar **peatones** y **vehículos** (sin bicicletas ni scooters/motos ligeras).
- Mostrar video anotado en una interfaz web.
- Exponer API JSON con conteo instantáneo sincronizado con el frame procesado.

## Modelo elegido
Se usa por defecto `yolo11n.pt` (variante tiny/nano) por latencia y FPS en Jetson Orin Nano.

Si quieres más precisión y aceptas menor FPS:
- `yolo11s.pt` (small)
- `yolo11m.pt` (medium)

Cambia en tu archivo de entorno:
```bash
MODEL_PATH=yolo11n.pt
```

## Estructura
- `app/main.py`: servidor FastAPI + endpoints web/API.
- `app/detector.py`: hilo de inferencia RTSP + YOLO11 + snapshot compartido.
- `app/templates/index.html`: interfaz web.
- `app/static/`: JS/CSS de UI.
- `scripts/setup.sh`: crea venv e instala dependencias.
- `run.sh`: ejecuta el servidor por terminal.

## Configuración
1. Crear entorno e instalar:
```bash
cd API_INTERFAZ
./scripts/setup.sh
```

2. Crear y editar `.env` con tu RTSP real:
```bash
cp .env.example .env
RTSP_URL=rtsp://usuario:password@IP_CAMARA:554/stream1
RTSP_TRANSPORT=auto
```

Alternativa recomendada (fuera del repo):
```bash
sudo cp .env.example /etc/yolov11-rtsp.env
sudo nano /etc/yolov11-rtsp.env
sudo chown "$USER":"$USER" /etc/yolov11-rtsp.env
sudo chmod 600 /etc/yolov11-rtsp.env
```

3. Mantener clases objetivo (COCO):
- `PERSON_CLASS_ID=0`
- `VEHICLE_CLASS_IDS=2,5,7,6` (car, bus, truck, train)
- Se excluyen bicicleta (`1`) y motocicleta/scooter (`3`).

## Ejecución por terminal
```bash
cd API_INTERFAZ
source .venv/bin/activate
./run.sh
```

Opcional: usar archivo de entorno fuera del repo:
```bash
ENV_FILE=/etc/yolov11-rtsp.env ./run.sh
```

Nota: `run.sh` busca automáticamente en este orden:
1. `ENV_FILE` (si lo defines)
2. `/etc/yolov11-rtsp.env`
3. `/etc/yolo11-rtsp.env`
4. `.env`

Si `RTSP_URL` no está configurada correctamente, la app detiene el arranque con error explícito.

Si ves error `461 Unsupported Transport`, configura explícitamente:
```bash
RTSP_TRANSPORT=udp
```
Si tu cámara requiere TCP, usa:
```bash
RTSP_TRANSPORT=tcp
```

Abrir:
- UI: `http://<IP_JETSON>:8000/`
- API: `http://<IP_JETSON>:8000/api/counts`

## API JSON
`GET /api/counts` devuelve:
```json
{
  "frame_id": 1024,
  "timestamp": "2026-03-02T01:25:44.238000+00:00",
  "connected": true,
  "people": 3,
  "vehicles": 5,
  "fps": 18.9,
  "model": "yolo11n.pt"
}
```

La sincronización con video se garantiza porque el stream MJPEG (`/video_feed`) y el endpoint `/api/counts` leen el mismo snapshot en memoria (mismo `frame_id`).

## Seguridad para GitHub (recomendado)
- Nunca subas secretos al repositorio: `.env` y `.env.*` están ignorados por `.gitignore`.
- Sube solo `.env.example` con placeholders.
- Guarda secretos reales solo en la Jetson, por ejemplo en `/etc/yolov11-rtsp.env`.
- Protege el archivo de secretos:
```bash
sudo chown "$USER":"$USER" /etc/yolov11-rtsp.env
sudo chmod 600 /etc/yolov11-rtsp.env
```
- Antes de hacer `git push`, valida que no se versionen secretos:
```bash
git status
git ls-files | grep -E '^\.env|\.env\.' || true
```

## Notas de rendimiento para Orin Nano
- Si baja FPS, prueba:
  - `IMG_SIZE=512` o `IMG_SIZE=416`
  - subir `CONF_THRESHOLD` a `0.4` o `0.45`
  - bajar calidad MJPEG (`JPEG_QUALITY=70`)
- Para precisión mayor, usa `MODEL_PATH=yolo11s.pt`.
