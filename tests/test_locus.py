#!/usr/bin/env python3
"""
Suite de tests LOCUS Scales — rejouée avant chaque livraison.

Utilisation (depuis la racine du dépôt) :
    python3 tests/test_locus.py                 # teste ./index.html + ./version.txt
    python3 tests/test_locus.py chemin/index.html
    python3 tests/test_locus.py --perf          # ajoute la mesure 200 animaux + 2 ans d'historique

Besoins : Python 3 + playwright (pip install playwright && playwright install chromium) + node (pour node --check).
Aucune connexion réseau : un faux Supabase remplace la vraie librairie, toutes les données sont inventées.
Code de sortie 0 = tout passe ; 1 = au moins un échec (la livraison doit attendre).
"""
import sys, os, re, json, time, shutil, tempfile, threading, functools, subprocess, http.server, random, datetime, traceback

HERE = os.path.dirname(os.path.abspath(__file__))
ARGS = [a for a in sys.argv[1:] if not a.startswith('--')]
PERF = '--perf' in sys.argv
INDEX = os.path.abspath(ARGS[0]) if ARGS else os.path.join(os.path.dirname(HERE), 'index.html')
VERSION_TXT = os.path.join(os.path.dirname(INDEX), 'version.txt')
SRC = open(INDEX, encoding='utf-8').read()

USER = {"id": "u-test-0001", "email": "test@exemple.invalid"}
SESSION = {"access_token": "faux", "refresh_token": "faux-refresh", "user": USER}
# Paramètres « t » déjà présents en 5.33 (arrow functions locales, sans bug connu). Ne jamais monter ce chiffre.
T_PARAM_BASELINE = 15
AUTH_KEY = 'sb-dkhmqkkmnexqixmkvzjo-auth-token'

# ---------------------------------------------------------------- faux Supabase (aucun réseau)
FAKE_SUPABASE = r"""
(function(){
  var LS = window.localStorage;
  var SS = window.sessionStorage; // le « serveur » vit à part, pour ne pas gonfler l'espace mesuré de l'app
  function loadDb(){ try{ return JSON.parse(SS.getItem('__fake_db')||'{}'); }catch(e){ return {}; } }
  function saveDb(db){ try{ SS.setItem('__fake_db', JSON.stringify(db)); }catch(e){} }
  var F = window.__fakeSb = { calls: [], offline: LS.getItem('__fake_offline')==='1',
    session: (function(){ try{ return JSON.parse(LS.getItem('__fake_session')||'null'); }catch(e){ return null; } })(), db: loadDb };
  function netErr(){ return { data:null, error:{ message:'TypeError: Failed to fetch' } }; }
  function B(t){ this.table=t; this.op='select'; this.payload=null; this.filters=[]; this.one=null; }
  ['select','order','limit','range','neq','gt','gte','lt','lte','like','ilike','is','not','or','match','contains','returns'].forEach(function(m){ B.prototype[m]=function(){ return this; }; });
  B.prototype.eq=function(c,v){ this.filters.push(['eq',c,v]); return this; };
  B.prototype['in']=function(c,v){ this.filters.push(['in',c,v]); return this; };
  B.prototype.insert=function(p){ this.op='insert'; this.payload=p; return this; };
  B.prototype.upsert=function(p){ this.op='upsert'; this.payload=p; return this; };
  B.prototype.update=function(p){ this.op='update'; this.payload=p; return this; };
  B.prototype['delete']=function(){ this.op='delete'; return this; };
  B.prototype.maybeSingle=function(){ this.one='maybe'; return this; };
  B.prototype.single=function(){ this.one='one'; return this; };
  B.prototype.run=function(){
    F.calls.push({ table:this.table, op:this.op, payload:this.payload, filters:this.filters, offline:F.offline });
    if(F.offline || LS.getItem('__fake_offline')==='1') return netErr();
    var db=loadDb(), rows=db[this.table]||[], f=this.filters, self=this;
    var key=function(r){ return r.id!==undefined ? r.id : r.user_id; };
    var ok=function(r){ return f.every(function(x){ return x[0]==='eq' ? r[x[1]]===x[2] : x[2].indexOf(r[x[1]])>=0; }); };
    var out;
    if(this.op==='upsert'||this.op==='insert'){
      var list=Array.isArray(this.payload)?this.payload:[this.payload];
      list.forEach(function(p){ var k=key(p), i=rows.findIndex(function(r){ return key(r)===k; });
        var row=Object.assign({}, i>=0?rows[i]:{}, p, { updated_at:new Date().toISOString() }); if(i>=0) rows[i]=row; else rows.push(row); });
      out=list;
    } else if(this.op==='update'){ rows=rows.map(function(r){ return ok(r)?Object.assign({},r,self.payload):r; }); out=rows.filter(ok); }
    else if(this.op==='delete'){ out=rows.filter(ok); rows=rows.filter(function(r){ return !ok(r); }); }
    else out=rows.filter(ok);
    db[this.table]=rows; saveDb(db);
    if(this.one) return { data: out[0]||null, error: (this.one==='one' && !out[0]) ? { message:'no rows' } : null };
    return { data: out, error: null };
  };
  B.prototype.then=function(a,b){ var self=this; return new Promise(function(r){ setTimeout(function(){ r(self.run()); }, 5); }).then(a,b); };
  function client(){
    var L=[];
    return {
      auth:{
        getSession:function(){ return Promise.resolve({ data:{ session:F.session }, error:null }); },
        getUser:function(){ return Promise.resolve({ data:{ user:F.session&&F.session.user }, error:null }); },
        onAuthStateChange:function(cb){ L.push(cb); setTimeout(function(){ cb('INITIAL_SESSION', F.session); },0); return { data:{ subscription:{ unsubscribe:function(){} } } }; },
        signInWithPassword:function(){ return Promise.resolve({ data:{}, error:{ message:'désactivé en test' } }); },
        signUp:function(){ return Promise.resolve({ data:{}, error:{ message:'désactivé en test' } }); },
        signOut:function(){ F.session=null; LS.removeItem('__fake_session'); L.forEach(function(cb){ cb('SIGNED_OUT', null); }); return Promise.resolve({ error:null }); },
        resend:function(){ return Promise.resolve({ error:null }); },
        resetPasswordForEmail:function(){ return Promise.resolve({ error:null }); },
        updateUser:function(){ return Promise.resolve({ data:{}, error:null }); }
      },
      from:function(t){ return new B(t); },
      rpc:function(n,a){ F.calls.push({ rpc:n, args:a }); if(F.offline) return Promise.resolve(netErr());
        return Promise.resolve({ data: n==='get_my_customers_decrypted' ? [] : null, error:null }); },
      storage:{ from:function(){ return { upload:function(){ return Promise.resolve({ data:{}, error:F.offline?{message:'offline'}:null }); },
        getPublicUrl:function(p){ return { data:{ publicUrl:'https://fake.invalid/'+p } }; }, remove:function(){ return Promise.resolve({ data:{}, error:null }); } }; } },
      functions:{ invoke:function(){ return Promise.resolve({ data:null, error:{ message:'désactivé en test' } }); } },
      channel:function(){ var c={ on:function(){ return c; }, subscribe:function(){ return c; } }; return c; },
      removeChannel:function(){}
    };
  }
  window.supabase = { createClient: client };
})();
"""

