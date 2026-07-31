/* PiGreco Racing — edit these values, then refresh Browser Sources in OBS */
window.PIGRECO_CONFIG = {
  teamName: "PiGreco Racing",
  pilotName: "Simone Marcato",
  twitchHandle: "@senormarcato",
  eventTitle: "Sim Racing Session",
  tagline: "Competizione · Rispetto · Ironia",
  startingMessage: "IN ARRIVO",
  brbMessage: "TORNO SUBITO",
  endingMessage: "GRAZIE PER AVER SEGUITO",
  endingSub: "Ci vediamo alla prossima sessione"
};

(function applyConfig() {
  const cfg = window.PIGRECO_CONFIG || {};
  const params = new URLSearchParams(window.location.search);
  Object.keys(cfg).forEach((key) => {
    if (params.has(key)) cfg[key] = params.get(key);
  });

  document.querySelectorAll("[data-cfg]").forEach((el) => {
    const key = el.getAttribute("data-cfg");
    if (cfg[key] != null) el.textContent = cfg[key];
  });
})();
