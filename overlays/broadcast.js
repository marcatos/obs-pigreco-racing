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
  if (cfg.broadcastTicker === false) root.classList.add("no-ticker");

  const maxLb = Math.max(5, Math.min(20, Number(cfg.broadcastLeaderboardRows) || 10));
  const url = cfg.telemetryWsUrl || "ws://127.0.0.1:8765";
  const director = cfg.broadcastDirector || "auto"; // auto|manual|off
  const sensitivity = cfg.broadcastDirectorSensitivity || "normal";
  // TV-style timing board: freeze standings/relative gaps for a few seconds
  const boardRefreshMs = Math.max(
    1500,
    Math.min(15000, Number(cfg.broadcastBoardRefreshMs) || 4000)
  );
  const tickerEnabled = cfg.broadcastTicker !== false;
  const tickerSpeed = Math.max(40, Math.min(200, Number(cfg.broadcastTickerSpeed) || 85));
  const tickerIdleMs = Math.max(
    5000,
    Math.min(120000, Number(cfg.broadcastTickerIdleMs) || 60000)
  );
  const tickerFirstDelayMs = Math.max(
    1000,
    Math.min(30000, Number(cfg.broadcastTickerFirstDelayMs) || 4000)
  );
  const pilotMarkUrl = String(cfg.broadcastPilotMarkUrl || "").trim();
  const pilotNameCfg = String(cfg.pilotName || "").trim();
  const Director = window.PigrecoBroadcastDirector;
  let socket = null;
  let retryMs = 1000;
  let lastFlag = "";
  let lastFocusPos = null;
  let focusFlashTimer = null;
  let directorState = { hero: null, queue: [] };
  let heroGen = 0;
  let heroExitTimer = null;
  let lastBoardAt = 0;
  let latchedGapByKey = Object.create(null);
  let latchedRelatives = null;
  let lastBoardFocusIdx = null;
  const lbRowsByKey = Object.create(null);
  let lbOrderKeys = [];
  let lbAnimToken = 0;
  let lbAnimating = false;
  let lbPendingRows = null;
  const LB_SWAP_MS = 440;
  const t0 = (typeof performance !== "undefined" && performance.now) ? performance.now() : Date.now();

  const elSession = root.querySelector("[data-bc-session]");
  const elLb = root.querySelector("[data-bc-lb-rows]");
  const elRel = root.querySelector("[data-bc-rel-rows]");
  const elFocus = root.querySelector("[data-bc-focus]");
  const elBanner = root.querySelector("[data-bc-flag-banner]");
  const elStatus = root.querySelector("[data-bc-status]");
  const elMoment = root.querySelector("[data-bc-moment]");
  const elTicker = root.querySelector("[data-bc-ticker]");
  const elTickerTrack = root.querySelector("[data-bc-ticker-track]");
  const elTickerViewport = root.querySelector(".bc-ticker-viewport");
  let tickerRowsCache = null;
  let tickerPhase = "idle"; // idle | rise | expand | show | collapse | drop
  let tickerTimer = null;
  let tickerStarted = false;
  let tickerAnim = null;
  const TICKER_RISE_MS = 440;
  const TICKER_EXPAND_MS = 500;
  const TICKER_COLLAPSE_MS = 500;
  const TICKER_DROP_MS = 420;
  const TICKER_HOLD_MS = 3200; // if whole field fits, hold then exit

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

  function boardCarKey(r) {
    if (r && r.carIdx != null) return "i" + r.carIdx;
    if (r && r.carNumber != null && r.carNumber !== "") return "n" + r.carNumber;
    return null;
  }

  function paintPosChange(slot, delta) {
    if (!slot) return;
    slot.className = "bc-lb-delta";
    slot.removeAttribute("aria-label");
    if (delta == null || !Number.isFinite(Number(delta)) || Number(delta) === 0) {
      slot.textContent = "";
      slot.setAttribute("aria-hidden", "true");
      return;
    }
    slot.removeAttribute("aria-hidden");
    var n = Math.trunc(Number(delta));
    if (n > 0) {
      slot.classList.add("bc-pos-up");
      slot.setAttribute("aria-label", "gained " + n);
      slot.textContent = "▲" + n;
    } else {
      slot.classList.add("bc-pos-down");
      slot.setAttribute("aria-label", "lost " + Math.abs(n));
      slot.textContent = "▼" + Math.abs(n);
    }
  }

  function latchGapsIfDue(standings, relatives, force) {
    const now = Date.now();
    const due = force || lastBoardAt === 0 || now - lastBoardAt >= boardRefreshMs;
    if (!due) {
      return { relatives: latchedRelatives || relatives, gapsRefreshed: false };
    }
    const nextGaps = Object.create(null);
    standings.forEach(function (r) {
      const key = boardCarKey(r);
      if (!key) return;
      nextGaps[key] = {
        gapMs: r.gapMs,
        intervalMs: r.intervalMs,
      };
    });
    latchedGapByKey = nextGaps;
    latchedRelatives = relatives.map(function (r) {
      return Object.assign({}, r);
    });
    lastBoardAt = now;
    return { relatives: latchedRelatives, gapsRefreshed: true };
  }

  function withLatchedGaps(standings) {
    return standings.map(function (r) {
      const row = Object.assign({}, r);
      const key = boardCarKey(r);
      const latched = key ? latchedGapByKey[key] : null;
      if (latched) {
        row.gapMs = latched.gapMs;
        row.intervalMs = latched.intervalMs;
      }
      // posChange / startPos come from tick (vs starting grid)
      return row;
    });
  }

  function fmtStandingGap(r) {
    if (r.pos === 1) {
      if (r.gapMs == null) return "POLE";
      return "LEADER";
    }
    if (r.gapMs == null && r.intervalMs == null) return "—";
    return fmtMs(r.gapMs != null ? r.gapMs : r.intervalMs);
  }

  /** Normalize for pilot match: "S.Marcato" / "Simone Marcato" → comparable tokens. */
  function normalizeDriverName(s) {
    return String(s || "")
      .toLowerCase()
      .normalize("NFD")
      .replace(/[\u0300-\u036f]/g, "")
      .replace(/[^a-z0-9]+/g, " ")
      .trim()
      .replace(/\s+/g, " ");
  }

  function namesMatchPilot(rowName, cfgName) {
    var a = normalizeDriverName(rowName);
    var b = normalizeDriverName(cfgName);
    if (!a || !b) return false;
    if (a === b) return true;
    var at = a.split(" ");
    var bt = b.split(" ");
    if (at.length < 2 || bt.length < 2) return false;
    var aLast = at[at.length - 1];
    var bLast = bt[bt.length - 1];
    if (aLast !== bLast) return false;
    var aFirst = at[0];
    var bFirst = bt[0];
    if (aFirst === bFirst) return true;
    if (aFirst.length === 1 && bFirst.indexOf(aFirst) === 0) return true;
    if (bFirst.length === 1 && aFirst.indexOf(bFirst) === 0) return true;
    return false;
  }

  function rowIsPilot(r) {
    if (!pilotMarkUrl) return false;
    if (pilotNameCfg && namesMatchPilot(r.name, pilotNameCfg)) return true;
    // No pilotName in config: mark the focused car only
    return !pilotNameCfg && !!r.isFocus;
  }

  function fillLbRow(el, r) {
    el.classList.toggle("is-focus", !!r.isFocus);
    var posN = el.querySelector(".bc-lb-pos-n");
    var deltaHost = el.querySelector(".bc-lb-delta");
    var num = el.querySelector(".bc-lb-num");
    var mark = el.querySelector(".bc-lb-mark");
    var nameText = el.querySelector(".bc-lb-name-text");
    var gap = el.querySelector(".bc-lb-gap");
    if (posN) posN.textContent = r.pos != null ? String(r.pos) : "—";
    paintPosChange(deltaHost, r.posChange);
    if (num) num.textContent = "#" + (r.carNumber || "—");
    if (nameText) nameText.textContent = r.name || "—";
    if (mark) {
      var isPilot = rowIsPilot(r);
      if (isPilot) {
        if (mark.getAttribute("src") !== pilotMarkUrl) mark.setAttribute("src", pilotMarkUrl);
        mark.hidden = false;
        mark.removeAttribute("hidden");
        el.classList.add("has-pilot-mark");
      } else {
        mark.hidden = true;
        mark.setAttribute("hidden", "");
        mark.removeAttribute("src");
        el.classList.remove("has-pilot-mark");
      }
    }
    if (gap) gap.textContent = fmtStandingGap(r);
  }

  function ensureLbRow(key, r) {
    var el = lbRowsByKey[key];
    if (!el) {
      el = document.createElement("li");
      el.className = "bc-lb-row";
      el.dataset.lbKey = key;
      el.innerHTML =
        '<span class="bc-lb-pos">' +
        '<span class="bc-lb-pos-n"></span>' +
        '<span class="bc-lb-delta" aria-hidden="true"></span>' +
        "</span>" +
        '<span class="bc-lb-num"></span>' +
        '<span class="bc-lb-name">' +
        '<img class="bc-lb-mark" alt="" hidden decoding="async" />' +
        '<span class="bc-lb-name-text"></span>' +
        "</span>" +
        '<span class="bc-lb-gap"></span>';
      lbRowsByKey[key] = el;
    }
    fillLbRow(el, r);
    return el;
  }

  function clearLbSwapStyles(el) {
    el.style.transition = "";
    el.style.transform = "";
    el.style.zIndex = "";
    el.classList.remove("is-swap-up", "is-swap-down", "is-swapping");
  }

  function applyStandingsDom(rows, animate) {
    if (!elLb) return;
    var nextKeys = [];
    rows.forEach(function (r) {
      var key = boardCarKey(r);
      if (key) nextKeys.push(key);
    });

    var firstTops = Object.create(null);
    if (animate && lbOrderKeys.length) {
      lbOrderKeys.forEach(function (k) {
        var el = lbRowsByKey[k];
        if (el && el.parentNode === elLb) {
          firstTops[k] = el.getBoundingClientRect().top;
        }
      });
    }

    var orderChanged =
      lbOrderKeys.length > 0 &&
      (nextKeys.length !== lbOrderKeys.length ||
        nextKeys.some(function (k, i) {
          return k !== lbOrderKeys[i];
        }));

    rows.forEach(function (r) {
      var key = boardCarKey(r);
      if (!key) return;
      var el = ensureLbRow(key, r);
      elLb.appendChild(el);
    });

    Object.keys(lbRowsByKey).forEach(function (k) {
      if (nextKeys.indexOf(k) === -1) {
        var dead = lbRowsByKey[k];
        if (dead && dead.parentNode) dead.parentNode.removeChild(dead);
        delete lbRowsByKey[k];
      }
    });

    if (animate && orderChanged) {
      var movers = [];
      nextKeys.forEach(function (k) {
        var el = lbRowsByKey[k];
        if (!el || firstTops[k] == null) return;
        var lastTop = el.getBoundingClientRect().top;
        var dy = firstTops[k] - lastTop;
        if (Math.abs(dy) < 0.5) return;
        var oldIdx = lbOrderKeys.indexOf(k);
        var newIdx = nextKeys.indexOf(k);
        var gained = oldIdx >= 0 && newIdx >= 0 && newIdx < oldIdx;
        movers.push({ el: el, dy: dy, gained: gained });
      });

      if (movers.length) {
        lbAnimating = true;
        var token = ++lbAnimToken;
        if (elLb.parentElement) elLb.parentElement.classList.add("is-lb-swapping");
        movers.forEach(function (m) {
          clearLbSwapStyles(m.el);
          m.el.style.transition = "none";
          m.el.style.transform = "translate3d(0," + m.dy + "px,0)";
          m.el.style.zIndex = m.gained ? "3" : "2";
          m.el.classList.add("is-swapping");
          m.el.classList.add(m.gained ? "is-swap-up" : "is-swap-down");
        });
        void elLb.offsetHeight;
        window.requestAnimationFrame(function () {
          window.requestAnimationFrame(function () {
            if (token !== lbAnimToken) return;
            movers.forEach(function (m) {
              m.el.style.transition =
                "transform " +
                LB_SWAP_MS +
                "ms cubic-bezier(0.22, 1, 0.36, 1), " +
                "background-color " +
                LB_SWAP_MS +
                "ms ease";
              m.el.style.transform = "translate3d(0,0,0)";
            });
          });
        });
        window.setTimeout(function () {
          if (token !== lbAnimToken) return;
          movers.forEach(function (m) {
            clearLbSwapStyles(m.el);
          });
          if (elLb.parentElement) elLb.parentElement.classList.remove("is-lb-swapping");
          lbAnimating = false;
          if (lbPendingRows) {
            var pending = lbPendingRows;
            lbPendingRows = null;
            applyStandingsDom(pending, true);
          }
        }, LB_SWAP_MS + 48);
      }
    }

    lbOrderKeys = nextKeys;
  }

  function renderStandingsRows(rows) {
    if (!elLb) return;
    if (lbAnimating) {
      lbPendingRows = rows;
      // Keep text fresh on existing nodes without reordering mid-flight
      rows.forEach(function (r) {
        var key = boardCarKey(r);
        if (key && lbRowsByKey[key]) fillLbRow(lbRowsByKey[key], r);
      });
      return;
    }
    applyStandingsDom(rows, true);
  }

  function tickerItemHtml(r) {
    var gap =
      r.pos === 1
        ? "LEADER"
        : r.gapMs == null && r.intervalMs == null
          ? "—"
          : fmtMs(r.gapMs != null ? r.gapMs : r.intervalMs);
    var club = String(r.clubName || "").trim();
    return (
      '<div class="bc-ticker-item' +
      (r.isFocus ? " is-focus" : "") +
      '">' +
      '<span class="bc-ticker-pos">' +
      (r.pos != null ? r.pos : "—") +
      "</span>" +
      '<span class="bc-ticker-num">#' +
      (r.carNumber || "—") +
      "</span>" +
      '<span class="bc-ticker-name">' +
      (r.name || "—") +
      "</span>" +
      (club ? '<span class="bc-ticker-club">' + club + "</span>" : "") +
      '<span class="bc-ticker-gap">' +
      gap +
      "</span>" +
      "</div>"
    );
  }

  function clearTickerTimer() {
    if (tickerTimer != null) {
      window.clearTimeout(tickerTimer);
      tickerTimer = null;
    }
  }

  function scheduleTicker(ms, fn) {
    clearTickerTimer();
    tickerTimer = window.setTimeout(function () {
      tickerTimer = null;
      fn();
    }, ms);
  }

  function setTickerUp(up) {
    if (!elTicker) return;
    elTicker.classList.toggle("is-up", !!up);
    elTicker.setAttribute("aria-hidden", up ? "false" : "true");
  }

  function setTickerExpanded(expanded) {
    if (!elTicker) return;
    elTicker.classList.toggle("is-expanded", !!expanded);
  }

  function cancelTickerAnim() {
    if (tickerAnim) {
      try {
        tickerAnim.cancel();
      } catch (e) {
        /* ignore */
      }
      tickerAnim = null;
    }
    if (elTickerTrack) {
      elTickerTrack.style.transform = "translate3d(0,0,0)";
    }
  }

  function stopTickerScroll() {
    cancelTickerAnim();
  }

  function buildTickerStrip(rows) {
    if (!elTickerTrack) return 0;
    elTickerTrack.innerHTML = rows.map(tickerItemHtml).join("");
    stopTickerScroll();
    void elTickerTrack.offsetWidth;
    return elTickerTrack.scrollWidth;
  }

  function tickerGoIdle() {
    tickerPhase = "idle";
    setTickerExpanded(false);
    setTickerUp(false);
    stopTickerScroll();
    if (!tickerEnabled || !tickerRowsCache || !tickerRowsCache.length) return;
    scheduleTicker(tickerIdleMs, tickerEnter);
  }

  function tickerDrop() {
    if (!elTicker) return;
    tickerPhase = "drop";
    setTickerUp(false);
    scheduleTicker(TICKER_DROP_MS, tickerGoIdle);
  }

  function tickerCollapse() {
    if (!elTicker) return;
    if (tickerPhase === "collapse" || tickerPhase === "drop" || tickerPhase === "idle") return;
    tickerPhase = "collapse";
    clearTickerTimer();
    stopTickerScroll();
    setTickerExpanded(false);
    scheduleTicker(TICKER_COLLAPSE_MS, tickerDrop);
  }

  function tickerExit() {
    tickerCollapse();
  }

  function tickerStartScroll() {
    if (!elTickerTrack) return;
    if (!tickerRowsCache || !tickerRowsCache.length) {
      tickerGoIdle();
      return;
    }
    tickerPhase = "show";
    cancelTickerAnim();
    var stripW = elTickerTrack.scrollWidth;
    if (!(stripW > 0)) {
      stripW = buildTickerStrip(tickerRowsCache);
    }
    var viewW = elTickerViewport ? elTickerViewport.clientWidth : 0;
    var dist = Math.max(0, stripW - Math.max(0, viewW));
    if (dist < 12) {
      scheduleTicker(TICKER_HOLD_MS, tickerExit);
      return;
    }
    var ms = Math.round(
      Math.max(4000, Math.min(90000, (dist / tickerSpeed) * 1000))
    );
    if (typeof elTickerTrack.animate === "function") {
      tickerAnim = elTickerTrack.animate(
        [
          { transform: "translate3d(0,0,0)" },
          { transform: "translate3d(" + -dist + "px,0,0)" },
        ],
        { duration: ms, easing: "linear", fill: "forwards" }
      );
      tickerAnim.onfinish = function () {
        tickerAnim = null;
        if (tickerPhase === "show") tickerExit();
      };
      scheduleTicker(ms + 120, function () {
        if (tickerPhase === "show") tickerExit();
      });
      return;
    }
    scheduleTicker(Math.max(TICKER_HOLD_MS, ms), tickerExit);
  }

  function tickerExpand() {
    if (!elTicker) return;
    tickerPhase = "expand";
    setTickerExpanded(true);
    scheduleTicker(TICKER_EXPAND_MS, tickerStartScroll);
  }

  function tickerEnter() {
    if (!tickerEnabled || !elTicker || !elTickerTrack) return;
    if (!tickerRowsCache || !tickerRowsCache.length) {
      scheduleTicker(tickerIdleMs, tickerEnter);
      return;
    }
    tickerPhase = "rise";
    elTicker.hidden = false;
    elTicker.removeAttribute("hidden");
    buildTickerStrip(tickerRowsCache);
    setTickerExpanded(false);
    void elTicker.offsetWidth;
    setTickerUp(true);
    scheduleTicker(TICKER_RISE_MS, tickerExpand);
  }

  function renderFieldTicker(standings) {
    if (!tickerEnabled || !elTicker || !elTickerTrack) return;
    var rows = Array.isArray(standings) ? standings : [];
    tickerRowsCache = rows.length ? rows : null;
    if (!rows.length) {
      clearTickerTimer();
      tickerPhase = "idle";
      setTickerExpanded(false);
      setTickerUp(false);
      stopTickerScroll();
      elTicker.hidden = true;
      elTicker.setAttribute("hidden", "");
      elTicker.setAttribute("aria-hidden", "true");
      elTickerTrack.innerHTML = "";
      tickerStarted = false;
      return;
    }
    elTicker.hidden = false;
    elTicker.removeAttribute("hidden");
    if (!tickerStarted) {
      tickerStarted = true;
      scheduleTicker(tickerFirstDelayMs, tickerEnter);
    }
  }

  function sectorDeltaClass(ms) {
    if (ms == null || !Number.isFinite(Number(ms))) return "";
    const n = Number(ms);
    if (n < 0) return "is-fast";
    if (n > 0) return "is-slow";
    return "is-even";
  }

  function focusMetricHtml(label, valueHtml, extraClass) {
    return (
      '<div class="bc-focus-metric' +
      (extraClass ? " " + extraClass : "") +
      '"><span class="bc-focus-k">' +
      label +
      '</span><span class="bc-focus-v">' +
      valueHtml +
      "</span></div>"
    );
  }

  function renderSectorsHtml(tick) {
    const list = Array.isArray(tick.sectors) ? tick.sectors : [];
    const deltas = Array.isArray(tick.sectorDeltaMs) ? tick.sectorDeltaMs : null;
    const cur = tick.sector != null ? Number(tick.sector) : null;
    if (!list.length && tick.deltaLiveMs == null) return "";
    var chips = "";
    if (list.length) {
      chips = list
        .slice(0, 6)
        .map(function (s, i) {
          var num = s.num != null ? s.num : i + 1;
          var d = deltas && deltas[i] != null ? deltas[i] : null;
          var cls = "bc-sector";
          if (cur != null && num === cur) cls += " is-active";
          else if (d != null) cls += " is-done";
          var deltaCls = sectorDeltaClass(d);
          if (deltaCls) cls += " " + deltaCls;
          return (
            '<span class="' +
            cls +
            '"><span class="bc-sector-k">S' +
            num +
            '</span><strong class="bc-sector-v">' +
            (d != null ? fmtMs(d) : "—") +
            "</strong></span>"
          );
        })
        .join("");
    }
    var live =
      tick.deltaLiveMs != null
        ? '<span class="bc-sector-live"><span class="bc-sector-k">Δ</span><strong class="bc-sector-v ' +
          sectorDeltaClass(tick.deltaLiveMs) +
          '">' +
          fmtMs(tick.deltaLiveMs) +
          "</strong></span>"
        : "";
    return '<div class="bc-sectors">' + chips + live + "</div>";
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
    const relatives = Array.isArray(tick.relatives) ? tick.relatives : [];
    const focusIdx = tick.focusCarIdx;
    const forceBoard =
      focusIdx != null &&
      lastBoardFocusIdx != null &&
      focusIdx !== lastBoardFocusIdx;
    if (focusIdx != null) lastBoardFocusIdx = focusIdx;
    const board = latchGapsIfDue(standings, relatives, forceBoard);
    const painted = withLatchedGaps(standings);

    renderStandingsRows(painted.slice(0, maxLb));
    renderFieldTicker(painted);

    if (elRel && (board.gapsRefreshed || !elRel.innerHTML)) {
      elRel.innerHTML = (board.relatives || [])
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
            (r.rel === 0 ? "—" : r.gapMs == null ? "—" : fmtMs(r.gapMs)) +
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
      const posNum = tick.position != null ? Number(tick.position) : null;
      const posChanged =
        lastFocusPos != null &&
        posNum != null &&
        Number.isFinite(posNum) &&
        posNum !== lastFocusPos;
      if (posNum != null && Number.isFinite(posNum)) lastFocusPos = posNum;
      elFocus.innerHTML =
        '<div class="bc-panel-head"><strong>FOCUS</strong><span>CAMERA</span></div>' +
        '<div class="bc-focus-body">' +
        '<div class="bc-focus-top">' +
        '<div class="bc-focus-pos">' +
        pos +
        of +
        "</div>" +
        '<div class="bc-focus-name">#' +
        num +
        " " +
        name +
        "</div>" +
        "</div>" +
        '<div class="bc-focus-meta">' +
        focusMetricHtml("LAST", fmtLap(tick.lastLapMs)) +
        focusMetricHtml("BEST", fmtLap(tick.bestLapMs)) +
        focusMetricHtml("GAP", fmtMs(tick.gapAheadMs)) +
        (tick.deltaBestMs != null
          ? focusMetricHtml(
              "ΔBEST",
              '<strong class="' +
                (Number(tick.deltaBestMs) <= 0 ? "is-purple" : "is-slow") +
                '">' +
                fmtMs(tick.deltaBestMs) +
                "</strong>"
            )
          : "") +
        (tick.fuelPct != null
          ? focusMetricHtml("FUEL", Number(tick.fuelPct).toFixed(0) + "%")
          : "") +
        (tick.inPit
          ? '<div class="bc-focus-metric is-pit"><span class="bc-pit-tag">PIT</span></div>'
          : "") +
        "</div>" +
        renderSectorsHtml(tick) +
        "</div>";
      if (posChanged) {
        elFocus.classList.remove("is-pos-flash");
        void elFocus.offsetWidth;
        elFocus.classList.add("is-pos-flash");
        if (focusFlashTimer != null) window.clearTimeout(focusFlashTimer);
        focusFlashTimer = window.setTimeout(function () {
          elFocus.classList.remove("is-pos-flash");
          focusFlashTimer = null;
        }, 450);
      }
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
