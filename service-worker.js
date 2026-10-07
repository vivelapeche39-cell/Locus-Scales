/* LOCUS Scales — service worker (palier 2, 7 oct 2026)
   BUT : permettre à l'app de DÉMARRER sans réseau (ou avec un réseau qui ne répond pas), sans jamais
   rester coincé sur une vieille version.

   RÈGLES DE SÉCURITÉ (ne pas les assouplir sans y repenser) :
   - index.html : RÉSEAU D'ABORD (revalidation, pas de vieux cache HTTP). On ne retombe sur la copie
     locale que si le réseau échoue ou ne répond pas en NAV_TIMEOUT_MS. Une nouvelle version déployée
     est donc reçue dès que le réseau répond.
   - version.txt : JAMAIS intercepté (le mécanisme anti-cache de l'app l'utilise tel quel, en no-store).
   - Supabase (API, auth, storage), Stripe et tout autre domaine : JAMAIS interceptés ni mis en cache.
   - Seules exceptions externes : les 2 bibliothèques CDN listées dans CDN_LIBS (cache d'abord, puis
     rafraîchies en arrière-plan).
   - Toute autre page (guides/, sitemap, etc.) : non interceptée.
   Ce fichier change rarement : le nom du cache est fixe, pas lié à APP_VERSION (index.html est de
   toute façon toujours redemandé au réseau). Si la logique ci-dessous change, incrémenter SW_VERSION.
   Échappatoire côté utilisateur : ouvrir l'app avec ?nosw=1 désactive le service worker et vide ses
   caches ; ?nosw=0 le réactive. */
var SW_VERSION = '1';
var SHELL_CACHE = 'locus-shell-v1';
var LIB_CACHE = 'locus-libs-v1';
var NAV_TIMEOUT_MS = 4000; // réseau « connecté mais qui ne répond pas » : on bascule sur la copie locale

var SCOPE_URL = self.registration.scope;
var SCOPE_PATH = new URL(SCOPE_URL).pathname;
var INDEX_URL = new URL('index.html', SCOPE_URL).href;
var SHELL_FILES = ['manifest.json', 'favicon.ico', 'icons/icon-192.png', 'icons/icon-512.png',
                   'icons/apple-touch-icon.png', 'icons/favicon-48.png']
  .map(function(p){ return new URL(p, SCOPE_URL).href; });
var CDN_LIBS = [
  'https://cdn.jsdelivr.net/npm/@supabase/supabase-js@2/dist/umd/supabase.js',
  'https://cdn.jsdelivr.net/npm/xlsx@0.18.5/dist/xlsx.full.min.js'
];

self.addEventListener('install', function(event){
  event.waitUntil((async function(){
    var shell = await caches.open(SHELL_CACHE);
    var libs = await caches.open(LIB_CACHE);
    var jobs = [];
    // Chaque élément est indépendant : un échec (hors-ligne à l'installation, fichier absent) n'annule rien.
    jobs.push(fetch(new Request(INDEX_URL, { cache: 'reload' })).then(function(r){
      if(r && r.ok) return shell.put(INDEX_URL, r);
    }).catch(function(){}));
    SHELL_FILES.forEach(function(u){
      jobs.push(fetch(new Request(u, { cache: 'reload' })).then(function(r){
        if(r && r.ok) return shell.put(u, r);
      }).catch(function(){}));
    });
    CDN_LIBS.forEach(function(u){
      jobs.push(fetch(u, { mode: 'cors', credentials: 'omit' }).then(function(r){
        if(r && r.ok) return libs.put(u, r);
      }).catch(function(){}));
    });
    await Promise.all(jobs);
    await self.skipWaiting();
  })());
});

self.addEventListener('activate', function(event){
  event.waitUntil((async function(){
    var keep = [SHELL_CACHE, LIB_CACHE];
    var keys = await caches.keys();
    await Promise.all(keys.filter(function(k){ return k.indexOf('locus-') === 0 && keep.indexOf(k) < 0; })
                          .map(function(k){ return caches.delete(k); }));
    await self.clients.claim();
  })());
});

