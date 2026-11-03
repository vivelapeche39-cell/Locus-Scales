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
def parcours_snake():
    s = make_snake(7, days_history=500)
    yr = TODAY.year
    s['health']['vetVisits'] = [{"id": "v1", "date": iso(TODAY - datetime.timedelta(days=20)), "reason": "<b>Bilan</b> & contrôle", "findings": ""}]
    # pesée notée par le bouton : elle est dans weights ET dans les événements (ne doit pas compter 2 fois)
    d = iso(TODAY - datetime.timedelta(days=3))
    s['health']['weights'].append({"date": d, "value": 1234})
    s['health']['events'].append({"date": d, "type": "weigh", "value": 1234})
    s['health']['events'].append({"date": iso(TODAY - datetime.timedelta(days=10)), "type": "lock", "partner": "<i>Kiwi</i>", "pairingId": "p1"})
    s['acquisitionDate'] = iso(TODAY - datetime.timedelta(days=480))
    return s

def t_parcours(browser, url):
    section('Parcours (v5.36)')
    s = parcours_snake(); sid = s['id']
    a = App(browser, url, snakes=[s, make_snake(2)]); a.open()
    open_card(a, sid)
    box = '#parcours-box'
    check('section Parcours présente sur la fiche', a.page.locator(box).count() == 1)
    check('cellulaire : verticale par défaut', a.page.locator(box + ' .prc-v').count() == 1)
    check('années passées repliées, année en cours ouverte',
          a.js(f"[...document.querySelectorAll('{box} .prc-year')].map(b=>b.getAttribute('aria-expanded'))") [:2] == ['true', 'false'],
          a.js(f"[...document.querySelectorAll('{box} .prc-year')].map(b=>b.textContent)"))
    html = a.js(f"document.querySelector('{box}').innerHTML")
    check('texte libre échappé (véto, partenaire)', '<b>Bilan' not in html and '&lt;b&gt;Bilan' in html and '<i>Kiwi' not in html, html[:0])
    n_grp = a.page.locator(box + ' .prc-grp').count()
    check('repas réguliers regroupés', n_grp >= 1, n_grp)
    if n_grp:
        rows0 = a.page.locator(box + ' .prc-row').count()
        txt = a.page.locator(box + ' .prc-grp').first.inner_text()
        n = int(re.match(r'\s*(\d+)', txt).group(1))
        a.page.locator(box + ' .prc-grp').first.click(); a.page.wait_for_timeout(150)
        rows1 = a.page.locator(box + ' .prc-row').count()
        check('« Voir » détaille le groupe', rows1 == rows0 + n, (rows0, n, rows1))
    # filtre Repas
    a.page.locator(box + ' .prc-chip').first.click(); a.page.wait_for_timeout(150)
    t = a.page.locator(box + ' .prc-v').inner_text()
    check('filtre Repas : les repas disparaissent', a.page.locator(box + ' .prc-grp').count() == 0 and 'A mangé' not in t, t[:200])
    a.page.locator(box + ' .prc-chip').first.click(); a.page.wait_for_timeout(150)
    # horizontale
    a.page.locator(box + ' .prc-seg button').nth(1).click(); a.page.wait_for_timeout(250)
    yr = TODAY.year
    n_exp = a.js("(()=>{const s=savedSnakes.find(x=>x.id===%s); return parcoursEvents(s).filter(e=>e.y===%d).length;})()" % (json.dumps(sid), yr))
    n_dots = a.page.locator(box + ' .prc-hdot').count()
    check('horizontale : un point par moment de l\'année', n_dots == n_exp and n_dots > 0, (n_dots, n_exp))
    n_w = len([w for w in s['health']['weights'] if w['date'].startswith(str(yr))])
    n_wdots = a.js(f"[...document.querySelectorAll('{box} .prc-hdot .v')].length")
    check('pesée notée par le bouton comptée une seule fois', n_wdots == n_w, (n_wdots, n_w))
    sl = a.js("document.getElementById('parcours-h').scrollLeft")
    check('horizontale : s\'ouvre près d\'aujourd\'hui (défilée)', TODAY.month < 3 or sl > 0, sl)
    before = a.page.locator(box + ' .prc-card').inner_text()
    a.page.locator(box + ' .prc-hdot').first.click(); a.page.wait_for_timeout(150)
    after = a.page.locator(box + ' .prc-card').inner_text()
    check('toucher un point affiche son détail', before != after, (before[:60], after[:60]))
    a.reload(wait=4500); open_card(a, sid)  # attendre la fin du message « Données récupérées »
    check('choix horizontal retenu après réouverture', a.page.locator(box + ' .prc-hscroll').count() == 1)
    # un repas noté met le Parcours à jour
    a.js('closeLogbook()'); a.page.wait_for_timeout(150)
    tour_fed(a, sid)
    today_dot = a.js("(()=>{const s=savedSnakes.find(x=>x.id===%s); return parcoursEvents(s).some(e=>e.d===localTodayStr() && e.fed);})()" % json.dumps(sid))
    n_dots2 = a.page.locator(box + ' .prc-hdot').count()
    check('repas noté : visible dans le Parcours', today_dot and n_dots2 == n_dots + 1, (today_dot, n_dots, n_dots2))
    check('pas d\'erreur JS (Parcours)', not a.real_errors(), a.real_errors()[:3])
    a.close()
    # anglais + animal sans historique
    b = App(browser, url, snakes=[parcours_snake(), make_snake(3)], lang='en'); b.open()
    open_card(b, sid)
    head = b.js("document.getElementById('parcours-box').parentElement.querySelector('h3').textContent")
    t = b.page.locator(box).inner_text()
    check('anglais : « History », sans mots français', 'History' in head and 'Vertical' in t and not re.search(r'\b(Repas|Mues|Pesées|Verticale|repas|aux \d+ jours)\b', t), (head, t[:200]))
    b.js('closeLogbook()'); b.page.wait_for_timeout(150)
    open_card(b, make_snake(3)['id'])
    t = b.page.locator(box).inner_text()
    check('animal sans historique : message clair', 'Nothing yet' in t or 'Born' in t, t[:120])
    check('pas d\'erreur JS (Parcours anglais)', not b.real_errors(), b.real_errors()[:3])
    b.close()

def t_proie_lot(browser, url):
    section('Proie en lot (v5.37)')
    snakes = [make_snake(i) for i in range(1, 7)]
    for s_ in snakes[:4]: s_.update({'preySpecies': 'mouse', 'preySize': 'Pinky', 'preySizeEstimated': False})
    snakes[4].update({'preySpecies': 'rat', 'preySize': 'Small', 'preySizeEstimated': False})
    snakes[5].update({'species': 'leopard_gecko', 'preySpecies': 'cricket', 'preySize': 'Small', 'genes': {}})
    a = App(browser, url, snakes=snakes); a.open()
    get = lambda: {s['id']: (s.get('preySpecies'), s.get('preySize'), bool(s.get('preySizeEstimated'))) for s in a.js("savedSnakes")}
    ids = [s_['id'] for s_ in snakes]
    # B) Sélection multiple : cocher 1 bébé → « Proie » → « Cocher aussi tous ceux en Souris Pinky » → Fuzzy
    a.js("showTab('mine')"); a.page.wait_for_timeout(200)
    a.page.locator('#batch-mode-toggle-btn').click(); a.page.wait_for_timeout(200)
    a.page.locator(f'.batch-select-cb[data-batch-id="{ids[0]}"]').check(); a.page.wait_for_timeout(100)
    a.page.locator('#batch-action-bar button:has-text("Proie")').click(); a.page.wait_for_timeout(200)
    same = a.page.locator('#quick-modal-body button:has-text("Cocher aussi")')
    check('« Cocher aussi tous ceux en Souris Pinky » proposé (+3)', same.count() == 1 and '+3' in same.first.inner_text(), same.count() and same.first.inner_text())
    same.first.click(); a.page.wait_for_timeout(200)
    title = a.js("document.getElementById('quick-modal-title').textContent")
    check('après « Cocher aussi » : 4 animaux sélectionnés', '4 ' in title and a.js("batchSelectedIds.size") == 4, title)
    a.page.select_option('#bp-sp', 'mouse'); a.page.select_option('#bp-size', 'Fuzzy')
    a.page.locator('#quick-modal-body button:has-text("Appliquer")').click(); a.page.wait_for_timeout(300)
    g = get()
    check('les 4 bébés passent en Fuzzy (confirmé, pas estimé)', all(g[i] == ('mouse', 'Fuzzy', False) for i in ids[:4]), [g[i] for i in ids[:4]])
    check('les autres ne bougent pas', g[ids[4]] == ('rat', 'Small', False) and g[ids[5]][:2] == ('cricket', 'Small'), (g[ids[4]], g[ids[5]]))
    # proie pas adaptée à l'espèce : le gecko est sauté
    a.page.locator('#batch-mode-toggle-btn').click(); a.page.wait_for_timeout(200)
    a.page.locator(f'.batch-select-cb[data-batch-id="{ids[5]}"]').check()
    a.page.locator(f'.batch-select-cb[data-batch-id="{ids[4]}"]').check(); a.page.wait_for_timeout(100)
    a.page.locator('#batch-action-bar button:has-text("Proie")').click(); a.page.wait_for_timeout(200)
    a.page.select_option('#bp-sp', 'mouse'); a.page.select_option('#bp-size', 'Adult')
    a.page.locator('#quick-modal-body button:has-text("Appliquer")').click(); a.page.wait_for_timeout(300)
    g = get(); toast = a.js("[...document.querySelectorAll('#toast-stack .toast')].map(t=>t.textContent).join(' | ')")
    check('proie pas adaptée : le gecko est sauté et nommé', g[ids[5]][:2] == ('cricket', 'Small') and g[ids[4]][:2] == ('mouse', 'Adult') and 'Testeur 6' in toast, (g[ids[5]], g[ids[4]], toast[-160:]))
    a.reload(wait=4500)
    g = get()
    check('proies en lot gardées après réouverture', all(g[i][:2] == ('mouse', 'Fuzzy') for i in ids[:4]), [g[i] for i in ids[:4]])
    # A) fenêtre « Proie de N animaux sans taille » (Mode Tournée)
    a.js("""(()=>{ savedSnakes.slice(0,3).forEach(s=>{ s.preySpecies=null; s.preySize=null; }); openTourFedPreyModal(null, savedSnakes.slice(0,3)); })()""")
    a.page.wait_for_timeout(200)
    check('fenêtre Mode Tournée : une case par animal + « Tout cocher »', a.page.locator('.tfp-row .tfp-cb').count() == 3 and a.js("document.getElementById('tfp-all').checked"))
    a.page.locator('.tfp-row .tfp-cb').nth(2).uncheck(); a.page.wait_for_timeout(100)
    check('décocher une ligne décoche « Tout cocher »', not a.js("document.getElementById('tfp-all').checked") and '(2/3)' in a.js("document.getElementById('tfp-count').textContent"))
    a.page.select_option('#tfp-bulk-sp', 'mouse'); a.page.select_option('#tfp-bulk-size', 'Hopper')
    a.page.locator('#quick-modal-body button:has-text("Appliquer aux cochés")').click(); a.page.wait_for_timeout(150)
    vals = a.js("[...document.querySelectorAll('.tfp-row')].map(r=>r.querySelector('.tfp-sp').value+'|'+r.querySelector('.tfp-size').value)")
    check('« Appliquer aux cochés » remplit seulement les lignes cochées', vals[0] == vals[1] == 'mouse|Hopper' and vals[2] != 'mouse|Hopper', vals)
    a.page.locator('#quick-modal-body button.save-btn').click(); a.page.wait_for_timeout(300)
    g = get()
    check('« Tout confirmer » enregistre la proie choisie en lot', g[ids[0]][:2] == ('mouse', 'Hopper') and g[ids[1]][:2] == ('mouse', 'Hopper'), (g[ids[0]], g[ids[1]]))
    check('pas d\'erreur JS (proie en lot)', not a.real_errors(), a.real_errors()[:3])
    a.close()
    b = App(browser, url, snakes=[make_snake(1)], lang='en'); b.open()
    b.js("showTab('mine')"); b.page.wait_for_timeout(200)
    b.page.locator('#batch-mode-toggle-btn').click(); b.page.wait_for_timeout(150)
    b.page.locator('.batch-select-cb').first.check(); b.page.wait_for_timeout(100)
    b.page.locator('#batch-action-bar button:has-text("Prey")').click(); b.page.wait_for_timeout(200)
    txt = b.js("document.getElementById('quick-modal-overlay').textContent")
    check('anglais : fenêtre Proie traduite', 'Usual prey' in txt and 'Apply to' in txt and not re.search(r'\b(Proie|Appliquer|animaux|cochés)\b', txt), txt[:200])
    b.close()