# ---------------------------------------------------------------- données inventées
def iso(d): return d.isoformat()
TODAY = datetime.date.today()

def make_snake(i, days_history=0, species='ball_python', genes=None, rng=None):
    """Reptile inventé. days_history>0 = journal de repas/mues/pesées sur cette période."""
    rng = rng or random.Random(i)
    sex = 'male' if i % 2 else 'female'
    events, weights = [], []
    if days_history:
        d = TODAY - datetime.timedelta(days=days_history)
        w = 300 + rng.randint(0, 900)
        while d < TODAY:
            if rng.random() < 0.85:
                events.append({"date": iso(d), "type": "fed", "quantity": "complete", "preyType": "frozen", "preyCount": 1})
            else:
                events.append({"date": iso(d), "type": "refused", "reason": "other"})
            if rng.random() < 0.12:
                events.append({"date": iso(d), "type": "shed", "quality": "complete"})
            if rng.random() < 0.3:
                w += rng.randint(-10, 40); weights.append({"date": iso(d), "value": w})
            d += datetime.timedelta(days=7 + rng.randint(0, 4))
    return {
        "id": "s_test_%04d" % i, "name": "Testeur %d" % i, "animalId": "T-%04d" % i, "sex": sex,
        "species": species, "genes": genes if genes is not None else ({"pastel": "single"} if i % 3 == 0 else {}),
        "birthDate": iso(TODAY - datetime.timedelta(days=400 + i)), "createdAt": 1700000000000 + i,
        "updatedAt": 1700000000000 + i, "preyType": "frozen",
        "placement": {"mode": "terrarium", "terrariumId": None, "row": None, "tub": None},
        "health": {"consecutiveRefusals": 0, "weights": weights, "events": events}
    }

# ---------------------------------------------------------------- petit cadre de test
RESULTS = []
def check(name, cond, detail=''):
    RESULTS.append((name, bool(cond), detail))
    print(('  OK   ' if cond else '  ÉCHEC ') + name + ('' if cond or not detail else '  → ' + str(detail)[:300]))
    return cond

def section(title): print('\n== ' + title)

WARNINGS = []
def warn(name, detail=''):
    """Limite connue, mesurée à chaque fois : n'empêche pas la livraison, mais reste visible."""
    WARNINGS.append((name, detail)); print('  AVERT ' + name + ('  → ' + str(detail)[:300] if detail else ''))

