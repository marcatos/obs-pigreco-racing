/**
 * Rotatore sponsor discreto per overlay live.
 * Config: window.PIGRECO_CONFIG.sponsors (+ timings).
 */
(function initSponsorRotator() {
  const mount = document.querySelector("[data-sponsor-rotator]");
  if (!mount) return;

  const cfg = window.PIGRECO_CONFIG || {};
  if (cfg.sponsorsEnabled === false) {
    mount.hidden = true;
    return;
  }

  const sponsors = Array.isArray(cfg.sponsors)
    ? cfg.sponsors.filter((s) => s && s.src)
    : [];
  if (!sponsors.length) {
    mount.hidden = true;
    return;
  }

  const displayMs = Number(cfg.sponsorDisplayMs) || 8000;
  const gapMs = Number(cfg.sponsorGapMs) || 18000;
  const fadeMs = Number(cfg.sponsorFadeMs) || 700;

  mount.innerHTML = "";
  mount.hidden = false;
  mount.style.setProperty("--sponsor-fade-ms", fadeMs + "ms");

  const label = document.createElement("span");
  label.className = "sponsor-label";
  label.textContent = cfg.sponsorLabel || "PARTNER";

  const frame = document.createElement("div");
  frame.className = "sponsor-logo-frame";

  const img = document.createElement("img");
  img.className = "sponsor-logo";
  img.alt = "";
  img.decoding = "async";

  frame.appendChild(img);
  mount.appendChild(label);
  mount.appendChild(frame);

  let index = 0;
  let visible = false;

  function show(i) {
    const s = sponsors[i % sponsors.length];
    img.src = s.src;
    img.alt = s.name || "Sponsor";
    mount.dataset.sponsor = s.name || "";
    mount.classList.add("is-visible");
    visible = true;
  }

  function hide() {
    mount.classList.remove("is-visible");
    visible = false;
  }

  function tick() {
    if (!visible) {
      show(index);
      index = (index + 1) % sponsors.length;
      window.setTimeout(tick, displayMs);
      return;
    }
    hide();
    window.setTimeout(tick, gapMs);
  }

  // Prima apparizione dopo un breve delay (non subito a scene switch)
  const initialDelay = Number(cfg.sponsorInitialDelayMs);
  window.setTimeout(tick, Number.isFinite(initialDelay) ? initialDelay : 12000);
})();