def t_decongelation_et_selection(browser, url):
    section('Liste de décongélation masquable + Sélection multiple visible (v5.37)')
    snakes = [make_snake(i) for i in range(1, 4)]
    for s_ in snakes: s_.update({'preySpecies': 'mouse', 'preySize': 'Adult', 'feedingIntervalDays': 1})
    a = App(browser, url, snakes=snakes); a.open()
    a.js("showTab('mine')"); a.page.wait_for_timeout(200)
    check('« Sélection multiple » visible sans ouvrir Filtres & tri', a.page.locator('#batch-mode-toggle-btn').is_visible())
    a.page.locator('#batch-mode-toggle-btn').click(); a.page.wait_for_timeout(150)
    a.page.locator('.batch-select-cb').first.check(); a.page.wait_for_timeout(150)
    check('barre d\'actions visible avec Filtres & tri fermé', a.page.locator('#batch-action-bar').is_visible() and not a.page.locator('#mine-filters-panel').is_visible())
    a.page.locator('#batch-mode-toggle-btn').click()
    a.js("showTab('elevage'); showSubtab('nourriture')"); a.page.wait_for_timeout(300)
    btn = a.page.locator('#defrost-toggle-btn')
    check('liste de décongélation affichée par défaut, bouton « Masquer »', a.page.locator('#defrost-list').is_visible() and 'Masquer' in btn.inner_text(), btn.inner_text())
    btn.click(); a.page.wait_for_timeout(150)
    check('« Masquer » cache la liste', not a.page.locator('#defrost-list').is_visible() and 'Afficher' in btn.inner_text(), btn.inner_text())
    a.reload(wait=2500); a.js("showTab('elevage'); showSubtab('nourriture')"); a.page.wait_for_timeout(300)
    check('liste masquée retenue après réouverture', not a.page.locator('#defrost-list').is_visible())
    a.page.locator('#defrost-toggle-btn').click(); a.page.wait_for_timeout(150)
    check('« Afficher » la remet', a.page.locator('#defrost-list').is_visible())
    check('pas d\'erreur JS (décongélation / sélection)', not a.real_errors(), a.real_errors()[:3])
    a.close()

def t_unites(browser, url):
    section('Unités °C/°F, g/oz-lb, cm/po (v5.38)')
    s = make_snake(11); sid = s['id']
    s['careParams'] = {"tempWarm": 31, "tempCool": 26, "humidity": 60}
    s['health']['weights'] = [{"date": iso(TODAY - datetime.timedelta(days=30)), "value": 1360}]
    a = App(browser, url, snakes=[s]); a.open()
    a.js("showTab('mine')"); a.page.wait_for_timeout(150)
    open_card(a, sid)
    body = a.js("document.getElementById('logbook-body').textContent")
    check('français par défaut : °C, g', 'Côté chaud (°C)' in body and '1360 g' in body, body[body.find('Côté chaud'):][:40])
    a.js("closeLogbook(); openConfigModal()"); a.page.wait_for_timeout(150)
    a.page.locator('#quick-modal-body button:has-text("°F")').first.click(); a.page.wait_for_timeout(150)
    a.page.locator('#quick-modal-body button:has-text("oz / lb")').click(); a.page.wait_for_timeout(150)
    a.page.locator('#quick-modal-body button:has-text("pouces")').first.click(); a.page.wait_for_timeout(150)
    a.js("closeQuickModal()")
    open_card(a, sid)
    warm = a.page.locator('#logbook-body input[oninput*="tempWarm"]')
    check('°F : 31 °C affiché 87.8 dans la case', 'Côté chaud (°F)' in a.js("document.getElementById('logbook-body').textContent") and warm.input_value() == '87.8', warm.input_value())
    warm.fill('88'); warm.dispatch_event('change'); a.page.wait_for_timeout(700)
    c = a.js("savedSnakes.find(x=>x.id===%s).careParams.tempWarm" % json.dumps(sid))
    check('°F saisi → gardé en °C dans les données (88 °F = 31,11 °C)', abs(c - 31.11) < 0.02, c)
    # pesée en oz
    a.page.locator('#logbook-body button.tour-action-btn[onclick*="weigh"]').first.click(); a.page.wait_for_timeout(200)
    lbl = a.js("document.getElementById('quick-modal-body').textContent")
    a.page.fill('#quick-weight-input', '49.4'); a.page.locator('#quick-modal-body button.save-btn').click(); a.page.wait_for_timeout(300)
    w = a.js("savedSnakes.find(x=>x.id===%s).health.weights.slice(-1)[0].value" % json.dumps(sid))
    check('pesée saisie en oz → gardée en g (49,4 oz = 1400,5 g)', 'oz' in lbl and abs(w - 1400.5) < 0.1, (w, lbl[-40:]))
    body = a.js("document.getElementById('logbook-body').textContent")
    check('historique affiché en lb/oz avec écart', '3 lb 1,4 oz' in body and '+1,4 oz' in body, body[body.find('lb')-20:][:80])
    # longueur en pouces
    a.page.locator('#logbook-body button.tour-action-btn[onclick*="length"]').first.click(); a.page.wait_for_timeout(200)
    a.page.fill('#quick-length-input', '40'); a.page.locator('#quick-modal-body button.save-btn').click(); a.page.wait_for_timeout(300)
    L = a.js("savedSnakes.find(x=>x.id===%s).health.lengths.slice(-1)[0].value" % json.dumps(sid))
    body = a.js("document.getElementById('logbook-body').textContent")
    check('longueur saisie en po → gardée en cm (40 po = 101,6 cm), affichée « 40 po »', abs(L - 101.6) < 0.05 and '40 po' in body, (L,))
    a.js("closeLogbook(); showTab('mine')"); a.page.wait_for_timeout(200)
    card = a.js("document.getElementById('saved-grid').textContent")
    check('carte de Mes reptiles en lb/oz', '3 lb 1,4 oz' in card, card[card.find('⚖'):][:60])
    check('conversion lb/oz sans « 16 oz » (1360 g = 3 lb)', a.js("fmtWeight(1360)") == '3 lb' and a.js("fmtWeight(1400.5)") == '3 lb 1,4 oz', (a.js("fmtWeight(1360)"), a.js("fmtWeight(1400.5)")))
    a.reload(wait=2500); open_card(a, sid)
    check('unités retenues après réouverture', 'Côté chaud (°F)' in a.js("document.getElementById('logbook-body').textContent"))
    check('pas d\'erreur JS (unités)', not a.real_errors(), a.real_errors()[:3])
    a.close()
    b = App(browser, url, snakes=[s], lang='en'); b.open()
    open_card(b, sid)
    body = b.js("document.getElementById('logbook-body').textContent")
    check('anglais sans réglage : °F et pouces par défaut, grammes gardés', 'Warm side (°F)' in body and '1360 g' in body, body[body.find('Warm side'):][:30])
    b.close()

def t_unites_etape2(browser, url):
    section('Unités, étape 2 (v5.39)')
    a = App(browser, url, snakes=[make_snake(1)]); a.open()
    # textes : paires et valeurs seules, dans les deux sens
    cases = a.js("""[
      unitProseTemp('Côté chaud : 88-92°F (31-33°C).', 'c'),
      unitProseTemp('Côté chaud : 88-92°F (31-33°C).', 'f'),
      unitProseTemp('Chaud 30-32°C / froid 24-26°C', 'f'),
      unitProseTemp('~60 jours à 29-30,5 °C (84-87 °F)', 'c'),
      unitProseTemp('zone chaude ~91°F seulement', 'c'),
      unitProseTemp('Rien à convertir ici, 30 % humidité', 'f'),
      unitProseTemp('précision typique ±2°F', 'c'),
      unitProseTemp('chutes jusqu\\'à 18-21°C/65-70°F', 'f')
    ]""")
    check('texte : un écart « ±2°F » devient ±1,1 °C (pas une température)', cases[6] == 'précision typique ±1,1 °C', cases[6])
    check('texte : paire avec barre oblique « 18-21°C/65-70°F »', cases[7] == "chutes jusqu'à 65-70 °F", cases[7])
    check('texte : garde la moitié dans l\'unité choisie',
          cases[0] == 'Côté chaud : 31-33 °C.' and cases[1] == 'Côté chaud : 88-92 °F.' and cases[3] == '~60 jours à 29-30,5 °C', cases[:4])
    check('texte : convertit une valeur seule', cases[2] == 'Chaud 86-90 °F / froid 75-79 °F' and cases[4] == 'zone chaude ~32,8 °C seulement' and cases[5].endswith('humidité'), (cases[2], cases[4]))
    # observateur : nouveau texte converti, contexte incubateur respecté, aucun glissement quand on change d'unité
    a.js("""(()=>{ const d=document.createElement('div'); d.id='u-t'; d.innerHTML='<p id="u-a">Chaud 30-32°C</p><p id="u-b" data-unit-ctx="inc">Incubation 31,5 °C</p>'; document.body.appendChild(d); })()""")
    a.page.wait_for_timeout(100)
    t1 = a.js("[document.getElementById('u-a').textContent, document.getElementById('u-b').textContent]")
    check('français par défaut : soins en °C, incubateur en °F', t1 == ['Chaud 30-32°C', 'Incubation 89 °F'], t1)
    a.js("openConfigModal()"); a.page.wait_for_timeout(100)
    cfg = a.js("document.getElementById('quick-modal-body').textContent")
    check('Configuration : réglages Incubateur et Dimensions des terrariums', 'Incubateur' in cfg and 'Dimensions des terrariums' in cfg and '°C' in cfg and '°F' in cfg)
    a.js("setUnitPref('temp','f')"); a.page.wait_for_timeout(100)
    a.js("setUnitPref('temp','c')"); a.js("setUnitPref('temp','f')"); a.js("setUnitPref('temp','c')"); a.page.wait_for_timeout(100)
    t2 = a.js("document.getElementById('u-a').textContent")
    check('changer d\'unité plusieurs fois ne déforme pas le texte', t2 == 'Chaud 30-32°C', t2)
    a.js("closeQuickModal()")
    # incubation : saisie en °F, gardée en °C, indice TSD en °F
    v = a.js("(()=>{ const c={id:'cl_t', incubTempC:null}; clutches.push(c); setClutchIncubTemp('cl_t','86'); return c.incubTempC; })()")
    hint = a.js("tsdHintText('leopard_gecko', 30)")
    check('incubateur en °F : 86 saisi → 30 °C gardé, indice affiché en °F', v == 30 and '86 °F' in hint, (v, hint[:60]))
    # liens publics : unités du propriétaire dans le lien
    link = a.js("showUrlFor('abc')")
    check('lien de show : unités du propriétaire incluses', '&u=c.g.cm.f.in' in link, link)
    # import : « 3 lb 2 oz »
    g = a.js("importWeightGrams('3 lb 2 oz', null)")
    check('import : « 3 lb 2 oz » = 1417 g (pas 32 lb)', abs(g - 1417.5) < 1, g)
    check('pas d\'erreur JS (unités étape 2)', not a.real_errors(), a.real_errors()[:3])
    a.close()
    # page ouverte avec les unités d'un propriétaire
    b = App(browser, url.replace('index.html', 'index.html?u=c.lb.cm.c.cm'), snakes=[make_snake(1)]); b.open()
    check('lien avec &u= : la page suit les unités du propriétaire', b.js("JSON.stringify(unitPrefs())") == json.dumps({"temp": "c", "weight": "lb", "length": "cm", "inc": "c", "dims": "cm"}, separators=(',', ':')), b.js("JSON.stringify(unitPrefs())"))
    b.close()