# ---------------------------------------------------------------- 1. vérifications statiques
def static_checks():
    section('Vérifications du fichier (sans navigateur)')
    m = re.search(r"const APP_VERSION = '([^']+)'", SRC)
    app_v = m.group(1) if m else None
    file_v = open(VERSION_TXT).read().strip() if os.path.exists(VERSION_TXT) else None
    check('APP_VERSION = version.txt', app_v and app_v == file_v, f'index.html={app_v} version.txt={file_v}')

    # node --check sur chaque bloc <script> en ligne
    blocks = [b for attrs, b in re.findall(r'<script((?![^>]*\bsrc=)[^>]*)>(.*?)</script>', SRC, re.S)
              if 'type=' not in attrs or 'javascript' in attrs or 'module' in attrs]
    tmp = tempfile.mkdtemp()
    bad = []
    for i, b in enumerate(blocks):
        if not b.strip() or 'application/ld+json' in b[:0]: continue
        p = os.path.join(tmp, f'b{i}.js'); open(p, 'w', encoding='utf-8').write(b)
        r = subprocess.run(['node', '--check', p], capture_output=True, text=True)
        if r.returncode: bad.append((i, ' | '.join(l for l in r.stderr.splitlines() if 'Error' in l or ':' in l)[:300]))
    check(f'node --check ({len(blocks)} blocs de script)', not bad, bad)

    dups = {}
    for n in re.findall(r'^(?:async )?function ([A-Za-z0-9_$]+)\s*\(', SRC, re.M): dups[n] = dups.get(n, 0) + 1
    dups = {k: v for k, v in dups.items() if v > 1}
    check('aucune fonction déclarée deux fois', not dups, dups)

    html_only = re.sub(r'<script[^>]*>.*?</script>', '', SRC, flags=re.S)
    ids = re.findall(r'\sid="([A-Za-z][\w-]*)"', html_only)
    seen, dupid = set(), set()
    for x in ids:
        (dupid if x in seen else seen).add(x)
    check('aucun id HTML statique en double', not dupid, sorted(dupid)[:20])

    tparams = re.findall(r'function\s*[A-Za-z0-9_$]*\s*\(([^)]*\bt\b[^)]*)\)', SRC)
    tparams = [x for x in tparams if re.search(r'(^|,)\s*t\s*(,|=|$)', x)]
    arrow_t = re.findall(r'[(,]\s*t\s*\)\s*=>|[^\w.$]t\s*=>', SRC)
    n_t = len(tparams) + len(arrow_t)
    check(f'aucun NOUVEAU paramètre nommé t (bug WebKit) — {n_t} anciens, max {T_PARAM_BASELINE}', n_t <= T_PARAM_BASELINE,
          f'{n_t - T_PARAM_BASELINE} de plus que la 5.33 — renommer le nouveau paramètre')

# ---------------------------------------------------------------- serveur local
def start_server():
    root = tempfile.mkdtemp(prefix='locus-test-')
    shutil.copy(INDEX, os.path.join(root, 'index.html'))
    if os.path.exists(VERSION_TXT): shutil.copy(VERSION_TXT, os.path.join(root, 'version.txt'))
    os.makedirs(os.path.join(root, 'lib'))
    open(os.path.join(root, 'lib', 'supabase.js'), 'w').write(FAKE_SUPABASE)
    real_xlsx = os.path.join(os.path.dirname(INDEX), 'lib', 'xlsx.full.min.js')
    if os.path.exists(real_xlsx): shutil.copy(real_xlsx, os.path.join(root, 'lib'))
    else: open(os.path.join(root, 'lib', 'xlsx.full.min.js'), 'w').write('/* absent en test */')
    class Quiet(http.server.SimpleHTTPRequestHandler):
        def log_message(self, *a): pass
    H = functools.partial(Quiet, directory=root)
    srv = http.server.ThreadingHTTPServer(('127.0.0.1', 0), H)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv, f'http://127.0.0.1:{srv.server_port}/index.html'

class App:
    """Une page LOCUS dans un navigateur iPhone simulé (390×844), réseau externe bloqué."""
    def __init__(self, browser, url, snakes=None, logged_in=True, lang='fr', server_db=None):
        self.url = url
        self.ctx = browser.new_context(viewport={'width': 390, 'height': 844}, service_workers='block', locale='fr-CA')
        self.ctx.route(lambda u: not u.startswith('http://127.0.0.1'), lambda r: r.abort())
        seed = {'locus_app_config_v1': None}
        init = ["try{ if(location.protocol==='http:' && !localStorage.getItem('__seeded')){", "localStorage.setItem('__seeded','1');"]
        cfg_key = re.search(r"const APP_CONFIG_KEY = '([^']+)'", SRC)
        if cfg_key: init.append(f"localStorage.setItem({json.dumps(cfg_key.group(1))}, {json.dumps(json.dumps({'lang': lang}))});")
        if logged_in:
            init.append(f"localStorage.setItem('__fake_session', {json.dumps(json.dumps(SESSION))});")
            init.append(f"localStorage.setItem({json.dumps(AUTH_KEY)}, {json.dumps(json.dumps({'refresh_token': 'faux-refresh'}))});")
            init.append(f"localStorage.setItem('locus_data_owner_v1', {json.dumps(USER['id'])});")
        if snakes is not None:
            init.append(f"localStorage.setItem('locus_snakes_v1', {json.dumps(json.dumps(snakes))});")
        if server_db is not None:
            init.append(f"sessionStorage.setItem('__fake_db', {json.dumps(json.dumps(server_db))});")
        init.append("} }catch(e){}")
        self.ctx.add_init_script(''.join(init))
        self.page = self.ctx.new_page()
        self.errors = []
        self.page.on('pageerror', lambda e: self.errors.append('pageerror: ' + str(e)))
        self.page.on('console', lambda m: m.type == 'error' and self.errors.append('console: ' + m.text[:300]))
        self.page.on('dialog', lambda d: d.accept())

    def open(self, wait=1500):
        t = time.time(); self.page.goto(self.url); self.page.wait_for_load_state('load')
        self.page.wait_for_function('typeof savedSnakes!=="undefined" && typeof showTab==="function"')
        took = time.time() - t
        self.page.wait_for_timeout(wait)
        return took
    def reload(self, wait=1500):
        self.page.reload(); self.page.wait_for_load_state('load'); self.page.wait_for_timeout(wait)
    def js(self, expr, arg=None): return self.page.evaluate(expr, arg)
    def real_errors(self):
        # le réseau externe est bloqué exprès : ces messages-là sont attendus
        ignore = ('net::ERR_FAILED', 'Failed to load resource', 'ERR_BLOCKED', 'ERR_INTERNET_DISCONNECTED')
        return [e for e in self.errors if not any(x in e for x in ignore)]
    def close(self): self.ctx.close()

