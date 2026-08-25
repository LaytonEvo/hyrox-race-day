/* Offline shell cache.
   Bump CACHE whenever you change index.html, and the next visit with a
   connection will pick the new version up. */
var CACHE = 'hyrox-v2';
var SHELL = [
  './',
  './index.html',
  './backup.html',
  './manifest.webmanifest',
  './icons/icon-192.png',
  './icons/icon-512.png',
  './icons/apple-touch-icon.png'
];

self.addEventListener('install', function (e) {
  e.waitUntil(
    caches.open(CACHE).then(function (c) { return c.addAll(SHELL); })
      .then(function () { return self.skipWaiting(); })
  );
});

self.addEventListener('activate', function (e) {
  e.waitUntil(
    caches.keys()
      .then(function (keys) {
        return Promise.all(keys.filter(function (k) { return k !== CACHE; })
                               .map(function (k) { return caches.delete(k); }));
      })
      .then(function () { return self.clients.claim(); })
  );
});

self.addEventListener('fetch', function (e) {
  var req = e.request;
  if (req.method !== 'GET') return;

  var url = new URL(req.url);

  // Never cache anything cross-origin (Google Fonts), and never cache the
  // seed file -- boot() expects a live answer or a clean 404.
  if (url.origin !== location.origin || url.pathname.indexOf('/data/') !== -1) return;

  e.respondWith(
    caches.match(req).then(function (hit) {
      if (hit) {
        // Refresh in the background so an update lands on the next launch.
        e.waitUntil(
          fetch(req).then(function (res) {
            if (res && res.ok) return caches.open(CACHE).then(function (c) { return c.put(req, res); });
          }).catch(function () {})
        );
        return hit;
      }
      return fetch(req).then(function (res) {
        if (res && res.ok && res.type === 'basic') {
          var copy = res.clone();
          caches.open(CACHE).then(function (c) { c.put(req, copy); });
        }
        return res;
      });
    })
  );
});
