# esp-cam

ESP32-S3 firmware for the Seeed XIAO ESP32S3 Sense that captures JPEGs on an interval, timestamps each shot, and uploads them to a companion FastAPI server.

## What it does

- Connects to WiFi and syncs time via SNTP
- Captures photos at a configurable interval
- Sends `capture_started_at` and `capture_finished_at` with each upload
- Python server stores images in SQLite, runs YOLO detection, and serves an analytics dashboard

## Hardware

- **Board:** Seeed XIAO ESP32S3 Sense
- **Target:** `esp32s3` (set in `sdkconfig.defaults`)

## Firmware setup

Requires ESP-IDF v6.x and a USB connection to the board.

```bash
source ~/.espressif/tools/activate_idf_v6.0.2.sh   # or your IDF activate script
idf.py set-target esp32s3
idf.py menuconfig
```

Under **Camera Uploader**, set:

| Option | Example |
|---|---|
| WiFi SSID / password | your network |
| Photo upload URL | `http://192.168.x.x:8000/upload` |
| Capture interval | `20000` (20 s) |
| Camera white balance preset | **Office** (default) for indoor scenes |

If colors look too warm or yellow indoors, try **Home** or **Cloudy** in menuconfig instead of Auto.

Build and flash:

```bash
idf.py build
idf.py -p /dev/cu.usbmodem1101 flash monitor
```

Use your machine's LAN IP in the upload URL, not `localhost`.

## Server setup

```bash
cd server
./run.sh
```

- **Dashboard:** http://localhost:8000/
- **Upload endpoint:** http://localhost:8000/upload
- **Stats API:** http://localhost:8000/api/stats/summary

Optional env vars:

| Variable | Default | Purpose |
|---|---|---|
| `DATABASE_PATH` | `server/data/esp_cam.db` | SQLite database file |
| `CAPTURES_DIR` | `server/captures` | JPEG storage directory |
| `CAPTURE_RETENTION_MINUTES` | `10` | Delete captures older than this |
| `CAPTURE_CLEANUP_INTERVAL_SECONDS` | `60` | How often cleanup runs |
| `PORT` | `8000` | Server port |
| `DETECTOR_URL` | _(unset)_ | YOLO detector base URL (set automatically in Docker Compose) |

On first startup, existing `latency.jsonl` / `detections.jsonl` files are imported into SQLite if the database is empty.

## Object detection (Docker)

Run the upload server with a YOLO26 medium detector sidecar:

```bash
docker compose up --build
```

- **Dashboard:** http://localhost:8000/
- **Upload endpoint:** http://localhost:8000/upload
- **Detector API:** http://localhost:8001/detect

Each upload triggers background inference. The dashboard shows annotated frames, detection lists, and Chart.js graphs for latency and class distribution. Metadata is stored in SQLite at `server/data/esp_cam.db`.

Docker env vars:

| Variable | Default | Purpose |
|---|---|---|
| `YOLO_MODEL` | `yolo26m.pt` | Ultralytics weights (n/s/m/l/x) |
| `YOLO_CONF` | `0.25` | Confidence threshold |
| `DETECTOR_PORT` | `8001` | Host port for detector service |

Run only the detector locally:

```bash
docker compose up --build detector
curl -F "image=@server/captures/some.jpg" "http://localhost:8001/detect?annotate=true"
```

To use detection without Docker, start the detector container and point the server at it:

```bash
DETECTOR_URL=http://localhost:8001 ./run.sh
```

## Stored data

Each capture is stored as a JPEG on disk with metadata in SQLite:

- `capture_started_at`, `capture_finished_at`, `received_at`
- `capture_time_ms` — finish minus start (on-device capture)
- `total_latency_ms` — received minus start (end-to-end)
- `inference_ms`, detections JSON — from YOLO after upload

Stats endpoints: `/api/stats/summary`, `/api/stats/timeseries`, `/api/stats/classes`

## Share the viewer remotely

The ESP must still upload to your **LAN IP** (e.g. `http://192.168.x.x:8000/upload`). The tunnel is only for viewing the dashboard from outside your network.

**Option A — helper script (recommended on macOS):**

```bash
# Start the full stack first (api + detector)
docker compose up -d

# Wait for API health, then start tunnel (uses 127.0.0.1, not localhost)
cd server && ./tunnel.sh
```

**Option B — Docker-managed tunnel:**

```bash
docker compose --profile tunnel up -d
docker compose logs tunnel
```

Copy the `https://….trycloudflare.com` URL from the output.

**Option C — manual:**

```bash
cloudflared tunnel --url http://127.0.0.1:8000
```

Use `127.0.0.1` instead of `localhost` on macOS — `localhost` can resolve to IPv6 while Docker publishes on IPv4, which breaks cloudflared.

If the tunnel page is blank, make sure **both** `api` and `detector` are running (`docker compose up -d`), not just the detector service.

## Project layout

```
main/              ESP-IDF app (WiFi, camera, SNTP, uploader)
server/app/        FastAPI package (api, services, models, static dashboard)
server/detector/   YOLO26 detection microservice (Docker)
server/data/       SQLite database (created at runtime)
server/captures/   JPEG files
docker-compose.yml
sdkconfig.defaults
.cursor/mcp.json   ESP-IDF MCP server config (optional)
```