# ---------------------------------------------------------------- 2. scénarios
def t_ouverture(browser, url):
    section('Ouverture')
    a = App(browser, url, logged_in=False)
    a.open()
    st = a.js("({v:APP_VERSION, n:savedSnakes.length, dash:getComputedStyle(document.getElementById('view-dash')).display!=='none'})")
    check('ouverture à vide (invité) sans erreur JS', not a.real_errors(), a.real_errors()[:3])
    check('tableau de bord affiché', st['dash'])
    a.close()

    snakes = [make_snake(i, days_history=120) for i in range(1, 7)]
    a = App(browser, url, snakes=snakes)
    a.open()
    check('ouverture connectée avec 6 animaux sans erreur JS', not a.real_errors(), a.real_errors()[:3])
    check('les 6 animaux sont chargés', a.js('savedSnakes.length') == 6)
    tabs = a.js("[...document.querySelectorAll('[id^=view-]')].map(e=>e.id.slice(5)).filter(x=>/^[a-z]+$/.test(x))")
    broken = []
    for tab in tabs:
        before = len(a.real_errors())
        try: a.js(f"showTab({json.dumps(tab)})"); a.page.wait_for_timeout(150)
        except Exception as e: broken.append(f'{tab}: {e}'); continue
        if len(a.real_errors()) > before: broken.append(f'{tab}: ' + a.real_errors()[-1])
    check(f'chaque onglet s\'ouvre sans erreur ({len(tabs)} onglets)', not broken, broken[:3])
    # chaque fiche s'ouvre (journal)
    bad = []
    for s in snakes[:3]:
        before = len(a.real_errors())
        a.js(f"openLogbook({json.dumps(s['id'])})"); a.page.wait_for_timeout(100)
        if len(a.real_errors()) > before: bad.append(a.real_errors()[-1])
        a.js("(document.getElementById('logbook-overlay')||{}).style && (document.getElementById('logbook-overlay').style.display='none')")
    check('le journal d\'un animal s\'ouvre sans erreur', not bad, bad[:2])
    a.close()

def open_card(a, sid):
    """Comme un utilisateur : onglet Mes reptiles → bouton « Journal de bord » de la fiche."""
    a.js("showTab('mine')"); a.page.wait_for_timeout(200)
    card = a.page.locator(f'#view-mine button[data-act="logbook"][data-id="{sid}"]').first
    card.scroll_into_view_if_needed(timeout=5000); card.click()
    a.page.wait_for_selector('#logbook-body button.tour-action-btn.fed', timeout=5000)

def tour_fed(a, sid):
    """Repas noté comme un vrai utilisateur : fiche → bouton Repas → « Mangé au complet »."""
    open_card(a, sid)
    a.page.locator('#logbook-body button.tour-action-btn.fed').first.click()
    a.page.locator(f"button[onclick=\"confirmFed('{sid}', 'complete')\"]").click(timeout=5000)
    a.page.wait_for_timeout(200)

def t_repas(browser, url):
    section('Noter un repas')
    s = make_snake(1); sid = s['id']
    a = App(browser, url, snakes=[s])
    a.open()
    tour_fed(a, sid)
    today = a.js('localTodayStr()')
    ev = a.js(f"savedSnakes.find(x=>x.id==='{sid}').health.events.filter(e=>e.type==='fed' && e.date==='{today}').length")
    check('repas ajouté à la fiche', ev == 1, ev)
    stored = a.js(f"JSON.parse(localStorage.getItem('locus_snakes_v1')).find(x=>x.id==='{sid}').health.events.filter(e=>e.type==='fed').length")
    check('repas enregistré sur l\'appareil', stored == 1, stored)
    a.reload()
    ev2 = a.js(f"savedSnakes.find(x=>x.id==='{sid}').health.events.filter(e=>e.type==='fed').length")
    check('repas toujours là après réouverture', ev2 == 1, ev2)
    a.page.wait_for_timeout(1500)  # envoi différé de 1,2 s
    srv = a.js(f"(window.__fakeSb.db().snakes||[]).find(r=>r.id==='{sid}')")
    srv_events = (srv or {}).get('data', srv or {})
    txt = json.dumps(srv or {})
    check('repas envoyé au serveur', '"type": "fed"' in txt or '"type":"fed"' in txt, txt[:200])
    a.js("undoLastLoggedEvent && undoLastLoggedEvent()")
    check('pas d\'erreur JS pendant le repas', not a.real_errors(), a.real_errors()[:3])
    a.close()

def server_snake_has(a, sid, needle):
    return needle in json.dumps(a.js(f"(window.__fakeSb.db().snakes||[]).find(r=>r.id==='{sid}')") or {}, separators=(',', ':'))

