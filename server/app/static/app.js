const frame = document.getElementById("frame");
const empty = document.getElementById("empty");
const meta = document.getElementById("meta");
const detections = document.getElementById("detections");
const status = document.getElementById("status");
const viewMode = document.getElementById("view-mode");
const timetravel = document.getElementById("timetravel");
const liveBtn = document.getElementById("live-btn");
const prevBtn = document.getElementById("prev-btn");
const nextBtn = document.getElementById("next-btn");
const scrubber = document.getElementById("scrubber");
const timetravelLabel = document.getElementById("timetravel-label");

const statCount = document.getElementById("stat-count");
const statCapture = document.getElementById("stat-capture");
const statLatency = document.getElementById("stat-latency");
const statInference = document.getElementById("stat-inference");

let lastFilename = null;
let latencyChart = null;
let detectionChart = null;
let classChart = null;
let chartPoints = [];

let liveMode = true;
let timeline = [];
let browseContext = null;

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

function formatTimestamp(iso) {
  if (!iso) return "—";
  return new Date(iso).toLocaleString([], {
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
  });
}

function row(label, value) {
  if (value == null || value === "") return "";
  return `<dt>${label}</dt><dd>${value}</dd>`;
}

function formatMs(value) {
  return value == null ? "—" : `${value} ms`;
}

function setViewMode(isLive) {
  liveMode = isLive;
  viewMode.textContent = isLive ? "Live" : "History";
  viewMode.classList.toggle("mode-live", isLive);
  viewMode.classList.toggle("mode-history", !isLive);
  liveBtn.classList.toggle("active", isLive);
}

function updateUrl(captureId) {
  const url = new URL(window.location.href);
  if (liveMode || captureId == null) {
    url.searchParams.delete("id");
  } else {
    url.searchParams.set("id", String(captureId));
  }
  history.replaceState(null, "", url);
}

function updateTimetravelUi() {
  if (!timeline.length) {
    timetravel.hidden = true;
    return;
  }

  timetravel.hidden = false;
  scrubber.max = String(Math.max(timeline.length - 1, 0));
  scrubber.disabled = timeline.length <= 1;

  const index = browseContext?.index ?? timeline.length - 1;
  scrubber.value = String(Math.max(0, Math.min(index, timeline.length - 1)));

  const current = timeline[Number(scrubber.value)];
  const position = timeline.length ? `${Number(scrubber.value) + 1} / ${timeline.length}` : "—";
  timetravelLabel.textContent = current
    ? `${formatTimestamp(current.received_at)} · ${position}`
    : position;

  prevBtn.disabled = browseContext?.prev_id == null;
  nextBtn.disabled = browseContext?.next_id == null;
}

function renderCapture(capture) {
  if (!capture) {
    frame.hidden = true;
    meta.hidden = true;
    detections.hidden = true;
    empty.hidden = false;
    return;
  }

  empty.hidden = true;
  frame.hidden = false;
  meta.hidden = false;
  detections.hidden = false;
  frame.src = `${capture.image_url}?v=${encodeURIComponent(capture.filename)}`;

  meta.innerHTML = [
    row("Capture started", capture.capture_started_at),
    row("Capture finished", capture.capture_finished_at),
    row("Received on server", capture.received_at),
    row("Capture time", formatMs(capture.capture_time_ms)),
    row("Total latency", formatMs(capture.total_latency_ms)),
    row("Detections", capture.detection_count != null ? String(capture.detection_count) : null),
    row("Inference", formatMs(capture.inference_ms)),
    row("Model", capture.detector_model),
    row("File", `${capture.filename} (${capture.bytes} bytes)`),
  ].join("");

  if (Array.isArray(capture.detections) && capture.detections.length) {
    detections.innerHTML = capture.detections.map((item) =>
      `<li>${item.class_name} ${(item.confidence * 100).toFixed(1)}%</li>`
    ).join("");
  } else if (capture.detection_count === 0) {
    detections.innerHTML = `<li class="none">No objects detected</li>`;
  } else {
    detections.innerHTML = `<li class="none">Detection pending…</li>`;
  }
}

async function loadTimeline() {
  const res = await fetch("/api/captures?limit=1000&offset=0");
  if (!res.ok) {
    timetravel.hidden = false;
    timetravelLabel.textContent = `History unavailable (${res.status}). Restart/rebuild the server.`;
    return;
  }
  const data = await res.json();
  timeline = (data.captures || [])
    .slice()
    .reverse()
    .map((capture) => ({
      id: capture.id,
      received_at: capture.received_at,
    }));
  updateTimetravelUi();
}

