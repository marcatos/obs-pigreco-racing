/**
 * Broadcast director domain (P3-06): hero queue + moment labels.
 * No DOM / WebSocket. Overlay adapter: broadcast.js
 */
(function attachBroadcastDirector(root) {
  function formatMomentLabel(item) {
    if (!item || !item.kind) return "";
    var payload = item.payload || {};
    var label = String(item.kind).replace("_", " ").toUpperCase();
    if (item.kind === "flag_change") label = String(payload.flag || "").toUpperCase();
    if (item.kind === "overtake") label = "OVERTAKE P" + (payload.toPos || "");
    if (item.kind === "fast_lap") label = "FASTEST";
    if (item.kind === "battle") label = "BATTLE";
    if (item.kind === "pit") label = "PIT " + String(payload.state || "").toUpperCase();
    if (item.kind === "session_end") label = String(payload.flag || "FINISH").toUpperCase();
    return label;
  }

  function enqueueEvent(state, ev, director) {
    var hero = state && state.hero ? state.hero : null;
    var queue = (state && Array.isArray(state.queue) ? state.queue : []).slice();
    if (director !== "auto") return { hero: hero, queue: queue };
    if (!ev || !ev.kind) return { hero: hero, queue: queue };
    var item = {
      kind: ev.kind,
      priority: Number(ev.priority) || 0,
      ttlMs: Number(ev.ttlMs) || 4000,
      payload: ev.payload || {},
    };
    if (hero && item.priority <= hero.priority) {
      if (queue.length < 2) queue.push(item);
      queue.sort(function (a, b) {
        return b.priority - a.priority;
      });
      return { hero: hero, queue: queue };
    }
    if (hero && item.priority > hero.priority) {
      queue.unshift(hero);
      if (queue.length > 2) queue.length = 2;
    }
    return { hero: item, queue: queue };
  }

  function clearDirectorState(state) {
    return { hero: null, queue: [] };
  }

  /**
   * CONTRACT: gapAheadMs is 0 when leading (no car ahead). That must not
   * count as a doorstop/close battle gap — otherwise P1 never drops BATTLE.
   */
  function isActiveGapMs(ms) {
    return ms != null && Number.isFinite(Number(ms)) && Number(ms) > 0;
  }

  function fightGapsArm(sample, opts) {
    sample = sample || {};
    opts = opts || {};
    var door = Number(opts.doorstopMs);
    var engage = Number(opts.engageMs);
    var rate = Number(opts.closeRate);
    if (!Number.isFinite(door)) door = 110;
    if (!Number.isFinite(engage)) engage = 850;
    if (!Number.isFinite(rate)) rate = 280;
    if (isActiveGapMs(sample.ga) && sample.ga <= door) return true;
    if (isActiveGapMs(sample.gb) && sample.gb <= door) return true;
    var catchAhead =
      isActiveGapMs(sample.ga) &&
      sample.ga <= engage &&
      Number(sample.closeAhead) >= rate;
    var catchBehind =
      isActiveGapMs(sample.gb) &&
      sample.gb <= engage &&
      Number(sample.closeBehind) >= rate;
    return !!(catchAhead || catchBehind);
  }

  function fightGapsHold(sample, exitMs) {
    sample = sample || {};
    var exit = Number(exitMs);
    if (!Number.isFinite(exit)) exit = 400;
    return (
      (isActiveGapMs(sample.ga) && sample.ga <= exit) ||
      (isActiveGapMs(sample.gb) && sample.gb <= exit)
    );
  }

  root.PigrecoBroadcastDirector = {
    formatMomentLabel: formatMomentLabel,
    enqueueEvent: enqueueEvent,
    clearDirectorState: clearDirectorState,
    isActiveGapMs: isActiveGapMs,
    fightGapsArm: fightGapsArm,
    fightGapsHold: fightGapsHold,
  };
})(typeof globalThis !== "undefined" ? globalThis : this);
