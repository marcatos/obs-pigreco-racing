/* =============================================================================
 * PiGreco Racing — CONFIG STREAMER
 * ---------------------------------------------------------------------------
 * 1) Copia questo file come config.js  (oppure modifica direttamente config.js)
 * 2) Compila i campi QUI SOTTO
 * 3) In OBS, su ogni Browser Source: tasto destro → Refresh cache of current page
 *
 * Override opzionali via URL (utile in OBS senza ritoccare il file):
 *   live-chrome.html?username=MioNick&eventTitle=Night%20Race
 * ============================================================================= */

window.PIGRECO_CONFIG = {
  // --- Identità (obbligatori per personalizzare) ---
  /** Nick / display name in lower-third e ending */
  username: "senormarcato",
  /** Nome completo mostrato in overlay (se vuoto usa username) */
  pilotName: "Simone Marcato",
  /** Handle Twitch senza o con @ (normalizzato automaticamente) */
  twitchHandle: "@senormarcato",

  // --- Team / evento ---
  teamName: "PiGreco Racing",
  eventTitle: "Sim Racing Session",
  tagline: "Competizione · Rispetto · Ironia",

  // --- Testi scene ---
  startingMessage: "IN ARRIVO",
  brbMessage: "TORNO SUBITO",
  endingMessage: "GRAZIE PER AVER SEGUITO",
  endingSub: "Ci vediamo alla prossima sessione"
};
