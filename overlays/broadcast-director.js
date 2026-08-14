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

  root.PigrecoBroadcastDirector = {
    formatMomentLabel: formatMomentLabel,
    enqueueEvent: enqueueEvent,
  };
})(typeof globalThis !== "undefined" ? globalThis : this);
