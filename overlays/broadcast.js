/**
 * Broadcast telecronaca UI (P3-02).
 * Consumes adapters/telemetry CONTRACT.md via WebSocket.
 * Mount: [data-broadcast-root]
 */
(function initBroadcastChrome() {
  const cfg = window.PIGRECO_CONFIG || {};
  const root = document.querySelector("[data-broadcast-root]");
  if (!root) return;

  if (cfg.telemetryEnabled !== true) {
    root.hidden = true;
    root.setAttribute("aria-hidden", "true");
    return;
  }

  root.hidden = false;
  root.setAttribute("aria-hidden", "false");
  root.dataset.state = "connecting";

  if (cfg.broadcastLeaderboard === false) root.classList.add("no-leaderboard");
  if (cfg.broadcastRelative === false) root.classList.add("no-relative");
  if (cfg.broadcastFocus === false) root.classList.add("no-focus");
  if (cfg.broadcastSession === false) root.classList.add("no-session");

  const maxLb = Math.max(5, Math.min(20, Number(cfg.broadcastLeaderboardRows) || 10));
  const url = cfg.telemetryWsUrl || "ws://127.0.0.1:8765";
  let socket = null;
  let retryMs = 1000;
  let lastFlag = "";

  const elSession = root.querySelector("[data-bc-session]");
  const elLb = root.querySelector("[data-bc-lb-rows]");
  const elRel = root.querySelector("[data-bc-rel-rows]");
  const elFocus = root.querySelector("[data-bc-focus]");
  const elBanner = root.querySelector("[data-bc-flag-banner]");
  const elStatus = root.querySelector("[data-bc-status]");

  function setStatus(text) {
    if (elStatus) elStatus.textContent = text;
  }

  setStatus("CONNECTING " + url);

  function fmtMs(ms) {
    if (ms == null || !Number.isFinite(Number(ms))) return "—";
    const n = Number(ms);
    const sign = n < 0 ? "-" : n > 0 ? "+" : "";
    const abs = Math.abs(n) / 1000;
    if (abs >= 60) {
      const m = Math.floor(abs / 60);
      const s = (abs % 60).toFixed(1);
      return sign + m + ":" + (abs % 60 < 10 ? "0" : "") + s;
    }
    return sign + abs.toFixed(2) + "s";
  }

  function fmtLap(ms) {
    if (ms == null || !Number.isFinite(Number(ms))) return "—";
    const t = Number(ms) / 1000;
    const m = Math.floor(t / 60);
    const s = t - m * 60;
    return m + ":" + (s < 10 ? "0" : "") + s.toFixed(3);
  }

  function render(tick) {
    if (!tick) return;

    const flag = (tick.flag || "none").toLowerCase();
    if (elSession) {
      elSession.dataset.flag = flag;
      const track = tick.trackName || "";
      const lap =
        tick.lap != null
          ? "LAP " + tick.lap + (tick.lapsTotal != null ? "/" + tick.lapsTotal : "")
          : "";
      const remain =
        tick.sessionLapsRemain != null ? tick.sessionLapsRemain + " TO GO" : "";
      const replay = tick.isReplay ? '<span class="bc-replay-tag">REPLAY</span>' : "";
      elSession.innerHTML =
        '<span class="bc-flag-dot" aria-hidden="true"></span>' +
        replay +
        "<span>" +
        (track || "SESSION") +
        "</span>" +
        (lap ? "<span>" + lap + "</span>" : "") +
        (remain ? "<span>" + remain + "</span>" : "") +
        "<span>" +
        String(flag).toUpperCase() +
        "</span>";
    }

    if (elBanner) {
      const show = flag && flag !== "none" && flag !== "green";
      elBanner.classList.toggle("is-on", show);
      elBanner.dataset.flag = show ? flag : "";
      if (show && flag !== lastFlag) {
        lastFlag = flag;
      }
      if (!show) lastFlag = "";
    }

    const standings = Array.isArray(tick.standings) ? tick.standings : [];
    if (elLb) {
      const rows = standings.slice(0, maxLb);
      elLb.innerHTML = rows
        .map(function (r) {
          const gap =
            r.pos === 1 ? "LEADER" : fmtMs(r.gapMs != null ? r.gapMs : r.intervalMs);
          return (
            '<li class="bc-lb-row' +
            (r.isFocus ? " is-focus" : "") +
            '">' +
            '<span class="bc-lb-pos">' +
            (r.pos != null ? r.pos : "—") +
            "</span>" +
            '<span class="bc-lb-num">#' +
            (r.carNumber || "—") +
            "</span>" +
            '<span class="bc-lb-name">' +
            (r.name || "—") +
            "</span>" +
            '<span class="bc-lb-gap">' +
            gap +
            "</span>" +
            "</li>"
          );
        })
        .join("");
    }

    const relatives = Array.isArray(tick.relatives) ? tick.relatives : [];
    if (elRel) {
      elRel.innerHTML = relatives
        .map(function (r) {
          const label =
            r.rel === 0 ? "YOU" : r.rel < 0 ? "P" + (r.rel) : "+" + r.rel;
          return (
            '<div class="bc-rel-row' +
            (r.rel === 0 ? " is-focus" : "") +
            '">' +
            "<span>" +
            label +
            "</span>" +
            "<span>#" +
            (r.carNumber || "") +
            " " +
            (r.name || "") +
            "</span>" +
            "<span>" +
            (r.rel === 0 ? "—" : fmtMs(r.gapMs)) +
            "</span>" +
            "</div>"
          );
        })
        .join("");
    }

    if (elFocus) {
      const pos = tick.position != null ? "P" + tick.position : "P—";
      const of = tick.positionOf != null ? "/" + tick.positionOf : "";
      const name = tick.focusDriverName || cfg.pilotName || "—";
      const num = tick.focusCarNumber || cfg.raceNumber || "";
      elFocus.innerHTML =
        '<div class="bc-focus-pos">' +
        pos +
        of +
        "</div>" +
        '<div class="bc-focus-name">#' +
        num +
        " " +
        name +
        "</div>" +
        '<div class="bc-focus-meta">' +
        "<span>LAST <strong>" +
        fmtLap(tick.lastLapMs) +
        "</strong></span>" +
        "<span>BEST <strong>" +
        fmtLap(tick.bestLapMs) +
        "</strong></span>" +
        "<span>GAP <strong>" +
        fmtMs(tick.gapAheadMs) +
        "</strong></span>" +
        "</div>";
    }
  }

  function scheduleReconnect() {
    window.setTimeout(connect, retryMs);
    retryMs = Math.min(retryMs * 1.5, 8000);
  }

  function connect() {
    if (typeof WebSocket === "undefined") {
      root.dataset.state = "unsupported";
      setStatus("WEBSOCKET UNSUPPORTED");
      return;
    }
    try {
      setStatus("CONNECTING " + url);
      socket = new WebSocket(url);
    } catch (_) {
      root.dataset.state = "error";
      setStatus("WS ERROR");
      scheduleReconnect();
      return;
    }

    socket.addEventListener("open", function () {
      retryMs = 1000;
      root.dataset.state = "live";
      setStatus("LIVE");
    });

    socket.addEventListener("message", function (ev) {
      let msg;
      try {
        msg = JSON.parse(ev.data);
      } catch (_) {
        return;
      }
      if (!msg || typeof msg !== "object") return;
      if (msg.type === "telemetry.tick") {
        root.dataset.state = "live";
        setStatus("LIVE");
        render(msg);
      } else if (msg.type === "telemetry.status" && msg.connected === false) {
        root.dataset.state = "idle";
        setStatus("SIM DISCONNECTED");
      }
    });

    socket.addEventListener("close", function () {
      root.dataset.state = "reconnecting";
      setStatus("RECONNECTING…");
      scheduleReconnect();
    });

    socket.addEventListener("error", function () {
      setStatus("WS ERROR — use http:// URL not file://");
      try {
        socket.close();
      } catch (_) {
        /* ignore */
      }
    });
  }

  connect();
})();
