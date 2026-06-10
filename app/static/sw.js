// Service Worker Minimalista para Cache Offline Básico
const CACHE_NAME = 'portal-cache-v1';
const urlsToCache = [
  '/',
  '/static/css/style.css', // Se existir
  'https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css',
  'https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css'
];

self.addEventListener('install', event => {
  event.waitUntil(
    caches.open(CACHE_NAME)
      .then(cache => cache.addAll(urlsToCache))
  );
});

self.addEventListener('fetch', event => {
  // Estratégia: Network First, fallback to Cache
  event.respondWith(
    fetch(event.request).catch(() => caches.match(event.request))
  );
});