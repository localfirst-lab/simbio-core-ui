// ==============================================================================
// Simbio OS - Progressive Web App Service Worker (v2.1)
// Garantisce l'esecuzione nativa a schermo intero (senza barra URL su Android/iOS)
// e caching offline delle risorse essenziali.
// ==============================================================================

const CACHE_NAME = 'simbio-core-v2.6';
const STATIC_ASSETS = [
  '/',
  '/hardware',
  '/console',
  '/orchestra',
  '/security',
  '/static/manifest.json',
  '/static/icon-192.png',
  '/static/icon-512.png',
  '/static/simbio_icon.png'
];

// 1. INSTALLAZIONE: pre-caching asset statici
self.addEventListener('install', (event) => {
  console.log('[Simbio SW] Installazione Service Worker...');
  event.waitUntil(
    caches.open(CACHE_NAME).then((cache) => {
      console.log('[Simbio SW] Pre-caching asset core...');
      return cache.addAll(STATIC_ASSETS).catch(err => {
        console.warn('[Simbio SW] Pre-caching parziale non critico:', err);
      });
    }).then(() => self.skipWaiting())
  );
});

// 2. ATTIVAZIONE: pulizia vecchie cache
self.addEventListener('activate', (event) => {
  console.log('[Simbio SW] Attivazione Service Worker...');
  event.waitUntil(
    caches.keys().then((keyList) => {
      return Promise.all(
        keyList.map((key) => {
          if (key !== CACHE_NAME) {
            console.log('[Simbio SW] Rimozione vecchia cache:', key);
            return caches.delete(key);
          }
        })
      );
    }).then(() => self.clients.claim())
  );
});

// 3. FETCH STRATEGY:
// - API e streaming SSE: sempre Network-First (non cachare chiamate dinamiche o stream)
// - Risorse statiche: Stale-While-Revalidate o Cache-First
self.addEventListener('fetch', (event) => {
  const url = new URL(event.request.url);

  // Non intercettare chiamate API, stream SSE o metodi non-GET
  if (
    event.request.method !== 'GET' ||
    url.pathname.startsWith('/api/') ||
    url.pathname.startsWith('/v1/') ||
    url.pathname.includes('/stream')
  ) {
    return;
  }

  event.respondWith(
    caches.match(event.request).then((cachedResponse) => {
      const fetchPromise = fetch(event.request).then((networkResponse) => {
        if (networkResponse && networkResponse.status === 200 && networkResponse.type === 'basic') {
          const responseToCache = networkResponse.clone();
          caches.open(CACHE_NAME).then((cache) => {
            cache.put(event.request, responseToCache);
          });
        }
        return networkResponse;
      }).catch((err) => {
        console.log('[Simbio SW] Fetch offline fallback per:', url.pathname);
        return cachedResponse;
      });

      return cachedResponse || fetchPromise;
    })
  );
});

// 4. NOTIFICHE PUSH (per messaggi e alert di sicurezza)
self.addEventListener('push', (event) => {
  let data = {};
  try {
    data = event.data ? event.data.json() : {};
  } catch (e) {
    data = { title: 'Simbio OS', body: event.data ? event.data.text() : 'Nuovo evento neurale' };
  }

  const title = data.title || 'Simbio Nucleo';
  const options = {
    body: data.body || 'Notifica dal sistema VPS',
    icon: '/static/icon-192.png',
    badge: '/static/icon-192.png',
    vibrate: [100, 50, 100],
    data: {
      url: data.url || '/'
    }
  };

  event.waitUntil(self.registration.showNotification(title, options));
});

// 5. CLICK SULLA NOTIFICA: focalizza o apre l'app a schermo intero
self.addEventListener('notificationclick', (event) => {
  event.notification.close();
  const targetUrl = event.notification.data ? event.notification.data.url : '/';

  event.waitUntil(
    clients.matchAll({ type: 'window', includeUncontrolled: true }).then((clientList) => {
      for (const client of clientList) {
        if (client.url.includes(targetUrl) && 'focus' in client) {
          return client.focus();
        }
      }
      if (clients.openWindow) {
        return clients.openWindow(targetUrl);
      }
    })
  );
});