def t_proie_repas(browser, url):
    section('Proie au repas (v5.40)')
    s = make_snake(21); sid = s['id']
    s.update({'preySpecies': 'mouse', 'preySize': 'Pinky', 'preyType': 'frozen', 'preySizeEstimated': False})
    n = make_snake(22); nid = n['id']
    for k in ('preySpecies', 'preySize'): n.pop(k, None)
    a = App(browser, url, snakes=[s, n]); a.open()
    a.js("feederStock[feederStockKey('mouse','Pinky')] = 10; feederStock[feederStockKey('mouse','Fuzzy')] = 10; feederStock[feederStockKey('mouse','Hopper')] = 5;")
    last = lambda i: a.js("(()=>{ const x=savedSnakes.find(y=>y.id===%s); const e=x.health.events.filter(e=>e.type==='fed').slice(-1)[0]; return { sp:e.preySpecies||null, sz:e.preySize||null, fsp:x.preySpecies||null, fsz:x.preySize||null, est:!!x.preySizeEstimated }; })()" % json.dumps(i))
    stock = lambda z: a.js("feederStock[feederStockKey('mouse',%s)]" % json.dumps(z))
    # 1) un seul toucher, comme avant
    tour_fed(a, sid)
    r = last(sid)
    check('un toucher : repas noté avec la proie habituelle (Pinky)', r['sp'] == 'mouse' and r['sz'] == 'Pinky' and r['fsz'] == 'Pinky', r)
    check('un toucher : le stock de Pinky baisse de 1', stock('Pinky') == 9, stock('Pinky'))
    # 2) changer de taille → demandé dès ce repas (coché) → nouvelle proie habituelle
    a.page.locator('#logbook-body button.tour-action-btn.fed').first.click(); a.page.wait_for_timeout(150)
    check('fenêtre Repas : Pinky déjà choisie, pas de question tant qu\'on ne change rien', a.page.locator('#fed-prey-box button[aria-pressed="true"]:has-text("Pinky")').count() == 1 and a.page.locator('#fed-habit').count() == 0)
    a.page.locator('#fed-prey-box button:has-text("Fuzzy")').click(); a.page.wait_for_timeout(100)
    check('autre taille touchée : « En faire la proie habituelle » apparaît, cochée', a.page.locator('#fed-habit').is_checked())
    a.page.locator(f"button[onclick=\"confirmFed('{sid}', 'complete')\"]").click(); a.page.wait_for_timeout(200)
    r = last(sid)
    check('repas en Fuzzy + Fuzzy devient la proie habituelle', r['sz'] == 'Fuzzy' and r['fsz'] == 'Fuzzy' and not r['est'], r)
    check('stock : Fuzzy baisse, Pinky ne bouge pas', stock('Fuzzy') == 9 and stock('Pinky') == 9, (stock('Fuzzy'), stock('Pinky')))
    # 3) juste cette fois
    a.page.locator('#logbook-body button.tour-action-btn.fed').first.click(); a.page.wait_for_timeout(150)
    a.page.locator('#fed-prey-box button:has-text("Hopper")').click(); a.page.wait_for_timeout(100)
    a.page.locator('#fed-habit').uncheck()
    a.page.locator(f"button[onclick=\"confirmFed('{sid}', 'complete')\"]").click(); a.page.wait_for_timeout(200)
    r = last(sid)
    check('« juste cette fois » : repas en Hopper, la fiche reste en Fuzzy', r['sz'] == 'Hopper' and r['fsz'] == 'Fuzzy', r)
    check('stock : Hopper baisse (5 → 4)', stock('Hopper') == 4, stock('Hopper'))
    body = a.js("document.getElementById('logbook-body').textContent")
    check('journal : la taille donnée est écrite (Hopper)', 'Hopper' in body)
    # 4) animal sans proie : choisir au premier repas
    a.js("closeLogbook()"); a.page.wait_for_timeout(100)
    open_card(a, nid)
    a.page.locator('#logbook-body button.tour-action-btn.fed').first.click(); a.page.wait_for_timeout(150)
    a.page.select_option('#fed-prey-box select', 'rat'); a.page.wait_for_timeout(100)
    a.page.locator('#fed-prey-box button:has-text("Weanling")').click(); a.page.wait_for_timeout(100)
    a.page.locator(f"button[onclick=\"confirmFed('{nid}', 'complete')\"]").click(); a.page.wait_for_timeout(200)
    r = last(nid)
    check('sans proie : choisie au 1er repas → devient la proie habituelle', r['sp'] == 'rat' and r['sz'] == 'Weanling' and r['fsp'] == 'rat' and r['fsz'] == 'Weanling', r)
    a.reload(wait=2500)
    check('proie habituelle gardée après réouverture', last(sid)['fsz'] == 'Fuzzy' and last(nid)['fsz'] == 'Weanling')
    check('pas d\'erreur JS (proie au repas)', not a.real_errors(), a.real_errors()[:3])
    a.close()
    b = App(browser, url, snakes=[s], lang='en'); b.open()
    open_card(b, sid)
    b.page.locator('#logbook-body button.tour-action-btn.fed').first.click(); b.page.wait_for_timeout(150)
    b.page.locator('#fed-prey-box button:has-text("Fuzzy")').click(); b.page.wait_for_timeout(100)
    t = b.js("document.getElementById('fed-prey-box').textContent")
    check('anglais : fenêtre Repas traduite', 'Prey given' in t and 'usual prey' in t and not re.search(r'Proie|habituelle', t), t[:120])
    b.close()

def t_tournee_deselection(browser, url):
    section('Mode Tournée : retoucher pour désélectionner (v5.41)')
    snakes = [make_snake(i) for i in range(31, 36)]
    for k, s_ in enumerate(snakes[:3]): s_['placement'] = {"mode": "rack", "rackId": "rack_1", "row": 1, "tub": k+1}
    for s_ in snakes[3:]: s_['placement'] = {"mode": "terrarium", "terrariumId": None, "row": None, "tub": None}
    snakes[4]['preyType'] = 'live'
    a = App(browser, url, snakes=snakes); a.open(wait=3500)
    a.js("showTab('elevage'); showSubtab('tour')"); a.page.wait_for_timeout(300)
    size = lambda: a.js("tourSelection.size")
    rackBtn = lambda: a.page.locator('#tour-grid [data-allrack]').first
    rackBtn().click(); a.page.wait_for_timeout(150)
    check('« Tout ce rack » : 3 bacs sélectionnés, bouton marqué ✓', size() == 3 and '✓' in rackBtn().inner_text(), (size(), rackBtn().inner_text()))
    rackBtn().click(); a.page.wait_for_timeout(150)
    check('« Tout ce rack » retouché : désélectionné', size() == 0 and '✓' not in rackBtn().inner_text(), size())
    a.page.locator('#tour-select-terra').click(); a.page.wait_for_timeout(150)
    check('« Sél. tous » terrariums : 2 sélectionnés', size() == 2 and '✓' in a.page.locator('#tour-select-terra').inner_text(), size())
    a.page.locator('#tour-select-terra').click(); a.page.wait_for_timeout(150)
    check('« Sél. tous » retouché : désélectionnés', size() == 0)
    # un rack sélectionné + terrariums retouchés : le rack reste
    rackBtn().click(); a.page.locator('#tour-select-terra').click(); a.page.locator('#tour-select-terra').click(); a.page.wait_for_timeout(150)
    check('retoucher les terrariums ne touche pas au rack', size() == 3, size())
    rackBtn().click(); a.page.wait_for_timeout(100)
    fz = a.page.locator('#tour-quickselect [onclick="selectByPreyType(\'frozen\')"]')
    fz.click(); a.page.wait_for_timeout(150)
    check('« Tout le décongelé » : 4 sélectionnés, bouton ✓', size() == 4 and '✓' in fz.inner_text(), (size(), fz.inner_text()))
    fz.click(); a.page.wait_for_timeout(150)
    check('« Tout le décongelé » retouché : sélection retirée', size() == 0 and '✓' not in fz.inner_text(), size())
    check('pas d\'erreur JS (Mode Tournée)', not a.real_errors(), a.real_errors()[:3])
    a.close()

