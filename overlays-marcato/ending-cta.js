/**
 * Ending socials — Twitch + YouTube with shared handle (SenorMarcato).
 */
(function initEndingCta() {
  const root = document.querySelector("[data-ending-cta]");
  if (!root) return;

  const cfg = window.PIGRECO_CONFIG || {};
  if (cfg.endingCtaEnabled === false) {
    root.hidden = true;
    return;
  }

  let handle = (cfg.socialHandle || cfg.twitchHandle || "SenorMarcato").trim();
  handle = handle.replace(/^@/, "");
  if (!handle) handle = "SenorMarcato";

  root.querySelectorAll(".ending-social-handle").forEach((el) => {
    el.textContent = handle;
  });

  root.hidden = false;
})();
