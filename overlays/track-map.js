/**
 * Track minimap (P3-03). Consumes telemetry.tick mapCars + trackId.
 * Mount: [data-track-map-root]
 */
(function initTrackMap() {
  const cfg = window.PIGRECO_CONFIG || {};
  const root = document.querySelector("[data-track-map-root]");
  if (!root) return;

  if (cfg.trackMapEnabled !== true && cfg.telemetryEnabled !== true) {
    // Prefer explicit trackMapEnabled; allow telemetryEnabled as soft enable
  }
  if (cfg.trackMapEnabled !== true) {
    root.hidden = true;
    root.setAttribute("aria-hidden", "true");
    return;
  }

  root.hidden = false;
  root.setAttribute("aria-hidden", "false");

  const url = cfg.trackMapWsUrl || cfg.telemetryWsUrl || "ws://127.0.0.1:8765";
  const pathEl = root.querySelector("[data-tm-path]");
  const carsEl = root.querySelector("[data-tm-cars]");
  const labelEl = root.querySelector("[data-tm-label]");
  const scale = 100;

  let socket = null;
  let retryMs = 1000;
  let pathPoints = null;
  let loadedTrackId = null;

  function genericOval(n) {
    const pts = [];
    for (let i = 0; i < n; i++) {
      const a = (Math.PI * 2 * i) / n;
      pts.push([0.5 + 0.42 * Math.cos(a), 0.5 + 0.28 * Math.sin(a)]);
    }
    return pts;
  }

  function toPath(pts) {
    if (!pts || !pts.length) return "";
    let d = "M " + (pts[0][0] * scale).toFixed(2) + " " + (pts[0][1] * scale).toFixed(2);
    for (let i = 1; i < pts.length; i++) {
      d += " L " + (pts[i][0] * scale).toFixed(2) + " " + (pts[i][1] * scale).toFixed(2);
    }
    return d + " Z";
  }

  function pointOn(pts, distPct) {
    if (!pts || !pts.length) return [50, 50];
    const closed = pts.concat([pts[0]]);
    let total = 0;
    const lens = [];
    for (let i = 0; i < closed.length - 1; i++) {
      const dx = closed[i + 1][0] - closed[i][0];
      const dy = closed[i + 1][1] - closed[i][1];
      const len = Math.hypot(dx, dy);
      lens.push(len);
      total += len;
    }
    let t = ((Number(distPct) % 1) + 1) % 1;
    let target = t * (total || 1);
    let acc = 0;
    for (let i = 0; i < lens.length; i++) {
      if (acc + lens[i] >= target) {
        const u = lens[i] < 1e-9 ? 0 : (target - acc) / lens[i];
        const x = closed[i][0] + u * (closed[i + 1][0] - closed[i][0]);
        const y = closed[i][1] + u * (closed[i + 1][1] - closed[i][1]);
        return [x * scale, y * scale];
      }
      acc += lens[i];
    }
    return [closed[0][0] * scale, closed[0][1] * scale];
  }

  async function loadTrack(trackId) {
    const id = trackId || "unknown";
    if (id === loadedTrackId && pathPoints) return;
    loadedTrackId = id;
    const candidates = [
      "assets/tracks/open/" + id + ".json",
      "assets/tracks/learned/" + id + ".json",
    ];
    for (let i = 0; i < candidates.length; i++) {
      try {
        const res = await fetch(candidates[i], { cache: "no-store" });
        if (!res.ok) continue;
        const data = await res.json();
        const pts = (data.points || []).map(function (p) {
          return [Number(p.x), Number(p.y)];
        });
        if (pts.length >= 8) {
          pathPoints = pts;
          if (pathEl) pathEl.setAttribute("d", toPath(pts));
          if (labelEl) labelEl.textContent = id;
          return;
        }
      } catch (_) {
        /* try next */
      }
    }
    pathPoints = genericOval(48);
    if (pathEl) pathEl.setAttribute("d", toPath(pathPoints));
    if (labelEl) labelEl.textContent = id + " (generic)";
  }

  function render(tick) {
    if (!tick) return;
    loadTrack(tick.trackId || tick.trackName);
    const cars = Array.isArray(tick.mapCars) ? tick.mapCars : [];
    if (!carsEl || !pathPoints) return;
    carsEl.innerHTML = cars
      .map(function (c) {
        const xy = pointOn(pathPoints, c.distPct);
        const cls = c.isFocus ? "tm-car is-focus" : "tm-car";
        return (
          '<circle class="' +
          cls +
          '" cx="' +
          xy[0].toFixed(2) +
          '" cy="' +
          xy[1].toFixed(2) +
          '" r="' +
          (c.isFocus ? 2.4 : 1.6) +
          '"></circle>'
        );
      })
      .join("");
  }

  function connect() {
    try {
      socket = new WebSocket(url);
    } catch (_) {
      window.setTimeout(connect, retryMs);
      return;
    }
    socket.addEventListener("open", function () {
      retryMs = 1000;
      root.dataset.state = "live";
    });
    socket.addEventListener("message", function (ev) {
      let msg;
      try {
        msg = JSON.parse(ev.data);
      } catch (_) {
        return;
      }
      if (msg && msg.type === "telemetry.tick") render(msg);
    });
    socket.addEventListener("close", function () {
      root.dataset.state = "reconnecting";
      window.setTimeout(connect, retryMs);
      retryMs = Math.min(retryMs * 1.5, 8000);
    });
  }

  pathPoints = genericOval(48);
  if (pathEl) pathEl.setAttribute("d", toPath(pathPoints));
  connect();
})();