def t_synchro(browser, url):
    section('Synchro hors ligne → en ligne')
    s = make_snake(2); sid = s['id']
    a = App(browser, url, snakes=[s])
    a.open(wait=2500)
    # coupure
    a.ctx.set_offline(True); a.js("localStorage.setItem('__fake_offline','1'); window.__fakeSb.offline=true; window.dispatchEvent(new Event('offline'))")
    tour_fed(a, sid)
    a.page.wait_for_timeout(1800)
    check('hors ligne : rien n\'arrive au serveur', not server_snake_has(a, sid, '"type":"fed"'))
    dirty = a.js("JSON.parse(localStorage.getItem('locus_dirty_sync_v1')||'{}')")
    check('hors ligne : la modif reste marquée « à envoyer »', sid in json.dumps(dirty), dirty)
    pill = a.js("(()=>{const p=document.getElementById('sync-pill'); return p ? getComputedStyle(p).display!=='none' : null})()")
    check('pastille de synchro visible hors ligne', pill, pill)
    # on ferme et rouvre l'app toujours hors ligne
    a.page.goto('about:blank'); a.ctx.set_offline(False)
    a.page.goto(a.url); a.page.wait_for_timeout(300); a.ctx.set_offline(True)
    a.page.wait_for_timeout(1200)
    still = a.js(f"savedSnakes.find(x=>x.id==='{sid}').health.events.some(e=>e.type==='fed')")
    check('repas gardé après réouverture hors ligne', still)
    # retour du réseau
    a.ctx.set_offline(False); a.js("localStorage.removeItem('__fake_offline'); window.__fakeSb.offline=false; window.dispatchEvent(new Event('online'))")
    a.page.wait_for_timeout(4000)
    check('retour en ligne : le repas arrive au serveur', server_snake_has(a, sid, '"type":"fed"'))
    check('pas d\'erreur JS (synchro)', not a.real_errors(), a.real_errors()[:3])
    a.close()

    section('Synchro entre deux appareils (fusion)')
    base = make_snake(3); sid = base['id']
    # 1er appareil : envoie la fiche au serveur
    a = App(browser, url, snakes=[base]); a.open(wait=2500)
    a.js("pushAllUserData(true)"); a.page.wait_for_timeout(500)
    db = a.js("window.__fakeSb.db()"); a.close()
    check('la fiche est sur le serveur', any(r.get('id') == sid for r in db.get('snakes', [])))
    # 2e appareil (même compte) : pesée notée là-bas, puis renvoyée au serveur
    b = App(browser, url, snakes=[], server_db=db); b.open(wait=3000)
    got = b.js(f"!!savedSnakes.find(x=>x.id==='{sid}')")
    check('2e appareil : la fiche arrive du serveur', got)
    b.js(f"(()=>{{const s=savedSnakes.find(x=>x.id==='{sid}'); s.health.weights.push({{date:localTodayStr(), value:777}}); s.updatedAt=Date.now(); storage.save(savedSnakes);}})()")
    b.page.wait_for_timeout(2500)
    db2 = b.js("window.__fakeSb.db()"); b.close()
    # 1er appareil : un repas noté hors ligne (pas encore envoyé), puis la synchro tire la version du serveur
    a = App(browser, url, snakes=[base], server_db=db)
    a.open(wait=2500); a.ctx.set_offline(True)
    a.js("window.__fakeSb.offline=true; localStorage.setItem('__fake_offline','1'); window.dispatchEvent(new Event('offline'))")
    tour_fed(a, sid); a.page.wait_for_timeout(2500)  # l'envoi différé (1,2 s) échoue hors ligne, comme dans la vraie vie
    a.js(f"sessionStorage.setItem('__fake_db', {json.dumps(json.dumps(db2))}); localStorage.removeItem('__fake_offline'); window.__fakeSb.offline=false")
    a.ctx.set_offline(False); a.js("window.dispatchEvent(new Event('online'))"); a.page.wait_for_timeout(1000)
    a.js("synchroniserAvecServeur()"); a.page.wait_for_timeout(4000)
    loc = a.js(f"(()=>{{const s=savedSnakes.find(x=>x.id==='{sid}'); return {{fed:s.health.events.some(e=>e.type==='fed' && e.date===localTodayStr()), w:s.health.weights.some(w=>w.value===777)}}}})()")
    check('fusion : le repas (appareil 1) ET la pesée (appareil 2) sont gardés', loc['fed'] and loc['w'], loc)
    check('fusion : le serveur a les deux', server_snake_has(a, sid, '"value":777') and server_snake_has(a, sid, '"type":"fed"'))
    check('pas d\'erreur JS (fusion)', not a.real_errors(), a.real_errors()[:3])
    a.close()

