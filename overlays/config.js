/* PiGreco Racing — edit these values, then refresh Browser Sources in OBS.
 * See config.example.js for the full template when sharing the pack. */

window.PIGRECO_CONFIG = {
  username: "senormarcato",
  pilotName: "Simone Marcato",
  twitchHandle: "@senormarcato",
  teamName: "PiGreco Racing",
  eventTitle: "Sim Racing Session",
  tagline: "Competizione · Rispetto · Ironia",
  startingMessage: "IN ARRIVO",
  brbMessage: "TORNO SUBITO",
  endingMessage: "GRAZIE PER AVER SEGUITO",
  endingSub: "Ci vediamo alla prossima sessione",

  // --- BRB return timer (vuoto = nascosto) ---
  /** "21:45" oggi (domani se già passato) oppure ISO datetime */
  brbUntil: "",
  brbReturnLabel: "TORNO ALLE",
  brbShowCountdown: true,
  brbCountdownLabel: "RITORNO TRA",
  brbCountdownDoneLabel: "STO TORNANDO",

  // --- Sessione / countdown ---
  sessionBadgeEnabled: true,
  /** practice | quali | race | cooldown | custom */
  sessionType: "race",
  sessionLabel: "",
  countdownEnabled: true,
  /** Secondi da ora (usato se goLiveAt è vuoto) */
  countdownSeconds: 600,
  /** Alternativa: "21:30" oggi oppure ISO datetime */
  goLiveAt: "",
  countdownLabel: "SI PARTE TRA",
  countdownDoneLabel: "IN DIRETTA",

  // --- Ending CTA ---
  endingCtaEnabled: true,
  discordInviteUrl: "https://discord.com/invite/wZ4ZfK9DYy",
  discordQrImage: "assets/qr-discord.png",
  endingCtaText: "Entra nel Discord del team",
  endingFollowText: "",

  // --- Sponsor (rotazione discreta in Live) ---
  sponsorsEnabled: true,
  sponsorLabel: "PARTNER",
  /** ms in cui il logo resta visibile */
  sponsorDisplayMs: 8000,
  /** ms di pausa tra uno sponsor e il successivo */
  sponsorGapMs: 18000,
  /** ritardo prima della prima apparizione dopo il load scena */
  sponsorInitialDelayMs: 12000,
  sponsorFadeMs: 700,
  sponsors: [
    { name: "SimGrid", src: "assets/official/simgrid-white.png" },
    { name: "Tektrama", src: "assets/official/tektrama-white.png" },
    { name: "GoSetups", src: "assets/official/gosetups.png" }
  ]
};

(function applyConfig() {
  const cfg = Object.assign({}, window.PIGRECO_CONFIG || {});
  const params = new URLSearchParams(window.location.search);

  Object.keys(cfg).forEach((key) => {
    if (params.has(key) && typeof cfg[key] !== "object") cfg[key] = params.get(key);
  });

  if (params.has("user")) cfg.username = params.get("user");
  if (params.has("nick")) cfg.username = params.get("nick");
  if (params.has("sponsorsEnabled")) {
    cfg.sponsorsEnabled =
      params.get("sponsorsEnabled") !== "0" && params.get("sponsorsEnabled") !== "false";
  }

  if (!cfg.pilotName && cfg.username) cfg.pilotName = cfg.username;

  let handle = (cfg.twitchHandle || cfg.username || "").trim();
  if (handle && !handle.startsWith("@")) handle = "@" + handle;
  cfg.twitchHandle = handle;
  if (!cfg.twitchHandle && cfg.username) {
    cfg.twitchHandle = "@" + String(cfg.username).replace(/^@/, "");
  }

  window.PIGRECO_CONFIG = cfg;

  document.querySelectorAll("[data-cfg]").forEach((el) => {
    const key = el.getAttribute("data-cfg");
    if (cfg[key] != null && cfg[key] !== "") el.textContent = cfg[key];
  });

  document.querySelectorAll("[data-sponsors-static]").forEach((row) => {
    const list = Array.isArray(cfg.sponsors) ? cfg.sponsors : [];
    if (!list.length) {
      row.hidden = true;
      return;
    }
    row.innerHTML = "";
    list.forEach((s) => {
      const img = document.createElement("img");
      img.src = s.src;
      img.alt = s.name || "";
      row.appendChild(img);
    });
  });

  document.documentElement.dataset.username = cfg.username || "";
  document.title =
    (cfg.teamName || "PiGreco") + " — " + (document.title.split("—").pop() || "").trim();
})();
