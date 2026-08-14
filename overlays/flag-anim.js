/**
 * Transparent flag FX overlay — listens to telemetry WS and animates
 * yellow / red / checkered without covering center gameplay.
 */
(function () {
  "use strict";

  var root = document.querySelector("[data-flag-fx]");
  if (!root) return;

  var labelEl = root.querySelector("[data-flag-fx-label]");
  var subEl = root.querySelector("[data-flag-fx-sub]");
  var cfg = window.PIGRECO_CONFIG || {};
  var wsUrl = cfg.telemetryWsUrl || "ws://127.0.0.1:8765";
  var brand = (root.getAttribute("data-brand") || "PiGreco Racing").trim();
  var q = new URLSearchParams(location.search);
  var forceFlag = (q.get("flag") || "").toLowerCase();
  var lastFlag = "none";
  var enterTimer = null;

  var LABELS = {
    yellow: "YELLOW FLAG",
    red: "RED FLAG",
    checkered: "CHECKERED",
  };

  function setFlag(flag) {
    var f = (flag || "none").toLowerCase();
    if (f === "green") f = "none";
    if (f === lastFlag) return;
    lastFlag = f;

    if (enterTimer) {
      clearTimeout(enterTimer);
      enterTimer = null;
    }
    root.classList.remove("is-enter");

    if (f === "yellow" || f === "red" || f === "checkered") {
      root.setAttribute("data-flag", f);
      if (labelEl) labelEl.textContent = LABELS[f] || f.toUpperCase();
      if (subEl) subEl.textContent = brand;
      root.classList.add("is-on");
      // retrigger sweep
      void root.offsetWidth;
      root.classList.add("is-enter");
      enterTimer = setTimeout(function () {
        root.classList.remove("is-enter");
      }, 750);
    } else {
      root.classList.remove("is-on", "is-enter");
    }
  }

  function connect() {
    if (cfg.telemetryEnabled === false && !forceFlag) {
      return;
    }
    var ws;
    try {
      ws = new WebSocket(wsUrl);
    } catch (e) {
      setTimeout(connect, 2000);
      return;
    }
    ws.onmessage = function (ev) {
      var msg;
      try {
        msg = JSON.parse(ev.data);
      } catch (e) {
        return;
      }
      if (!msg || typeof msg !== "object") return;
      if (msg.type === "telemetry.tick" && msg.flag != null) {
        setFlag(String(msg.flag));
      } else if (
        msg.type === "telemetry.event" &&
        msg.kind === "flag_change" &&
        msg.payload
      ) {
        setFlag(String(msg.payload.flag || ""));
      }
    };
    ws.onclose = function () {
      setTimeout(connect, 2000);
    };
    ws.onerror = function () {
      try {
        ws.close();
      } catch (e) {}
    };
  }

  if (forceFlag && ["yellow", "red", "checkered"].indexOf(forceFlag) >= 0) {
    setFlag(forceFlag);
  }
  connect();
})();
