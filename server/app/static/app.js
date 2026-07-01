const frame = document.getElementById("frame");
const empty = document.getElementById("empty");
const meta = document.getElementById("meta");
const detections = document.getElementById("detections");
const status = document.getElementById("status");

const statCount = document.getElementById("stat-count");
const statCapture = document.getElementById("stat-capture");
const statLatency = document.getElementById("stat-latency");
const statInference = document.getElementById("stat-inference");

let lastFilename = null;
let latencyChart = null;
let detectionChart = null;
let classChart = null;

const chartDefaults = {
  responsive: true,
  maintainAspectRatio: false,
  plugins: {
    legend: {
      labels: { color: "#c9d1d9" },
    },
  },
  scales: {
    x: {
      ticks: { color: "#8b949e", maxRotation: 0, autoSkip: true, maxTicksLimit: 8 },
      grid: { color: "rgba(48,54,61,0.6)" },
    },
    y: {
      ticks: { color: "#8b949e" },
      grid: { color: "rgba(48,54,61,0.6)" },
    },
  },
};

function shortLabel(iso, filename) {
  if (!iso) return filename.slice(-12);
  const date = new Date(iso);
  return date.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", second: "2-digit" });
}

function row(label, value) {
  if (value == null || value === "") return "";
  return `<dt>${label}</dt><dd>${value}</dd>`;
}

function formatMs(value) {
  return value == null ? "—" : `${value} ms`;
}

function initCharts() {
  if (typeof Chart === "undefined") {
    console.warn("Chart.js unavailable; live feed will still work.");
    return;
  }

  latencyChart = new Chart(document.getElementById("latency-chart"), {
    type: "line",
    data: {
      labels: [],
      datasets: [
        {
          label: "Capture time",
          data: [],
          borderColor: "#3fb950",
          backgroundColor: "rgba(63,185,80,0.15)",
          tension: 0.25,
        },
        {
          label: "Total latency",
          data: [],
          borderColor: "#f0883e",
          backgroundColor: "rgba(240,136,62,0.15)",
          tension: 0.25,
        },
        {
          label: "Inference",
          data: [],
          borderColor: "#a371f7",
          backgroundColor: "rgba(163,113,247,0.15)",
          tension: 0.25,
        },
      ],
    },
    options: chartDefaults,
  });

  detectionChart = new Chart(document.getElementById("detection-chart"), {
    type: "bar",
    data: {
      labels: [],
      datasets: [
        {
          label: "Objects detected",
          data: [],
          backgroundColor: "rgba(88,166,255,0.55)",
          borderColor: "#58a6ff",
          borderWidth: 1,
        },
      ],
    },
    options: chartDefaults,
  });

  classChart = new Chart(document.getElementById("class-chart"), {
    type: "doughnut",
    data: {
      labels: [],
      datasets: [
        {
          data: [],
          backgroundColor: [
            "#58a6ff", "#3fb950", "#f0883e", "#a371f7", "#ff7b72",
            "#d2a8ff", "#79c0ff", "#ffa657", "#7ee787", "#ff9492",
          ],
        },
      ],
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: {
        legend: {
          position: "bottom",
          labels: { color: "#c9d1d9" },
        },
      },
    },
  });
}

async function refreshLatest() {
  const res = await fetch("/api/latest");
  const data = await res.json();
  if (!data.latest) {
    frame.hidden = true;
    meta.hidden = true;
    detections.hidden = true;
    empty.hidden = false;
    return;
  }

  const latest = data.latest;
  empty.hidden = true;
  frame.hidden = false;
  meta.hidden = false;
  detections.hidden = false;
  frame.src = `${latest.image_url}?v=${encodeURIComponent(latest.filename)}`;

  meta.innerHTML = [
    row("Capture started", latest.capture_started_at),
    row("Capture finished", latest.capture_finished_at),
    row("Received on server", latest.received_at),
    row("Capture time", formatMs(latest.capture_time_ms)),
    row("Total latency", formatMs(latest.total_latency_ms)),
    row("Detections", latest.detection_count != null ? String(latest.detection_count) : null),
    row("Inference", formatMs(latest.inference_ms)),
    row("Model", latest.detector_model),
    row("File", `${latest.filename} (${latest.bytes} bytes)`),
  ].join("");

  if (Array.isArray(latest.detections) && latest.detections.length) {
    detections.innerHTML = latest.detections.map((item) =>
      `<li>${item.class_name} ${(item.confidence * 100).toFixed(1)}%</li>`
    ).join("");
  } else if (latest.detection_count === 0) {
    detections.innerHTML = `<li class="none">No objects detected</li>`;
  } else {
    detections.innerHTML = `<li class="none">Detection pending…</li>`;
  }

  if (latest.filename !== lastFilename) {
    lastFilename = latest.filename;
    refreshCharts();
  }
}

async function refreshSummary() {
  const res = await fetch("/api/stats/summary");
  const data = await res.json();
  statCount.textContent = String(data.count ?? 0);
  statCapture.textContent = formatMs(data.avg_capture_time_ms);
  statLatency.textContent = formatMs(data.avg_total_latency_ms);
  statInference.textContent = formatMs(data.avg_inference_ms);
}

async function refreshCharts() {
  if (!latencyChart || !detectionChart || !classChart) {
    return;
  }

  const [timeseriesRes, classesRes] = await Promise.all([
    fetch("/api/stats/timeseries?limit=100"),
    fetch("/api/stats/classes?limit=50"),
  ]);

  const timeseries = await timeseriesRes.json();
  const classes = await classesRes.json();

  const points = timeseries.points || [];
  const labels = points.map((point) => shortLabel(point.received_at, point.filename));

  latencyChart.data.labels = labels;
  latencyChart.data.datasets[0].data = points.map((point) => point.capture_time_ms);
  latencyChart.data.datasets[1].data = points.map((point) => point.total_latency_ms);
  latencyChart.data.datasets[2].data = points.map((point) => point.inference_ms);
  latencyChart.update();

  detectionChart.data.labels = labels;
  detectionChart.data.datasets[0].data = points.map((point) => point.detection_count ?? 0);
  detectionChart.update();

  classChart.data.labels = (classes.classes || []).map((item) => item.class_name);
  classChart.data.datasets[0].data = (classes.classes || []).map((item) => item.count);
  classChart.update();
}

async function refreshAll() {
  try {
    await Promise.all([refreshLatest(), refreshSummary()]);
    status.textContent = `Updated ${new Date().toLocaleTimeString()}`;
  } catch (err) {
    status.textContent = `Refresh failed: ${err}`;
  }
}

initCharts();
refreshAll();
setInterval(refreshAll, 2000);
setInterval(refreshCharts, 10000);
