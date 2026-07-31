/**
 * Ending CTA — Discord QR + follow line from config
 */
(function initEndingCta() {
  const root = document.querySelector("[data-ending-cta]");
  if (!root) return;

  const cfg = window.PIGRECO_CONFIG || {};
  if (cfg.endingCtaEnabled === false) {
    root.hidden = true;
    return;
  }

  const invite = (cfg.discordInviteUrl || "").trim();
  const qrPath = (cfg.discordQrImage || "assets/qr-discord.png").trim();
  const cta = (cfg.endingCtaText || "Entra nel Discord del team").trim();
  const follow = (cfg.endingFollowText || "").trim();

  const qrImg = root.querySelector("[data-ending-qr]");
  const ctaEl = root.querySelector("[data-ending-cta-text]");
  const followEl = root.querySelector("[data-ending-follow]");
  const linkEl = root.querySelector("[data-ending-discord-link]");

  if (qrImg) {
    if (qrPath) qrImg.src = qrPath;
    else if (invite) {
      qrImg.src =
        "https://api.qrserver.com/v1/create-qr-code/?size=200x200&bgcolor=080A0C&color=00C400&data=" +
        encodeURIComponent(invite);
    } else {
      qrImg.hidden = true;
    }
  }

  if (ctaEl) ctaEl.textContent = cta;
  if (followEl) {
    if (follow) followEl.textContent = follow;
    else if (cfg.twitchHandle) followEl.textContent = "Segui " + cfg.twitchHandle + " su Twitch";
  }
  if (linkEl && invite) {
    linkEl.textContent = invite.replace(/^https?:\/\//, "");
    linkEl.href = invite;
  }

  root.hidden = false;
})();
