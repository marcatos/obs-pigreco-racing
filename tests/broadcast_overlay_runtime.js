/**
 * Runtime harness for overlays/broadcast.js (Task 7 review locks).
 * Fake DOM + clock + WebSocket; no browser.
 */
"use strict";

const fs = require("fs");
const path = require("path");
const vm = require("vm");

const ROOT = path.resolve(__dirname, "..");
const NO_WIDGET = ["no-leaderboard", "no-relative", "no-focus", "no-session"];

function assert(cond, msg) {
  if (!cond) throw new Error(msg || "assert failed");
}
function assertEq(a, b, msg) {
  if (a !== b) {
    throw new Error((msg || "assertEq") + ": " + JSON.stringify(a) + " !== " + JSON.stringify(b));
  }
}

function createClock() {
  var now = 1e12;
  var nextId = 1;
  var timers = [];
  function setTimeoutFn(fn, ms) {
    var id = nextId++;
    timers.push({ id: id, at: now + Number(ms) || 0, fn: fn, interval: 0 });
    return id;
  }
  function setIntervalFn(fn, ms) {
    var id = nextId++;
    var step = Number(ms) || 0;
    timers.push({ id: id, at: now + step, fn: fn, interval: step });
    return id;
  }
  function clearTimeoutFn(id) {
    timers = timers.filter(function (t) {
      return t.id !== id;
    });
  }
  function advance(ms) {
    var target = now + ms;
    var guard = 0;
    while (guard++ < 10000) {
      var due = timers.filter(function (t) {
        return t.at <= target;
      });
      if (!due.length) {
        now = target;
        return;
      }
      due.sort(function (a, b) {
        return a.at - b.at || a.id - b.id;
      });
      var t = due[0];
      now = t.at;
      if (t.interval) t.at = now + t.interval;
      else {
        timers = timers.filter(function (x) {
          return x.id !== t.id;
        });
      }
      t.fn();
    }
    throw new Error("clock advance loop exceeded");
  }
  return {
    now: function () {
      return now;
    },
    setTimeout: setTimeoutFn,
    setInterval: setIntervalFn,
    clearTimeout: clearTimeoutFn,
    clearInterval: clearTimeoutFn,
    advance: advance,
  };
}

function createClassList() {
  var set = new Set();
  return {
    add: function (c) {
      set.add(c);
    },
    remove: function (c) {
      set.delete(c);
    },
    toggle: function (c, force) {
      if (arguments.length > 1) {
        if (force) set.add(c);
        else set.delete(c);
      } else if (set.has(c)) set.delete(c);
      else set.add(c);
      return set.has(c);
    },
    contains: function (c) {
      return set.has(c);
    },
    toArray: function () {
      return Array.from(set);
    },
  };
}

function createEl() {
  return {
    hidden: false,
    innerHTML: "",
    textContent: "",
    dataset: {},
    classList: createClassList(),
    getAttribute: function () {
      return "";
    },
    setAttribute: function () {},
  };
}

function loadOverlay(opts) {
  opts = opts || {};
  var clock = createClock();
  var els = {
    root: createEl(),
    session: createEl(),
    lb: createEl(),
    rel: createEl(),
    focus: createEl(),
    banner: createEl(),
    status: createEl(),
    moment: createEl(),
  };
  els.moment.hidden = true;
  els.root.hidden = true;
  var bySel = {
    "[data-broadcast-root]": els.root,
    "[data-bc-session]": els.session,
    "[data-bc-lb-rows]": els.lb,
    "[data-bc-rel-rows]": els.rel,
    "[data-bc-focus]": els.focus,
    "[data-bc-flag-banner]": els.banner,
    "[data-bc-status]": els.status,
    "[data-bc-moment]": els.moment,
  };
  els.root.querySelector = function (sel) {
    return bySel[sel] || null;
  };

  var wsInst = null;
  function FakeWebSocket() {
    wsInst = this;
    this._listeners = {};
  }
  FakeWebSocket.prototype.addEventListener = function (type, fn) {
    this._listeners[type] = this._listeners[type] || [];
    this._listeners[type].push(fn);
  };
  FakeWebSocket.prototype.close = function () {};

  var RealDate = Date;
  function FakeDate() {
    if (!(this instanceof FakeDate)) return new FakeDate();
    return new RealDate(clock.now());
  }
  FakeDate.now = function () {
    return clock.now();
  };
  FakeDate.parse = RealDate.parse;
  FakeDate.UTC = RealDate.UTC;

  var cfg = Object.assign(
    {
      telemetryEnabled: true,
      broadcastDirector: opts.director || "auto",
      broadcastDirectorSensitivity: "normal",
      telemetryWsUrl: "ws://127.0.0.1:8765",
    },
    opts.config || {}
  );

  var sandbox = {
    console: console,
    Date: FakeDate,
    performance: {
      now: function () {
        return 0;
      },
    },
    WebSocket: FakeWebSocket,
    document: {
      querySelector: function (sel) {
        return bySel[sel] || null;
      },
    },
    PIGRECO_CONFIG: cfg,
  };
  sandbox.window = sandbox;
  sandbox.globalThis = sandbox;
  sandbox.setTimeout = clock.setTimeout;
  sandbox.setInterval = clock.setInterval;
  sandbox.clearTimeout = clock.clearTimeout;
  sandbox.clearInterval = clock.clearInterval;

  vm.createContext(sandbox);
  if (opts.withDirector !== false) {
    vm.runInContext(fs.readFileSync(path.join(ROOT, "overlays", "broadcast-director.js"), "utf8"), sandbox);
  }
  vm.runInContext(fs.readFileSync(path.join(ROOT, "overlays", "broadcast.js"), "utf8"), sandbox);

  function emit(type, ev) {
    var list = (wsInst && wsInst._listeners[type]) || [];
    list.forEach(function (fn) {
      fn(ev);
    });
  }

  return {
    els: els,
    clock: clock,
    send: function (msg) {
      emit("message", { data: JSON.stringify(msg) });
    },
  };
}

