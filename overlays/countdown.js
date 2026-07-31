/**
 * Starting Soon countdown — config: goLiveAt | countdownSeconds
 */
(function initCountdown() {
  const el = document.querySelector("[data-countdown]");
  if (!el) return;

  const cfg = window.PIGRECO_CONFIG || {};
  if (cfg.countdownEnabled === false) {
    el.hidden = true;
    return;
  }

  const display = el.querySelector("[data-countdown-value]") || el;
  const labelEl = el.querySelector("[data-countdown-label]");

  function parseTarget() {
    if (cfg.goLiveAt) {
      const raw = String(cfg.goLiveAt).trim();
      // HH:MM today (local)
      if (/^\d{1,2}:\d{2}$/.test(raw)) {
        const [h, m] = raw.split(":").map(Number);
        const d = new Date();
        d.setHours(h, m, 0, 0);
        if (d.getTime() <= Date.now()) d.setDate(d.getDate() + 1);
        return d;
      }
      const d = new Date(raw);
      if (!Number.isNaN(d.getTime())) return d;
    }
    const secs = Number(cfg.countdownSeconds);
    if (Number.isFinite(secs) && secs > 0) {
      return new Date(Date.now() + secs * 1000);
    }
    return null;
  }

  const target = parseTarget();
  if (!target) {
    el.hidden = true;
    return;
  }

  el.hidden = false;
  if (labelEl) labelEl.textContent = cfg.countdownLabel || "SI PARTE TRA";

  function fmt(ms) {
    const total = Math.max(0, Math.floor(ms / 1000));
    const h = Math.floor(total / 3600);
    const m = Math.floor((total % 3600) / 60);
    const s = total % 60;
    if (h > 0) {
      return (
        String(h).padStart(2, "0") +
        ":" +
        String(m).padStart(2, "0") +
        ":" +
        String(s).padStart(2, "0")
      );
    }
    return String(m).padStart(2, "0") + ":" + String(s).padStart(2, "0");
  }

  function tick() {
    const left = target.getTime() - Date.now();
    if (left <= 0) {
      display.textContent = "00:00";
      el.classList.add("is-zero");
      if (labelEl) labelEl.textContent = cfg.countdownDoneLabel || "IN DIRETTA";
      return;
    }
    display.textContent = fmt(left);
    window.setTimeout(tick, 250);
  }

  tick();
})();
