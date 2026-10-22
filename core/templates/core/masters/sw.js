const CACHE = 'santehgo-master-v8';
const SHELL = ['/masters/', '/static/core/css/masters.css?v=8', '/static/core/css/masters-flow.css?v=1', '/static/core/js/install-pwa.js?v=2', '/static/core/js/masters.js?v=7', '/static/core/img/logo.svg?v=2', '/static/core/img/pwa-icon-192.png?v=3'];

self.addEventListener('install', (event) => {
  event.waitUntil(caches.open(CACHE).then((cache) => cache.addAll(SHELL)).then(() => self.skipWaiting()));
});

self.addEventListener('activate', (event) => {
  event.waitUntil(caches.keys().then((keys) => Promise.all(keys.filter((key) => key !== CACHE).map((key) => caches.delete(key)))).then(() => self.clients.claim()));
});

self.addEventListener('fetch', (event) => {
  if (event.request.method !== 'GET') return;
  event.respondWith(fetch(event.request).catch(() => caches.match(event.request).then((response) => response || caches.match('/masters/'))));
});

self.addEventListener('push', (event) => {
  const data = event.data ? event.data.json() : {};
  event.waitUntil(self.registration.showNotification(data.title || 'Новая заявка', {
    body: data.body || 'В общей очереди появилась новая заявка',
    icon: '/static/core/img/pwa-icon-192.png?v=3',
    badge: '/static/core/img/pwa-icon-192.png?v=3',
    tag: data.tag || 'new-request',
    data: { url: data.url || '/masters/' },
    vibrate: [180, 80, 180],
  }));
});

self.addEventListener('notificationclick', (event) => {
  event.notification.close();
  event.waitUntil(clients.matchAll({ type: 'window', includeUncontrolled: true }).then((windows) => {
    const existing = windows.find((client) => client.url.includes('/masters/'));
    return existing ? existing.focus() : clients.openWindow(event.notification.data.url);
  }));
});
