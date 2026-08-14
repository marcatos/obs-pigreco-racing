/**
 * Rotatore sponsor per overlay live.
 * Modes via data-sponsor-rotator:
 *   (default) discrete top-left: show → gap → next
 *   "cam-bar" continuous bottom bar: cycle every displayMs (default 5s)
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

  const mode = (mount.getAttribute("data-sponsor-rotator") || "").trim() || "discrete";
  const isCamBar = mode === "cam-bar";
  const displayMs = Number(cfg.sponsorDisplayMs) || (isCamBar ? 5000 : 8000);
  const gapMs = Number.isFinite(Number(cfg.sponsorGapMs))
    ? Number(cfg.sponsorGapMs)
    : isCamBar
      ? 0
      : 18000;
  const fadeMs = Number(cfg.sponsorFadeMs) || (isCamBar ? 400 : 700);

  mount.innerHTML = "";
  mount.hidden = false;
  mount.style.setProperty("--sponsor-fade-ms", fadeMs + "ms");

  const frame = document.createElement("div");
  frame.className = "sponsor-logo-frame";

  const img = document.createElement("img");
  img.className = "sponsor-logo";
  img.alt = "";
  img.decoding = "async";
  frame.appendChild(img);

  let nameEl = null;
  if (isCamBar) {
    nameEl = document.createElement("span");
    nameEl.className = "cam-sponsor-name";
    mount.appendChild(frame);
    mount.appendChild(nameEl);
  } else {
    const label = document.createElement("span");
    label.className = "sponsor-label";
    label.textContent = cfg.sponsorLabel || "PARTNER";
    mount.appendChild(label);
    mount.appendChild(frame);
  }

  let index = 0;

  function applySponsor(i) {
    const s = sponsors[i % sponsors.length];
    img.src = s.src;
    img.alt = s.name || "Sponsor";
    mount.dataset.sponsor = s.name || "";
    if (nameEl) {
      const label = (s.name || "").trim();
      nameEl.textContent = label;
      nameEl.hidden = !label;
    }
  }

  if (isCamBar) {
    applySponsor(0);
    if (sponsors.length < 2) return;

    function advance() {
      mount.classList.add("is-fading");
      window.setTimeout(() => {
        index = (index + 1) % sponsors.length;
        applySponsor(index);
        mount.classList.remove("is-fading");
      }, fadeMs);
    }

    const initialDelay = Number(cfg.sponsorInitialDelayMs);
    const startAt = Number.isFinite(initialDelay) ? Math.max(0, initialDelay) : 0;
    window.setTimeout(() => {
      window.setInterval(advance, displayMs);
    }, startAt);
    return;
  }

  let visible = false;

  function show(i) {
    applySponsor(i);
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

  const initialDelay = Number(cfg.sponsorInitialDelayMs);
  window.setTimeout(tick, Number.isFinite(initialDelay) ? initialDelay : 12000);
})();
