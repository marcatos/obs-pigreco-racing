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
  endingSub: "Ci vediamo alla prossima sessione"
};

(function applyConfig() {
  const cfg = Object.assign({}, window.PIGRECO_CONFIG || {});
  const params = new URLSearchParams(window.location.search);

  Object.keys(cfg).forEach((key) => {
    if (params.has(key)) cfg[key] = params.get(key);
  });

  // Aliases / derived fields
  if (params.has("user")) cfg.username = params.get("user");
  if (params.has("nick")) cfg.username = params.get("nick");

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

  document.documentElement.dataset.username = cfg.username || "";
  document.title = (cfg.teamName || "PiGreco") + " — " + (document.title.split("—").pop() || "").trim();
})();
