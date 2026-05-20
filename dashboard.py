#!/usr/bin/env python3
"""KNN-MMD Training Dashboard - serves real-time acc/loss charts in browser."""

import http.server
import json
import os
import argparse
from urllib.parse import urlparse, parse_qs

LOG_DIR = "./logs"
PORT = 8899

HTML = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>KNN-MMD Dashboard</title>
<script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.0/dist/chart.umd.min.js"></script>
<style>
  * { box-sizing: border-box; margin: 0; padding: 0; }
  body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; background: #0f172a; color: #e2e8f0; padding: 20px; }
  .header { display: flex; align-items: center; gap: 20px; margin-bottom: 20px; flex-wrap: wrap; }
  .header h1 { font-size: 1.5rem; color: #38bdf8; }
  .header select { padding: 6px 12px; border-radius: 6px; background: #1e293b; color: #e2e8f0; border: 1px solid #334155; font-size: 0.9rem; }
  .header label { font-size: 0.85rem; color: #94a3b8; }
  .best-cards { display: flex; gap: 16px; margin-bottom: 20px; flex-wrap: wrap; }
  .card { background: #1e293b; border: 1px solid #334155; border-radius: 10px; padding: 16px 24px; min-width: 150px; }
  .card .label { font-size: 0.75rem; color: #94a3b8; text-transform: uppercase; letter-spacing: 0.05em; }
  .card .value { font-size: 1.5rem; font-weight: 700; color: #38bdf8; }
  .card .sub { font-size: 0.8rem; color: #64748b; }
  .charts { display: grid; grid-template-columns: 1fr 1fr; gap: 20px; }
  @media (max-width: 900px) { .charts { grid-template-columns: 1fr; } }
  .chart-box { background: #1e293b; border: 1px solid #334155; border-radius: 10px; padding: 16px; }
  .chart-box h3 { font-size: 0.95rem; margin-bottom: 10px; color: #cbd5e1; }
  .status { font-size: 0.8rem; color: #64748b; margin-top: 10px; }
  .status.ok { color: #4ade80; }
  .status.err { color: #f87171; }
</style>
</head>
<body>
<div class="header">
  <h1>KNN-MMD Training Dashboard</h1>
  <div>
    <label>Run:</label>
    <select id="run-select" onchange="loadMetrics()"></select>
  </div>
  <span id="status" class="status">Connecting...</span>
</div>

<div class="best-cards">
  <div class="card">
    <div class="label">Best Accuracy</div>
    <div class="value" id="best-acc">--</div>
    <div class="sub" id="best-acc-epoch"></div>
  </div>
  <div class="card">
    <div class="label">Best Loss</div>
    <div class="value" id="best-loss">--</div>
    <div class="sub" id="best-loss-epoch"></div>
  </div>
  <div class="card">
    <div class="label">Task</div>
    <div class="value" id="task-name">--</div>
  </div>
</div>

<div class="charts">
  <div class="chart-box">
    <h3>Accuracy</h3>
    <canvas id="acc-chart"></canvas>
  </div>
  <div class="chart-box">
    <h3>Loss</h3>
    <canvas id="loss-chart"></canvas>
  </div>
</div>

<script>
let accChart, lossChart;
let pollTimer = null;

const COLORS = { train: '#38bdf8', valid: '#4ade80', test: '#f472b6' };

function makeChart(canvasId, datasets) {
  const ctx = document.getElementById(canvasId).getContext('2d');
  return new Chart(ctx, {
    type: 'line',
    data: { labels: [], datasets: datasets },
    options: {
      responsive: true,
      animation: false,
      scales: {
        x: { ticks: { color: '#94a3b8' }, grid: { color: '#1e293b' } },
        y: { ticks: { color: '#94a3b8' }, grid: { color: '#1e293b' }, beginAtZero: false }
      },
      plugins: { legend: { labels: { color: '#cbd5e1' } } }
    }
  });
}

function initCharts() {
  accChart = makeChart('acc-chart', [
    { label: 'Train Acc', data: [], borderColor: COLORS.train, tension: 0.3, pointRadius: 0 },
    { label: 'Valid Acc', data: [], borderColor: COLORS.valid, tension: 0.3, pointRadius: 0 },
    { label: 'Test Acc', data: [], borderColor: COLORS.test, tension: 0.3, pointRadius: 0, borderDash: [4, 4] }
  ]);
  lossChart = makeChart('loss-chart', [
    { label: 'Train Loss', data: [], borderColor: COLORS.train, tension: 0.3, pointRadius: 0 },
    { label: 'Valid Loss', data: [], borderColor: COLORS.valid, tension: 0.3, pointRadius: 0 },
    { label: 'Test Loss', data: [], borderColor: COLORS.test, tension: 0.3, pointRadius: 0, borderDash: [4, 4] }
  ]);
}

async function loadRuns() {
  try {
    const resp = await fetch('/api/runs');
    const runs = await resp.json();
    const sel = document.getElementById('run-select');
    sel.innerHTML = '';
    runs.forEach(r => {
      const opt = document.createElement('option');
      opt.value = r;
      opt.textContent = r;
      sel.appendChild(opt);
    });
    if (runs.length > 0) {
      sel.value = runs[runs.length - 1];
    }
  } catch(e) {
    document.getElementById('status').textContent = 'Cannot reach server';
    document.getElementById('status').className = 'status err';
  }
}

async function loadMetrics() {
  const run = document.getElementById('run-select').value;
  if (!run) return;
  try {
    const resp = await fetch('/api/metrics?run=' + encodeURIComponent(run));
    if (!resp.ok) throw new Error('not found');
    const data = await resp.json();
    const h = data.history;
    const epochs = h.map(e => e.epoch);

    // Update charts
    accChart.data.labels = epochs;
    accChart.data.datasets[0].data = h.map(e => e.train_acc);
    accChart.data.datasets[1].data = h.map(e => e.valid_acc);
    accChart.data.datasets[2].data = h.map(e => e.test_acc);
    accChart.update('none');

    lossChart.data.labels = epochs;
    lossChart.data.datasets[0].data = h.map(e => e.train_loss);
    lossChart.data.datasets[1].data = h.map(e => e.valid_loss);
    lossChart.data.datasets[2].data = h.map(e => e.test_loss);
    lossChart.update('none');

    // Update best cards
    const last = h[h.length - 1];
    document.getElementById('best-acc').textContent = (last.best_acc * 100).toFixed(2) + '%';
    document.getElementById('best-loss').textContent = last.best_loss.toFixed(4);
    document.getElementById('task-name').textContent = data.args.task || '--';

    // Find epoch for best acc / best loss
    let bestAccEp = h[0], bestLossEp = h[0];
    h.forEach(e => { if (e.best_acc >= bestAccEp.best_acc) bestAccEp = e; });
    h.forEach(e => { if (e.best_loss <= bestLossEp.best_loss) bestLossEp = e; });
    document.getElementById('best-acc-epoch').textContent = 'Epoch ' + bestAccEp.epoch;
    document.getElementById('best-loss-epoch').textContent = 'Epoch ' + bestLossEp.epoch;

    document.getElementById('status').textContent = 'Updated at ' + new Date().toLocaleTimeString();
    document.getElementById('status').className = 'status ok';
  } catch(e) {
    document.getElementById('status').textContent = 'Error: ' + e.message;
    document.getElementById('status').className = 'status err';
  }
}

async function init() {
  initCharts();
  await loadRuns();
  await loadMetrics();
  pollTimer = setInterval(loadMetrics, 5000);
}

window.addEventListener('load', init);
</script>
</body>
</html>"""


class DashboardHandler(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path
        qs = parse_qs(parsed.query)

        if path == "/api/runs":
            self._json_response(self._list_runs())
        elif path == "/api/metrics":
            run_name = qs.get("run", [None])[0]
            if not run_name:
                self._error("Missing ?run= parameter", 400)
                return
            data = self._get_metrics(run_name)
            if data is None:
                self._error("Run not found", 404)
                return
            self._json_response(data)
        elif path == "/":
            self._serve_html()
        else:
            self._error("Not found", 404)

    def _serve_html(self):
        body = HTML.encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _json_response(self, data):
        body = json.dumps(data).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(body)

    def _error(self, msg, code):
        body = json.dumps({"error": msg}).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _list_runs(self):
        if not os.path.isdir(LOG_DIR):
            return []
        runs = sorted([
            d for d in os.listdir(LOG_DIR)
            if os.path.isdir(os.path.join(LOG_DIR, d))
        ])
        return runs

    def _get_metrics(self, run_name):
        safe = os.path.basename(run_name)
        path = os.path.join(LOG_DIR, safe, "metrics.json")
        if not os.path.isfile(path):
            return None
        with open(path, "r") as f:
            return json.load(f)

    def log_message(self, format, *args):
        pass  # suppress access logs


def main():
    global LOG_DIR
    parser = argparse.ArgumentParser(description="KNN-MMD Training Dashboard")
    parser.add_argument("--port", type=int, default=PORT, help="HTTP server port (default: 8899)")
    parser.add_argument("--log-dir", type=str, default=LOG_DIR, help="Path to training logs directory")
    args = parser.parse_args()

    LOG_DIR = args.log_dir

    os.makedirs(LOG_DIR, exist_ok=True)

    server = http.server.HTTPServer(("0.0.0.0", args.port), DashboardHandler)
    print(f"Dashboard running at http://localhost:{args.port}")
    print(f"Watching logs in: {os.path.abspath(LOG_DIR)}")
    print("Press Ctrl+C to stop")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopped.")


if __name__ == "__main__":
    main()