function testAutoDoesNotHideWidgetsViaDirector() {
  var ctx = loadOverlay({ withDirector: true, director: "auto" });
  ctx.send({ type: "telemetry.tick", flag: "yellow", standings: [], relatives: [] });
  ctx.send({
    type: "telemetry.event",
    kind: "flag_change",
    priority: 100,
    ttlMs: 4000,
    payload: { flag: "yellow" },
  });
  NO_WIDGET.forEach(function (cls) {
    assert(!ctx.els.root.classList.contains(cls), "auto+director must not add " + cls);
  });

  var toggled = loadOverlay({
    withDirector: true,
    director: "auto",
    config: { broadcastLeaderboard: false },
  });
  assert(toggled.els.root.classList.contains("no-leaderboard"), "config toggle still adds no-leaderboard");
  assert(!toggled.els.root.classList.contains("no-relative"), "untoggled widgets stay visible");
}

function testMissingDirectorAppliesTickBanner() {
  var ctx = loadOverlay({ withDirector: false, director: "auto" });
  ctx.send({ type: "telemetry.tick", flag: "yellow", standings: [], relatives: [] });
  assert(ctx.els.banner.classList.contains("is-on"), "missing Director still applies tick-driven flag banner");
  assertEq(ctx.els.banner.dataset.flag, "yellow", "banner dataset.flag from tick");

  ctx.send({
    type: "telemetry.event",
    kind: "flag_change",
    priority: 100,
    ttlMs: 4000,
    payload: { flag: "red" },
  });
  assertEq(ctx.els.banner.dataset.flag, "yellow", "missing Director enqueueEvent is a no-op");
}

function testAutoUsesEventPathForBannerWhenDirectorPresent() {
  var ctx = loadOverlay({ withDirector: true, director: "auto" });
  ctx.send({ type: "telemetry.tick", flag: "yellow", standings: [], relatives: [] });
  assert(!ctx.els.banner.classList.contains("is-on"), "auto+Director does not apply tick-driven banner");
  ctx.send({
    type: "telemetry.event",
    kind: "flag_change",
    priority: 100,
    ttlMs: 4000,
    payload: { flag: "yellow" },
  });
  assert(ctx.els.banner.classList.contains("is-on"), "auto+Director applies banner from flag_change event");
  assertEq(ctx.els.banner.dataset.flag, "yellow");
}

function testHeroExitRaceKeepsNewChip() {
  var ctx = loadOverlay({ withDirector: true, director: "auto" });
  ctx.send({
    type: "telemetry.event",
    kind: "battle",
    priority: 60,
    ttlMs: 500,
    payload: {},
  });
  assert(ctx.els.moment.innerHTML.indexOf("BATTLE") !== -1, "battle chip shown");
  assertEq(ctx.els.moment.hidden, false);

  ctx.clock.advance(500);
  assert(ctx.els.moment.classList.contains("is-exit"), "exit animation started");

  ctx.send({
    type: "telemetry.event",
    kind: "flag_change",
    priority: 100,
    ttlMs: 4000,
    payload: { flag: "yellow" },
  });
  assert(ctx.els.moment.innerHTML.indexOf("YELLOW") !== -1, "new hero chip during exit window");
  assertEq(ctx.els.moment.hidden, false);

  ctx.clock.advance(250);
  assertEq(ctx.els.moment.hidden, false, "pending exit must not hide the new hero");
  assert(ctx.els.moment.innerHTML.indexOf("YELLOW") !== -1, "new hero chip remains after 200ms");
  assert(ctx.els.moment.innerHTML.indexOf("bc-moment-chip") !== -1, "chip markup remains");
}

testAutoDoesNotHideWidgetsViaDirector();
testMissingDirectorAppliesTickBanner();
testAutoUsesEventPathForBannerWhenDirectorPresent();
testHeroExitRaceKeepsNewChip();
console.log("ok");
