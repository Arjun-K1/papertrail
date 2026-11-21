// PaperTrail UI: theme toggle, read/favourite, tasks, listen, offline.
// No data is stored here. All stories, tasks, and settings live on the server.
(function () {
  // Theme: saved choice wins, otherwise the system setting.
  var saved = null;
  try { saved = localStorage.getItem("papertrail-theme"); } catch (e) {}
  if (saved) { document.documentElement.setAttribute("data-theme", saved); }

  // Service worker: cache the app shell so it opens offline after one visit.
  if ("serviceWorker" in navigator) {
    navigator.serviceWorker.register("/sw.js").catch(function () {});
  }

  function post(path, data) {
    return fetch(path, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(data || {})
    });
  }

  document.addEventListener("click", function (ev) {
    var el = ev.target.closest("[data-read],[data-fav],[data-remove-feed],[data-del-task],[data-done]");
    if (!el) return;
    if (el.hasAttribute("data-read")) {
      post("/api/read", { id: el.getAttribute("data-read"), read: true })
        .then(function () { location.reload(); });
    } else if (el.hasAttribute("data-fav")) {
      post("/api/favourite", { id: el.getAttribute("data-fav") })
        .then(function () { location.reload(); });
    } else if (el.hasAttribute("data-remove-feed")) {
      if (confirm("Remove this feed?")) {
        post("/api/feeds", { _method: "delete", url: el.getAttribute("data-remove-feed") })
          .then(function () { location.reload(); });
      }
    } else if (el.hasAttribute("data-del-task")) {
      if (confirm("Delete this task?")) {
        post("/api/tasks", { _method: "delete", id: el.getAttribute("data-del-task") })
          .then(function () { location.reload(); });
      }
    }
  });

  document.addEventListener("change", function (ev) {
    var el = ev.target.closest("[data-done]");
    if (!el) return;
    post("/api/tasks", { id: el.getAttribute("data-done"), done: el.checked })
      .then(function () { location.reload(); });
  });

  // Theme toggle button, added to the nav if it exists.
  var nav = document.querySelector("nav");
  if (nav) {
    var btn = document.createElement("button");
    btn.type = "button";
    btn.textContent = "Dark mode";
    btn.style.marginLeft = "auto";
    btn.addEventListener("click", function () {
      var cur = document.documentElement.getAttribute("data-theme");
      var next = cur === "dark" ? "light" : "dark";
      document.documentElement.setAttribute("data-theme", next);
      try { localStorage.setItem("papertrail-theme", next); } catch (e) {}
    });
    nav.appendChild(btn);
  }
})();

// Read the digest aloud in the browser. Uses the Web Speech API,
// so it works with no server TTS and no audio file to download.
function speakDigest() {
  if (!("speechSynthesis" in window)) {
    alert("Your browser does not support speech. Use the plain text version instead.");
    return;
  }
  fetch("/api/speak").then(function (r) { return r.json(); }).then(function (d) {
    window.speechSynthesis.cancel();
    var u = new SpeechSynthesisUtterance(d.text);
    u.rate = 1.0;
    window.speechSynthesis.speak(u);
  });
}
