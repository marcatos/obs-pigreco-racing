/* GENERATED from config.values.json — usa il pannello OBS o modifica il JSON */
window.PIGRECO_CONFIG = {
  "username": "senormarcato",
  "pilotName": "Simone Marcato",
  "raceNumber": "42",
  "twitchHandle": "@senormarcato",
  "teamName": "PiGreco Racing",
  "eventTitle": "Sim Racing Session",
  "tagline": "Competizione · Rispetto · Ironia",
  "startingMessage": "IN ARRIVO",
  "brbMessage": "TORNO SUBITO",
  "endingMessage": "GRAZIE PER AVER SEGUITO",
  "endingSub": "Ci vediamo alla prossima sessione",
  "brbUntil": "",
  "brbReturnLabel": "TORNO ALLE",
  "brbShowCountdown": true,
  "brbCountdownLabel": "RITORNO TRA",
  "brbCountdownDoneLabel": "STO TORNANDO",
  "sessionBadgeEnabled": true,
  "sessionType": "race",
  "sessionLabel": "",
  "countdownEnabled": true,
  "countdownSeconds": 600,
  "goLiveAt": "",
  "countdownLabel": "SI PARTE TRA",
  "countdownDoneLabel": "IN DIRETTA",
  "endingCtaEnabled": true,
  "discordInviteUrl": "https://discord.com/invite/wZ4ZfK9DYy",
  "discordQrImage": "assets/qr-discord.png",
  "endingCtaText": "Entra nel Discord del team",
  "endingFollowText": "",
  "sponsorsEnabled": true,
  "sponsorLabel": "PARTNER",
  "sponsorDisplayMs": 5000,
  "sponsorGapMs": 0,
  "sponsorInitialDelayMs": 0,
  "sponsorFadeMs": 400,
  "sponsors": [
    {
      "name": "SimGrid",
      "src": "assets/official/simgrid-white.png"
    },
    {
      "name": "Tektrama",
      "src": "assets/official/tektrama-white.png"
    },
    {
      "name": "GoSetups",
      "src": "assets/official/gosetups.png"
    }
  ],
  "telemetryEnabled": true,
  "telemetryWsUrl": "ws://127.0.0.1:8765",
  "broadcastLeaderboard": true,
  "broadcastRelative": true,
  "broadcastFocus": true,
  "broadcastSession": true,
  "broadcastLeaderboardRows": 10,
  "broadcastBoardRefreshMs": 4000,
  "broadcastTicker": true,
  "broadcastTickerSpeed": 85,
  "broadcastTickerIdleMs": 60000,
  "broadcastTickerFirstDelayMs": 4000,
  "broadcastBattlePanel": true,
  "broadcastRaceBest": true,
  "broadcastDirector": "auto",
  "broadcastDirectorSensitivity": "normal",
  "trackMapEnabled": false,
  "trackMapWsUrl": "ws://127.0.0.1:8765",
  "youtubePromoEnabled": true,
  "youtubeHandle": "",
  "youtubePromoTitle": "LIKE & SUBSCRIBE",
  "youtubePromoFirstDelayMs": 90000,
  "youtubePromoIdleMs": 180000,
  "youtubePromoHoldMs": 2200,
  "youtubePromoLapTriggers": true,
  "youtubePromoForceCooldownMs": 20000
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
