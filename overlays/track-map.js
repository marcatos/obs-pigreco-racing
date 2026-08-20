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
  const sectorsEl = root.querySelector("[data-tm-sectors]");
  const svgEl = root.querySelector(".tm-svg");

  let socket = null;
  let retryMs = 1000;
  let loadedTrackId = null;
  let pathEl = null;
  let meta = { offset: 0, direction: 1 };
  let loadGen = 0;
  let markerR = 28;
  let prevTs = 0;
  let rafId = 0;
  let lastRafTs = 0;
  let lastSectorKey = "";
  const prevDist = Object.create(null);
  /** @type {Record<string, {target:number, display:number, carNumber:string, isFocus:boolean, el:SVGGElement|null}>} */
  const carState = Object.create(null);
  const LERP_PER_SEC = 14;

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
      markerR = 28;
      return;
    }
    const vb = svgEl.viewBox.baseVal;
    const m = Math.min(vb.width || 1000, vb.height || 1000);
    markerR = Math.max(24, Math.min(56, m * 0.052));
  }

  async function loadTrack(trackId) {
    const id = String(trackId || "").trim() || "unknown";
    if (id === loadedTrackId && pathEl) return true;
    const gen = ++loadGen;
    loadedTrackId = id;
    pathEl = null;
    meta = { offset: 0, direction: 1 };
    if (hostEl) hostEl.innerHTML = "";
    clearCars();
    lastSectorKey = "";
    if (sectorsEl) sectorsEl.innerHTML = "";

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

  function wrap01(t) {
    t = t % 1;
    if (t < 0) t += 1;
    return t;
  }

  function ensureCarEl(idx, c) {
    let st = carState[idx];
    if (!st) {
      st = {
        target: 0,
        display: 0,
        carNumber: "?",
        isFocus: false,
        el: null,
      };
      carState[idx] = st;
    }
    const num =
      c.carNumber != null && c.carNumber !== "" ? String(c.carNumber) : "?";
    const focus = !!c.isFocus;
    if (!st.el && carsEl) {
      const g = document.createElementNS("http://www.w3.org/2000/svg", "g");
      g.setAttribute("class", focus ? "tm-car is-focus" : "tm-car");
      const circle = document.createElementNS("http://www.w3.org/2000/svg", "circle");
      circle.setAttribute("class", "tm-car-dot");
      circle.setAttribute("cx", "0");
      circle.setAttribute("cy", "0");
      const text = document.createElementNS("http://www.w3.org/2000/svg", "text");
      text.setAttribute("class", "tm-car-num");
      text.setAttribute("x", "0");
      text.setAttribute("y", "0");
      text.textContent = num;
      g.appendChild(circle);
      g.appendChild(text);
      carsEl.appendChild(g);
      st.el = g;
    }
    if (st.el && (st.carNumber !== num || st.isFocus !== focus)) {
      st.el.setAttribute("class", focus ? "tm-car is-focus" : "tm-car");
      const text = st.el.querySelector(".tm-car-num");
      if (text) text.textContent = num;
      if (focus && carsEl) carsEl.appendChild(st.el);
    }
    st.carNumber = num;
    st.isFocus = focus;
    return st;
  }

  function paintCar(st, total) {
    if (!st.el || !pathEl || !(total > 0)) return;
    const t = applyDistOffset(st.display + lead, meta.offset, meta.direction);
    const pt = pathEl.getPointAtLength(wrap01(t) * total);
    st.el.setAttribute(
      "transform",
      "translate(" + pt.x.toFixed(2) + " " + pt.y.toFixed(2) + ")"
    );
    const r = st.isFocus ? markerR * 1.22 : markerR;
    const circle = st.el.querySelector(".tm-car-dot");
    const text = st.el.querySelector(".tm-car-num");
    if (circle) circle.setAttribute("r", r.toFixed(2));
    if (text) text.setAttribute("font-size", (r * 1.05).toFixed(2));
  }

  function tickCars(nowMs) {
    if (!pathEl || !carsEl) return;
    let total = 0;
    try {
      total = pathEl.getTotalLength();
    } catch (_) {
      return;
    }
    if (!(total > 0)) return;
    const dt =
      lastRafTs > 0
        ? Math.max(0.001, Math.min(0.05, (nowMs - lastRafTs) / 1000))
        : 0.016;
    lastRafTs = nowMs;
    const alpha = 1 - Math.exp(-LERP_PER_SEC * dt);
    Object.keys(carState).forEach(function (idx) {
      const st = carState[idx];
      const delta = wrapDelta(st.target, st.display);
      st.display = wrap01(st.display + delta * alpha);
      paintCar(st, total);
    });
  }

  function startRaf() {
    if (rafId) return;
    function loop(now) {
      rafId = window.requestAnimationFrame(loop);
      tickCars(now);
    }
    rafId = window.requestAnimationFrame(loop);
  }

  function clearCars() {
    Object.keys(carState).forEach(function (k) {
      const st = carState[k];
      if (st.el && st.el.parentNode) st.el.parentNode.removeChild(st.el);
      delete carState[k];
    });
    if (carsEl) carsEl.innerHTML = "";
  }

  function paintSectors(tick) {
    if (!sectorsEl || !pathEl) return;
    const list = Array.isArray(tick.sectors) ? tick.sectors : [];
    const cur = tick.sector != null ? Number(tick.sector) : null;
    const key =
      list
        .map(function (s) {
          return String(s.num) + ":" + String(s.startPct);
        })
        .join("|") +
      "#" +
      String(cur || "");
    if (key === lastSectorKey && sectorsEl.childNodes.length) {
      Array.prototype.forEach.call(sectorsEl.querySelectorAll(".tm-sector"), function (el) {
        const n = Number(el.getAttribute("data-num"));
        el.classList.toggle("is-active", cur != null && n === cur);
      });
      return;
    }
    lastSectorKey = key;
    sectorsEl.innerHTML = "";
    if (!list.length) return;
    let total = 0;
    try {
      total = pathEl.getTotalLength();
    } catch (_) {
      return;
    }
    if (!(total > 0)) return;
    list.forEach(function (s) {
      const pct = Number(s.startPct);
      if (!Number.isFinite(pct)) return;
      const t = applyDistOffset(pct + lead, meta.offset, meta.direction);
      const pt = pathEl.getPointAtLength(wrap01(t) * total);
      const num = s.num != null ? Number(s.num) : 0;
      const g = document.createElementNS("http://www.w3.org/2000/svg", "g");
      g.setAttribute(
        "class",
        cur != null && num === cur ? "tm-sector is-active" : "tm-sector"
      );
      g.setAttribute("data-num", String(num));
      g.setAttribute("transform", "translate(" + pt.x.toFixed(2) + " " + pt.y.toFixed(2) + ")");
      const tickMark = document.createElementNS("http://www.w3.org/2000/svg", "circle");
      tickMark.setAttribute("class", "tm-sector-dot");
      tickMark.setAttribute("r", Math.max(4, markerR * 0.28).toFixed(2));
      const label = document.createElementNS("http://www.w3.org/2000/svg", "text");
      label.setAttribute("class", "tm-sector-label");
      label.setAttribute("y", (-markerR * 0.85).toFixed(2));
      label.textContent = "S" + num;
      g.appendChild(tickMark);
      g.appendChild(label);
      sectorsEl.appendChild(g);
    });
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
      updateMarkerScale();
      paintSectors(tick);
      const seen = Object.create(null);
      const nextPrev = Object.create(null);
      cars.forEach(function (c, i) {
        const idx = c.carIdx != null ? String(c.carIdx) : "i" + i;
        seen[idx] = true;
        let dist = Number(c.distPct);
        if (!Number.isFinite(dist)) dist = 0;
        if (prevDist[idx] != null && dtSec > 0 && predict > 0) {
          const rate = wrapDelta(dist, prevDist[idx]) / dtSec;
          dist += rate * predict;
        }
        nextPrev[idx] = Number(c.distPct);
        const isNew = !carState[idx];
        const st = ensureCarEl(idx, c);
        st.target = wrap01(dist);
        if (isNew) st.display = st.target;
      });
      Object.keys(carState).forEach(function (idx) {
        if (!seen[idx]) {
          const st = carState[idx];
          if (st.el && st.el.parentNode) st.el.parentNode.removeChild(st.el);
          delete carState[idx];
        }
      });
      Object.keys(prevDist).forEach(function (k) {
        delete prevDist[k];
      });
      Object.keys(nextPrev).forEach(function (k) {
        prevDist[k] = nextPrev[k];
      });
      prevTs = ts;
      startRaf();
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

  function showcaseTickUrl() {
    const path = String(window.location.pathname || "").replace(/\\/g, "/");
    if (path.indexOf("overlays-marcato") !== -1) {
      return new URL("../overlays/showcase-telemetry-tick.json", window.location.href).href;
    }
    return new URL("showcase-telemetry-tick.json", window.location.href).href;
  }

  function loadShowcaseFixture() {
    const params = new URLSearchParams(window.location.search || "");
    if (params.get("showcase") !== "1") return false;
    setHint("TRACK · SHOWCASE", "connecting");
    fetch(showcaseTickUrl())
      .then(function (r) {
        if (!r.ok) throw new Error("HTTP " + r.status);
        return r.json();
      })
      .then(function (msg) {
        if (!msg || msg.type !== "telemetry.tick") throw new Error("bad fixture");
        setHint("TRACK", "live");
        render(msg);
      })
      .catch(function () {
        setHint("TRACK · SHOWCASE FAIL", "error");
      });
    return true;
  }

  setHint("", "ready");
  if (!loadShowcaseFixture()) {
    connect();
  }
})();