def t_deux_appareils_ouverts(browser, url):
    section('Deux appareils ouverts en même temps (même animal)')
    base = make_snake(4); sid = base['id']
    a = App(browser, url, snakes=[base]); a.open(wait=2500)
    a.js("pushAllUserData(true)"); a.page.wait_for_timeout(500); db = a.js("window.__fakeSb.db()")
    b = App(browser, url, snakes=[], server_db=db); b.open(wait=3000)
    b.js(f"(()=>{{const s=savedSnakes.find(x=>x.id==='{sid}'); s.health.weights.push({{date:localTodayStr(), value:777}}); s.updatedAt=Date.now(); storage.save(savedSnakes);}})()")
    b.page.wait_for_timeout(2500); db2 = b.js("window.__fakeSb.db()")
    # l'appareil 1, resté ouvert avec sa vieille copie, note un repas
    a.js(f"sessionStorage.setItem('__fake_db', {json.dumps(json.dumps(db2))})")
    tour_fed(a, sid); a.page.wait_for_timeout(2500)
    db3 = a.js("window.__fakeSb.db()")
    # v5.34 — fusion avant envoi : la pesée de l'appareil 2 ne doit JAMAIS disparaître du serveur
    check('le repas de l\'appareil 1 n\'efface pas la pesée de l\'appareil 2 sur le serveur',
          '"value": 777' in json.dumps(db3) and '"fed"' in json.dumps(db3))
    check('l\'appareil 1 reçoit la pesée au moment de son envoi',
          a.js(f"savedSnakes.find(x=>x.id==='{sid}').health.weights.some(w=>w.value===777)"))
    b.js(f"sessionStorage.setItem('__fake_db', {json.dumps(json.dumps(db3))})"); b.reload(wait=4000)
    db4 = b.js("window.__fakeSb.db()")
    check('à la réouverture de l\'appareil 2, le serveur a la pesée ET le repas',
          '"value": 777' in json.dumps(db4) and '"fed"' in json.dumps(db4))
    a.js(f"sessionStorage.setItem('__fake_db', {json.dumps(json.dumps(db4))})"); a.reload(wait=4000)
    both = a.js(f"(()=>{{const s=savedSnakes.find(x=>x.id==='{sid}'); return s.health.weights.some(w=>w.value===777) && s.health.events.some(e=>e.type==='fed')}})()")
    check('puis l\'appareil 1 a les deux aussi', both)
    check('pas d\'erreur JS (deux appareils)', not a.real_errors() and not b.real_errors(), (a.real_errors() + b.real_errors())[:3])
    a.close(); b.close()

def t_suppression_ne_revient_pas(browser, url):
    section('Une entrée supprimée ne revient pas du serveur')
    base = make_snake(5, days_history=30); sid = base['id']
    a = App(browser, url, snakes=[base]); a.open(wait=2500)
    a.js("pushAllUserData(true)"); a.page.wait_for_timeout(500)
    n0 = a.js(f"savedSnakes.find(x=>x.id==='{sid}').health.events.length")
    # supprime la 1re entrée du journal par la vraie fonction (confirmation acceptée automatiquement)
    a.js(f"deleteHealthEvent('{sid}', 0)"); a.page.wait_for_timeout(2500)
    n1 = a.js(f"savedSnakes.find(x=>x.id==='{sid}').health.events.length")
    srv = a.js(f"((window.__fakeSb.db().snakes||[]).find(r=>r.id==='{sid}')||{{}}).health")
    check('suppression gardée sur l\'appareil après l\'envoi', n1 == n0 - 1, (n0, n1))
    check('suppression envoyée au serveur (pas ramenée par la fusion avant envoi)', srv and len(srv.get('events', [])) == n0 - 1, srv and len(srv.get('events', [])))
    a.close()

def t_grille_elevage_a_jour(browser, url):
    section('Onglet Élevage à jour après un repas noté ailleurs (v5.35)')
    snakes = [make_snake(i) for i in range(1, 4)]
    for s_ in snakes: s_['placement'] = {"mode": "rack", "rackId": "rack_1", "row": 1, "tub": int(s_['id'][-1])}
    a = App(browser, url, snakes=snakes); a.open()
    sid = snakes[0]['id']
    a.js("showTab('elevage')"); a.page.wait_for_timeout(200)
    before = a.js("document.getElementById('tour-grid').innerText")
    tour_fed(a, sid)  # repas noté depuis Mes reptiles : Élevage caché
    a.js("document.getElementById('logbook-overlay').style.display='none'; showTab('elevage')"); a.page.wait_for_timeout(200)
    after = a.js("document.getElementById('tour-grid').innerText")
    check('grille d\'Élevage redessinée à l\'ouverture (repas visible)', before != after and 'Testeur 1' in after, (before[:120], after[:120]))
    check('pas d\'erreur JS (grille Élevage)', not a.real_errors(), a.real_errors()[:3])
    a.close()

def t_import(browser, url):
    section('Import d\'un fichier CSV')
    a = App(browser, url, snakes=[])
    a.open()
    csv = 'Nom;ID;Sexe;Espèce;Génétique;Date de naissance\nAurore;IMP-001;Femelle;Python royal;Pastel;2024-06-01\nBruno;IMP-002;Mâle;Python royal;Het Clown;2023-05-12\nCéleste;IMP-003;Femelle;Python royal;Normal;2025-07-20\n'
    path = os.path.join(tempfile.mkdtemp(), 'collection_test.csv'); open(path, 'w', encoding='utf-8').write(csv)
    a.js("showTab('mine')")
    a.page.set_input_files('#generic-csv-file-input', path)
    a.page.wait_for_timeout(800)
    # l'aperçu demande une confirmation : on clique le bouton d'import visible
    clicked = a.js("""(()=>{
      const btns=[...document.querySelectorAll('button')].filter(b=>b.offsetParent && /import/i.test(b.textContent) && !/fichier|file|choisir|choose/i.test(b.textContent));
      if(!btns.length) return null; const b=btns[btns.length-1]; const txt=b.textContent.trim(); b.click(); return txt; })()""")
    a.page.wait_for_timeout(800)
    got = a.js("savedSnakes.map(s=>({n:s.name, id:s.animalId, sex:s.sex, g:s.genes}))")
    names = sorted(x['n'] for x in got)
    check('3 animaux importés', names == ['Aurore', 'Bruno', 'Céleste'], f'bouton={clicked} reçu={got}')
    au = next((x for x in got if x['n'] == 'Aurore'), {})
    br = next((x for x in got if x['n'] == 'Bruno'), {})
    check('import : sexe et gène Pastel lus', au.get('sex') == 'female' and 'pastel' in (au.get('g') or {}), au)
    check('import : het Clown lu', 'clown' in json.dumps(br.get('g') or {}), br)
    # même fichier une 2e fois : pas de doublon
    a.page.set_input_files('#generic-csv-file-input', path); a.page.wait_for_timeout(800)
    a.js("""(()=>{const btns=[...document.querySelectorAll('button')].filter(b=>b.offsetParent && /import/i.test(b.textContent) && !/fichier|file|choisir|choose/i.test(b.textContent)); if(btns.length) btns[btns.length-1].click();})()""")
    a.page.wait_for_timeout(800)
    check('réimport du même fichier : aucun doublon', a.js('savedSnakes.length') == 3, a.js('savedSnakes.length'))
    a.reload()
    check('animaux importés gardés après réouverture', a.js('savedSnakes.length') == 3)
    check('pas d\'erreur JS (import)', not [e for e in a.real_errors() if not e.startswith('dialog:')], a.real_errors()[:3])
    a.close()

