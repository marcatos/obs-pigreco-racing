/**
 * YouTube like / subscribe / bell promo panel.
 * Cycle: enter → like → subscribe → bell → hold → exit → idle.
 * Lap triggers (telemetry WS): end of lap 1, end of final lap / checkered.
 */
(function () {
  const cfg = window.PIGRECO_CONFIG || {};
  const enabled = cfg.youtubePromoEnabled !== false;
  const firstDelayMs = Math.max(
    5000,
    Math.min(300000, Number(cfg.youtubePromoFirstDelayMs) || 90000)
  );
  const idleMs = Math.max(
    30000,
    Math.min(600000, Number(cfg.youtubePromoIdleMs) || 180000)
  );
  const holdMs = Math.max(1200, Math.min(8000, Number(cfg.youtubePromoHoldMs) || 2200));
  const lapTriggers = cfg.youtubePromoLapTriggers !== false;
  const wsUrl = String(cfg.telemetryWsUrl || cfg.youtubePromoWsUrl || "ws://127.0.0.1:8765").trim();
  const forceCooldownMs = Math.max(
    8000,
    Math.min(120000, Number(cfg.youtubePromoForceCooldownMs) || 20000)
  );

  const t0 = typeof performance !== "undefined" && performance.now ? performance.now() : Date.now();

  function log(level, msg, extra) {
    const line = "[youtube-promo] " + msg;
    if (level === "ERROR") console.error(line, extra != null ? extra : "");
    else if (level === "WARN") console.warn(line, extra != null ? extra : "");
    else if (level === "DEBUG") console.debug(line, extra != null ? extra : "");
    else console.info(line, extra != null ? extra : "");
  }

  function elapsedMs() {
    const now = typeof performance !== "undefined" && performance.now ? performance.now() : Date.now();
    return Math.round(now - t0);
  }

  if (!enabled) {
    log("INFO", "disabled via config");
    return;
  }

  const PROMO_HTML =
    '<div class="yt-promo-card">' +
    '<div class="yt-promo-head">' +
    '<div class="yt-promo-mark" aria-hidden="true">' +
    '<svg viewBox="0 0 24 24" focusable="false"><path fill="currentColor" d="M23.5 6.2a3 3 0 0 0-2.1-2.1C19.5 3.5 12 3.5 12 3.5s-7.5 0-9.4.6A3 3 0 0 0 .5 6.2 31.5 31.5 0 0 0 0 12a31.5 31.5 0 0 0 .5 5.8 3 3 0 0 0 2.1 2.1c1.9.6 9.4.6 9.4.6s7.5 0 9.4-.6a3 3 0 0 0 2.1-2.1A31.5 31.5 0 0 0 24 12a31.5 31.5 0 0 0-.5-5.8zM9.8 15.5v-7l6.3 3.5-6.3 3.5z"/></svg>' +
    "</div>" +
    '<div class="yt-promo-copy">' +
    '<div class="yt-promo-kicker" data-yt-kicker>LIKE &amp; SUBSCRIBE</div>' +
    '<div class="yt-promo-handle" data-yt-handle></div>' +
    "</div></div>" +
    '<div class="yt-promo-actions" data-yt-actions>' +
    '<div class="yt-promo-btn is-like" data-yt-like aria-hidden="true">' +
    '<svg class="yt-like-outline" viewBox="0 0 24 24"><path d="M7 22H4a1 1 0 0 1-1-1v-9a1 1 0 0 1 1-1h3zm2-11.2 3.2-6.5A1.8 1.8 0 0 1 14.1 3a2.2 2.2 0 0 1 2.1 2.9L15.5 9H20a2 2 0 0 1 2 2.3l-1.1 7A2.5 2.5 0 0 1 18.4 21H9z" fill="none" stroke="currentColor" stroke-width="1.7"/></svg>' +
    '<svg class="yt-like-fill" viewBox="0 0 24 24"><path d="M7 22H4a1 1 0 0 1-1-1v-9a1 1 0 0 1 1-1h3zm2-11.2 3.2-6.5A1.8 1.8 0 0 1 14.1 3a2.2 2.2 0 0 1 2.1 2.9L15.5 9H20a2 2 0 0 1 2 2.3l-1.1 7A2.5 2.5 0 0 1 18.4 21H9z"/></svg>' +
    "</div>" +
    '<div class="yt-promo-btn is-sub" data-yt-sub aria-hidden="true"><span class="yt-sub-label" data-yt-sub-label>Subscribe</span></div>' +
    '<div class="yt-promo-btn is-bell" data-yt-bell aria-hidden="true">' +
    '<svg viewBox="0 0 24 24"><path d="M12 22a2.2 2.2 0 0 0 2.2-2.2h-4.4A2.2 2.2 0 0 0 12 22zm7-6.2V11a7 7 0 1 0-14 0v4.8L3 18v1h18v-1l-2-2.2z"/></svg>' +
    "</div>" +
    '<div class="yt-promo-cursor" data-yt-cursor aria-hidden="true">' +
    '<svg viewBox="0 0 24 24"><path fill="#fff" stroke="#111" stroke-width="1.2" d="M4 3.5 19 12l-7.2 1.6L9.2 21 4 3.5z"/></svg>' +
    "</div>" +
    '<div class="yt-promo-burst" data-yt-burst aria-hidden="true"></div>' +
    "</div></div>";

  let root = document.querySelector("[data-yt-promo]");
  if (!root) {
    const host = document.querySelector(".live-root") || document.querySelector(".stage");
    if (!host) {
      log("ERROR", "mount failed — no .live-root/.stage");
      return;
    }
    root = document.createElement("div");
    root.className = "yt-promo";
    root.setAttribute("data-yt-promo", "");
    root.setAttribute("hidden", "");
    root.setAttribute("aria-hidden", "true");
    host.appendChild(root);
  }
  if (!root.querySelector("[data-yt-actions]")) {
    root.innerHTML = PROMO_HTML;
  }

  let handle = String(cfg.youtubeHandle || cfg.socialHandle || cfg.twitchHandle || "").trim();
  if (handle && handle.charAt(0) !== "@") handle = "@" + handle.replace(/^@+/, "");
  if (!handle) handle = "@channel";

  const kicker = String(cfg.youtubePromoTitle || "LIKE & SUBSCRIBE").trim() || "LIKE & SUBSCRIBE";
  const kickerEl = root.querySelector("[data-yt-kicker]");
  const handleEl = root.querySelector("[data-yt-handle]");
  const likeBtn = root.querySelector("[data-yt-like]");
  const subBtn = root.querySelector("[data-yt-sub]");
  const subLabel = root.querySelector("[data-yt-sub-label]");
  const bellBtn = root.querySelector("[data-yt-bell]");
  const cursor = root.querySelector("[data-yt-cursor]");
  const burst = root.querySelector("[data-yt-burst]");
  const actions = root.querySelector("[data-yt-actions]");

  if (kickerEl) kickerEl.textContent = kicker;
  if (handleEl) handleEl.textContent = handle;

  let timer = null;
  let phase = "idle";
  let runToken = 0;
  let lastForceAt = 0;
  let prevLap = null;
  let prevFlag = "";
  let firedFirstLap = false;
  let firedLastLap = false;
  let sessionKey = "";
  let socket = null;
  let retryMs = 1000;

  function clearTimer() {
    if (timer != null) {
      window.clearTimeout(timer);
      timer = null;
    }
  }

  function after(ms, fn) {
    clearTimer();
    timer = window.setTimeout(function () {
      timer = null;
      fn();
    }, ms);
  }

  function resetVisual() {
    root.classList.remove("is-on", "is-exit", "is-liked", "is-subscribed", "is-ringing");
    if (subLabel) subLabel.textContent = "Subscribe";
    if (cursor) {
      cursor.classList.remove("is-click");
      cursor.style.transform = "translate3d(18px, 18px, 0)";
    }
    if (likeBtn) likeBtn.classList.remove("is-hit");
    if (subBtn) subBtn.classList.remove("is-hit");
    if (bellBtn) bellBtn.classList.remove("is-hit");
  }

  function moveCursorTo(el, done) {
    if (!cursor || !actions || !el) {
      if (done) done();
      return;
    }
    const a = actions.getBoundingClientRect();
    const b = el.getBoundingClientRect();
    const x = b.left - a.left + b.width * 0.55;
    const y = b.top - a.top + b.height * 0.65;
    cursor.style.transform = "translate3d(" + x.toFixed(1) + "px," + y.toFixed(1) + "px,0)";
    after(400, function () {
      if (done) done();
    });
  }

  function clickPulse(el, done) {
    if (cursor) {
      cursor.classList.remove("is-click");
      void cursor.offsetWidth;
      cursor.classList.add("is-click");
    }
    if (el) {
      el.classList.add("is-hit");
      after(160, function () {
        el.classList.remove("is-hit");
        if (done) done();
      });
    } else if (done) {
      done();
    }
  }

  function placeBurstOn(el) {
    if (!burst || !actions || !el) return;
    const a = actions.getBoundingClientRect();
    const b = el.getBoundingClientRect();
    burst.style.left = b.left - a.left + b.width / 2 - 5 + "px";
    burst.style.top = b.top - a.top + b.height / 2 - 5 + "px";
  }

  function scheduleIdle() {
    phase = "idle";
    log("INFO", "idle for " + idleMs + "ms (t+" + elapsedMs() + "ms)");
    after(idleMs, function () {
      startShow("schedule");
    });
  }

  function finishExit(token) {
    if (token !== runToken) return;
    root.hidden = true;
    root.setAttribute("hidden", "");
    root.setAttribute("aria-hidden", "true");
    resetVisual();
    scheduleIdle();
  }

  function runSequence(token, reason) {
    phase = "show";
    log("INFO", "sequence start reason=" + reason + " handle=" + handle + " (t+" + elapsedMs() + "ms)");

    after(520, function () {
      if (token !== runToken) return;
      moveCursorTo(likeBtn, function () {
        if (token !== runToken) return;
        clickPulse(likeBtn, function () {
          if (token !== runToken) return;
          placeBurstOn(likeBtn);
          root.classList.add("is-liked");
          log("DEBUG", "liked");
          after(700, function () {
            if (token !== runToken) return;
            moveCursorTo(subBtn, function () {
              if (token !== runToken) return;
              clickPulse(subBtn, function () {
                if (token !== runToken) return;
                root.classList.add("is-subscribed");
                if (subLabel) subLabel.textContent = "Subscribed";
                log("DEBUG", "subscribed");
                after(750, function () {
                  if (token !== runToken) return;
                  moveCursorTo(bellBtn, function () {
                    if (token !== runToken) return;
                    clickPulse(bellBtn, function () {
                      if (token !== runToken) return;
                      root.classList.add("is-ringing");
                      log("DEBUG", "bell");
                      after(holdMs, function () {
                        if (token !== runToken) return;
                        phase = "exit";
                        root.classList.remove("is-on");
                        root.classList.add("is-exit");
                        log("INFO", "exit");
                        after(450, function () {
                          finishExit(token);
                        });
                      });
                    });
                  });
                });
              });
            });
          });
        });
      });
    });
  }

  function startShow(reason) {
    reason = reason || "schedule";
    runToken += 1;
    const token = runToken;
    clearTimer();
    resetVisual();
    root.hidden = false;
    root.removeAttribute("hidden");
    root.setAttribute("aria-hidden", "false");
    void root.offsetWidth;
    root.classList.add("is-on");
    phase = "enter";
    runSequence(token, reason);
  }

  function forceShow(reason) {
    const now = Date.now();
    if (now - lastForceAt < forceCooldownMs && phase !== "idle") {
      log("DEBUG", "force ignored (cooldown) reason=" + reason);
      return;
    }
    lastForceAt = now;
    log("INFO", "force show reason=" + reason);
    startShow(reason);
  }

  function resetLapFlags(why) {
    firedFirstLap = false;
    firedLastLap = false;
    prevLap = null;
    prevFlag = "";
    log("DEBUG", "lap flags reset (" + why + ")");
  }

  function onTelemetryTick(tick) {
    if (!tick || tick.connected === false) return;
    const lap = tick.lap != null && Number.isFinite(Number(tick.lap)) ? Number(tick.lap) : null;
    const total =
      tick.lapsTotal != null && Number.isFinite(Number(tick.lapsTotal))
        ? Number(tick.lapsTotal)
        : null;
    const flag = String(tick.flag || "none").toLowerCase();
    const sk = String(tick.session || "") + "|" + String(tick.trackId || tick.trackName || "") + "|" + String(total);
    if (sk !== sessionKey) {
      sessionKey = sk;
      resetLapFlags("session");
    }

    if (prevLap != null && lap != null && lap > prevLap) {
      // Crossed start/finish: completed prevLap
      if (prevLap === 1 && !firedFirstLap) {
        firedFirstLap = true;
        forceShow("first_lap");
      }
      if (total != null && total > 0 && prevLap >= total && !firedLastLap) {
        firedLastLap = true;
        forceShow("last_lap");
      }
    }

    if (
      !firedLastLap &&
      (flag === "checkered" || flag === "white") &&
      prevFlag !== flag &&
      (total == null || (prevLap != null && prevLap >= Math.max(1, total - 1)))
    ) {
      firedLastLap = true;
      forceShow(flag === "checkered" ? "checkered" : "white_flag");
    }

    if (lap != null) prevLap = lap;
    prevFlag = flag;
  }

  function onTelemetryEvent(ev) {
    if (!ev || !ev.kind) return;
    if (ev.kind === "session_end" && !firedLastLap) {
      firedLastLap = true;
      forceShow("session_end");
    }
  }

  function connectTelemetry() {
    if (!lapTriggers || !wsUrl) return;
    try {
      if (socket) {
        try {
          socket.close();
        } catch (e) {
          /* ignore */
        }
      }
      socket = new WebSocket(wsUrl);
    } catch (err) {
      log("WARN", "ws connect failed", err);
      window.setTimeout(connectTelemetry, retryMs);
      retryMs = Math.min(15000, retryMs * 1.5);
      return;
    }
    socket.addEventListener("open", function () {
      retryMs = 1000;
      log("INFO", "telemetry ws open " + wsUrl);
    });
    socket.addEventListener("close", function () {
      log("WARN", "telemetry ws closed — retry");
      window.setTimeout(connectTelemetry, retryMs);
      retryMs = Math.min(15000, retryMs * 1.5);
    });
    socket.addEventListener("message", function (msg) {
      var data;
      try {
        data = JSON.parse(msg.data);
      } catch (e) {
        return;
      }
      if (!data || !data.type) return;
      if (data.type === "telemetry.tick") onTelemetryTick(data);
      else if (data.type === "telemetry.event") onTelemetryEvent(data);
    });
  }

  resetVisual();
  root.hidden = true;
  root.setAttribute("hidden", "");
  window.PigrecoYoutubePromo = { forceShow: forceShow };
  log(
    "INFO",
    "ready handle=" +
      handle +
      " firstDelayMs=" +
      firstDelayMs +
      " idleMs=" +
      idleMs +
      " lapTriggers=" +
      lapTriggers
  );
  after(firstDelayMs, function () {
    startShow("schedule");
  });
  connectTelemetry();
})();
