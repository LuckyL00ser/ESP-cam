"""YOLO26 object detection microservice."""

from __future__ import annotations

import base64
import io
import os
import time
from contextlib import asynccontextmanager

import cv2
import numpy as np
from fastapi import FastAPI, File, HTTPException, Query, UploadFile
from PIL import Image
from ultralytics import YOLO

MODEL_NAME = os.environ.get("YOLO_MODEL", "yolo26m.pt")
CONFIDENCE = float(os.environ.get("YOLO_CONF", "0.25"))
MAX_UPLOAD_BYTES = int(os.environ.get("MAX_UPLOAD_BYTES", str(5 * 1024 * 1024)))

_model: YOLO | None = None


@asynccontextmanager
async def lifespan(_app: FastAPI):
    global _model
    print(f"Loading YOLO model: {MODEL_NAME}")
    _model = YOLO(MODEL_NAME)
    print(f"Model ready: {MODEL_NAME}")
    yield


app = FastAPI(title="esp-cam YOLO detector", version="0.1.0", lifespan=lifespan)


def parse_detections(results) -> list[dict]:
    detections: list[dict] = []
    for result in results:
        names = result.names
        for box in result.boxes:
            class_id = int(box.cls)
            detections.append(
                {
                    "class_id": class_id,
                    "class_name": names[class_id],
                    "confidence": round(float(box.conf), 4),
                    "bbox_xyxy": [round(float(v), 1) for v in box.xyxy[0].tolist()],
                }
            )
    detections.sort(key=lambda item: item["confidence"], reverse=True)
    return detections


@app.get("/health")
def health() -> dict:
    return {
        "status": "ok" if _model is not None else "loading",
        "model": MODEL_NAME,
        "confidence_threshold": CONFIDENCE,
    }


@app.post("/detect")
async def detect(
    image: UploadFile = File(...),
    annotate: bool = Query(False, description="Return base64-encoded annotated JPEG"),
) -> dict:
    if _model is None:
        raise HTTPException(status_code=503, detail="Model not loaded yet")

    if image.content_type not in (None, "image/jpeg", "application/octet-stream"):
        raise HTTPException(status_code=415, detail=f"Expected JPEG, got {image.content_type}")

    data = await image.read()
    if not data:
        raise HTTPException(status_code=400, detail="Empty upload")
    if len(data) > MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=413, detail="Image too large")

    try:
        pil_image = Image.open(io.BytesIO(data)).convert("RGB")
    except Exception as exc:
        raise HTTPException(status_code=400, detail="Invalid image data") from exc

    # Ultralytics expects BGR (OpenCV) arrays; ESP JPEGs are RGB from PIL.
    image_bgr = cv2.cvtColor(np.array(pil_image), cv2.COLOR_RGB2BGR)

    started = time.perf_counter()
    results = _model.predict(source=image_bgr, conf=CONFIDENCE, verbose=False)
    inference_ms = round((time.perf_counter() - started) * 1000.0, 1)

    payload: dict = {
        "model": MODEL_NAME,
        "inference_ms": inference_ms,
        "detection_count": len(results[0].boxes),
        "detections": parse_detections(results),
    }

    if annotate:
        annotated_pil = results[0].plot(pil=True)
        buf = io.BytesIO()
        annotated_pil.save(buf, format="JPEG", quality=90)
        payload["annotated_jpeg_b64"] = base64.b64encode(buf.getvalue()).decode("ascii")

    return payload