def t_combos_bci(browser, url):
    section('Noms de combos BCI (v5.42)')
    m = make_snake(41, species='boa_bci', genes={'bci_kahl': 'visual', 'bci_anery1': 'visual', 'bci_hypo': 'single', 'bci_jungle': 'single'})
    f = make_snake(42, species='boa_bci', genes={'bci_kahl': 'visual', 'bci_anery1': 'visual', 'bci_hypo': 'single'})
    m['sex'], f['sex'] = 'male', 'female'
    m['name'] = 'Lune'
    bp = make_snake(43)
    a = App(browser, url, snakes=[m, f, bp]); a.open(wait=3000)
    cases = a.js("""[
      speciesComboTitle({bci_kahl:'visual', bci_anery1:'visual', bci_hypo:'single', bci_jungle:'single'}, 'boa_bci'),
      speciesComboTitle({bci_kahl:'visual', bci_anery1:'visual'}, 'boa_bci'),
      speciesComboTitle({bci_sharp:'visual', bci_anery1:'visual'}, 'boa_bci'),
      speciesComboTitle({bci_bwc:'het', bci_sharp:'het', bci_anery1:'visual'}, 'boa_bci'),
      speciesComboTitle({bci_hypo:'homo', bci_kahl:'visual'}, 'boa_bci'),
      speciesComboTitle({bci_kahl:'visual', bci_anery1:{status:'visual', possible:true}}, 'boa_bci'),
      speciesComboTitle({bci_hypo:'homo', bci_jungle:'homo', bci_vpi:'visual'}, 'boa_bci'),
      speciesComboTitle({pastel:'single', spider:'single'}, 'ball_python'),
      speciesComboTitle({bci_kahl:'visual', bci_hypo:'single', bci_anery1:'het'}, 'boa_bci')
    ]""")
    check('Moonglow + Jungle (le plus précis gagne)', cases[0] == 'Moonglow · Jungle', cases[0])
    check('Snow = Kahl + Anery 1 ; Sharp Snow = Sharp + Anery 1', cases[1] == 'Snow' and cases[2] == 'Sharp Snow', cases[1:3])
    check('Artic = Paradigm (het BWC + het Sharp) + Anery 1', cases[3] == 'Artic', cases[3])
    check('Super Hypo + Albino Kahl : pas de nom inventé', cases[4] is None, cases[4])
    check('gène « possible » : ne compte pas pour un combo', cases[5] is None, cases[5])
    check('Super Tanglow = Super Hypo + Super Jungle + VPI', cases[6] == 'Super Tanglow', cases[6])
    check('python royal : Bumblebee (5.43)', cases[7] == 'Bumblebee', cases[7])
    check('het Anery ne fait pas un Moonglow (reste Sunglow)', cases[8] == 'Sunglow', cases[8])
    # calculateur
    a.js("showTab('calc')"); a.page.wait_for_timeout(200)
    a.js("loadSnake(%s,'male'); loadSnake(%s,'female'); runCross();" % (json.dumps(m['id']), json.dumps(f['id']))); a.page.wait_for_timeout(300)
    res = a.js("document.getElementById('results').textContent")
    check('calculateur : Moonglow et Moonglow · Jungle dans les résultats, gènes visibles', 'Moonglow · Jungle' in res and 'Moonglow' in res and 'Anerythristic' in res, res[:300])
    # carte + fiche + annonce
    a.js("showTab('mine')"); a.page.wait_for_timeout(200)
    card = a.js("document.getElementById('saved-grid').textContent")
    check('carte de Mes reptiles : « Moonglow · Jungle »', 'Moonglow · Jungle' in card)
    open_card(a, m['id'])
    body = a.js("document.getElementById('logbook-body').textContent")
    check('fiche : nom de combo au-dessus des gènes', 'Moonglow · Jungle' in body)
    t = a.js("generateListingText(%s,'en').title" % json.dumps(m['id']))
    tbp = a.js("generateListingText(%s,'en').title" % json.dumps(bp['id']))
    check('annonce : « Moonglow Jungle » + vraie espèce (pas « Ball Python »)', 'Moonglow Jungle' in t and 'Ball Python' not in t, t)
    check('annonce python royal : toujours « Ball Python »', 'Ball Python' in tbp, tbp)
    # import
    g = a.js("parseImportGenes('Sharp Snow het Blood', 'boa_bci').genes")
    check('import : « Sharp Snow het Blood » → Sharp + Anery 1 + het Blood', g.get('bci_sharp') == 'visual' and g.get('bci_anery1') == 'visual' and g.get('bci_blood') == 'het' and 'bci_kahl' not in g, g)
    g = a.js("parseImportGenes('Moonglow', 'boa_bci').genes")
    check('import : « Moonglow » → Kahl + Anery 1 + Hypo', g == {'bci_kahl': 'visual', 'bci_anery1': 'visual', 'bci_hypo': 'single'}, g)
    check('pas d\'erreur JS (combos)', not a.real_errors(), a.real_errors()[:3])
    a.close()

def t_combos_bp(browser, url):
    section('Noms de combos python royal (v5.43)')
    m = make_snake(51, genes={'pastel': 'single', 'spider': 'single'}); m['sex'] = 'male'
    f = make_snake(52, genes={'pastel': 'single'}); f['sex'] = 'female'
    a = App(browser, url, snakes=[m, f]); a.open(wait=3000)
    c = a.js("""[
      speciesComboTitle({pastel:'single', spider:'single'}, 'ball_python'),
      speciesComboTitle({pastel:'homo', spider:'single'}, 'ball_python'),
      speciesComboTitle({lesser:'single', pinstripe:'single', spider:'single'}, 'ball_python'),
      speciesComboTitle({albino:'het', candy:'het'}, 'ball_python'),
      speciesComboTitle({butter:'single', pastel:'single', spider:'single'}, 'ball_python'),
      speciesComboTitle({albino:'visual'}, 'ball_python'),
      speciesComboTitle({blackpastel:'single', cinnamon:'single'}, 'ball_python')
    ]""")
    check('Bumblebee, Killer Bee, King Spin', c[:3] == ['Bumblebee', 'Killer Bee', 'King Spin'], c[:3])
    check('Candino/Toffino et 8 Ball : pas en double (déjà nommés par le même locus)', c[3] is None and c[6] is None, (c[3], c[6]))
    check('Queen Bee (ambigu) jamais affiché : Butter + Bumblebee à la place', c[4] == 'Bumblebee · Butter', c[4])
    check('un seul gène : pas de nom de combo', c[5] is None, c[5])
    a.js("showTab('calc')"); a.page.wait_for_timeout(200)
    a.js("loadSnake(%s,'male'); loadSnake(%s,'female'); runCross();" % (json.dumps(m['id']), json.dumps(f['id']))); a.page.wait_for_timeout(300)
    res = a.js("document.getElementById('results').textContent")
    check('calculateur : Bumblebee et Killer Bee dans les résultats', 'Bumblebee' in res and 'Killer Bee' in res, res[:200])
    a.js("showTab('mine')"); a.page.wait_for_timeout(200)
    check('carte : « Bumblebee »', 'Bumblebee' in a.js("document.getElementById('saved-grid').textContent"))
    t = a.js("generateListingText(%s,'en').title" % json.dumps(m['id']))
    check('annonce : « Bumblebee Ball Python »', 'Bumblebee Ball Python' in t, t)
    check('pas d\'erreur JS (combos python royal)', not a.real_errors(), a.real_errors()[:3])
    a.close()

XLSX_STUB = """(()=>{ if(typeof XLSX!=='undefined' && XLSX.__real!==false && XLSX.utils && XLSX.read) return; window.XLSX = { __real:false, utils:{
  book_new:()=>({ SheetNames:[], Sheets:{} }), aoa_to_sheet:(aoa)=>({ __aoa:aoa }),
  book_append_sheet:(wb, ws, n)=>{ wb.SheetNames.push(n); wb.Sheets[n] = ws; } },
  writeFile:(wb, name)=>{ window.__xlsxOut = { name, sheets: wb.SheetNames.map(n=>({ n, rows: wb.Sheets[n].__aoa })) }; } }; })()"""

def t_export_complet(browser, url):
    section('Tout exporter en Excel (v5.44)')
    import csv
    s1 = make_snake(61, days_history=90, genes={'pastel': 'single'}); s2 = make_snake(62, days_history=60)
    s1['health']['vetVisits'] = [{"id": "v1", "date": iso(TODAY - datetime.timedelta(days=5)), "reason": "Bilan", "findings": "RAS"}]
    s1['health']['lengths'] = [{"date": iso(TODAY - datetime.timedelta(days=4)), "value": 92.5}]
    a = App(browser, url, snakes=[s1, s2]); a.open(wait=2500)
    a.js(XLSX_STUB)  # la vraie librairie (lib/xlsx.full.min.js) est dans le dépôt, pas dans le zip de test
    a.js("showTab('export')"); a.page.wait_for_timeout(200)
    a.page.locator('#view-export button[onclick="exportEverythingExcel()"]').click(); a.page.wait_for_timeout(300)
    out = a.js("window.__xlsxOut")
    sh = {x['n']: x['rows'] for x in (out or {}).get('sheets', [])}
    check('fichier : Lisez-moi + 7 onglets', list(sh.keys()) == ['Lisez-moi', 'Animaux', 'Journal', 'Longueurs', 'Santé', 'Accouplements', 'Pontes', 'Dépenses'], list(sh.keys()))
    an = sh.get('Animaux', []); jr = sh.get('Journal', [])
    n_events = sum(len(s['health']['events']) for s in (s1, s2)); n_w = sum(len(s['health']['weights']) for s in (s1, s2))
    check('Animaux : 2 lignes', len(an) == 3, len(an))
    check('Journal : chaque événement + chaque pesée', len(jr) - 1 == n_events + n_w, (len(jr) - 1, n_events, n_w))
    check('Santé et Longueurs remplis', len(sh.get('Santé', [])) == 2 and sh.get('Longueurs', [[], [0, 0, 0, 0, None]])[1][4] == 92.5)
    # l'import reconnaît les en-têtes et les activités du Journal
    hm = a.js("(h)=>mapLogHeaders(h)", jr[0]) if jr else None
    acts = a.js("(rows)=>[...new Set(rows.slice(1).map(r=>r[4]))].map(x=>[x, mapLogActivity(x)])", jr) if jr else []
    check('Journal : en-têtes reconnus par l\'import d\'historique', bool(hm), hm)
    # v5.50 — colonne Génétique à côté du nom (Journal, Longueurs, Santé) ; l'import d'historique l'ignore
    check('Journal/Longueurs/Santé : colonne Génétique en 3e position', all((sh.get(k) or [[None]*3])[0][2] == 'Génétique' for k in ('Journal', 'Longueurs', 'Santé')), [(sh.get(k) or [[]])[0][:3] for k in ('Journal', 'Longueurs', 'Santé')])
    g1 = a.js("(id)=>{ const s=savedSnakes.find(x=>x.id===id); return summarizeGenes(s.genes)||''; }", s1['id'])
    check('Journal : la génétique de l\'animal est remplie sur ses lignes', bool(g1) and all(r[2] and g1 in r[2] for r in jr[1:] if r[1] == s1['name']), (g1, [r[2] for r in jr[1:3]]))
    check('Journal : l\'import lit toujours Date, Activité, Poids aux bonnes colonnes (Génétique ignorée)', bool(hm) and hm.get('date') == 3 and hm.get('activity') == 4 and hm.get('weight') == 7 and 2 not in hm.values(), hm)
    want = {'A mangé': 'fed', 'Refus': 'refused', 'Mue': 'shed', 'Pesée': 'weight'}
    check('Journal : activités relues correctement (A mangé, Refus, Mue, Pesée)', all(dict(acts).get(k) == v for k, v in want.items() if k in dict(acts)) and 'A mangé' in dict(acts), acts)
    check('pas d\'erreur JS (export)', not a.real_errors(), a.real_errors()[:3])
    a.close()
    # aller-retour : l'onglet Animaux réimporté (en CSV) dans une app vide
    path = os.path.join(tempfile.mkdtemp(), 'animaux.csv')
    with open(path, 'w', encoding='utf-8', newline='') as fh: csv.writer(fh).writerows(an)
    b = App(browser, url, snakes=[]); b.open(); b.js("showTab('mine')")
    b.page.set_input_files('#generic-csv-file-input', path); b.page.wait_for_timeout(1000)
    b.js("""(()=>{ const btns=[...document.querySelectorAll('button')].filter(x=>x.offsetParent && /import/i.test(x.textContent) && !/fichier|file|choisir|choose/i.test(x.textContent)); if(btns.length) btns[btns.length-1].click(); })()""")
    b.page.wait_for_timeout(1200)
    got = b.js("savedSnakes.map(s=>({n:s.name, sex:s.sex, w:(s.health&&s.health.weights||[]).map(x=>x.value)}))")
    lastw = lambda s: sorted(s['health']['weights'], key=lambda w: w['date'])[-1]['value'] if s['health']['weights'] else None
    ok = sorted(x['n'] for x in got) == sorted([s1['name'], s2['name']]) and all((x['w'][-1] if x['w'] else None) == lastw(s1 if x['n'] == s1['name'] else s2) for x in got)
    check('réimport de l\'onglet Animaux : les 2 animaux reviennent, avec sexe et dernier poids', ok, got)
    b.close()
