// service-worker.js (DEV MODE — no caching, no interception)

self.addEventListener("install", (event) => {
  console.log("[SW] Installed");
  self.skipWaiting();
});

self.addEventListener("activate", (event) => {
  console.log("[SW] Activated");
  event.waitUntil(self.clients.claim());
});

self.addEventListener("fetch", (event) => {
  // IMPORTANT:
  // We deliberately do NOT intercept or cache requests.
  // This ensures all requests go directly to the network (your API).
  return;
});
