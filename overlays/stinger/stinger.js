(function () {
  "use strict";

  var STING_MS = 800;
  var params = new URLSearchParams(window.location.search);
  var preview = params.get("preview") === "1" || params.get("preview") === "true";
  var loop = params.get("loop") === "1" || params.get("loop") === "true";
  var hideHud = params.get("hud") === "0";

  var stage = document.getElementById("stage");
  var hud = document.getElementById("hud");
  var replayBtn = document.getElementById("replay");
  var timer = null;

  if (preview) {
    document.body.classList.add("preview");
  }
  if (hideHud || (!preview && !loop && params.get("hud") !== "1")) {
    // In OBS Browser Source (no query) hide chrome; ?preview=1 keeps HUD
    if (!preview) {
      hud.classList.add("hidden");
    }
  }
  if (hideHud) {
    hud.classList.add("hidden");
  }

  function play() {
    stage.classList.remove("play");
    // Force reflow so CSS animation restarts
    void stage.offsetWidth;
    stage.classList.add("play");
    if (timer) {
      clearTimeout(timer);
    }
    if (loop) {
      timer = setTimeout(play, STING_MS + 120);
    }
  }

  replayBtn.addEventListener("click", function () {
    play();
  });

  // Auto-play on load (OBS / file://)
  play();
})();
