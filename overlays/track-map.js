/**
 * Track minimap (P3-07): official iRacing SVG cache by TrackID.
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

  function setHint(text) {
    if (labelEl) labelEl.textContent = text;
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
    const paths = svgRoot.querySelectorAll("path");
    let best = null;
    let bestLen = 0;
    paths.forEach(function (p) {
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
      setHint("TRACK MAP — run Start-SyncTrackMaps");
      root.dataset.state = "missing";
      return false;
    }
    const text = await hit.res.text();
    if (gen !== loadGen) return false;
    const parsed = new DOMParser().parseFromString(text, "image/svg+xml");
    const srcSvg = parsed.documentElement;
    if (!srcSvg || srcSvg.nodeName.toLowerCase() !== "svg") {
      setHint("TRACK MAP — invalid SVG");
      root.dataset.state = "error";
      return false;
    }

    const vb = srcSvg.getAttribute("viewBox");
    if (vb && svgEl) svgEl.setAttribute("viewBox", vb);
    else if (svgEl) {
      const w = parseFloat(srcSvg.getAttribute("width")) || 100;
      const h = parseFloat(srcSvg.getAttribute("height")) || 100;
      svgEl.setAttribute("viewBox", "0 0 " + w + " " + h);
    }

    // Import children into host (paths/groups)
    const frag = document.createDocumentFragment();
    Array.from(srcSvg.childNodes).forEach(function (n) {
      frag.appendChild(document.importNode(n, true));
    });
    if (hostEl) {
      hostEl.innerHTML = "";
      hostEl.appendChild(frag);
      hostEl.querySelectorAll("path").forEach(function (p) {
        p.classList.add("tm-path");
      });
      pathEl = pickPath(hostEl);
    }
    setHint("TRACK " + id);
    root.dataset.state = "ready";
    return !!pathEl;
  }

  function render(tick) {
    if (!tick) return;
    const tid = tick.trackId || tick.trackName || "unknown";
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
      carsEl.innerHTML = cars
        .map(function (c) {
          const t = applyDistOffset(c.distPct, meta.offset, meta.direction);
          const pt = pathEl.getPointAtLength(t * total);
          const cls = c.isFocus ? "tm-car is-focus" : "tm-car";
          return (
            '<circle class="' +
            cls +
            '" cx="' +
            pt.x.toFixed(2) +
            '" cy="' +
            pt.y.toFixed(2) +
            '" r="' +
            (c.isFocus ? 2.4 : 1.6) +
            '"></circle>'
          );
        })
        .join("");
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
      if (!loadedTrackId) setHint("TRACK MAP");
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

  setHint("TRACK MAP");
  connect();
})();