async function showBrowseContext(context) {
  browseContext = context;
  setViewMode(false);
  renderCapture(context.capture);
  updateTimetravelUi();
  updateUrl(context.capture.id);

  if (context.capture.filename !== lastFilename) {
    lastFilename = context.capture.filename;
    refreshCharts();
  }
}

async function goToId(captureId) {
  if (captureId == null) return;
  const res = await fetch(`/api/captures/${captureId}`);
  if (!res.ok) return;
  const context = await res.json();
  await showBrowseContext(context);
}

async function goLive() {
  setViewMode(true);
  browseContext = null;
  updateUrl(null);
  await refreshLatest();
  updateTimetravelUi();
}

function chartClickHandler(_event, elements) {
  if (!elements.length) return;
  const point = chartPoints[elements[0].index];
  if (point?.id) {
    goToId(point.id);
  }
}

function initCharts() {
  if (typeof Chart === "undefined") {
    console.warn("Chart.js unavailable; live feed will still work.");
    return;
  }

  const clickOptions = {
    ...chartDefaults,
    onClick: chartClickHandler,
  };

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
    options: clickOptions,
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
    options: clickOptions,
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
    renderCapture(null);
    return;
  }

  const latest = data.latest;
  renderCapture(latest);

  if (liveMode) {
    const index = timeline.findIndex((entry) => entry.id === latest.id);
    const resolvedIndex = index >= 0 ? index : Math.max(timeline.length - 1, 0);
    browseContext = {
      capture: latest,
      index: resolvedIndex,
      total: timeline.length,
      prev_id: resolvedIndex > 0 ? timeline[resolvedIndex - 1]?.id ?? null : null,
      next_id: null,
    };
    updateTimetravelUi();
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

  chartPoints = timeseries.points || [];
  const labels = chartPoints.map((point) => shortLabel(point.received_at, point.filename));

  latencyChart.data.labels = labels;
  latencyChart.data.datasets[0].data = chartPoints.map((point) => point.capture_time_ms);
  latencyChart.data.datasets[1].data = chartPoints.map((point) => point.total_latency_ms);
  latencyChart.data.datasets[2].data = chartPoints.map((point) => point.inference_ms);
  latencyChart.update();

  detectionChart.data.labels = labels;
  detectionChart.data.datasets[0].data = chartPoints.map((point) => point.detection_count ?? 0);
  detectionChart.update();

  classChart.data.labels = (classes.classes || []).map((item) => item.class_name);
  classChart.data.datasets[0].data = (classes.classes || []).map((item) => item.count);
  classChart.update();
}

async function refreshAll() {
  try {
    await loadTimeline();
    if (liveMode) {
      await refreshLatest();
    } else if (browseContext?.capture?.id != null) {
      const res = await fetch(`/api/captures/${browseContext.capture.id}`);
      if (res.ok) {
        browseContext = await res.json();
        renderCapture(browseContext.capture);
        updateTimetravelUi();
      }
    }
    await refreshSummary();
    status.textContent = `Updated ${new Date().toLocaleTimeString()}`;
  } catch (err) {
    status.textContent = `Refresh failed: ${err}`;
  }
}

liveBtn.addEventListener("click", () => {
  goLive();
});

prevBtn.addEventListener("click", () => {
  if (browseContext?.prev_id != null) {
    goToId(browseContext.prev_id);
  }
});

nextBtn.addEventListener("click", () => {
  if (browseContext?.next_id != null) {
    goToId(browseContext.next_id);
  } else if (browseContext?.next_id == null && !liveMode) {
    goLive();
  }
});

scrubber.addEventListener("input", () => {
  const entry = timeline[Number(scrubber.value)];
  if (entry?.id != null) {
    goToId(entry.id);
  }
});

async function bootstrap() {
  initCharts();
  await loadTimeline();

  const url = new URL(window.location.href);
  const captureId = Number.parseInt(url.searchParams.get("id") || "", 10);
  if (Number.isFinite(captureId)) {
    await goToId(captureId);
    await refreshSummary();
  } else {
    setViewMode(true);
    await refreshAll();
  }

  setInterval(refreshAll, 2000);
  setInterval(refreshCharts, 10000);
}

bootstrap();
