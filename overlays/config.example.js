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
  raceNumber: "42", // numero gara sulla barra cam
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

  // --- Sponsor rotator (barra sotto la cam su Live Race / Live Singolo) ---
  // Un logo alla volta nella barra inferiore del riquadro cam; cicla ogni sponsorDisplayMs.
  sponsorsEnabled: true,
  sponsorLabel: "PARTNER",
  sponsorDisplayMs: 5000,       // rotazione loghi (ms)
  sponsorGapMs: 0,              // 0 = continuo sulla barra cam
  sponsorInitialDelayMs: 0,     // attesa prima del primo cambio
  sponsorFadeMs: 400,
  // Aggiungi/rimuovi voci; metti i file PNG/SVG in overlays/assets/official/
  sponsors: [
    { name: "SimGrid", src: "assets/official/simgrid-white.png" },
    { name: "Tektrama", src: "assets/official/tektrama-white.png" },
    { name: "GoSetups", src: "assets/official/gosetups.png" }
  ],

  // --- Telemetry / telecronaca (P3-02) ---
  // Avvia: python adapters/telemetry/mock_server.py  OPPURE  iracing_bridge.py
  telemetryEnabled: false,
  telemetryWsUrl: "ws://127.0.0.1:8765",
  broadcastLeaderboard: true,
  broadcastRelative: true,
  broadcastFocus: true,
  broadcastSession: true,
  broadcastLeaderboardRows: 10,
  // TV-style: refresh standings/relative gaps every N ms (not every telemetry tick)
  broadcastBoardRefreshMs: 4000,
  // NASCAR-style field ticker: slide in → crawl once → slide out → pause
  broadcastTicker: true,
  broadcastTickerSpeed: 85, // px/sec while visible
  broadcastTickerIdleMs: 60000, // after one P1→last pass, hide this long before next
  broadcastTickerFirstDelayMs: 4000,
  broadcastDirector: "auto",
  broadcastDirectorSensitivity: "normal",
  // P3-03 track minimap Browser Source (track-map.html)
  trackMapEnabled: false,
  trackMapWsUrl: "ws://127.0.0.1:8765",
  // Advance dots slightly along the lap (0–1) to counter replay/WS lag; 0 disables
  trackMapLeadPct: 0.004,
  // Extrapolate along-track using recent speed (seconds ahead); 0 = off
  trackMapPredictSec: 0,
  // Optional mark next to pilot row in standings (matched by pilotName, not raceNumber)
  broadcastPilotMarkUrl: "",
  // Live “Battle for Px” pack (bottom-center; show/hide with close gaps)
  broadcastBattlePanel: true,
  // Race/session best lap chip (field best so far)
  broadcastRaceBest: true,
  // 0 = use director sensitivity presets (closing-speed based arming)
  broadcastBattleMs: 0, // max gap (ms) to consider an approach
  broadcastBattleIncludeMs: 0, // serious join/rejoin (tighter than keep)
  broadcastBattleKeepMs: 0, // soft stay threshold (default 400ms)
  broadcastBattleLeaveMs: 0, // must stay beyond keep this long before drop (default 3000)
  broadcastBattleExitMs: 0, // panel far threshold (defaults to keep)
  broadcastBattleCloseRate: 0, // gap shrink speed ms/s to arm
  broadcastBattleTicks: 0, // consecutive close ticks to arm
  // YouTube like/subscribe/bell promo (live-chrome)
  youtubePromoEnabled: true,
  youtubeHandle: "", // falls back to socialHandle / twitchHandle
  youtubePromoTitle: "LIKE & SUBSCRIBE",
  youtubePromoFirstDelayMs: 90000,
  youtubePromoIdleMs: 180000, // pause between scheduled appearances
  youtubePromoHoldMs: 2200, // hold after bell before exit
  youtubePromoLapTriggers: true, // force on end of lap 1 + last lap / checkered
  youtubePromoForceCooldownMs: 20000,
};
