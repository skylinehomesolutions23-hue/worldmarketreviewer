if ("serviceWorker" in navigator) {
  window.addEventListener("load", () => {
    navigator.serviceWorker
      .register("/static/sw.js")
      .then(reg => {
        console.log("Service worker registered", reg);
      })
      .catch(err => {
        console.error("SW registration failed", err);
      });
  });
}