def t_remboursement_parents(browser, url):
    section('Remboursement des parents (v5.51)')
    m = make_snake(81); m['sex'] = 'male'; m['purchasePrice'] = 1000
    f = make_snake(82); f['sex'] = 'female'; f['purchasePrice'] = 500
    babies = []
    for i, (st, price) in enumerate([('sold', 400), ('sold', 400), ('forsale', 900), ('sold', 200)]):
        b = make_snake(90 + i); b['sireId'] = m['id']; b['damId'] = f['id']; b['status'] = st
        if st == 'sold': b['soldPrice'] = price
        else: b['askingPrice'] = price
        babies.append(b)
    a = App(browser, url, snakes=[m, f] + babies); a.open(wait=2500)
    # 2 accouplements du même couple (2 saisons) : les bébés ne comptent qu'une fois ; coût total 100 $
    a.js("""(ids)=>{ pairings.push({id:'pr_a', maleId:ids[0], femaleId:ids[1], pairedDate:'2025-10-01', lockDates:[], estimatedCost:60},
                                   {id:'pr_b', maleId:ids[0], femaleId:ids[1], pairedDate:'2026-10-01', lockDates:[], estimatedCost:40}); saveElevage(); }""", [m['id'], f['id']])
    r = a.js("(ids)=>{ const c=computeRepaymentCouples(); return [computeRepayment(ids[0], c), computeRepayment(ids[1], c), Object.keys(c).length]; }", [m['id'], f['id']])
    # ventes conclues 1000 $ − coût 100 $ = 900 $ ; 50/50 → 450 $ chacun ; le bébé à vendre (900 $) ne compte pas
    check('1 seul couple malgré 2 accouplements', r[2] == 1, r)
    check('ventes conclues seulement, moins le coût : 450 $ au père (45 %)', r[0]['repaid'] == 450 and r[0]['pct'] == 45, r[0])
    check('mère : 450 $ sur 500 $, pas encore remboursée', r[1]['repaid'] == 450 and not r[1]['done'], r[1])
    a.js("setRepaySirePct('pr_a', 80)")
    r = a.js("(ids)=>{ const c=computeRepaymentCouples(); return [computeRepayment(ids[0], c), computeRepayment(ids[1], c), pairings.filter(p=>p.id==='pr_b')[0].repaySirePct]; }", [m['id'], f['id']])
    check('partage 80/20 : père 720 $, mère 180 $ ; appliqué aux 2 accouplements du couple', r[0]['repaid'] == 720 and r[1]['repaid'] == 180 and r[2] == 80, r)
    a.js("(id)=>setRepayTarget(id, '150')", f['id'])
    r = a.js("(id)=>computeRepayment(id)", f['id'])
    check('montant à rembourser baissé à 150 $ : mère ✅ remboursée, jamais plus que le montant', r['done'] and r['repaid'] == 150, r)
    rt = a.js("(id)=>{ window.currentUser = window.currentUser || {id:'u'}; const s=savedSnakes.find(x=>x.id===id); return [snakeToRow(s).repay_target, rowToSnake(snakeToRow(s)).repayTarget]; }", f['id'])
    check('montant à rembourser envoyé au serveur (repay_target) et relu', rt == [150, 150], rt)
    a.js("(id)=>openLogbook(id)", m['id']); a.page.wait_for_timeout(400)
    txt = a.js("document.body.innerText")
    check('fiche du père : « Remboursé par les ventes 720 $ / 1000 $ (72 %) »', 'Remboursé par les ventes' in txt and '720 $ / 1000 $ (72 %)' in txt, [l for l in txt.split('\n') if 'Rembours' in l][:3])
    a.js("document.getElementById('logbook-overlay').style.display='none'; showTab('fiscal')"); a.page.wait_for_timeout(400)
    roi = a.js("(document.getElementById('pairing-roi-list')||{}).innerText||''")
    check('Fiscal → ROI : ligne « Rembourse les parents » avec le montant en $', 'Rembourse les parents' in roi and '720 $' in roi and '180 $' in roi, roi[:300])
    nrows = a.js("document.querySelectorAll('#pairing-roi-list .sale-row').length")
    check('ROI : 1 seule ligne pour le couple (2 accouplements), bébés comptés une fois : +1800 $', nrows == 1 and '+1800 $' in roi and '+1840' not in roi, (nrows, roi[:200]))
    cs = a.js("(ids)=>clutchProfitSummary({ref:'PX-1'}, savedSnakes.find(x=>x.id===ids[0]), savedSnakes.find(x=>x.id===ids[1]))", [m['id'], f['id']])
    check('ponte : plus de « Net vs coût des parents », état du remboursement à la place', 'Net vs' not in cs and 'Parents remboursés' in cs and '720 $ / 1000 $' in cs, cs[:300])
    check('pas d\'erreur JS (remboursement)', not a.real_errors(), a.real_errors()[:3])
    a.close()
def t_sante_accouplement(browser, url):
    section('Santé notée au moment d\'accoupler (v5.52)')
    d = lambda n: iso(TODAY - datetime.timedelta(days=n))
    gp = make_snake(101); gp['sex'] = 'male'; gp['health']['traitObs'] = [{"id": "o1", "kind": "skeletal", "level": 2, "date": d(300)}]
    m = make_snake(103); m['sex'] = 'male'; m['sireId'] = gp['id']
    f = make_snake(104); f['sex'] = 'female'; f['health']['traitObs'] = [{"id": "o2", "kind": "wobble", "level": 1, "date": d(200)}, {"id": "o3", "kind": "wobble", "level": 3, "date": d(20)}]
    kids = []
    for i, lv in enumerate([2, 3, 0]):
        k = make_snake(110 + i); k['damId'] = f['id']; k['health']['traitObs'] = [{"id": "k%d" % i, "kind": "skeletal", "level": lv, "date": d(10)}]
        kids.append(k)
    clean = make_snake(120); clean['sex'] = 'female'
    a = App(browser, url, snakes=[gp, m, f, clean] + kids); a.open(wait=2500)
    box = a.js("(ids)=>breedingHealthBox(ids[0], ids[1], false)", [m['id'], f['id']])
    check('mâle : kinking de son père rappelé', 'son père' in box and 'Kinking' in box and 'niveau 2' in box, box[:400])
    check('femelle : son DERNIER niveau de wobble (3), pas l\'ancien', 'Wobble — niveau 3' in box and 'niveau 1 (' not in box, box[:400])
    check('femelle : « 2 bébé(s) sur 3 noté(s), niveau max 3 »', '2 bébé(s) sur 3 noté(s), niveau max 3' in box, box[:500])
    none = a.js("(ids)=>[breedingHealthBox(ids[0], ids[1], false), pairHealthIconHtml(ids[0], ids[1])]", [gp['id'] if False else clean['id'], clean['id']])
    check('rien de noté = rien d\'affiché (boîte et bouton 🩺)', none == ['', ''], none)
    a.js("""(ids)=>{ const ms=document.getElementById('pairing-male'), fs=document.getElementById('pairing-female');
      ms.innerHTML='<option value="'+ids[0]+'">m</option>'; fs.innerHTML='<option value="'+ids[1]+'">f</option>'; ms.value=ids[0]; fs.value=ids[1]; updatePairingReproductionInfo(); }""", [m['id'], f['id']])
    form = a.js("document.getElementById('pairing-health-info').textContent")
    check('formulaire Accouplements : la boîte 🩺 apparaît au choix du couple', 'Problèmes de santé notés' in form and 'Wobble' in form, form[:200])
    ico = a.js("(ids)=>pairHealthIconHtml(ids[0], ids[1])", [m['id'], f['id']])
    check('Mode Verrou : bouton 🩺 sur le couple', '🩺' in ico and 'openPairHealthFacts' in ico, ico[:200])
    a.js("(ids)=>openPairHealthFacts(ids[0], ids[1])", [m['id'], f['id']]); a.page.wait_for_timeout(200)
    check('bouton 🩺 : la fenêtre montre les faits', 'Kinking' in a.js("document.body.innerText"))
    check('pas d\'erreur JS (santé à l\'accouplement)', not a.real_errors(), a.real_errors()[:3])
    a.close()
def t_congeler_taille(browser, url):
    section('Congeler un lot : taille selon le stade (v5.53)')
    d = lambda n: iso(TODAY - datetime.timedelta(days=n))
    a = App(browser, url, snakes=[make_snake(130)]); a.open(wait=2000)
    a.js("""(ds)=>{ rodentBins.push({ id:'rb_t1', binType:'stock', species:'rat', label:'Stock rats', stockBatches:[{ id:'sb1', quantity:10, referenceDate:ds[0] }, { id:'sb2', quantity:4, referenceDate:ds[1] }] }); feederStock = {}; saveElevage(); }""", [d(35), d(3)])
    a.js("openRodentFreezeModal(); renderRodentFreezeModalBody('rat', 'rb_t1')"); a.page.wait_for_timeout(200)
    st = a.js("[document.getElementById('rf-stage').value, document.getElementById('rf-size').value]")
    check('à l\'ouverture : stade Pinky → taille Pinky', st == ['pinky', 'Pinky'], st)
    a.js("const e=document.getElementById('rf-stage'); e.value='small'; e.dispatchEvent(new Event('change'))")
    sz = a.js("document.getElementById('rf-size').value")
    check('stade Small choisi → taille Small (avant : restait Pinky)', sz == 'Small', sz)
    a.js("document.getElementById('rf-qty').value='10'; confirmRodentFreeze('rat')"); a.page.wait_for_timeout(200)
    fs = a.js("feederStock")
    check('10 rats Small entrent au stock congelé comme Small', fs.get(a.js("feederStockKey('rat','Small')")) == 10 and not fs.get(a.js("feederStockKey('rat','Pinky')")), fs)
    m = a.js("[rodentFreezeSizeForStage('rat','hopper'), rodentFreezeSizeForStage('mouse','hopper'), rodentFreezeSizeForStage('mouse','small'), rodentFreezeSizeForStage('asf','large')]")
    check('taille la plus proche : rat Hopper → Weanling, souris Hopper → Hopper, souris Small → Adult, ASF Large → Adult', m == ['Weanling', 'Hopper', 'Adult', 'Adult'], m)
    check('pas d\'erreur JS (congeler)', not a.real_errors(), a.real_errors()[:3])
    a.close()
