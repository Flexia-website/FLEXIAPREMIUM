// FLEXIA Service Worker v6 - Fully Fixed & Optimized
const CACHE_NAME = 'flexia-v6';
const urlsToCache = [
  '/',
  '/index.html',
  '/snake.html',              // ✅ Correct filename
  '/coin-flip.html',
  '/plinko.html',
  '/achievements.html',
  '/receipt.html',            // ✅ Now cached properly
  '/admin.html',
  '/manifest.json',
  '/logo/flexia-logo.png',
  '/logo/favicon.ico',
  '/logo/apple-touch-icon.png',
  'https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css',
  'https://fonts.googleapis.com/css2?family=Orbitron:wght@400;700;900&family=Rajdhani:wght@300;500;700&display=swap'
];

self.addEventListener('install', event => {
  console.log('[ServiceWorker] Installing...');
  event.waitUntil(
    caches.open(CACHE_NAME)
      .then(cache => {
        console.log('[ServiceWorker] Caching app shell');
        return cache.addAll(urlsToCache);
      })
      .then(() => self.skipWaiting())
      .catch(err => {
        console.error('[ServiceWorker] Cache install failed:', err);
      })
  );
});

self.addEventListener('activate', event => {
  console.log('[ServiceWorker] Activating...');
  event.waitUntil(
    caches.keys().then(cacheNames => {
      return Promise.all(
        cacheNames.map(name => {
          if (name !== CACHE_NAME) {
            console.log('[ServiceWorker] Deleting old cache:', name);
            return caches.delete(name);
          }
        })
      );
    }).then(() => self.clients.claim())
  );
});

self.addEventListener('fetch', event => {
  const request = event.request;

  // Skip non-GET requests
  if (request.method !== 'GET') {
    return;
  }

  // Skip API calls (dynamic data)
  if (request.url.includes('/api/')) {
    return;
  }

  // Handle receipt.html with network-first (for fresh data) but fallback to cache
  if (request.url.includes('receipt.html')) {
    event.respondWith(
      fetch(request).then(networkResponse => {
        // If network succeeds, update cache
        if (networkResponse && networkResponse.ok) {
          const clone = networkResponse.clone();
          caches.open(CACHE_NAME).then(cache => cache.put(request, clone));
        }
        return networkResponse;
      }).catch(() => {
        // Fallback to cache if offline
        return caches.match(request).then(cached => {
          return cached || caches.match('/index.html');
        });
      })
    );
    return;
  }

  // Default: Cache-first strategy for static assets
  event.respondWith(
    caches.match(request).then(cachedResponse => {
      if (cachedResponse) {
        return cachedResponse;
      }
      return fetch(request).then(networkResponse => {
        // Only cache valid responses
        if (!networkResponse || networkResponse.status !== 200 || networkResponse.type !== 'basic') {
          return networkResponse;
        }
        const responseClone = networkResponse.clone();
        caches.open(CACHE_NAME).then(cache => {
          cache.put(request, responseClone);
        });
        return networkResponse;
      }).catch(() => {
        // Fallback to shell for HTML requests
        if (request.headers.get('accept').includes('text/html')) {
          return caches.match('/index.html');
        }
      });
    })
  );
});

// Allow skipWaiting via message (for updates)
self.addEventListener('message', event => {
  if (event.data && event.data.type === 'SKIP_WAITING') {
    self.skipWaiting();
  }
});