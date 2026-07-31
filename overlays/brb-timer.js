/**
 * BRB return-time timer — config: brbUntil (HH:MM | ISO)
 * Shows "Torno alle HH:MM" + optional countdown (reuse .countdown styles).
 */
(function initBrbTimer() {
  const el = document.querySelector("[data-brb-timer]");
  if (!el) return;

  const cfg = window.PIGRECO_CONFIG || {};
  const untilRaw = cfg.brbUntil != null ? String(cfg.brbUntil).trim() : "";
  if (!untilRaw) {
    el.hidden = true;
    return;
  }

  function parseTarget(raw) {
    if (/^\d{1,2}:\d{2}$/.test(raw)) {
      const [h, m] = raw.split(":").map(Number);
      const d = new Date();
      d.setHours(h, m, 0, 0);
      if (d.getTime() <= Date.now()) d.setDate(d.getDate() + 1);
      return d;
    }
    const d = new Date(raw);
    if (!Number.isNaN(d.getTime())) return d;
    return null;
  }

  const target = parseTarget(untilRaw);
  if (!target) {
    el.hidden = true;
    return;
  }

  const returnEl = el.querySelector("[data-brb-return]");
  const countdownWrap = el.querySelector("[data-brb-countdown]");
  const countdownValue =
    (countdownWrap && countdownWrap.querySelector("[data-brb-countdown-value]")) ||
    el.querySelector("[data-brb-countdown-value]");
  const countdownLabel = el.querySelector("[data-brb-countdown-label]");

  const hh = String(target.getHours()).padStart(2, "0");
  const mm = String(target.getMinutes()).padStart(2, "0");
  const prefix = (cfg.brbReturnLabel || "TORNO ALLE").trim();
  if (returnEl) returnEl.textContent = prefix + " " + hh + ":" + mm;

  el.hidden = false;

  const showCountdown = cfg.brbShowCountdown !== false;
  if (!showCountdown || !countdownWrap || !countdownValue) {
    if (countdownWrap) countdownWrap.hidden = true;
    return;
  }

  countdownWrap.hidden = false;
  if (countdownLabel) {
    countdownLabel.textContent = cfg.brbCountdownLabel || "RITORNO TRA";
  }

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
      countdownValue.textContent = "00:00";
      countdownWrap.classList.add("is-zero");
      if (countdownLabel) {
        countdownLabel.textContent = cfg.brbCountdownDoneLabel || "STO TORNANDO";
      }
      if (returnEl) {
        returnEl.textContent = cfg.brbCountdownDoneLabel || "STO TORNANDO";
      }
      return;
    }
    countdownValue.textContent = fmt(left);
    window.setTimeout(tick, 250);
  }

  tick();
})();