def t_lignee_annuler(browser, url):
    section('Lignées de rongeurs : annuler et modifier (v5.54)')
    a = App(browser, url, snakes=[make_snake(140)]); a.open(wait=2000)
    a.js("""(()=>{ rodentBins.push({ id:'rl3', binType:'reproduction', species:'rat', label:'Bac 3', lineageNumber:3, lineageGeneration:1, lineageLetter:null, maleOrigin:null, cumulativeFootprint:[] },
                                  { id:'rl5', binType:'reproduction', species:'rat', label:'Bac 5', lineageNumber:5, lineageGeneration:1, lineageLetter:null, maleOrigin:null, cumulativeFootprint:[] },
                                  { id:'rl7', binType:'reproduction', species:'rat', label:'Bac 7', lineageNumber:7, lineageGeneration:1, lineageLetter:null, maleOrigin:null, cumulativeFootprint:[{number:3, generation:1}] }); saveElevage(); })()""")
    adv = lambda same, male: a.js("""(a)=>{ openRodentLineageLetterModal('rl3'); document.getElementById('rodent-letter-samefemales').value=a[0]; document.getElementById('rodent-letter-male-origin').value=a[1]; confirmRodentLineageLetterIncrement('rl3'); }""", [same, male])
    code = lambda: a.js("rodentLineageCode(rodentBins.find(b=>b.id==='rl3'))")
    conflict = lambda: a.js("rodentFootprintConflict(rodentBinFootprint(rodentBins.find(b=>b.id==='rl7')), 3)")
    check('avant : bac 7 apparenté à la lignée 3.1 (avertissement actif)', conflict() is True)
    adv('non', '5')
    check('erreur : « non » → nouvelle génération 3.2, avertissement perdu', code() == '3.2' and conflict() is False, (code(), conflict()))
    a.js("undoRodentLineageLast('rl3')"); a.page.wait_for_timeout(100)
    m = a.js("rodentBins.find(b=>b.id==='rl3').maleOrigin")
    check('↩️ Annuler : retour à 3.1, mâle d\'avant, avertissement revenu', code() == '3.1' and m is None and conflict() is True, (code(), m, conflict()))
    adv('oui', '5'); adv('oui', '')
    check('2 changements de mâle : 3.1b', code() == '3.1b', code())
    a.js("openRodentLineageEntryEdit('rl3', 1); document.getElementById('rle-linked').value='non'; saveRodentLineageEntryEdit('rl3', 1)")
    check('modifier le 1er changement en « nouvelle génération » : codes recalculés → 3.2a', code() == '3.2a', code())
    a.js("deleteRodentLineageEntry('rl3', 1)"); a.page.wait_for_timeout(100)
    h = a.js("rodentBins.find(b=>b.id==='rl3').lineageHistory.map(x=>x.generation+(x.letter||''))")
    check('supprimer le changement du milieu : 3.1a, historique cohérent', code() == '3.1a' and h == ['1', '1a'], (code(), h))
    txt = a.js("document.body.innerText")
    check('historique : bouton « Annuler le dernier changement » et ✏️ par ligne', 'Annuler le dernier changement' in txt and a.js("document.querySelectorAll('[onclick^=\"openRodentLineageEntryEdit\"]').length") == 2)
    a.js("(()=>{ const b=rodentBins.find(x=>x.id==='rl3'); b.lineageCustomName='<img src=x onerror=window.__xss=1>'; openRodentLineageHistoryModal('rl3'); })()"); a.page.wait_for_timeout(200)
    check('nom de lignée personnalisé échappé dans l\'historique', not a.js("window.__xss"))
    check('pas d\'erreur JS (lignées)', not a.real_errors(), a.real_errors()[:3])
    a.close()
def t_gecko_poudre(browser, url):
    section('Geckos à la poudre : refus, repas, onglet Rongeurs (v5.55)')
    g1 = make_snake(150, species='crested_gecko'); g1['preySpecies'] = 'mrp'; g1['preySize'] = 'Portion normale'
    g2 = make_snake(151, species='leopard_gecko'); g2['preySpecies'] = 'cricket'; g2['preySize'] = 'Medium'
    a = App(browser, url, snakes=[g1, g2]); a.open(wait=2500)
    vis = a.js("(()=>{ const b=document.querySelector('.subtab-btn[data-sub=\"rongeurs\"]'); return b ? b.style.display : 'absent'; })()")
    check('aucun mangeur de rongeurs ni bac : onglet Rongeurs caché tout seul', vis == 'none', vis)
    a.js("(ids)=>{ tourSelection = new Set(ids.map(id=>'terra:'+id)); openTourRefusalPreyModal(); }", [g1['id'], g2['id']])
    a.page.wait_for_timeout(200)
    t = a.js("document.body.innerText")
    rows = a.js("[...document.querySelectorAll('.trp-row')].map(r=>({k:r.getAttribute('data-kind'), btns:r.querySelectorAll('.trp-type-btn').length, opts:[...(r.querySelector('.trp-fate')||{options:[]}).options].map(o=>o.value)}))")
    check('titre « Refus — et la nourriture ? »', 'et la nourriture' in t, t[:200])
    check('poudre : « gaspillée (jetée) » direct, pas de ❄️/🐭', any(r['k'] == 'portion' and r['btns'] == 0 and r['opts'] == ['lost'] for r in rows), rows)
    check('insectes : gaspillés ou donnés à un autre seulement, pas de ❄️/🐭', any(r['k'] is None and r['btns'] == 0 and r['opts'] == ['lost', 'passed'] for r in rows), rows)
    a.js("closeQuickModal()")
    box = a.js("(id)=>fedPreyInnerHtml(savedSnakes.find(s=>s.id===id), 'mrp', 'Portion normale', 'frozen')", g1['id'])
    check('fenêtre Repas : « Nourriture donnée », pas de ❄️/🐭', 'Nourriture donnée' in box and '❄️' not in box, box[:200])
    bp = make_snake(152)
    a.js("(s)=>{ savedSnakes.push(s); renderSavedList(); }", bp)
    vis2 = a.js("document.querySelector('.subtab-btn[data-sub=\"rongeurs\"]').style.display")
    check('un python royal ajouté : l\'onglet Rongeurs revient', vis2 == '', vis2)
    a.js("(id)=>{ savedSnakes = savedSnakes.filter(s=>s.id!==id); renderSavedList(); togglePersonalizationFeature('rongeurs'); }", bp['id'])
    vis3 = a.js("document.querySelector('.subtab-btn[data-sub=\"rongeurs\"]').style.display")
    check('réaffiché à la main dans le Mode personnalisé : reste affiché', vis3 == '' and a.js("personalizationPrefs.rongeursForced") is True, vis3)
    check('pas d\'erreur JS (geckos)', not a.real_errors(), a.real_errors()[:3])
    a.close()
def t_scenario_sous_sol(browser, url):
    section('Scénario sous-sol : 70+ actions hors ligne, app tuée, retour du Wi-Fi')
    snakes = [make_snake(200 + i) for i in range(45)]
    m = snakes[0]; m['sex'] = 'male'; f = snakes[1]; f['sex'] = 'female'
    ids = [x['id'] for x in snakes]
    a = App(browser, url, snakes=snakes); a.open(wait=3000)
    a.js("(ids)=>{ pairings.push({id:'pr_ss', maleId:ids[0], femaleId:ids[1], pairedDate:localTodayStr(), lockDates:[]}); saveElevage(); pushAllUserData(true); }", ids)
    a.page.wait_for_timeout(2500)
    # coupure (sous-sol)
    a.ctx.set_offline(True); a.js("localStorage.setItem('__fake_offline','1'); window.__fakeSb.offline=true; window.dispatchEvent(new Event('offline'))")
    # 25 pesées
    a.js("(ids)=>{ ids.slice(0,25).forEach((id,i)=>{ const s=savedSnakes.find(x=>x.id===id); ensureSnakeMeta(s); s.health.weights.push({date:localTodayStr(), value:300+i}); s.updatedAt=Date.now(); }); storage.save(savedSnakes); }", ids)
    # 40 repas en Mode Tournée
    a.js("(ids)=>{ tourSelection = new Set(ids.slice(5,45).map(id=>'terra:'+id)); tourFedPreyChecked = true; try{ applyTourAction('fed_frozen'); } finally { tourFedPreyChecked = false; } }", ids)
    # 3 refus (proie gaspillée) et 2 mues
    a.js("(ids)=>{ const plan={}; ids.slice(2,5).forEach(id=>plan[id]={fate:'lost', toId:null, preyType:'frozen'}); tourRefusalPlan=plan; tourSelection=new Set(ids.slice(2,5).map(id=>'terra:'+id)); try{ applyTourAction('refused'); } finally { tourRefusalPlan=null; } }", ids)
    a.js("(ids)=>{ tourShedQualityPending='complete'; tourSelection=new Set(ids.slice(0,2).map(id=>'terra:'+id)); try{ applyTourAction('shed'); } finally { tourShedQualityPending=null; } }", ids)
    # 1 lock
    a.js("quickAddLockToday('pr_ss')")
    a.page.wait_for_timeout(1500)
    counts = a.js("(ids)=>{ const t=localStorage.getItem('locus_snakes_v1'); const arr=JSON.parse(t); const g=(id)=>arr.find(x=>x.id===id); const today=localTodayStr();"
                  " return { w: ids.slice(0,25).filter(id=>g(id).health.weights.some(w=>w.date===today && w.value>=300)).length,"
                  " fed: ids.slice(5,45).filter(id=>g(id).health.events.some(e=>e.type==='fed' && e.date===today)).length,"
                  " ref: ids.slice(2,5).filter(id=>g(id).health.events.some(e=>e.type==='refused' && e.date===today)).length,"
                  " shed: ids.slice(0,2).filter(id=>g(id).health.events.some(e=>e.type==='shed' && e.date===today)).length,"
                  " lock: (JSON.parse(localStorage.getItem('locus_elevage_v1')).pairings.find(p=>p.id==='pr_ss').lockDates||[]).length }; }", ids)
    check('hors ligne : tout est écrit sur le téléphone (25 pesées, 40 repas, 3 refus, 2 mues, 1 lock)', counts == {'w': 25, 'fed': 40, 'ref': 3, 'shed': 2, 'lock': 1}, counts)
    pill = a.js("(document.getElementById('sync-pill')||{}).textContent||''")
    import re as _re
    nch = int((_re.search(r'(\d+) changements gardés', pill) or [0, 0])[1])
    check('pastille (v5.56) : « N changements gardés sur ce téléphone — tu peux fermer l\'app », N compte les gestes (≥ 70)', 'gardés sur ce téléphone' in pill and 'fermer' in pill and nch >= 70, pill)
    a.js("document.getElementById('sync-pill').click()"); a.page.wait_for_timeout(200)
    check('toucher la pastille hors ligne : explication « rien n\'est perdu »', 'rien n\'est perdu' in a.js("document.body.innerText"))
    a.js("closeQuickModal()")
    # rappel 24 h + message d'installation (iPhone, onglet Safari)
    a.js("(()=>{ const p=pendingChangesInfo(); p.since=Date.now()-3*86400000; localStorage.setItem('locus_pending_changes_v1', JSON.stringify(p)); localStorage.removeItem('locus_install_nudge_at'); window.isIosDevice=()=>true; window.isStandaloneMode=()=>false; window.isIosWebview=()=>false; _syncStartupDone=false; syncStartupReminders(); })()")
    a.page.wait_for_timeout(300)
    bt = a.js("document.body.innerText")
    check('rappel : « en attente depuis 3 jour(s) » à l\'ouverture sans réseau', 'en attente depuis 3 jour(s)' in bt, [l for l in bt.split('\n') if 'attente' in l][:3])
    check('iPhone dans Safari sans installation : message « Installe LOCUS pour protéger tes données »', 'Installe LOCUS pour protéger tes données' in bt)
    a.js("closeQuickModal(); _syncStartupDone=false; syncStartupReminders()"); a.page.wait_for_timeout(200)
    check('message d\'installation : pas répété la même semaine', a.js("document.getElementById('quick-modal-overlay').style.display") != 'flex')
    check('serveur : rien reçu pendant la coupure', not server_snake_has(a, ids[10], '"type":"fed"'))
    # app tuée (appel, fermeture), rouverte toujours hors ligne
    a.page.goto('about:blank'); a.ctx.set_offline(False)
    a.page.goto(a.url); a.page.wait_for_timeout(300); a.ctx.set_offline(True)
    a.page.wait_for_timeout(1500)
    re_ = a.js("(ids)=>ids.slice(5,45).filter(id=>savedSnakes.find(x=>x.id===id).health.events.some(e=>e.type==='fed' && e.date===localTodayStr())).length", ids)
    check('app tuée puis rouverte hors ligne : les 40 repas sont là', re_ == 40, re_)
    # retour du Wi-Fi
    a.ctx.set_offline(False); a.js("localStorage.removeItem('__fake_offline'); window.__fakeSb.offline=false; window.dispatchEvent(new Event('online'))")
    a.page.wait_for_timeout(6000)
    db = a.js("window.__fakeSb.db()")
    srv = {r['id']: json.dumps(r) for r in db.get('snakes', [])}
    today = a.js("localTodayStr()")
    fed_ok = sum(1 for id in ids[5:45] if '"type": "fed"' in srv.get(id, '').replace('"type":"fed"', '"type": "fed"') and today in srv.get(id, ''))
    w_ok = sum(1 for i, id in enumerate(ids[:25]) if str(300 + i) in srv.get(id, ''))
    ref_ok = sum(1 for id in ids[2:5] if 'refused' in srv.get(id, ''))
    lock_ok = any(today in json.dumps(p) and p.get('id') == 'pr_ss' for p in db.get('pairings', []))
    check('Wi-Fi revenu : tout arrive au serveur (40 repas, 25 pesées, 3 refus, le lock)', (fed_ok, w_ok, ref_ok, lock_ok) == (40, 25, 3, True), (fed_ok, w_ok, ref_ok, lock_ok))
    left = a.js("countPendingSync()")
    check('plus rien en attente, pastille partie', left == 0 and not a.js("!!document.getElementById('sync-pill')"), left)
    check('compteur de changements remis à zéro après l\'envoi', a.js("localStorage.getItem('locus_pending_changes_v1')") is None)
    check('pas d\'erreur JS (scénario sous-sol)', not a.real_errors(), a.real_errors()[:3])
    a.close()