// Une réponse issue d'une redirection ne peut pas être servie à une navigation : on la « nettoie ».
async function cleanResponse(resp){
  if(!resp.redirected) return resp;
  var body = await resp.blob();
  return new Response(body, { status: resp.status, statusText: resp.statusText, headers: resp.headers });
}

function offlineNotReadyPage(){
  var html = '<!doctype html><html lang="fr"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">' +
    '<title>LOCUS Scales</title><style>body{background:#000;color:#EDE6D6;font-family:system-ui,sans-serif;padding:32px;line-height:1.5}h1{color:#C9973E}</style></head><body>' +
    '<h1>LOCUS Scales</h1><p>Pas de connexion, et l\'app n\'a pas encore été enregistrée sur cet appareil. Reconnecte-toi une première fois, puis elle pourra démarrer hors-ligne.</p>' +
    '<p>No connection, and the app has not been saved on this device yet. Connect once, then it will be able to start offline.</p></body></html>';
  return new Response(html, { status: 503, headers: { 'Content-Type': 'text/html; charset=utf-8' } });
}

async function networkFirstIndex(event){
  var cache = await caches.open(SHELL_CACHE);
  var cached = await cache.match(INDEX_URL);
  var net = fetch(new Request(event.request.url, { cache: 'no-cache', redirect: 'follow', credentials: 'same-origin' }))
    .then(async function(resp){
      if(resp && resp.ok){
        var clean = await cleanResponse(resp);
        cache.put(INDEX_URL, clean.clone()).catch(function(){});
        return clean;
      }
      return null;
    }).catch(function(){ return null; });
  event.waitUntil(net); // laisse la mise à jour du cache se terminer même si on a déjà répondu avec la copie locale
  if(!cached){
    var first = await net;
    return first || offlineNotReadyPage();
  }
  var timeout = new Promise(function(resolve){ setTimeout(function(){ resolve(null); }, NAV_TIMEOUT_MS); });
  var winner = await Promise.race([net, timeout]);
  return winner || cached;
}

async function cacheFirstStatic(request){
  var cache = await caches.open(SHELL_CACHE);
  var key = new URL(request.url); key.search = '';
  var cached = await cache.match(key.href);
  if(cached) return cached;
  var resp = await fetch(request);
  if(resp && resp.ok) cache.put(key.href, resp.clone()).catch(function(){});
  return resp;
}

async function staleWhileRevalidateLib(event){
  var cache = await caches.open(LIB_CACHE);
  var url = event.request.url;
  var cached = await cache.match(url);
  var net = fetch(event.request).then(function(resp){
    if(resp && resp.ok) cache.put(url, resp.clone()).catch(function(){});
    return resp;
  }).catch(function(){ return null; });
  if(cached){ event.waitUntil(net); return cached; }
  var resp = await net;
  return resp || Response.error();
}

self.addEventListener('fetch', function(event){
  var req = event.request;
  if(req.method !== 'GET') return;
  var url = new URL(req.url);

  if(url.origin !== self.location.origin){
    if(CDN_LIBS.indexOf(req.url) >= 0){ event.respondWith(staleWhileRevalidateLib(event)); }
    return; // Supabase, Stripe, tout le reste : réseau direct, rien en cache
  }

  var isIndex = (url.pathname === SCOPE_PATH || url.pathname === SCOPE_PATH + 'index.html');
  if(req.mode === 'navigate' && isIndex){
    event.respondWith(networkFirstIndex(event));
    return;
  }

  var plain = url.origin + url.pathname;
  if(SHELL_FILES.indexOf(plain) >= 0){
    event.respondWith(cacheFirstStatic(req));
    return;
  }
  // version.txt et tout le reste : non interceptés
});
