/**
 * Broadcast telecronaca UI (P3-02).
 * Consumes adapters/telemetry CONTRACT.md via WebSocket.
 * Mount: [data-broadcast-root]
 */
(function initBroadcastChrome() {
  const cfg = window.PIGRECO_CONFIG || {};
  const root = document.querySelector("[data-broadcast-root]");
  if (!root) return;

  const showcaseMode =
    new URLSearchParams(window.location.search || "").get("showcase") === "1";
  if (showcaseMode) {
    // Paint immediately for headless PNG capture (no wait for ticker idle).
    cfg.broadcastTickerFirstDelayMs = 0;
    cfg.broadcastTickerIdleMs = 0;
    cfg.broadcastBoardRefreshMs = 1000;
  }

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
  if (cfg.broadcastBattlePanel === false) root.classList.add("no-fight");
  if (cfg.broadcastRaceBest === false) root.classList.add("no-best");

  const maxLb = Math.max(5, Math.min(20, Number(cfg.broadcastLeaderboardRows) || 10));
  const url = cfg.telemetryWsUrl || "ws://127.0.0.1:8765";
  const director = cfg.broadcastDirector || "auto"; // auto|manual|off
  const sensitivity = cfg.broadcastDirectorSensitivity || "normal";
  const BATTLE_SENS = {
    // engage/closeRate/ticks = arm panel.
    // include = serious join/rejoin; keep = soft stay; leaveMs = time beyond keep before drop.
    calm: {
      engageMs: 1100,
      includeMs: 280,
      keepMs: 400,
      leaveMs: 3000,
      exitMs: 400,
      closeRate: 220,
      ticks: 5,
    },
    normal: {
      engageMs: 850,
      includeMs: 250,
      keepMs: 400,
      leaveMs: 3000,
      exitMs: 400,
      closeRate: 280,
      ticks: 4,
    },
    hype: {
      engageMs: 650,
      includeMs: 220,
      keepMs: 400,
      leaveMs: 3000,
      exitMs: 400,
      closeRate: 320,
      ticks: 3,
    },
  };
  const battleSens = BATTLE_SENS[sensitivity] || BATTLE_SENS.normal;
  const battlePanelEnabled = cfg.broadcastBattlePanel !== false;
  const battleEngageMs = Math.max(
    300,
    Math.min(2500, Number(cfg.broadcastBattleMs) || battleSens.engageMs)
  );
  const battleIncludeMs = Math.max(
    120,
    Math.min(800, Number(cfg.broadcastBattleIncludeMs) || battleSens.includeMs)
  );
  const battleKeepMs = Math.max(
    battleIncludeMs,
    Math.min(1500, Number(cfg.broadcastBattleKeepMs) || battleSens.keepMs)
  );
  const battleLeaveMs = Math.max(
    500,
    Math.min(10000, Number(cfg.broadcastBattleLeaveMs) || battleSens.leaveMs)
  );
  const battleExitMs = Math.max(
    battleKeepMs,
    Math.min(2000, Number(cfg.broadcastBattleExitMs) || battleSens.exitMs || battleKeepMs)
  );
  const battleCloseRate = Math.max(
    80,
    Math.min(2000, Number(cfg.broadcastBattleCloseRate) || battleSens.closeRate)
  );
  const battleTicksNeed = Math.max(
    2,
    Math.min(12, Number(cfg.broadcastBattleTicks) || battleSens.ticks)
  );
  const battleDoorstopMs = Math.max(60, Math.min(250, Number(cfg.broadcastBattleDoorstopMs) || 110));
  const FIGHT_SWAP_MS = 520;
  const FIGHT_PACK_MAX = 3;
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
  const elFlagStrip = root.querySelector("[data-bc-flag-strip]");
  const elFlagStripLabel = root.querySelector("[data-bc-flag-strip-label]");
  const elFlagStripText = root.querySelector("[data-bc-flag-strip-text]");
  const flagStripMs = Math.max(
    2000,
    Math.min(30000, Number(cfg.broadcastFlagStripMs) || 10000)
  );
  const FLAG_STRIP_RISE_MS = 420;
  const FLAG_STRIP_EXPAND_MS = 480;
  const FLAG_STRIP_COLLAPSE_MS = 480;
  const FLAG_STRIP_DROP_MS = 420;
  const TIMED_FLAGS = { white: 1, debris: 1, checkered: 1 };
  const HOLD_FLAGS = { yellow: 1, red: 1 };
  const elStatus = root.querySelector("[data-bc-status]");
  const elMoment = root.querySelector("[data-bc-moment]");
  const elTicker = root.querySelector("[data-bc-ticker]");
  const elTickerTrack = root.querySelector("[data-bc-ticker-track]");
  const elTickerViewport = root.querySelector(".bc-ticker-viewport");
  const elFight = root.querySelector("[data-bc-fight]");
  const elFightTitle = root.querySelector("[data-bc-fight-title]");
  const elFightRows = root.querySelector("[data-bc-fight-rows]");
  const elBest = root.querySelector("[data-bc-best]");
  const elBestTime = root.querySelector("[data-bc-best-time]");
  const elBestDriver = root.querySelector("[data-bc-best-driver]");
  const raceBestEnabled = cfg.broadcastRaceBest !== false;
  let raceBestMs = null;
  let raceBestFlashTimer = null;
  let battleStreak = 0;
  let battleActive = false;
  let battleFarSince = 0;
  let battleEmptySince = 0;
  let fightPrevOrder = [];
  let fightFlashTimer = null;
  let fightGapHist = { ahead: null, behind: null, t: 0 };
  let fightStickyKeys = Object.create(null);
  let fightLeaveAt = Object.create(null);
  let fightDroppedKeys = Object.create(null);
  let fightAnimating = false;
  let fightDispSeps = null;
  let fightDispSide = null;
  let fightDispAt = 0;
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

  let flagStripPhase = "idle"; // idle|rise|expand|show|collapse|drop
  let flagStripTimer = null;
  let flagStripCurrent = "";
  let flagStripGen = 0;
  let flagStripDismissed = "";

  function flagStripMeta(flag) {
    var f = String(flag || "").toLowerCase();
    if (f === "white") return { label: "LAST LAP", text: "FINAL LAP" };
    if (f === "debris") return { label: "DEBRIS", text: "DEBRIS ON TRACK" };
    if (f === "checkered") return { label: "CHECKERED", text: "SESSION FINISH" };
    if (f === "yellow") return { label: "YELLOW", text: "CAUTION" };
    if (f === "red") return { label: "RED", text: "SESSION STOPPED" };
    if (f === "blue") return { label: "BLUE", text: "LET LEADER BY" };
    return { label: f.toUpperCase(), text: f.toUpperCase() };
  }

  function clearFlagStripTimer() {
    if (flagStripTimer != null) {
      window.clearTimeout(flagStripTimer);
      flagStripTimer = null;
    }
  }

  function scheduleFlagStrip(ms, fn) {
    clearFlagStripTimer();
    flagStripTimer = window.setTimeout(function () {
      flagStripTimer = null;
      fn();
    }, ms);
  }

  function setFlagStripUp(up) {
    if (!elFlagStrip) return;
    elFlagStrip.classList.toggle("is-up", !!up);
    elFlagStrip.hidden = !up && flagStripPhase === "idle";
    elFlagStrip.setAttribute("aria-hidden", up ? "false" : "true");
  }

  function setFlagStripExpanded(expanded) {
    if (!elFlagStrip) return;
    elFlagStrip.classList.toggle("is-expanded", !!expanded);
  }

  function flagStripGoIdle() {
    if (TIMED_FLAGS[flagStripCurrent]) {
      flagStripDismissed = flagStripCurrent;
    }
    flagStripPhase = "idle";
    flagStripCurrent = "";
    setFlagStripExpanded(false);
    setFlagStripUp(false);
    if (elFlagStrip) {
      elFlagStrip.hidden = true;
      elFlagStrip.dataset.flag = "";
    }
    directorLog("DEBUG", "flag strip idle");
  }

  function flagStripDrop() {
    flagStripPhase = "drop";
    setFlagStripUp(false);
    scheduleFlagStrip(FLAG_STRIP_DROP_MS, flagStripGoIdle);
  }

  function flagStripCollapse() {
    if (flagStripPhase === "collapse" || flagStripPhase === "drop" || flagStripPhase === "idle") return;
    directorLog("INFO", "flag strip collapse flag=" + flagStripCurrent);
    flagStripPhase = "collapse";
    clearFlagStripTimer();
    setFlagStripExpanded(false);
    scheduleFlagStrip(FLAG_STRIP_COLLAPSE_MS, flagStripDrop);
  }

  function showFlagStrip(flag) {
    if (!elFlagStrip) return;
    var f = String(flag || "").toLowerCase();
    if (!TIMED_FLAGS[f] && !HOLD_FLAGS[f] && f !== "blue") return;
    flagStripGen += 1;
    var gen = flagStripGen;
    flagStripCurrent = f;
    if (TIMED_FLAGS[f]) flagStripDismissed = "";
    var meta = flagStripMeta(f);
    elFlagStrip.hidden = false;
    elFlagStrip.dataset.flag = f;
    if (elFlagStripLabel) elFlagStripLabel.textContent = meta.label;
    if (elFlagStripText) elFlagStripText.textContent = meta.text;
    clearFlagStripTimer();
    flagStripPhase = "rise";
    setFlagStripExpanded(false);
    setFlagStripUp(true);
    directorLog("INFO", "flag strip show flag=" + f + " timed=" + !!TIMED_FLAGS[f]);
    scheduleFlagStrip(FLAG_STRIP_RISE_MS, function () {
      if (gen !== flagStripGen) return;
      flagStripPhase = "expand";
      setFlagStripExpanded(true);
      scheduleFlagStrip(FLAG_STRIP_EXPAND_MS, function () {
        if (gen !== flagStripGen) return;
        flagStripPhase = "show";
        if (TIMED_FLAGS[f]) {
          scheduleFlagStrip(flagStripMs, function () {
            if (gen !== flagStripGen) return;
            flagStripCollapse();
          });
        }
      });
    });
  }

  function syncFlagStrip(flag) {
    var f = String(flag || "none").toLowerCase();
    if (f === "none" || f === "green") {
      flagStripDismissed = "";
      if (HOLD_FLAGS[flagStripCurrent] || flagStripCurrent) {
        // Green clears hold flags; timed flags keep their remaining hold.
        if (HOLD_FLAGS[flagStripCurrent] || !TIMED_FLAGS[flagStripCurrent]) {
          flagStripCollapse();
        }
      }
      return;
    }
    if (f === flagStripDismissed) return;
    if (f === flagStripCurrent && flagStripPhase !== "idle") return;
    showFlagStrip(f);
  }

  function applyFlagBanner(flag) {
    syncFlagStrip(flag);
  }

  function clearLeaderboardDom() {
    if (focusFlashTimer != null) {
      window.clearTimeout(focusFlashTimer);
      focusFlashTimer = null;
    }
    lastFocusPos = null;
    lbAnimToken += 1;
    lbAnimating = false;
    lbPendingRows = null;
    lbOrderKeys = [];
    Object.keys(lbRowsByKey).forEach(function (k) {
      var dead = lbRowsByKey[k];
      if (dead && dead.parentNode) dead.parentNode.removeChild(dead);
      delete lbRowsByKey[k];
    });
    if (elLb) {
      elLb.innerHTML = "";
      if (elLb.parentElement) elLb.parentElement.classList.remove("is-lb-swapping");
    }
    if (elRel) elRel.innerHTML = "";
    if (elFocus) elFocus.innerHTML = "";
    if (elTickerTrack) elTickerTrack.innerHTML = "";
    if (elBestDriver) elBestDriver.innerHTML = "";
    if (elSession) {
      elSession.innerHTML = "";
      elSession.dataset.flag = "green";
    }
  }

  function clearBoardAndFightState() {
    lastBoardAt = 0;
    latchedGapByKey = Object.create(null);
    latchedRelatives = null;
    lastBoardFocusIdx = null;
    fightPrevOrder = [];
    fightStickyKeys = Object.create(null);
    fightLeaveAt = Object.create(null);
    fightDroppedKeys = Object.create(null);
    fightGapHist = { ahead: null, behind: null, t: 0 };
    fightDispSeps = null;
    fightDispSide = null;
    battleActive = false;
    battleStreak = 0;
    clearLeaderboardDom();
    if (elFight) {
      elFight.hidden = true;
      elFight.classList.remove("is-on");
      if (elFightRows) elFightRows.innerHTML = "";
    }
  }

  function clearSessionOverlayState(reason) {
    clearMomentLayer();
    clearBoardAndFightState();
    if (reason !== "ws_open") {
      setStatus("SESSION RESET");
    }
    directorLog("INFO", "session_reset reason=" + (reason || ""));
  }

  function clearMomentLayer() {
    if (heroExitTimer != null) {
      window.clearTimeout(heroExitTimer);
      heroExitTimer = null;
    }
    heroGen += 1;
    directorState = Director && Director.clearDirectorState
      ? Director.clearDirectorState(directorState)
      : { hero: null, queue: [] };
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
    if (ev.kind === "flag_change" || ev.kind === "session_end") {
      applyFlagBanner(ev.payload && ev.payload.flag);
      return;
    }
    if (!Director) return;
    var prevHero = directorState.hero;
    directorState = Director.enqueueEvent(directorState, ev, director);
    directorLog("DEBUG", "event kind=" + ev.kind + " priority=" + (ev.priority || 0));
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

  function fmtFightGap(ms) {
    if (ms == null || !Number.isFinite(Number(ms))) return { text: "—", side: false };
    const abs = Math.abs(Number(ms));
    return { text: (abs / 1000).toFixed(3) + "s", side: abs < 60 };
  }

  /** SIDE hysteresis only — gap text stays live (no 50ms quantize). */
  function fightGapIsSide(ms, wasSide) {
    if (ms == null || !Number.isFinite(Number(ms))) return false;
    var abs = Math.abs(Number(ms));
    if (wasSide) return abs < 110;
    return abs < 60;
  }

  function fmtFightGapStable(ms, wasSide) {
    if (ms == null || !Number.isFinite(Number(ms))) return { text: "—", side: false };
    var abs = Math.abs(Number(ms));
    var side = fightGapIsSide(ms, wasSide);
    return { text: (abs / 1000).toFixed(3) + "s", side: side };
  }

  function fightOrdersEqual(a, b) {
    if (!a || !b || a.length !== b.length) return false;
    var i;
    for (i = 0; i < a.length; i++) {
      if (a[i] !== b[i]) return false;
    }
    return true;
  }

  function stabilizeFightSeps(rawSeps, _structureChanged) {
    // Live ms every paint; only SIDE boolean is sticky (hysteresis).
    var next = rawSeps.slice();
    fightDispSide = next.map(function (ms, idx) {
      var was = !!(fightDispSide && fightDispSide[idx]);
      return fightGapIsSide(ms, was);
    });
    fightDispSeps = next;
    fightDispAt = Date.now();
    return fightDispSeps;
  }

  function fightSepHtml(ms, wasSide) {
    var sep = fmtFightGapStable(ms, wasSide);
    return (
      '<div class="bc-fight-sep' +
      (sep.side ? " is-side" : "") +
      '">' +
      (sep.side ? '<span class="bc-fight-side-tag">SIDE</span>' : "") +
      '<span class="bc-fight-gap">' +
      sep.text +
      "</span></div>"
    );
  }

  var HELMET_SVG =
    '<svg class="bc-fight-avatar bc-fight-helmet" viewBox="0 0 64 64" xmlns="http://www.w3.org/2000/svg" aria-hidden="true">' +
    '<path fill="#2a3238" d="M32 6c-12.5 0-22 9.2-22 22.5V40c0 8.5 6.2 14 14 14h16c7.8 0 14-5.5 14-14v-11.5C54 15.2 44.5 6 32 6z"/>' +
    '<path fill="#1a1f24" d="M14 28.5c0-9.5 7.8-16.5 18-16.5s18 7 18 16.5V36H14v-7.5z"/>' +
    '<path fill="#4a5560" d="M12 30h40v6.5c0 1.2-.6 2-2 2.4L32 44 14 38.9c-1.4-.4-2-1.2-2-2.4V30z"/>' +
    '<path fill="#9aa5b0" opacity=".85" d="M18 31.5h28v3.2c0 .7-.5 1.2-1.3 1.4L32 38.5 19.3 36.1c-.8-.2-1.3-.7-1.3-1.4v-3.2z"/>' +
    '<path stroke="currentColor" stroke-width="2" d="M14 37.5h36"/>' +
    '<circle cx="32" cy="18" r="2.2" fill="#c8d0d8"/>' +
    "</svg>";

  function shortDriverName(name) {
    var s = String(name || "").trim();
    if (!s) return "—";
    function capWord(w) {
      if (!w) return "";
      return w
        .split("-")
        .map(function (part) {
          if (!part) return "";
          return part.charAt(0).toUpperCase() + part.slice(1).toLowerCase();
        })
        .join("-");
    }
    var parts = s.split(/\s+/).filter(Boolean);
    if (parts.length === 1) return capWord(parts[0]).slice(0, 14);
    var first = parts[0].charAt(0).toUpperCase();
    var last = capWord(parts[parts.length - 1]).slice(0, 12);
    return first + ". " + last;
  }

  function findFocusStandingIndex(standings, focusCarIdx) {
    var i;
    for (i = 0; i < standings.length; i++) {
      if (focusCarIdx != null && standings[i].carIdx === focusCarIdx) return i;
      if (standings[i].isFocus) return i;
    }
    return -1;
  }

  function battleEligibleFromTick(tick) {
    if (!tick) return false;
    if (typeof tick.battleEligible === "boolean") return tick.battleEligible;
    // Fail closed for known non-race/practice if bridge old:
    var s = String(tick.session || "").toLowerCase();
    if (s === "quali" || s === "cooldown" || s === "unknown" || !s) return false;
    if (s === "race") {
      var lap = Number(tick.lap);
      return Number.isFinite(lap) && lap >= 1;
    }
    if (s === "practice") {
      var rows = Array.isArray(tick.standings) ? tick.standings : [];
      return rows.length >= 2;
    }
    return false;
  }

  /** LapDistPct corridor where estimated gaps thrash at S/F (matches domain_events). */
  var SF_MUTE_LO = 0.04;
  var SF_MUTE_HI = 0.96;

  function focusNearStartFinish(tick, standings) {
    var d = tick && tick.focusDistPct;
    if (d == null || !Number.isFinite(Number(d))) {
      var i = findFocusStandingIndex(standings || [], tick && tick.focusCarIdx);
      if (i >= 0) d = standings[i].distPct;
    }
    if (d == null || !Number.isFinite(Number(d))) return false;
    d = Number(d) % 1;
    if (d < 0) d += 1;
    return d < SF_MUTE_LO || d > SF_MUTE_HI;
  }

  function sampleFightGaps(tick) {
    var now =
      typeof performance !== "undefined" && performance.now ? performance.now() : Date.now();
    var ga =
      tick.gapAheadMs != null && Number.isFinite(Number(tick.gapAheadMs))
        ? Number(tick.gapAheadMs)
        : null;
    var gb =
      tick.gapBehindMs != null && Number.isFinite(Number(tick.gapBehindMs))
        ? Number(tick.gapBehindMs)
        : null;
    var closeAhead = 0;
    var closeBehind = 0;
    if (fightGapHist.t > 0) {
      var dt = Math.max(0.08, (now - fightGapHist.t) / 1000);
      if (ga != null && fightGapHist.ahead != null && ga >= 0 && fightGapHist.ahead >= 0) {
        // Positive = we are catching the car ahead (gap shrinking).
        closeAhead = (fightGapHist.ahead - ga) / dt;
      }
      if (gb != null && fightGapHist.behind != null && gb >= 0 && fightGapHist.behind >= 0) {
        // Positive = car behind is catching us (gap shrinking).
        closeBehind = (fightGapHist.behind - gb) / dt;
      }
    }
    fightGapHist = { ahead: ga, behind: gb, t: now };
    return { ga: ga, gb: gb, closeAhead: closeAhead, closeBehind: closeBehind };
  }

  function fightShouldArm(sample) {
    if (Director && Director.fightGapsArm) {
      return Director.fightGapsArm(sample, {
        doorstopMs: battleDoorstopMs,
        engageMs: battleEngageMs,
        closeRate: battleCloseRate,
      });
    }
    var door =
      (sample.ga != null && sample.ga > 0 && sample.ga <= battleDoorstopMs) ||
      (sample.gb != null && sample.gb > 0 && sample.gb <= battleDoorstopMs);
    if (door) return true;
    var catchAhead =
      sample.ga != null &&
      sample.ga > 0 &&
      sample.ga <= battleEngageMs &&
      sample.closeAhead >= battleCloseRate;
    var catchBehind =
      sample.gb != null &&
      sample.gb > 0 &&
      sample.gb <= battleEngageMs &&
      sample.closeBehind >= battleCloseRate;
    return catchAhead || catchBehind;
  }

  function fightShouldHold(sample) {
    if (Director && Director.fightGapsHold) {
      return Director.fightGapsHold(sample, battleExitMs);
    }
    var near =
      (sample.ga != null && sample.ga > 0 && sample.ga <= battleExitMs) ||
      (sample.gb != null && sample.gb > 0 && sample.gb <= battleExitMs);
    return near;
  }

  function fightNow() {
    return typeof performance !== "undefined" && performance.now ? performance.now() : Date.now();
  }

  /**
   * Connected train around focus (consecutive intervals), up to 3 cars.
   * Sticky stay while gap <= keep; beyond keep for leaveMs → drop.
   * Rejoin only with tighter include (serious approach).
   */
  function buildFightPack(standings, focusCarIdx, joinThr, keepThr) {
    var focusI = findFocusStandingIndex(standings, focusCarIdx);
    if (focusI < 0 || !standings.length) return null;
    var now = fightNow();

    function carKeyAt(i) {
      return boardCarKey(standings[i]) || "i" + i;
    }

    /** Gap between standings[i-1] (ahead) and standings[i]. */
    function edgeGap(i) {
      return Math.abs(Number(standings[i].intervalMs) || 0);
    }

    function acceptEdge(gapAbs, key) {
      if (fightStickyKeys[key]) {
        if (gapAbs <= keepThr) {
          delete fightLeaveAt[key];
          return true;
        }
        // Beyond keep: keep showing until leaveMs elapsed, then drop.
        if (!fightLeaveAt[key]) fightLeaveAt[key] = now;
        if (now - fightLeaveAt[key] < battleLeaveMs) return true;
        delete fightLeaveAt[key];
        fightDroppedKeys[key] = true;
        return false;
      }
      // Already dropped this battle: only a serious close re-admits them.
      if (fightDroppedKeys[key]) {
        if (gapAbs <= joinThr) {
          delete fightDroppedKeys[key];
          delete fightLeaveAt[key];
          return true;
        }
        return false;
      }
      // First join while battle is live: allow up to keep (0.4s).
      if (gapAbs <= keepThr) {
        delete fightLeaveAt[key];
        return true;
      }
      return false;
    }

    var lo = focusI;
    var hi = focusI;

    while (lo > 0 && focusI - lo < 2) {
      var aheadKey = carKeyAt(lo - 1);
      if (!acceptEdge(edgeGap(lo), aheadKey)) break;
      lo -= 1;
    }
    while (hi < standings.length - 1 && hi - focusI < 2) {
      var behindKey = carKeyAt(hi + 1);
      if (!acceptEdge(edgeGap(hi + 1), behindKey)) break;
      hi += 1;
    }

    while (hi - lo + 1 > FIGHT_PACK_MAX) {
      var gapDropLo = edgeGap(lo + 1);
      var gapDropHi = edgeGap(hi);
      var stickyLo = !!fightStickyKeys[carKeyAt(lo)];
      var stickyHi = !!fightStickyKeys[carKeyAt(hi)];
      if (lo === focusI) {
        hi -= 1;
      } else if (hi === focusI) {
        lo += 1;
      } else if (stickyLo && !stickyHi) {
        hi -= 1;
      } else if (stickyHi && !stickyLo) {
        lo += 1;
      } else if (gapDropHi >= gapDropLo) {
        hi -= 1;
      } else {
        lo += 1;
      }
    }

    if (hi - lo + 1 < 2) {
      fightStickyKeys = Object.create(null);
      fightLeaveAt = Object.create(null);
      return null;
    }

    var rows = [];
    var contested = null;
    var nextSticky = Object.create(null);
    var nextLeave = Object.create(null);
    var i;

    for (i = lo; i <= hi; i++) {
      var gapToFocus = 0;
      var j;
      if (i < focusI) {
        for (j = i + 1; j <= focusI; j++) gapToFocus -= edgeGap(j);
      } else if (i > focusI) {
        for (j = focusI + 1; j <= i; j++) gapToFocus += edgeGap(j);
      }
      var r = standings[i];
      var key = carKeyAt(i);
      var pos = r.pos != null ? Number(r.pos) : i + 1;
      if (contested == null || pos < contested) contested = pos;
      nextSticky[key] = true;
      if (fightLeaveAt[key]) nextLeave[key] = fightLeaveAt[key];
      rows.push({
        key: key,
        pos: pos,
        carNumber: r.carNumber || "",
        name: r.name || "—",
        isFocus: i === focusI,
        gapMs: gapToFocus,
        countryCode: r.countryCode || null,
        country: r.country || null,
      });
    }

    fightStickyKeys = nextSticky;
    fightLeaveAt = nextLeave;

    var seps = [];
    var k;
    for (k = 0; k < rows.length - 1; k++) {
      seps.push(Math.abs(Number(rows[k + 1].gapMs) - Number(rows[k].gapMs)));
    }
    return { contestedPos: contested, rows: rows, seps: seps };
  }

  function setFightOn(on) {
    if (!elFight) return;
    elFight.classList.toggle("is-on", !!on);
    elFight.setAttribute("aria-hidden", on ? "false" : "true");
    if (on) {
      elFight.hidden = false;
      elFight.removeAttribute("hidden");
    }
  }

  function hideFightPanel() {
    if (!elFight) return;
    setFightOn(false);
    window.setTimeout(function () {
      if (!battleActive && elFight && !elFight.classList.contains("is-on")) {
        elFight.hidden = true;
        elFight.setAttribute("hidden", "");
      }
    }, 450);
    if (elFightRows) elFightRows.innerHTML = "";
    fightPrevOrder = [];
    fightStickyKeys = Object.create(null);
    fightLeaveAt = Object.create(null);
    fightDroppedKeys = Object.create(null);
    fightDispSeps = null;
    fightDispSide = null;
    fightDispAt = 0;
    battleFarSince = 0;
    battleEmptySince = 0;
    fightAnimating = false;
  }

  function flagAssetBase() {
    // Config server (:8766): always load from pigreco overlays pack.
    if (location.pathname.indexOf("/o/") === 0) {
      return "/o/overlays/assets/flags/";
    }
    var scripts = document.getElementsByTagName("script");
    var i;
    for (i = scripts.length - 1; i >= 0; i--) {
      var src = scripts[i].getAttribute("src") || "";
      if (src.indexOf("broadcast.js") < 0) continue;
      if (src.indexOf("../overlays/") >= 0) return "../overlays/assets/flags/";
      if (/\/overlays\/broadcast\.js/.test(src)) {
        return src.replace(/broadcast\.js(?:\?.*)?$/, "assets/flags/");
      }
      return "assets/flags/";
    }
    return "assets/flags/";
  }

  var FLAG_ASSET_BASE = flagAssetBase();

  function flagEmojiFromCode(code) {
    var cc = String(code || "")
      .trim()
      .toUpperCase();
    if (cc.length !== 2 || cc === "UN") return "";
    var a = cc.charCodeAt(0) - 65;
    var b = cc.charCodeAt(1) - 65;
    if (a < 0 || a > 25 || b < 0 || b > 25) return "";
    return String.fromCodePoint(0x1f1e6 + a, 0x1f1e6 + b);
  }

  function flagSpanHtml(code, country) {
    var cc = String(code || "")
      .trim()
      .toLowerCase();
    if (cc.length !== 2 || cc === "un") return "";
    var title = String(country || code || "")
      .replace(/&/g, "&amp;")
      .replace(/"/g, "&quot;")
      .replace(/</g, "&lt;");
    // SVG images (OBS CEF often blanks emoji regional flags on Windows).
    return (
      '<img class="bc-flag" src="' +
      FLAG_ASSET_BASE +
      cc +
      '.svg" alt="" title="' +
      title +
      '" width="18" height="12" decoding="async" draggable="false" />'
    );
  }

  function fightAvatarHtml(r) {
    if (r.isFocus && pilotMarkUrl) {
      return (
        '<img class="bc-fight-avatar bc-fight-mono" src="' +
        pilotMarkUrl +
        '" alt="" decoding="async" draggable="false" />'
      );
    }
    return HELMET_SVG;
  }

  function fightCardHtml(r, swapClass) {
    var flag = flagSpanHtml(r.countryCode, r.country);
    return (
      '<div class="bc-fight-card' +
      (r.isFocus ? " is-focus" : "") +
      (swapClass || "") +
      '" data-fight-key="' +
      r.key +
      '">' +
      '<div class="bc-fight-avatar-wrap">' +
      fightAvatarHtml(r) +
      '<span class="bc-fight-pos">P' +
      (r.pos != null ? r.pos : "—") +
      "</span>" +
      "</div>" +
      '<div class="bc-fight-meta">' +
      '<span class="bc-fight-num">#' +
      (r.carNumber || "—") +
      "</span>" +
      '<span class="bc-fight-name-row">' +
      (flag ? '<span class="bc-fight-nat">' + flag + "</span>" : "") +
      '<span class="bc-fight-name">' +
      shortDriverName(r.name) +
      "</span>" +
      "</span>" +
      "</div>" +
      "</div>"
    );
  }

  function paintFightSepEl(el, ms, wasSide) {
    var sep = fmtFightGapStable(ms, wasSide);
    el.classList.toggle("is-side", sep.side);
    var tag = el.querySelector(".bc-fight-side-tag");
    if (sep.side) {
      if (!tag) {
        tag = document.createElement("span");
        tag.className = "bc-fight-side-tag";
        tag.textContent = "SIDE";
        el.insertBefore(tag, el.firstChild);
      } else if (tag.textContent !== "SIDE") {
        tag.textContent = "SIDE";
      }
    } else if (tag) {
      tag.remove();
    }
    var gap = el.querySelector(".bc-fight-gap");
    if (!gap) {
      gap = document.createElement("span");
      gap.className = "bc-fight-gap";
      el.appendChild(gap);
    }
    if (gap.textContent !== sep.text) gap.textContent = sep.text;
    return sep.side;
  }

  function paintFightCard(card, r) {
    card.classList.toggle("is-focus", !!r.isFocus);
    var posEl = card.querySelector(".bc-fight-pos");
    var posText = "P" + (r.pos != null ? r.pos : "—");
    if (posEl && posEl.textContent !== posText) posEl.textContent = posText;
    var numEl = card.querySelector(".bc-fight-num");
    var numText = "#" + (r.carNumber || "—");
    if (numEl && numEl.textContent !== numText) numEl.textContent = numText;
    var nameEl = card.querySelector(".bc-fight-name");
    var nameText = shortDriverName(r.name);
    if (nameEl && nameEl.textContent !== nameText) nameEl.textContent = nameText;

    var meta = card.querySelector(".bc-fight-meta");
    if (meta) {
      var nameRow = meta.querySelector(".bc-fight-name-row");
      if (!nameRow) {
        nameRow = document.createElement("span");
        nameRow.className = "bc-fight-name-row";
        if (nameEl) nameRow.appendChild(nameEl);
        meta.appendChild(nameRow);
      }
      var nat = nameRow.querySelector(".bc-fight-nat");
      var flagHtml = flagSpanHtml(r.countryCode, r.country);
      if (flagHtml) {
        if (!nat) {
          nat = document.createElement("span");
          nat.className = "bc-fight-nat";
          nameRow.insertBefore(nat, nameRow.firstChild);
        }
        if (nat.innerHTML !== flagHtml) nat.innerHTML = flagHtml;
      } else if (nat) {
        nat.remove();
      }
    }

    var wrap = card.querySelector(".bc-fight-avatar-wrap");
    if (!wrap) return;
    var hasMono = !!wrap.querySelector(".bc-fight-mono");
    var wantMono = !!(r.isFocus && pilotMarkUrl);
    if (hasMono === wantMono) return;
    var posKeep = wrap.querySelector(".bc-fight-pos");
    var posHtml = posKeep ? posKeep.outerHTML : "";
    wrap.innerHTML = fightAvatarHtml(r) + posHtml;
  }

  function renderFightRows(pack) {
    if (!elFightRows || !pack) return;
    var order = pack.rows.map(function (r) {
      return r.key;
    });
    var structureChanged = !fightOrdersEqual(fightPrevOrder, order);
    var swapped = Object.create(null);

    if (structureChanged && fightPrevOrder.length) {
      pack.rows.forEach(function (r) {
        var prev = fightPrevOrder.indexOf(r.key);
        var now = order.indexOf(r.key);
        if (prev >= 0 && now >= 0 && now !== prev) {
          if (now < prev) swapped[r.key] = "up";
          else swapped[r.key] = "down";
        }
      });
    }

    if (elFightTitle) {
      var title =
        "BATTLE FOR P" + (pack.contestedPos != null ? pack.contestedPos : "—");
      if (elFightTitle.textContent !== title) elFightTitle.textContent = title;
    }

    var seps = stabilizeFightSeps(pack.seps, structureChanged);

    // Same drivers/order: update text only — never recreate mono/helmet.
    if (!structureChanged && elFightRows.querySelector("[data-fight-key]")) {
      var cards = elFightRows.querySelectorAll(".bc-fight-card");
      var sepEls = elFightRows.querySelectorAll(".bc-fight-sep");
      var idx;
      for (idx = 0; idx < pack.rows.length; idx++) {
        if (cards[idx]) paintFightCard(cards[idx], pack.rows[idx]);
      }
      for (idx = 0; idx < seps.length; idx++) {
        if (!sepEls[idx]) continue;
        var side = paintFightSepEl(sepEls[idx], seps[idx], !!(fightDispSide && fightDispSide[idx]));
        if (!fightDispSide) fightDispSide = [];
        fightDispSide[idx] = side;
      }
      fightPrevOrder = order;
      return;
    }

    var firstRects = Object.create(null);
    if (structureChanged && fightPrevOrder.length) {
      elFightRows.querySelectorAll("[data-fight-key]").forEach(function (node) {
        var key = node.getAttribute("data-fight-key");
        if (!key) return;
        firstRects[key] = node.getBoundingClientRect();
      });
    }

    var html = "";
    pack.rows.forEach(function (r, rowIdx) {
      if (rowIdx > 0) {
        html += fightSepHtml(seps[rowIdx - 1], !!(fightDispSide && fightDispSide[rowIdx - 1]));
      }
      var swap =
        swapped[r.key] === "up"
          ? " is-swap-up"
          : swapped[r.key] === "down"
            ? " is-swap-down"
            : "";
      html += fightCardHtml(r, swap);
    });
    elFightRows.innerHTML = html;
    fightPrevOrder = order;
    fightDispSide = seps.map(function (ms, sIdx) {
      return fightGapIsSide(ms, !!(fightDispSide && fightDispSide[sIdx]));
    });

    if (structureChanged && Object.keys(firstRects).length) {
      fightAnimating = true;
      elFightRows.querySelectorAll("[data-fight-key]").forEach(function (node) {
        var key = node.getAttribute("data-fight-key");
        var first = key ? firstRects[key] : null;
        if (!first) return;
        var last = node.getBoundingClientRect();
        var dx = first.left - last.left;
        if (Math.abs(dx) < 1) return;
        node.classList.add("is-flipping");
        node.style.transition = "none";
        node.style.transform = "translateX(" + dx + "px)";
        void node.offsetWidth;
        node.style.transition = "transform " + FIGHT_SWAP_MS + "ms cubic-bezier(0.22, 1, 0.36, 1)";
        node.style.transform = "translateX(0)";
      });
      if (fightFlashTimer) window.clearTimeout(fightFlashTimer);
      fightFlashTimer = window.setTimeout(function () {
        fightAnimating = false;
        if (!elFightRows) return;
        elFightRows.querySelectorAll(".bc-fight-card").forEach(function (el) {
          el.style.transition = "";
          el.style.transform = "";
          el.classList.remove("is-swap-up", "is-swap-down", "is-flipping");
        });
      }, FIGHT_SWAP_MS + 40);
    }
  }

  function updateFightPanel(tick, standings) {
    if (!battlePanelEnabled || !elFight) return;
    if (!battleEligibleFromTick(tick)) {
      if (battleActive) {
        battleActive = false;
        battleStreak = 0;
        hideFightPanel();
        directorLog("INFO", "fight panel off (session not eligible)");
      } else {
        battleStreak = 0;
      }
      return;
    }
    var nearSf = focusNearStartFinish(tick, standings);
    var sample = sampleFightGaps(tick);
    var arm = !nearSf && fightShouldArm(sample);
    var hold = nearSf || fightShouldHold(sample);
    var now = fightNow();

    if (nearSf && !battleActive) {
      battleStreak = 0;
      return;
    }

    if (battleActive) {
      if (!hold) {
        if (!battleFarSince) battleFarSince = now;
        if (now - battleFarSince >= battleLeaveMs) {
          battleActive = false;
          battleStreak = 0;
          hideFightPanel();
          directorLog("INFO", "fight panel off (gaps > keep for " + battleLeaveMs + "ms)");
          return;
        }
      } else {
        battleFarSince = 0;
      }
    } else {
      battleFarSince = 0;
      battleEmptySince = 0;
      if (arm) battleStreak += 1;
      else battleStreak = 0;
      if (battleStreak >= battleTicksNeed) {
        battleActive = true;
        battleStreak = 0;
        fightStickyKeys = Object.create(null);
        fightLeaveAt = Object.create(null);
        fightDroppedKeys = Object.create(null);
        setFightOn(true);
        directorLog(
          "INFO",
          "fight panel on includeMs=" +
            battleIncludeMs +
            " keepMs=" +
            battleKeepMs +
            " leaveMs=" +
            battleLeaveMs
        );
      }
    }

    if (!battleActive) return;
    // Skip DOM rebuild mid-FLIP so the slide can finish cleanly.
    if (fightAnimating) return;
    var pack = buildFightPack(standings, tick.focusCarIdx, battleIncludeMs, battleKeepMs);
    if (!pack || pack.rows.length < 2) {
      if (!battleEmptySince) battleEmptySince = now;
      // Pack already waited leaveMs per-car; dismiss promptly once empty.
      if (now - battleEmptySince >= 400) {
        battleActive = false;
        battleStreak = 0;
        hideFightPanel();
        directorLog("INFO", "fight panel off (pack empty)");
      }
      return;
    }
    battleEmptySince = 0;
    renderFightRows(pack);
  }

  function findRaceBest(standings) {
    var best = null;
    var i;
    var rows = Array.isArray(standings) ? standings : [];
    for (i = 0; i < rows.length; i++) {
      var r = rows[i];
      var ms = r && r.bestLapMs;
      if (ms == null || !Number.isFinite(Number(ms)) || Number(ms) <= 0) continue;
      ms = Number(ms);
      if (!best || ms < best.ms) {
        best = {
          ms: ms,
          name: r.name || "—",
          carNumber: r.carNumber || "",
          countryCode: r.countryCode || null,
          country: r.country || null,
          isFocus: !!r.isFocus,
        };
      }
    }
    return best;
  }

  function updateRaceBestPanel(standings) {
    if (!raceBestEnabled || !elBest) return;
    var best = findRaceBest(standings);
    if (!best) {
      elBest.hidden = true;
      elBest.setAttribute("hidden", "");
      elBest.setAttribute("aria-hidden", "true");
      elBest.classList.remove("is-on", "is-hot");
      return;
    }
    elBest.hidden = false;
    elBest.removeAttribute("hidden");
    elBest.setAttribute("aria-hidden", "false");
    elBest.classList.add("is-on");
    if (elBestTime) {
      var timeTxt = fmtLap(best.ms);
      if (elBestTime.textContent !== timeTxt) elBestTime.textContent = timeTxt;
    }
    if (elBestDriver) {
      var flag = flagSpanHtml(best.countryCode, best.country);
      var html =
        (flag ? '<span class="bc-best-flag">' + flag + "</span>" : "") +
        '<span class="bc-best-num">#' +
        (best.carNumber || "—") +
        "</span>" +
        '<span class="bc-best-name">' +
        shortDriverName(best.name) +
        "</span>";
      if (elBestDriver.innerHTML !== html) elBestDriver.innerHTML = html;
      elBestDriver.classList.toggle("is-focus", !!best.isFocus);
    }
    if (raceBestMs != null && best.ms < raceBestMs - 0.5) {
      elBest.classList.add("is-hot");
      if (raceBestFlashTimer) window.clearTimeout(raceBestFlashTimer);
      raceBestFlashTimer = window.setTimeout(function () {
        if (elBest) elBest.classList.remove("is-hot");
      }, 2200);
    }
    raceBestMs = best.ms;
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
    var flagHost = el.querySelector(".bc-lb-flag");
    if (flagHost) {
      var flagHtml = flagSpanHtml(r.countryCode, r.country);
      if (flagHtml) {
        if (flagHost.innerHTML !== flagHtml) flagHost.innerHTML = flagHtml;
        flagHost.hidden = false;
        flagHost.removeAttribute("hidden");
      } else {
        flagHost.innerHTML = "";
        flagHost.hidden = true;
        flagHost.setAttribute("hidden", "");
      }
    }
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
        '<span class="bc-lb-flag" hidden aria-hidden="true"></span>' +
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
    var flag = flagSpanHtml(r.countryCode, r.country || club);
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
      (flag ? flag + " " : "") +
      (r.name || "—") +
      "</span>" +
      (club && !flag ? '<span class="bc-ticker-club">' + club + "</span>" : "") +
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

    applyFlagBanner(flag);

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
    updateFightPanel(tick, standings);
    updateRaceBestPanel(standings);

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
    setStatus("SHOWCASE FIXTURE…");
    fetch(showcaseTickUrl())
      .then(function (r) {
        if (!r.ok) throw new Error("HTTP " + r.status);
        return r.json();
      })
      .then(function (msg) {
        if (!msg || msg.type !== "telemetry.tick") throw new Error("bad fixture");
        root.dataset.state = "live";
        setStatus("SHOWCASE");
        render(msg);
      })
      .catch(function (err) {
        root.dataset.state = "error";
        setStatus("SHOWCASE FIXTURE FAIL");
        directorLog("WARN", "showcase fixture: " + (err && err.message ? err.message : err));
      });
    return true;
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
      // Drop any standings/hero left from a previous WS lifetime (long-lived
      // bridge, missed session_reset, or Browser Source that never reloaded).
      clearSessionOverlayState("ws_open");
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
      } else if (msg.type === "telemetry.session_reset") {
        root.dataset.state = "live";
        clearSessionOverlayState(msg.reason);
      } else if (msg.type === "telemetry.status" && msg.connected === false) {
        root.dataset.state = "idle";
        setStatus("SIM DISCONNECTED");
        clearMomentLayer();
        clearBoardAndFightState();
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

  if (!loadShowcaseFixture()) {
    connect();
  }
})();
