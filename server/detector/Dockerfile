FROM python:3.12-slim-bookworm

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    libgl1 \
    libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

ARG YOLO_MODEL=yolo26m.pt
RUN python -c "from ultralytics import YOLO; YOLO('${YOLO_MODEL}')"

COPY app.py .

ENV YOLO_MODEL=${YOLO_MODEL}
ENV YOLO_CONF=0.25

EXPOSE 8001

CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8001"]
