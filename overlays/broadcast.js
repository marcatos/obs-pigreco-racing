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
  const director = cfg.broadcastDirector || "auto"; // auto|manual|off
  const sensitivity = cfg.broadcastDirectorSensitivity || "normal";
  const Director = window.PigrecoBroadcastDirector;
  let socket = null;
  let retryMs = 1000;
  let lastFlag = "";
  let directorState = { hero: null, queue: [] };
  let heroGen = 0;
  let heroExitTimer = null;
  const t0 = (typeof performance !== "undefined" && performance.now) ? performance.now() : Date.now();

  const elSession = root.querySelector("[data-bc-session]");
  const elLb = root.querySelector("[data-bc-lb-rows]");
  const elRel = root.querySelector("[data-bc-rel-rows]");
  const elFocus = root.querySelector("[data-bc-focus]");
  const elBanner = root.querySelector("[data-bc-flag-banner]");
  const elStatus = root.querySelector("[data-bc-status]");
  const elMoment = root.querySelector("[data-bc-moment]");

  function setStatus(text) {
    if (elStatus) elStatus.textContent = text;
  }

  function directorLog(level, msg, extra) {
    var line = "[broadcast-director] " + msg;
    if (level === "ERROR") console.error(line, extra != null ? extra : "");
    else if (level === "WARN") console.warn(line, extra != null ? extra : "");
    else if (level === "DEBUG") console.debug(line, extra != null ? extra : "");
    else console.info(line, extra != null ? extra : "");
  }

  directorLog("INFO", "start mode=" + director + " sensitivity=" + sensitivity);
  if (!Director) {
    directorLog("ERROR", "PigrecoBroadcastDirector missing — moment layer disabled");
  }

  setStatus("CONNECTING " + url);

  function applyFlagBanner(flag) {
    if (!elBanner) return;
    var f = String(flag || "none").toLowerCase();
    var show = f && f !== "none" && f !== "green";
    elBanner.classList.toggle("is-on", show);
    elBanner.dataset.flag = show ? f : "";
    if (show) lastFlag = f;
    else lastFlag = "";
  }

  function clearMomentLayer() {
    if (heroExitTimer != null) {
      window.clearTimeout(heroExitTimer);
      heroExitTimer = null;
    }
    heroGen += 1;
    directorState = { hero: null, queue: [] };
    if (!elMoment) return;
    elMoment.hidden = true;
    elMoment.innerHTML = "";
    elMoment.classList.remove("is-enter", "is-exit");
    elMoment.dataset.kind = "";
  }

  function showHero(item) {
    if (!item) return;
    if (heroExitTimer != null) {
      window.clearTimeout(heroExitTimer);
      heroExitTimer = null;
      directorLog("DEBUG", "cancelled pending hero exit gen=" + heroGen);
    }
    heroGen += 1;
    item.until = Date.now() + item.ttlMs;
    directorState.hero = item;
    if (!elMoment) return;
    elMoment.hidden = false;
    elMoment.dataset.kind = item.kind;
    elMoment.classList.remove("is-exit");
    elMoment.classList.add("is-enter");
    var label = Director
      ? Director.formatMomentLabel(item)
      : String(item.kind).replace("_", " ").toUpperCase();
    elMoment.innerHTML = '<div class="bc-moment-chip"></div>';
    var chip = elMoment.querySelector(".bc-moment-chip");
    if (chip) chip.textContent = label;
  }

  function enqueueEvent(ev) {
    if (director !== "auto") return;
    if (!ev || !ev.kind) return;
    if (!Director) return;
    var prevHero = directorState.hero;
    directorState = Director.enqueueEvent(directorState, ev, director);
    directorLog("DEBUG", "event kind=" + ev.kind + " priority=" + (ev.priority || 0));
    if (ev.kind === "flag_change" || ev.kind === "session_end") {
      applyFlagBanner(ev.payload && ev.payload.flag);
    }
    if (directorState.hero && directorState.hero !== prevHero) {
      showHero(directorState.hero);
    }
  }

  function tickHero() {
    var hero = directorState.hero;
    if (!hero) return;
    if (Date.now() < hero.until) return;
    if (elMoment) {
      elMoment.classList.remove("is-enter");
      elMoment.classList.add("is-exit");
    }
    directorState.hero = null;
    var exitGen = heroGen;
    heroExitTimer = window.setTimeout(function () {
      heroExitTimer = null;
      if (exitGen !== heroGen) return;
      if (directorState.hero) return;
      if (directorState.queue.length) showHero(directorState.queue.shift());
      else if (elMoment) {
        elMoment.hidden = true;
        elMoment.innerHTML = "";
      }
    }, 200);
  }
  window.setInterval(tickHero, 100);

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

  function fmtRemainMs(ms) {
    if (ms == null || !Number.isFinite(Number(ms)) || Number(ms) < 0) return "";
    const total = Math.floor(Number(ms) / 1000);
    const h = Math.floor(total / 3600);
    const m = Math.floor((total % 3600) / 60);
    const s = total % 60;
    if (h > 0) {
      return h + ":" + String(m).padStart(2, "0") + ":" + String(s).padStart(2, "0");
    }
    return m + ":" + String(s).padStart(2, "0");
  }

  function render(tick) {
    if (!tick) return;

    const flag = (tick.flag || "none").toLowerCase();
    if (elSession) {
      elSession.dataset.flag = flag === "none" ? "green" : flag;
      const track = tick.trackName || "";
      const lap =
        tick.lap != null
          ? "LAP " + tick.lap + (tick.lapsTotal != null ? "/" + tick.lapsTotal : "")
          : "";
      // iRacing sentinel 32767 = unlimited / N/A — never show as "TO GO"
      const remainN = Number(tick.sessionLapsRemain);
      const remainOk =
        tick.sessionLapsRemain != null &&
        Number.isFinite(remainN) &&
        remainN >= 0 &&
        remainN < 32000;
      const remain = remainOk ? remainN + " TO GO" : "";
      const timeLeft =
        !remainOk && tick.sessionTimeRemainMs != null
          ? fmtRemainMs(tick.sessionTimeRemainMs)
          : "";
      const replay = tick.isReplay ? '<span class="bc-replay-tag">REPLAY</span>' : "";
      const flagLabel = flag === "none" ? "" : String(flag).toUpperCase();
      elSession.innerHTML =
        '<span class="bc-flag-dot" aria-hidden="true"></span>' +
        replay +
        "<span>" +
        (track || "SESSION") +
        "</span>" +
        (lap ? "<span>" + lap + "</span>" : "") +
        (remain ? "<span>" + remain + "</span>" : "") +
        (timeLeft ? "<span>" + timeLeft + "</span>" : "") +
        (flagLabel ? "<span>" + flagLabel + "</span>" : "");
    }

    // Auto + Director: latch banner from tick unless a flag/session_end hero
    // owns the event-driven banner (Browser Source refresh mid-yellow).
    if (elBanner) {
      var hero = directorState.hero;
      var flagHero =
        hero && (hero.kind === "flag_change" || hero.kind === "session_end");
      if (director !== "auto" || !Director || !flagHero) {
        applyFlagBanner(flag);
      }
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
            (r.posChange === 1
              ? '<span class="bc-pos-up" aria-label="gained">▲</span>'
              : r.posChange === -1
                ? '<span class="bc-pos-down" aria-label="lost">▼</span>'
                : "") +
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
          var tag = "CAM";
          var kind = "is-focus";
          if (r.rel < 0) {
            tag = "AHD";
            kind = "is-ahead";
          } else if (r.rel > 0) {
            tag = "BHD";
            kind = "is-behind";
          }
          var driver =
            "#" +
            (r.carNumber || "") +
            " " +
            (r.name || "");
          return (
            '<div class="bc-rel-row ' +
            kind +
            '">' +
            '<span class="bc-rel-tag">' +
            tag +
            "</span>" +
            '<span class="bc-rel-driver">' +
            driver.trim() +
            "</span>" +
            '<span class="bc-rel-gap">' +
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
        '<div class="bc-panel-head"><strong>FOCUS</strong><span>CAMERA</span></div>' +
        '<div class="bc-focus-body">' +
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
        (tick.deltaBestMs != null
          ? "<span>Δ BEST <strong class=\"" +
            (Number(tick.deltaBestMs) <= 0 ? "is-purple" : "is-slow") +
            "\">" +
            fmtMs(tick.deltaBestMs) +
            "</strong></span>"
          : "") +
        (tick.fuelPct != null
          ? "<span>FUEL <strong>" + Number(tick.fuelPct).toFixed(0) + "%</strong></span>"
          : "") +
        (tick.inPit
          ? "<span class=\"bc-pit-tag\">PIT</span>"
          : "") +
        "</div>" +
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
      var now = (typeof performance !== "undefined" && performance.now) ? performance.now() : Date.now();
      directorLog("INFO", "ws open in " + Math.round(now - t0) + " ms");
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
      } else if (msg.type === "telemetry.event") {
        enqueueEvent(msg);
      } else if (msg.type === "telemetry.status" && msg.connected === false) {
        root.dataset.state = "idle";
        setStatus("SIM DISCONNECTED");
        clearMomentLayer();
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