def pick_gene(a, side, query, gene_id, status):
    a.page.fill(f'#input-{side}', query); a.page.wait_for_timeout(150)
    a.page.locator(f'#list-{side} .combo-opt[data-id="{gene_id}"][data-status="{status}"]').first.click()
    a.page.wait_for_timeout(150)

def results_map(a):
    return a.js("lastDistributions ? (()=>{const m={}; lastDistributions.forEach(d=>{const k=d.traits.map(x=>x.label).sort().join('+')||'Normal'; m[k]=(m[k]||0)+d.prob;}); return m;})() : null")

def t_calculateur(browser, url):
    section('Calculateur génétique (hors ligne)')
    a = App(browser, url, logged_in=False)
    a.open(); a.ctx.set_offline(True)  # app déjà chargée, puis réseau coupé
    a.js("showTab('calc')")
    pick_gene(a, 'male', 'pastel', 'pastel', 'single')
    a.js("runCross()"); a.page.wait_for_timeout(200)
    r = results_map(a)
    ok = r and len(r) == 2 and all(abs(v - 0.5) < 1e-9 for v in r.values())
    check('Pastel × Normal = 50 % / 50 %', ok, r)
    a.close()
    a = App(browser, url, logged_in=False); a.open(); a.ctx.set_offline(True); a.js("showTab('calc')")
    pick_gene(a, 'male', 'clown', 'clown', 'het'); pick_gene(a, 'female', 'clown', 'clown', 'het')
    a.js("runCross()"); a.page.wait_for_timeout(200)
    r = results_map(a)
    vis = [v for k, v in (r or {}).items() if k == 'Clown']
    check('het Clown × het Clown = 25 % Clown visuel', len(vis) == 1 and abs(vis[0] - 0.25) < 1e-9, r)
    html = a.js("document.getElementById('results').innerText")
    check('résultats affichés à l\'écran', '25' in html and 'Clown' in html, html[:200])
    check('pas d\'erreur JS (calculateur)', not a.real_errors(), a.real_errors()[:3])
    a.close()

FR_WORDS = re.compile(r"\b(Repas|Mangé|Mue|Refusé|Animaux|Aujourd'hui|Ajouter|Enregistrer|Supprimer|jours?|Femelle|Mâle)\b")
def t_langue(browser, url):
    section('Changement de langue')
    snakes = [make_snake(i, days_history=60) for i in range(1, 4)]
    a = App(browser, url, snakes=snakes, lang='fr')
    a.open()
    open_card(a, snakes[0]['id'])
    fr_btn = a.page.locator('#logbook-body button.tour-action-btn.fed').first.inner_text()
    fr_title = a.js("document.getElementById('logbook-body').innerText.slice(0,400)")
    a.js("setLangTop('en')"); a.page.wait_for_timeout(400)
    en_btn = a.page.locator('#logbook-body button.tour-action-btn.fed').first.inner_text()
    check('fiche ouverte : bouton Repas traduit sans recharger', fr_btn != en_btn, f'{fr_btn!r} → {en_btn!r}')
    a.js("document.getElementById('logbook-overlay').style.display='none'")
    leftovers = {}
    for tab in ['dash', 'elevage', 'mine', 'calc', 'ventes', 'incubation', 'utilitaire']:
        a.js(f"showTab('{tab}')"); a.page.wait_for_timeout(200)
        txt = a.js(f"document.getElementById('view-{tab}').innerText")
        hits = sorted(set(FR_WORDS.findall(txt)) - {'jour', 'jours'})
        if hits: leftovers[tab] = hits[:6]
    check('anglais : aucun mot français courant visible dans les onglets', not leftovers, leftovers)
    a.reload()
    check('la langue choisie reste après réouverture', a.js('currentLang') == 'en')
    a.js("setLangTop('fr')"); a.page.wait_for_timeout(300)
    check('retour au français', a.js('currentLang') == 'fr' and a.js("document.documentElement.lang") in ('fr', 'fr-CA', None, ''))
    check('pas d\'erreur JS (langue)', not a.real_errors(), a.real_errors()[:3])
    a.close()