def t_sante_tournee(browser, url):
    section('🩺 Santé dans le Mode Tournée + régurgitation (v5.57)')
    d = lambda n: iso(TODAY - datetime.timedelta(days=n))
    a1 = make_snake(160); a2 = make_snake(161); a3 = make_snake(162)
    a3['health']['events'] = [{"id": "f1", "date": d(25), "type": "fed"}]; a3['feedingIntervalDays'] = 7
    a = App(browser, url, snakes=[a1, a2, a3]); a.open(wait=2500)
    a.js("showTab('elevage'); showSubtab('tour')"); a.page.wait_for_timeout(300)
    check('bouton « 🩺 Santé » dans la barre du Mode Tournée', a.page.locator("button[onclick=\"openTourHealthModal()\"]").count() == 1)
    a.js("(ids)=>{ tourSelection = new Set(ids.map(id=>'terra:'+id)); openTourHealthModal(); document.getElementById('tour-health-note').value='sang'; document.getElementById('tour-health-quar').checked=true; applyTourHealth('poop_bad'); }", [a1['id'], a2['id']])
    r = a.js("(ids)=>ids.map(id=>{ const s=savedSnakes.find(x=>x.id===id); return [ (s.health.defecations||[]).map(x=>x.note).join('|'), !!(s.quarantine&&s.quarantine.active) ]; })", [a1['id'], a2['id']])
    check('selles anormales « sang » + quarantaine pour les 2 animaux sélectionnés', all('sang' in x[0] and x[1] for x in r), r)
    a.js("undoTourHealth()")
    r = a.js("(ids)=>ids.map(id=>{ const s=savedSnakes.find(x=>x.id===id); return [ (s.health.defecations||[]).length, !!(s.quarantine&&s.quarantine.active) ]; })", [a1['id'], a2['id']])
    check('Annuler : selles retirées et quarantaine remise comme avant', all(x == [0, False] for x in r), r)
    a.js("(id)=>{ tourSelection = new Set(['terra:'+id]); openTourHealthModal(); document.getElementById('tour-health-note').value='2 h après le repas'; applyTourHealth('regurg'); }", a3['id'])
    nf = a.js("(id)=>nextFeedingDate(savedSnakes.find(x=>x.id===id))", a3['id'])
    check('régurgitation : prochain repas pas avant 14 jours', nf == iso(TODAY + datetime.timedelta(days=14)), nf)
    risk = a.js("(id)=>healthRiskAssessment(savedSnakes.find(x=>x.id===id))", a3['id'])
    types = [x['type'] for x in risk['signals']]
    check('« À surveiller » : régurgitation, et PAS « 25 j sans repas » pendant le repos', 'regurg' in types and 'feeding' not in types, risk)
    rf = a.js("(id)=>savedSnakes.find(x=>x.id===id).health.consecutiveRefusals||0", a3['id'])
    check('une régurgitation n\'est pas comptée comme un refus', rf == 0, rf)
    a.js("(id)=>openLogbook(id)", a3['id']); a.page.wait_for_timeout(300)
    check('journal : « 🤮 Régurgitation — 2 h après le repas »', '🤮 Régurgitation — 2 h après le repas' in a.js("document.body.innerText"))
    pe = a.js("(id)=>parcoursEvents(savedSnakes.find(x=>x.id===id)).filter(e=>e.cat==='sante').length", a3['id'])
    check('Parcours : la régurgitation est dans la rangée Santé', pe >= 1, pe)
    a.js("(id)=>{ closeLogbook && closeLogbook(); tourSelection = new Set(['terra:'+id]); openTourHealthModal(); applyTourHealth('note'); }", a1['id'])
    check('note de santé vide : refusée (rien d\'ajouté)', a.js("(id)=>savedSnakes.find(x=>x.id===id).health.events.filter(e=>e.type==='health_note').length", a1['id']) == 0)
    check('pas d\'erreur JS (santé en tournée)', not a.real_errors(), a.real_errors()[:3])
    a.close()
def t_slugs_commande(browser, url):
    section('Slugs à la ponte + commande groupée (v5.58)')
    m = make_snake(170); m['sex'] = 'male'; m['status'] = 'forsale'; m['askingPrice'] = 400; m['name'] = 'Male PC'
    f = make_snake(171); f['sex'] = 'female'; f['status'] = 'forsale'; f['askingPrice'] = 200; f['name'] = 'Femelle SH'
    dam = make_snake(172); dam['sex'] = 'female'; sire = make_snake(173); sire['sex'] = 'male'
    a = App(browser, url, snakes=[m, f, dam, sire]); a.open(wait=2500)
    # --- slugs
    a.js("""(ids)=>{ showTab('incubation'); const ss=document.getElementById('clutch-sire'), ds=document.getElementById('clutch-dam');
      ss.innerHTML='<option value="'+ids[0]+'">s</option>'; ds.innerHTML='<option value="'+ids[1]+'">d</option>'; ss.value=ids[0]; ds.value=ids[1]; updateClutchReproductionFields();
      document.getElementById('clutch-eggcount').value='7'; document.getElementById('clutch-slugcount').value='2'; document.getElementById('clutch-laydate').value=localTodayStr(); pendingPairingIdForClutch='__none__'; }""", [sire['id'], dam['id']])
    a.js("pendingPairingIdForClutch=null; window.confirm=()=>true; addClutch()"); a.page.wait_for_timeout(300)
    c = a.js("(id)=>{ const c=clutches.filter(x=>x.damId===id).pop(); return c ? [c.eggCount, c.slugCount] : null; }", dam['id'])
    check('ponte : 7 œufs viables + 2 slugs enregistrés', c == [7, 2], c)
    fs = a.js("(id)=>femaleFertilityStats(savedSnakes.find(x=>x.id===id))", dam['id'])
    check('fertilité de la femelle : 2 non viables sur 9', fs['bad'] == 2 and fs['total'] == 9, fs)
    check('champ Slugs vide après l\'enregistrement', a.js("document.getElementById('clutch-slugcount').value") == '')
    # --- commande groupée
    a.js("(ids)=>{ batchSelectedIds = new Set(ids); openBatchReservationModal(); document.getElementById('brs-buyer').value='Rémi'; document.getElementById('brs-deposit').value='150'; batchResSplit(); }", [m['id'], f['id']])
    sh = a.js("[...document.querySelectorAll('.brs-share')].map(x=>parseFloat(x.value))")
    check('acompte 150 $ pré-réparti selon le prix : 100 / 50', sh == [100, 50], sh)
    a.js("const x=document.querySelectorAll('.brs-share'); x[0].value='90'; x[0].dataset.manual=1; batchResCheck()")
    check('parts qui ne font pas 150 $ : refusé', a.js("batchResCheck()") is False)
    a.js("const x=document.querySelectorAll('.brs-share'); x[1].value='60'; x[1].dataset.manual=1; document.getElementById('brs-delivery').value='40'; confirmBatchReservation()")
    a.page.wait_for_timeout(300)
    r = a.js("(ids)=>ids.map(id=>{ const r=savedSnakes.find(x=>x.id===id).reservation||{}; return [r.orderId||null, r.depositAmount, r.totalPrice, r.buyerName]; })", [m['id'], f['id']])
    check('2 réservations, même commande, parts choisies 90 / 60, prix 400 / 200', r[0][0] and r[0][0] == r[1][0] and [r[0][1], r[1][1], r[0][2], r[1][2]] == [90, 60, 400, 200] and r[0][3] == 'Rémi', r)
    ex = a.js("expenses.filter(e=>e.category==='Emballage & expédition').map(e=>e.amount)")
    check('frais de livraison 40 $ ajoutés aux Dépenses', ex == [40], ex)
    a.js("(id)=>openLogbook(id)", m['id']); a.page.wait_for_timeout(300)
    t = a.js("document.body.innerText")
    check('fiche : commande de 2 animaux, total 600 $ — acompte 150 $ — solde 450 $', '600 $ — acompte 150 $ — solde 450 $' in t and 'Reçu de la commande' in t, [l for l in t.split('\n') if 'commande' in l.lower()][:4])
    a.js("closeLogbook()")
    a.js("(id)=>cancelReservation(id)", f['id']); a.page.wait_for_timeout(200)
    t = a.js("document.body.innerText")
    check('annuler la femelle : on demande ce que devient son acompte de 60 $ (gardé / remboursé / reporté)', '60 $' in t and 'Gardé' in t and 'Remboursé' in t and 'Reporté' in t, t[:300])
    a.js("(id)=>{ closeQuickModal(); cancelReservation(id, 'kept'); }", f['id']); a.page.wait_for_timeout(200)
    k = a.js("(id)=>{ const s=savedSnakes.find(x=>x.id===id); return [s.status, (s.keptDeposits||[]).map(d=>d.amount), snakeToRow(s).kept_deposits.length]; }", f['id'])
    check('acompte gardé : femelle à vendre, 60 $ gardés, envoyés au serveur (kept_deposits)', k == ['forsale', [60], 1], k)
    a.js("showTab('fiscal'); fiscalYear = String(new Date().getFullYear()); renderFiscalView()"); a.page.wait_for_timeout(300)
    inc = a.js("document.getElementById('fiscal-income').textContent"); sl = a.js("document.getElementById('fiscal-sales-list').innerText")
    check('Fiscal : l\'acompte gardé compte dans les revenus (60 $) et apparaît dans la liste', inc.startswith('60') and 'Acompte gardé' in sl, (inc, sl[:120]))
    oid = r[0][0]
    a.js("(o)=>{ window.confirm=()=>true; markOrderSold(o); }", oid); a.page.wait_for_timeout(300)
    s1 = a.js("(id)=>{ const s=savedSnakes.find(x=>x.id===id); return [s.status, s.soldPrice, s.buyer]; }", m['id'])
    check('« Commande vendue » : le mâle est vendu 400 $ à Rémi', s1 == ['sold', 400, 'Rémi'], s1)
    check('pas d\'erreur JS (slugs + commande)', not a.real_errors(), a.real_errors()[:3])
    a.close()
