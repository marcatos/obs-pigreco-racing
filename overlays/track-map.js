/**
 * Track minimap (P3-07): official iRacing SVG cache by TrackID.
 * Style: black ribbon + white edge, numbered car dots (no dark plate).
 * Mount: [data-track-map-root]
 */
(function initTrackMap() {
  const cfg = window.PIGRECO_CONFIG || {};
  const root = document.querySelector("[data-track-map-root]");
  if (!root) return;

  const enabled =
    cfg.trackMapEnabled === true ||
    cfg.trackMapEnabled === "true" ||
    cfg.trackMapEnabled === 1;
  if (!enabled) {
    root.hidden = true;
    root.setAttribute("aria-hidden", "true");
    return;
  }

  root.hidden = false;
  root.removeAttribute("hidden");
  root.setAttribute("aria-hidden", "false");

  const url = cfg.trackMapWsUrl || cfg.telemetryWsUrl || "ws://127.0.0.1:8765";
  // Advance dots along the lap (0–1). Replay/WS often trail the live camera.
  const leadPct = Number(cfg.trackMapLeadPct);
  const lead = Number.isFinite(leadPct) ? leadPct : 0.004;
  const predictSec = Number(cfg.trackMapPredictSec);
  const predict = Number.isFinite(predictSec) ? predictSec : 0;
  const labelEl = root.querySelector("[data-tm-label]");
  const hostEl = root.querySelector("[data-tm-track]");
  const carsEl = root.querySelector("[data-tm-cars]");
  const svgEl = root.querySelector(".tm-svg");

  let socket = null;
  let retryMs = 1000;
  let loadedTrackId = null;
  let pathEl = null;
  let meta = { offset: 0, direction: 1 };
  let loadGen = 0;
  let markerR = 18;
  let prevTs = 0;
  const prevDist = Object.create(null);

  function setHint(text, state) {
    if (labelEl) labelEl.textContent = text || "";
    if (state) root.dataset.state = state;
  }

  function applyDistOffset(distPct, offset, direction) {
    let t = Number(distPct) % 1;
    if (t < 0) t += 1;
    if (Number(direction) < 0) t = (1 - t) % 1;
    t = (t + Number(offset || 0)) % 1;
    if (t < 0) t += 1;
    return t;
  }

  function escapeXml(s) {
    return String(s)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;");
  }

  function candidateUrls(trackId) {
    const id = encodeURIComponent(trackId);
    return [
      "assets/tracks/iracing/" + id + ".svg",
      "../overlays/assets/tracks/iracing/" + id + ".svg",
    ];
  }

  function metaUrls(trackId) {
    const id = encodeURIComponent(trackId);
    return [
      "assets/tracks/iracing/" + id + ".meta.json",
      "../overlays/assets/tracks/iracing/" + id + ".meta.json",
    ];
  }

  async function fetchFirstOk(urls) {
    for (let i = 0; i < urls.length; i++) {
      try {
        const res = await fetch(urls[i], { cache: "no-store" });
        if (res.ok) return { res, url: urls[i] };
      } catch (_) {
        /* next */
      }
    }
    return null;
  }

  function pickPath(svgRoot) {
    const paths = svgRoot.querySelectorAll("path.tm-path, path");
    let best = null;
    let bestLen = 0;
    paths.forEach(function (p) {
      if (p.classList.contains("tm-path-outline")) return;
      try {
        const len = p.getTotalLength();
        if (len > bestLen) {
          bestLen = len;
          best = p;
        }
      } catch (_) {
        /* ignore */
      }
    });
    return best;
  }

  function styleTrackPaths(container) {
    const paths = Array.from(container.querySelectorAll("path"));
    paths.forEach(function (p) {
      p.removeAttribute("fill");
      p.removeAttribute("stroke");
      p.removeAttribute("stroke-width");
      const outline = p.cloneNode(true);
      outline.classList.add("tm-path-outline");
      outline.classList.remove("tm-path");
      p.classList.add("tm-path");
      if (p.parentNode) p.parentNode.insertBefore(outline, p);
    });
  }

  function updateMarkerScale() {
    if (!svgEl || !svgEl.viewBox || !svgEl.viewBox.baseVal) {
      markerR = 18;
      return;
    }
    const vb = svgEl.viewBox.baseVal;
    const m = Math.min(vb.width || 1000, vb.height || 1000);
    markerR = Math.max(14, Math.min(36, m * 0.03));
  }

  async function loadTrack(trackId) {
    const id = String(trackId || "").trim() || "unknown";
    if (id === loadedTrackId && pathEl) return true;
    const gen = ++loadGen;
    loadedTrackId = id;
    pathEl = null;
    meta = { offset: 0, direction: 1 };
    if (hostEl) hostEl.innerHTML = "";
    if (carsEl) carsEl.innerHTML = "";

    const metaHit = await fetchFirstOk(metaUrls(id));
    if (gen !== loadGen) return false;
    if (metaHit) {
      try {
        const m = await metaHit.res.json();
        meta = {
          offset: Number(m.offset) || 0,
          direction: Number(m.direction) === -1 ? -1 : 1,
        };
      } catch (_) {
        /* defaults */
      }
    }

    const hit = await fetchFirstOk(candidateUrls(id));
    if (gen !== loadGen) return false;
    if (!hit) {
      setHint("TRACK MAP — run Start-SyncTrackMaps", "missing");
      return false;
    }
    const text = await hit.res.text();
    if (gen !== loadGen) return false;
    const parsed = new DOMParser().parseFromString(text, "image/svg+xml");
    const srcSvg = parsed.documentElement;
    if (!srcSvg || srcSvg.nodeName.toLowerCase() !== "svg") {
      setHint("TRACK MAP — invalid SVG", "error");
      return false;
    }

    const vb = srcSvg.getAttribute("viewBox");
    if (vb && svgEl) svgEl.setAttribute("viewBox", vb);
    else if (svgEl) {
      const w = parseFloat(srcSvg.getAttribute("width")) || 100;
      const h = parseFloat(srcSvg.getAttribute("height")) || 100;
      svgEl.setAttribute("viewBox", "0 0 " + w + " " + h);
    }

    const frag = document.createDocumentFragment();
    Array.from(srcSvg.childNodes).forEach(function (n) {
      frag.appendChild(document.importNode(n, true));
    });
    if (hostEl) {
      hostEl.innerHTML = "";
      hostEl.appendChild(frag);
      styleTrackPaths(hostEl);
      pathEl = pickPath(hostEl);
    }
    updateMarkerScale();
    setHint("", "ready");
    return !!pathEl;
  }

  function wrapDelta(a, b) {
    let d = a - b;
    if (d < -0.5) d += 1;
    if (d > 0.5) d -= 1;
    return d;
  }

  function render(tick) {
    if (!tick) return;
    const tid = tick.trackId || tick.trackName || "unknown";
    const ts = typeof tick.ts === "number" ? tick.ts : Date.now();
    const dtSec =
      prevTs > 0 ? Math.max(0.02, Math.min(0.5, (ts - prevTs) / 1000)) : 0;
    loadTrack(tid).then(function (ok) {
      if (!ok || !pathEl || !carsEl) return;
      const cars = Array.isArray(tick.mapCars) ? tick.mapCars : [];
      let total = 0;
      try {
        total = pathEl.getTotalLength();
      } catch (_) {
        return;
      }
      if (!(total > 0)) return;
      updateMarkerScale();
      const ordered = cars.slice().sort(function (a, b) {
        return (a.isFocus ? 1 : 0) - (b.isFocus ? 1 : 0);
      });
      const nextPrev = Object.create(null);
      carsEl.innerHTML = ordered
        .map(function (c) {
          let dist = Number(c.distPct);
          if (!Number.isFinite(dist)) dist = 0;
          const idx = c.carIdx != null ? String(c.carIdx) : "";
          if (idx && prevDist[idx] != null && dtSec > 0 && predict > 0) {
            const rate = wrapDelta(dist, prevDist[idx]) / dtSec; // laps/sec
            dist += rate * predict;
          }
          if (idx) nextPrev[idx] = Number(c.distPct);
          const t = applyDistOffset(dist + lead, meta.offset, meta.direction);
          const pt = pathEl.getPointAtLength(t * total);
          const r = c.isFocus ? markerR * 1.15 : markerR;
          const num = escapeXml(c.carNumber != null && c.carNumber !== "" ? c.carNumber : "?");
          const cls = c.isFocus ? "tm-car is-focus" : "tm-car";
          const fs = (r * 1.05).toFixed(2);
          return (
            '<g class="' +
            cls +
            '" transform="translate(' +
            pt.x.toFixed(2) +
            " " +
            pt.y.toFixed(2) +
            ')">' +
            '<circle class="tm-car-dot" cx="0" cy="0" r="' +
            r.toFixed(2) +
            '"></circle>' +
            '<text class="tm-car-num" x="0" y="0" font-size="' +
            fs +
            '">' +
            num +
            "</text>" +
            "</g>"
          );
        })
        .join("");
      Object.keys(prevDist).forEach(function (k) {
        delete prevDist[k];
      });
      Object.keys(nextPrev).forEach(function (k) {
        prevDist[k] = nextPrev[k];
      });
      prevTs = ts;
    });
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
      setHint("TRACK MAP — reconnecting…", "reconnecting");
      window.setTimeout(connect, retryMs);
      retryMs = Math.min(retryMs * 1.5, 8000);
    });
  }

  setHint("", "ready");
  connect();
})();
