(function initEndingCta() {
  const root = document.querySelector("[data-ending-cta]");
  if (!root) return;
  const cfg = window.PIGRECO_CONFIG || {};
  if (cfg.endingCtaEnabled === false) {
    root.hidden = true;
    return;
  }
  const ctaEl = root.querySelector("[data-ending-cta-text]");
  const followEl = root.querySelector("[data-ending-follow]");
  if (ctaEl) ctaEl.textContent = (cfg.endingCtaText || "Segui su Twitch").trim();
  if (followEl) {
    followEl.textContent = (cfg.endingFollowText || ("Segui " + (cfg.twitchHandle || "") + " su Twitch")).trim();
  }
  const qr = root.querySelector("[data-ending-qr]");
  if (qr) qr.hidden = true;
  root.hidden = false;
})();
