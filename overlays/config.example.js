/* =============================================================================
 * PiGreco Racing — CONFIG STREAMER
 * ---------------------------------------------------------------------------
 * 1) Copia questo file come config.js  (oppure modifica direttamente config.js)
 * 2) Compila i campi QUI SOTTO
 * 3) In OBS, su ogni Browser Source: tasto destro → Refresh cache of current page
 *
 * Override opzionali via URL:
 *   live-chrome.html?username=MioNick&eventTitle=Night%20Race
 * ============================================================================= */

window.PIGRECO_CONFIG = {
  username: "tuo_nick",
  pilotName: "Nome Cognome",
  twitchHandle: "@tuo_nick",

  teamName: "PiGreco Racing",
  eventTitle: "Sim Racing Session",
  tagline: "Competizione · Rispetto · Ironia",

  startingMessage: "IN ARRIVO",
  brbMessage: "TORNO SUBITO",
  endingMessage: "GRAZIE PER AVER SEGUITO",
  endingSub: "Ci vediamo alla prossima sessione",

  // --- BRB return timer (lascia vuoto per nascondere) ---
  brbUntil: "", // es. "21:45" oggi (domani se passato) oppure "2026-07-31T21:45:00"
  brbReturnLabel: "TORNO ALLE",
  brbShowCountdown: true, // countdown mm:ss sotto l'orario di ritorno
  brbCountdownLabel: "RITORNO TRA",
  brbCountdownDoneLabel: "STO TORNANDO",

  // --- Sessione / countdown ---
  sessionBadgeEnabled: true,
  sessionType: "race", // practice | quali | race | cooldown | custom
  sessionLabel: "",
  countdownEnabled: true,
  countdownSeconds: 600,
  goLiveAt: "", // es. "21:30" oppure "2026-07-31T21:30:00"
  countdownLabel: "SI PARTE TRA",
  countdownDoneLabel: "IN DIRETTA",

  // --- Ending CTA ---
  endingCtaEnabled: true,
  discordInviteUrl: "https://discord.com/invite/wZ4ZfK9DYy",
  discordQrImage: "assets/qr-discord.png",
  endingCtaText: "Entra nel Discord del team",
  endingFollowText: "",

  // --- Sponsor rotator (Live Race / Live Singolo) ---
  // Appare in alto a sinistra, un logo alla volta, poi scompare per non appesantire lo stream.
  sponsorsEnabled: true,
  sponsorLabel: "PARTNER",
  sponsorDisplayMs: 8000,       // quanto resta a schermo
  sponsorGapMs: 18000,          // pausa prima del prossimo
  sponsorInitialDelayMs: 12000, // attesa dopo ingresso in scena Live
  sponsorFadeMs: 700,
  // Aggiungi/rimuovi voci; metti i file PNG/SVG in overlays/assets/official/
  sponsors: [
    { name: "SimGrid", src: "assets/official/simgrid-white.png" },
    { name: "Tektrama", src: "assets/official/tektrama-white.png" },
    { name: "GoSetups", src: "assets/official/gosetups.png" }
  ],

  // --- Telemetry bridge (P3 — disabled by default; needs mock/real adapter) ---
  telemetryEnabled: false,
  telemetryWsUrl: "ws://127.0.0.1:8765"
};
