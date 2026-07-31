/**
 * Session type badge — config: sessionType, sessionLabel
 */
(function initSessionBadge() {
  const el = document.querySelector("[data-session-badge]");
  if (!el) return;

  const cfg = window.PIGRECO_CONFIG || {};
  if (cfg.sessionBadgeEnabled === false) {
    el.hidden = true;
    return;
  }

  const map = {
    practice: "PRACTICE",
    quali: "QUALIFYING",
    qualifying: "QUALIFYING",
    race: "RACE",
    cooldown: "COOLDOWN",
    custom: (cfg.sessionLabel || "SESSION").toUpperCase(),
  };

  const key = String(cfg.sessionType || "race").toLowerCase();
  const text =
    (cfg.sessionLabel && String(cfg.sessionLabel).trim()) ||
    map[key] ||
    map.race;

  el.hidden = false;
  el.dataset.session = key;
  const value = el.querySelector("[data-session-value]") || el;
  value.textContent = text;
})();