def t_parite_traductions(browser, url):
    section('Traductions FR/EN')
    a = App(browser, url, logged_in=False); a.open(wait=300)
    r = a.js("""(()=>{ const T = (typeof TRANSLATIONS!=='undefined') ? TRANSLATIONS : (typeof I18N!=='undefined' ? I18N : null);
      if(!T || !T.fr || !T.en) return null;
      const fr=Object.keys(T.fr), en=Object.keys(T.en);
      return { onlyFr: fr.filter(k=>!(k in T.en)), onlyEn: en.filter(k=>!(k in T.fr)) }; })()""")
    if r is None:
        check('dictionnaire de traduction trouvé', False, 'ni TRANSLATIONS ni I18N avec .fr/.en')
    else:
        check('mêmes clés en français et en anglais', not r['onlyFr'] and not r['onlyEn'], r)
    missing = a.js("[...document.querySelectorAll('[data-i18n]')].map(e=>e.dataset.i18n).filter((k,i,arr)=>arr.indexOf(k)===i).filter(k=>{ try{ return tLang(k,'en')===k || tLang(k,'fr')===k; }catch(e){ return true; } })")
    check('chaque data-i18n de la page a sa traduction', not missing, missing[:10])
    a.close()

# ---------------------------------------------------------------- 3. mesure (éleveur grincheux, point 1)
def t_perf(browser, url):
    section('Mesure : 200 animaux + 2 ans d\'historique')
    rng = random.Random(42)
    snakes = [make_snake(i, days_history=730, rng=rng) for i in range(1, 201)]
    raw = json.dumps(snakes)
    n_events = sum(len(s['health']['events']) for s in snakes)
    print(f'  données : {len(snakes)} animaux, {n_events} événements, {len(raw)/1024/1024:.2f} Mo de JSON')
    a = App(browser, url, snakes=snakes)
    # Processeur ralenti ×4 ≈ iPhone moyen (approximation, pas une vraie mesure iPhone)
    cdp = a.ctx.new_cdp_session(a.page); cdp.send('Emulation.setCPUThrottlingRate', {'rate': 4})
    took = a.open(wait=9000)  # laisse passer la synchro et la copie automatique du démarrage
    m = a.js("""(()=>{ const t0=performance.now(); showTab('elevage'); const t1=performance.now(); showTab('dash'); const t2=performance.now();
      openLogbook(savedSnakes[0].id); const t3=performance.now(); document.getElementById('logbook-overlay').style.display='none';
      return { elevage:Math.round(t1-t0), dash:Math.round(t2-t1), journal:Math.round(t3-t2),
        appMo:(estimateStorageBytes()/1024/1024).toFixed(2), budgetMo:(STORAGE_BUDGET_BYTES/1024/1024),
        dcl: Math.round(performance.getEntriesByType('navigation')[0].domContentLoadedEventEnd) }; })()""")
    shown = a.js("showTab('mine'), document.querySelectorAll('#view-mine button[data-act=\"logbook\"]').length")
    print(f'  fiches affichées d\'un coup dans Mes reptiles : {shown} sur {len(snakes)}')
    sid = a.js("document.querySelector('#view-mine button[data-act=\"logbook\"]').dataset.id")
    open_card(a, sid)
    a.page.locator('#logbook-body button.tour-action-btn.fed').first.click()
    a.js("window.__t0 = 0; document.addEventListener('click', ()=>{ window.__t0 = performance.now(); }, {capture:true, once:true})")
    a.page.locator(f"button[onclick=\"confirmFed('{sid}', 'complete')\"]").click()
    save_ms = a.js("new Promise(r=>requestAnimationFrame(()=>setTimeout(()=>r(Math.round(performance.now()-window.__t0)),0)))")
    print(f'  ouverture (jusqu\'à l\'app prête) : {took:.2f} s   (DOMContentLoaded {m["dcl"]} ms)')
    print(f'  onglet Élevage : {m["elevage"]} ms   tableau de bord : {m["dash"]} ms   journal d\'un animal : {m["journal"]} ms')
    print(f'  toucher « Mangé au complet » → écran à jour : {save_ms} ms')
    print(f'  espace utilisé selon l\'app (sans photos) : {m["appMo"]} Mo sur un budget d\'alerte de {m["budgetMo"]:.0f} Mo')
    check('mesure faite sans erreur JS', not a.real_errors(), a.real_errors()[:3])
    a.close()
    return m, took, save_ms

# ---------------------------------------------------------------- lancement
def main():
    from playwright.sync_api import sync_playwright
    print(f'LOCUS — tests sur {INDEX}')
    static_checks()
    srv, url = start_server()
    tests = [t_ouverture, t_repas, t_synchro, t_deux_appareils_ouverts, t_suppression_ne_revient_pas, t_grille_elevage_a_jour, t_import, t_calculateur, t_langue, t_parite_traductions]
    if PERF: tests.append(t_perf)
    with sync_playwright() as p:
        browser = p.chromium.launch()
        for t in tests:
            try: t(browser, url)
            except Exception as e:
                check(f'{t.__name__} s\'est rendu au bout', False, ''.join(traceback.format_exception_only(type(e), e)).strip())
        browser.close()
    srv.shutdown()
    bad = [r for r in RESULTS if not r[1]]
    print(f'\n{len(RESULTS) - len(bad)}/{len(RESULTS)} vérifications passent.' + (f'  ({len(WARNINGS)} avertissement(s) — limites connues)' if WARNINGS else ''))
    if bad:
        print('ÉCHECS :'); [print('  - ' + r[0]) for r in bad]
    sys.exit(1 if bad else 0)

if __name__ == '__main__':
    main()