def t_keltic_dragons(browser, url):
    section('BCI : Keltic, Smoke, Red/Sun Dragon (v5.45)')
    m = make_snake(71, species='boa_bci', genes={'bci_keltic': 'single'}); m['sex'] = 'male'
    f = make_snake(72, species='boa_bci', genes={'bci_motley': 'single'}); f['sex'] = 'female'
    a = App(browser, url, snakes=[m, f]); a.open(wait=2500)
    a.js("showTab('calc')"); a.page.wait_for_timeout(150)
    a.js("loadSnake(%s,'male'); loadSnake(%s,'female'); runCross();" % (json.dumps(m['id']), json.dumps(f['id']))); a.page.wait_for_timeout(300)
    res = a.js("document.getElementById('results').textContent")
    pct = a.js("(()=>{ let p=0; lastDistributions.forEach(d=>{ if(d.traits.some(t=>t.label==='Smoke')) p+=d.prob; }); return p; })()")
    check('Keltic × Motley : 25 % « Smoke »', abs(pct - 0.25) < 1e-9, pct)
    check('Smoke : avertissement létal affiché', 'Smoke' in res and ('LÉTAL' in res or 'létal' in res), res[:300])
    c = a.js("""[
      speciesComboTitle({bci_kahl:'visual', bci_blood:'visual'}, 'boa_bci'),
      speciesComboTitle({bci_sharp:'visual', bci_blood:'visual'}, 'boa_bci'),
      speciesComboTitle({bci_hypo:'single', bci_sharp:'visual', bci_blood:'visual'}, 'boa_bci'),
      speciesComboTitle({bci_hypo:'single', bci_kahl:'visual'}, 'boa_bci')
    ]""")
    check('Red Dragon (Kahl ou Sharp + Blood), Sun Dragon (+ Hypo), Sunglow intact', c == ['Red Dragon', 'Red Dragon', 'Sun Dragon', 'Sunglow'], c)
    p = a.js("parseImportGenes('Red Dragon', 'boa_bci')")
    check('import « Red Dragon » : Blood seulement + note (lignée inconnue)', p['genes'] == {'bci_blood': 'visual'} and any(x.get('note') == 'bci_dragon' for x in p.get('combos', [])), p)
    g = a.js("parseImportGenes('Smoke', 'boa_bci').genes")
    check('import « Smoke » : Keltic + Motley', g == {'bci_keltic': 'single', 'bci_motley': 'single'}, g)
    check('Super Keltic nommé', a.js("speciesComboTitle({bci_keltic:'homo', bci_kahl:'visual', bci_anery1:'visual'}, 'boa_bci')") == 'Snow · Super Keltic', a.js("speciesComboTitle({bci_keltic:'homo', bci_kahl:'visual', bci_anery1:'visual'}, 'boa_bci')"))
    check('pas d\'erreur JS (Keltic)', not a.real_errors(), a.real_errors()[:3])
    a.close()

def t_refus_type_proie(browser, url):
    section('Refus → proie passée à un autre : ❄️ / 🐭 (v5.47)')
    r = make_snake(81); g = make_snake(82)
    for s_ in (r, g):
        s_['placement'] = {"mode": "terrarium", "terrariumId": None, "row": None, "tub": None}
        s_['preySpecies'] = 'mouse'; s_['preySize'] = 'Fuzzy'; s_['preyType'] = 'frozen'
    a = App(browser, url, snakes=[r, g]); a.open(wait=3500)
    a.js("feederStock[feederStockKey('mouse','Fuzzy')] = 10; feederStockLive[feederStockKey('mouse','Fuzzy')] = 4;")
    a.js("showTab('elevage'); showSubtab('tour')"); a.page.wait_for_timeout(300)
    a.js("tourSelection.clear(); tourSelection.add('terra:%s')" % r['id'])
    a.page.locator('button.tour-action-btn.refused[onclick="applyTourAction(\'refused\')"]').first.click(); a.page.wait_for_timeout(250)
    row = a.page.locator('.trp-row').first
    check('fenêtre de refus : boutons ❄️ et 🐭 visibles, ❄️ actif (fiche)', row.locator('.trp-type-btn').count() == 2 and row.get_attribute('data-type') == 'frozen', row.get_attribute('data-type'))
    row.locator('.trp-type-btn[data-type="live"]').click(); a.page.wait_for_timeout(100)
    check('🐭 touché : type vivant, défaut « retournée au bac »', row.get_attribute('data-type') == 'live' and row.locator('.trp-fate').input_value() == 'returned', row.locator('.trp-fate').input_value())
    row.locator('.trp-fate').select_option('passed'); row.locator('.trp-to').select_option(g['id'])
    a.page.locator('button[onclick="confirmTourRefusalPrey()"]').click(); a.page.wait_for_timeout(300)
    st = a.js("[feederStock[feederStockKey('mouse','Fuzzy')], feederStockLive[feederStockKey('mouse','Fuzzy')]]")
    check('stock : une vivante retirée, congelé intact', st == [10, 3], st)
    ev = a.js("(()=>{ const T=localTodayStr(); const f=savedSnakes.find(x=>x.id==='%s').health.events.find(e=>e.type==='fed'&&e.date===T); const rf=savedSnakes.find(x=>x.id==='%s').health.events.find(e=>e.type==='refused'&&e.date===T); return [f&&f.preyType, rf&&rf.preyType, rf&&rf.preyFate]; })()" % (g['id'], r['id']))
    check('repas du receveur noté 🐭 vivant, refus garde le type', ev == ['live', 'live', 'passed'], ev)
    check('pas d\'erreur JS (refus)', not a.real_errors(), a.real_errors()[:3])
    a.close()

def t_renote_apres_suppression(browser, url):
    section('Entrée supprimée puis renotée à l\'identique : elle reste (v5.48)')
    s = make_snake(91); sid = s['id']
    s['placement'] = {"mode": "terrarium", "terrariumId": None, "row": None, "tub": None}
    s['preySpecies'] = 'rat'; s['preySize'] = 'Small'; s['preyType'] = 'frozen'
    a = App(browser, url, snakes=[s]); a.open(wait=3500)
    a.js("showTab('elevage'); showSubtab('tour')"); a.page.wait_for_timeout(300)
    past = iso(TODAY - datetime.timedelta(days=2))
    fed = lambda: a.js("(()=>{ setTourDateChoice('other'); tourDateOtherValue='%s'; tourSelection.clear(); tourSelection.add('terra:%s'); applyTourAction('fed_frozen'); })()" % (past, sid))
    count = lambda: a.js("savedSnakes.find(x=>x.id==='%s').health.events.filter(e=>e.type==='fed').length" % sid)
    fed(); a.page.wait_for_timeout(2500)
    a.js("undoLastLoggedEvent()"); a.page.wait_for_timeout(2500)
    check('repas annulé : parti, pierre tombale posée', count() == 0, count())
    # un 2e appareil (copie à jour, pierre tombale comprise) note une pesée sur le même animal
    db = a.js("window.__fakeSb.db()")
    b = App(browser, url, snakes=[], server_db=db); b.open(wait=3000)
    b.js("(()=>{const s=savedSnakes.find(x=>x.id==='%s'); s.health.weights.push({date:localTodayStr(), value:777}); s.updatedAt=Date.now(); storage.save(savedSnakes);})()" % sid)
    b.page.wait_for_timeout(2500); db2 = b.js("window.__fakeSb.db()"); b.close()
    # le 1er appareil renote le même repas : fusion avant envoi avec une fiche changée des deux côtés
    a.js("sessionStorage.setItem('__fake_db', %s)" % json.dumps(json.dumps(db2)))
    fed(); a.page.wait_for_timeout(3000)
    srv = lambda: sum(1 for e in ((a.js("(window.__fakeSb.db().snakes||[]).find(r=>r.id==='%s')" % sid) or {}).get('health') or {}).get('events', []) if e.get('type') == 'fed')
    check('renoté à l\'identique pendant qu\'un autre appareil a modifié la fiche : arrive au serveur (avant 5.48 : effacé)', srv() == 1 and count() == 1, (srv(), count()))
    a.reload(wait=4000)
    check('renoté : toujours là après réouverture', count() == 1, count())
    check('le repas renoté est bien à la date choisie', a.js("savedSnakes.find(x=>x.id==='%s').health.events.find(e=>e.type==='fed').date" % sid) == past)
    # pesée : même chose
    a.js("(()=>{ const x=savedSnakes.find(y=>y.id==='%s'); addHealthTombstone(x, measureKey('w', {date:'2026-10-30', value:1152})); pushHealthMeasure(x, 'weights', {date:'2026-10-30', value:1152}); storage.save(savedSnakes); })()" % sid)
    a.page.wait_for_timeout(3000); a.reload(wait=4000)
    w = a.js("savedSnakes.find(x=>x.id==='%s').health.weights.filter(w=>w.date==='2026-10-30').length" % sid)
    check('pesée renotée après suppression : reste', w == 1, w)
    check('pas d\'erreur JS (renoter)', not a.real_errors(), a.real_errors()[:3])
    a.close()

def t_prix_combos(browser, url):
    section('Calculateur : prix retenus par résultat (v5.49)')
    a = App(browser, url, snakes=[make_snake(95)]); a.open(wait=3000)
    a.js("showTab('calc')")
    pick_gene(a, 'male', 'pastel', 'pastel', 'single')
    a.js("runCross()"); a.page.wait_for_timeout(300)
    name0 = a.js("comboPriceKey(lastResults[0])")
    inp = a.page.locator('#price-0'); inp.scroll_into_view_if_needed(); inp.fill('180'); inp.blur(); a.page.wait_for_timeout(200)
    check('prix tapé : retenu pour ce résultat', a.js("comboPrices[%s]" % json.dumps(name0)) == 180, a.js("comboPrices"))
    a.js("runCross()"); a.page.wait_for_timeout(300)
    check('nouvelle simulation : case déjà remplie, valeur attendue calculée', a.page.locator('#price-0').input_value() == '180' and a.js("document.getElementById('value-expected').textContent") != '0 $', (a.page.locator('#price-0').input_value(), a.js("document.getElementById('value-expected').textContent")))
    a.page.wait_for_timeout(2500)
    db = a.js("window.__fakeSb.db()")
    srv = (db.get('app_state') or [{}])
    srv = srv[0] if isinstance(srv, list) and srv else srv
    check('prix envoyé au serveur (app_state.combo_prices)', name0 in json.dumps(srv.get('combo_prices') if isinstance(srv, dict) else None), str(srv)[:200])
    b = App(browser, url, snakes=[], server_db=db); b.open(wait=3500)
    check('2e appareil : le prix arrive', b.js("comboPrices[%s]" % json.dumps(name0)) == 180, b.js("comboPrices"))
    b.close()
    inp = a.page.locator('#price-0'); inp.fill(''); inp.blur(); a.page.wait_for_timeout(200)
    check('case vidée : prix oublié', a.js("comboPrices[%s]" % json.dumps(name0)) is None)
    a.js("showTab('reglement')"); a.page.wait_for_timeout(200)
    txt = a.js("document.getElementById('view-reglement').innerText")
    check('Réglementation : carte États-Unis, plus de balise <i> affichée', 'États-Unis' in txt and '<i>' not in txt, txt[-300:])
    check('pas d\'erreur JS (prix)', not a.real_errors(), a.real_errors()[:3])
    a.close()

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
    tests = [t_ouverture, t_repas, t_synchro, t_deux_appareils_ouverts, t_suppression_ne_revient_pas, t_grille_elevage_a_jour, t_parcours, t_proie_lot, t_decongelation_et_selection, t_unites, t_unites_etape2, t_proie_repas, t_tournee_deselection, t_combos_bci, t_combos_bp, t_export_complet, t_keltic_dragons, t_refus_type_proie, t_renote_apres_suppression, t_prix_combos, t_remboursement_parents, t_sante_accouplement, t_congeler_taille, t_lignee_annuler, t_gecko_poudre, t_scenario_sous_sol, t_sante_tournee, t_slugs_commande, t_import, t_calculateur, t_langue, t_parite_traductions]
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
