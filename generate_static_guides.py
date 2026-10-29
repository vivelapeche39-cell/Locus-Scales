#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Génère les fiches d'espèces statiques du dossier guides/ à partir de SPECIES_REFERENCE (index.html).

Usage : python3 generate_static_guides.py species.json [--only id1,id2] [--all]
  species.json : export de SPECIES_REFERENCE (JSON.stringify(SPECIES_REFERENCE) dans l'app).
  Par défaut, seules les espèces SANS page existante sont générées (les pages déjà en ligne ne sont
  pas réécrites). --all regénère tout. --only limite à certains ids.
Met aussi à jour la liste des serpents/lézards de guides/index.html (toutes les pages existantes).
Format identique aux pages déjà publiées (corn-snake.html). v5.29 — 29 oct 2026."""
import json, os, sys, html as _html

SITE = "https://app.locusscales.com"
GUIDES = os.path.join(os.path.dirname(os.path.abspath(__file__)), "guides")

def esc(t):
    return _html.escape(t or "", quote=False).replace('"', "&quot;")

def slug(sid):
    return sid.replace("_", "-")

L = {
 "fr": dict(tag="Fiche d'entretien", back="← Toutes les fiches d'espèces", other="English",
            intro="Valeurs de référence rapides et sourcées. La suite complète d'outils élevage/génétique de LOCUS Scales est pensée spécifiquement pour le python royal — cette page est une référence de courtoisie pour les autres espèces.",
            latin="Nom latin", origin="Localité", life="Espérance de vie", habitat="Mode de vie",
            warm="Côté chaud", cool="Côté froid", hum="Humidité", diet="Diète : ", freq="Fréquence de nourrissage : ",
            sub="Substrat : ", uvb="UVB : ", encl="🏠 Taille de terrarium", baby="Bébé :", subad="Sub-adulte :", adult="Adulte :",
            faq="Questions fréquentes", cta="Découvrir LOCUS Scales →", disc="Contenu de référence général — ne remplace pas un avis vétérinaire.",
            fallback="Fiche de référence sourcée par LOCUS Scales."),
 "en": dict(tag="Species care guide", back="← All species guides", other="Français",
            intro="Quick sourced reference values. LOCUS Scales' full breeding/genetics toolset is built specifically for ball pythons — this page is a courtesy reference for other species.",
            latin="Scientific name", origin="Native range", life="Lifespan", habitat="Lifestyle",
            warm="Warm side", cool="Cool side", hum="Humidity", diet="Diet: ", freq="Feeding frequency: ",
            sub="Substrate: ", uvb="UVB: ", encl="🏠 Enclosure size", baby="Baby :", subad="Sub-adult :", adult="Adult :",
            faq="Common questions", cta="Discover LOCUS Scales →", disc="General reference content — does not replace veterinary advice.",
            fallback="Sourced care reference from LOCUS Scales."),
}

def template_head_style():
    s = open(os.path.join(GUIDES, "corn-snake.html"), encoding="utf-8").read()
    a = s.index("<style>"); b = s.index("</style>") + len("</style>")
    return s[a:b]

def page(sp, lang, style):
    t = L[lang]; en = lang == "en"
    g = lambda k: sp.get(k + ("En" if en else "Fr")) or ""
    name = sp["nameEn"] if en else sp["nameFr"]
    fname = slug(sp["id"]) + ("-en" if en else "") + ".html"
    other = slug(sp["id"]) + ("" if en else "-en") + ".html"
    note = g("note")
    desc = (note[:167] + "…") if len(note) > 170 else (note or t["fallback"])
    url = f"{SITE}/guides/{fname}"
    faq = sp.get("faqEn" if en else "faqFr") or []
    ld = [{"@context": "https://schema.org", "@type": "Article", "headline": name, "description": note or t["fallback"], "url": url,
           "publisher": {"@type": "Organization", "name": "LOCUS Scales", "url": SITE}, "inLanguage": lang}]
    if faq:
        ld.append({"@context": "https://schema.org", "@type": "FAQPage", "mainEntity": [
            {"@type": "Question", "name": q["q"], "acceptedAnswer": {"@type": "Answer", "text": q["a"]}} for q in faq]})
    ident = ""
    for lab, val, it in [(t["latin"], sp.get("nameLatin"), True), (t["origin"], g("origin"), False), (t["life"], g("lifespan"), False), (t["habitat"], g("habitatType"), False)]:
        if val:
            v = f"<i>{esc(val)}</i>" if it else esc(val)
            ident += f'<div><div class="label">{lab}</div><div class="val">{v}</div></div>'
    stats = "".join(f'<div class="stat"><div class="label">{lab}</div><div class="val">{v}</div></div>' for lab, v in
                    [(t["warm"], f'{sp["tempWarm"]}°C'), (t["cool"], f'{sp["tempCool"]}°C'), (t["hum"], f'{sp["humidity"]}%')])
    blocks = ""
    if g("diet"): blocks += f'<p class="block"><b>{t["diet"]}</b>{esc(g("diet"))}</p>'
    if g("feedFreq"): blocks += f'<p class="block"><b>{t["freq"]}</b>{esc(g("feedFreq"))}</p>'
    sub = f'<p class="block"><b>{t["sub"]}</b>{esc(g("substrate"))}</p>' if g("substrate") else ""
    uvb = f'<p class="block"><b>{t["uvb"]}</b>{esc(g("uvb"))}</p>' if g("uvb") else ""
    e = lambda k: sp.get(k + ("En" if en else "")) or ""
    encl = ""
    if e("enclosureBaby") or e("enclosureSub") or e("enclosureAdult"):
        encl = f'<h2>{t["encl"]}</h2><div class="enclosure">' + "".join(
            f'<div><b>{lab}</b> {esc(v)}</div>' for lab, v in [(t["baby"], e("enclosureBaby")), (t["subad"], e("enclosureSub")), (t["adult"], e("enclosureAdult"))] if v) + "</div>"
    faqh = (f'<h2>{t["faq"]}</h2>' + "".join(f'<div class="qa"><div class="q">{esc(q["q"])}</div><div class="a">{esc(q["a"])}</div></div>' for q in faq)) if faq else ""
    title = f"{name} | LOCUS Scales"
    return fname, f'''<!DOCTYPE html>
<html lang="{lang}">
<head>
<meta charset="UTF-8"/>
<meta name="viewport" content="width=device-width, initial-scale=1.0"/>
<title>{esc(title)}</title>
<meta name="description" content="{esc(desc)}"/>
<meta name="robots" content="index, follow"/>
<link rel="canonical" href="{url}"/>
<link rel="alternate" hreflang="en" href="{SITE}/guides/{slug(sp["id"])}-en.html"/>
<link rel="alternate" hreflang="fr" href="{SITE}/guides/{slug(sp["id"])}.html"/>
<meta property="og:title" content="{esc(title)}"/>
<meta property="og:description" content="{esc(desc)}"/>
<meta property="og:type" content="article"/>
<meta property="og:url" content="{url}"/>
<meta property="og:site_name" content="LOCUS Scales"/>
<script type="application/ld+json">
{chr(10).join(json.dumps(x, ensure_ascii=False) for x in ld)}
</script>
{style}
</head>
<body>
<div class="wrap">
  <div class="langtoggle"><a href="{SITE}/guides/{other}">{t["other"]}</a></div>
  <div class="backlink"><a href="./index.html">{t["back"]}</a></div>
  <div class="brand">
    <div class="brand-name">LOCUS<span class="dot">.</span>Scales</div>
    <div class="brand-tag">{t["tag"]}</div>
  </div>
  <h1>{esc(name)}</h1>
  <p class="note" style="text-align:center;color:var(--ink-dim);">{t["intro"]}</p>
  <div class="identity">{ident}</div>
  <div class="stats">{stats}</div>
  <p class="note">{esc(note)}</p>
  {blocks}
  {sub}
  {uvb}
  {encl}
  {faqh}
  <div class="cta">
    <a class="btn" href="{SITE}">{t["cta"]}</a>
    <p class="disclaimer">{t["disc"]}</p>
  </div>
</div>
</body>
</html>
'''

def update_index(species):
    p = os.path.join(GUIDES, "index.html"); s = open(p, encoding="utf-8").read()
    cats = [("serpent", "🐍 Serpents"), ("lezard", "🦎 Lézards"), ("tortue", "🐢 Tortues")]
    allsp = [{"id": "ball_python", "category": "serpent", "nameFr": "Python royal"}] + species
    out = ""
    for cat, lab in cats:
        items = [sp for sp in allsp if sp.get("category") == cat and os.path.exists(os.path.join(GUIDES, slug(sp["id"]) + ".html"))]
        if items:
            out += f"<h2>{lab}</h2><ul>" + "".join(f'<li><a href="./{slug(sp["id"])}.html">{esc(sp["nameFr"])}</a></li>' for sp in items) + "</ul>"
    a = s.index("<h2>🐍 Serpents</h2>"); b = s.index("\n  <h2>📋 Autre</h2>")
    s = s[:a] + out + s[b:]
    open(p, "w", encoding="utf-8").write(s)

if __name__ == "__main__":
    species = json.load(open(sys.argv[1], encoding="utf-8"))
    only = None
    if "--only" in sys.argv: only = set(sys.argv[sys.argv.index("--only") + 1].split(","))
    regen_all = "--all" in sys.argv
    style = template_head_style()
    written = []
    for sp in species:
        if only and sp["id"] not in only: continue
        exists = os.path.exists(os.path.join(GUIDES, slug(sp["id"]) + ".html"))
        if exists and not regen_all and not only: continue
        for lang in ("fr", "en"):
            fn, content = page(sp, lang, style)
            open(os.path.join(GUIDES, fn), "w", encoding="utf-8").write(content)
            written.append(fn)
    update_index(species)
    print("\n".join(written) or "(aucune page générée)")
