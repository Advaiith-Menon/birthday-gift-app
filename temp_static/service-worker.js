const SHELL_CACHE_NAME = 'app-shell-v1';
const MEDIA_CACHE_NAME = 'media-cache-v1';

// Precache only the core app files
const shellAssets = [
  '/',
  '/static/manifest.json',

];

// Install event: Precache the app shell
self.addEventListener('install', event => {
  event.waitUntil(
    caches.open(SHELL_CACHE_NAME).then(cache => {
      console.log('[Service Worker] Pre-caching app shell');
      return cache.addAll(shellAssets);
    })
  );
});

// Activate event: Clean up old caches
self.addEventListener('activate', event => {
  event.waitUntil(
    caches.keys().then(cacheNames => {
      return Promise.all(
        cacheNames.filter(cacheName => {
          return cacheName !== SHELL_CACHE_NAME && cacheName !== MEDIA_CACHE_NAME;
        }).map(cacheName => {
          return caches.delete(cacheName);
        })
      );
    })
  );
  self.clients.claim();
});

// Fetch event: Use different strategies for different resources
self.addEventListener('fetch', event => {
  const url = new URL(event.request.url);

  // Strategy for app shell files: Cache-first
  // Check if the request URL is one of our shell assets
  if (url.origin === location.origin && shellAssets.includes(url.pathname)) {
    event.respondWith(caches.match(event.request));
    return;
  }

  // Strategy for media files: Cache-first, with network fallback and cache update
  if (
    url.pathname.endsWith('.jpg') ||
    url.pathname.endsWith('.png') ||
    url.pathname.endsWith('.mp4') ||
    url.pathname.endsWith('.mp3')
  ) {
    event.respondWith(
      caches.match(event.request).then(cachedResponse => {
        // Return cached response if it exists
        if (cachedResponse) {
          return cachedResponse;
        }

        // If not, fetch from the network, cache it, and return it.
        return fetch(event.request).then(networkResponse => {
          if (!networkResponse || networkResponse.status !== 200) {
            return networkResponse;
          }

          const responseToCache = networkResponse.clone();
          caches.open(MEDIA_CACHE_NAME).then(cache => {
            cache.put(event.request, responseToCache);
          });

          return networkResponse;
        });
      })
    );
    return;
  }

  // Default strategy for all other requests: Network-first
  event.respondWith(fetch(event.request));
});