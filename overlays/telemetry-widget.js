/**
 * Telemetry widget stub (P3-01) — connects only when telemetryEnabled is true.
 * Consumes adapters/telemetry CONTRACT.md (WebSocket). Real UI lands in P3-02.
 */
(function initTelemetryWidget() {
  const cfg = window.PIGRECO_CONFIG || {};
  const mount = document.querySelector("[data-telemetry-widget]");

  if (cfg.telemetryEnabled !== true) {
    if (mount) {
      mount.hidden = true;
      mount.setAttribute("aria-hidden", "true");
    }
    return;
  }

  if (!mount) return;

  mount.hidden = false;
  mount.setAttribute("aria-hidden", "false");
  mount.dataset.state = "connecting";

  const url = cfg.telemetryWsUrl || "ws://127.0.0.1:8765";
  let socket = null;
  let retryMs = 1000;
  let closedByDisable = false;
  let lastTick = null;

  function renderStub() {
    const pos = lastTick && lastTick.position != null ? String(lastTick.position) : "—";
    const of =
      lastTick && lastTick.positionOf != null ? "/" + String(lastTick.positionOf) : "";
    const gap =
      lastTick && lastTick.gapAheadMs != null
        ? (lastTick.gapAheadMs / 1000).toFixed(2) + "s"
        : "—";
    mount.textContent = "P" + pos + of + "  +" + gap;
  }

  function scheduleReconnect() {
    if (closedByDisable) return;
    window.setTimeout(connect, retryMs);
    retryMs = Math.min(retryMs * 1.5, 8000);
  }

  function connect() {
    if (closedByDisable) return;
    if (typeof WebSocket === "undefined") {
      mount.dataset.state = "unsupported";
      return;
    }
    try {
      socket = new WebSocket(url);
    } catch (err) {
      mount.dataset.state = "error";
      scheduleReconnect();
      return;
    }

    socket.addEventListener("open", function () {
      retryMs = 1000;
      mount.dataset.state = "live";
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
        lastTick = msg;
        renderStub();
      } else if (msg.type === "telemetry.status" && msg.connected === false) {
        mount.dataset.state = "idle";
      }
    });

    socket.addEventListener("close", function () {
      mount.dataset.state = "reconnecting";
      scheduleReconnect();
    });

    socket.addEventListener("error", function () {
      try {
        socket.close();
      } catch (_) {
        /* ignore */
      }
    });
  }

  renderStub();
  connect();
})();
