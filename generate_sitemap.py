#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Génère sitemap.xml pour LOCUS Scales — à re-exécuter chaque fois que le dossier guides/ change
(nouvelle espèce ajoutée, etc.).

3 nov 2026 — lastmod = la VRAIE date de dernière modification de chaque page (avant : la date du jour
pour tout, et Google finit par ignorer des dates qui changent toutes en même temps).
Ordre de priorité pour chaque fichier :
  1. fichiers passés en argument = modifiés aujourd'hui (pas encore envoyés sur GitHub) :
       python3 generate_sitemap.py guides/features.html guides/fonctionnalites.html
  2. date du dernier commit Git du fichier (si le dossier est un dépôt Git cloné)
  3. date déjà inscrite dans le sitemap.xml actuel
  4. date du jour (nouvelle page)"""
import os, re, sys, subprocess
from datetime import date

SITE_ORIGIN = "https://app.locusscales.com"
TODAY = date.today().isoformat()
GUIDES_DIR = "guides"
TOUCHED = {a.strip("./") for a in sys.argv[1:]}

previous = {}
try:
    with open("sitemap.xml", encoding="utf-8") as f:
        for loc, mod in re.findall(r"<loc>([^<]*)</loc>\s*<lastmod>([^<]*)</lastmod>", f.read()):
            previous[loc] = mod
except OSError:
    pass

def lastmod_for(path, loc):
    if path in TOUCHED:
        return TODAY
    try:
        d = subprocess.run(["git", "log", "-1", "--format=%cs", "--", path], capture_output=True, text=True, timeout=20).stdout.strip()
        if d:
            return d
    except Exception:
        pass
    return previous.get(loc, TODAY)

urls = []

# Page d'accueil de l'app (priorité la plus haute)
urls.append({"loc": f"{SITE_ORIGIN}/", "path": "index.html", "priority": "1.0", "changefreq": "weekly"})

# Toutes les pages du dossier guides/
guide_files = sorted(f for f in os.listdir(GUIDES_DIR) if f.endswith(".html"))
for fname in guide_files:
    priority = "0.9" if fname == "index.html" else "0.8"
    urls.append({
        "loc": f"{SITE_ORIGIN}/guides/{fname}",
        "path": f"{GUIDES_DIR}/{fname}",
        "priority": priority,
        "changefreq": "monthly",
    })

entries = "\n".join(
    f'  <url>\n    <loc>{u["loc"]}</loc>\n    <lastmod>{lastmod_for(u["path"], u["loc"])}</lastmod>\n    <changefreq>{u["changefreq"]}</changefreq>\n    <priority>{u["priority"]}</priority>\n  </url>'
    for u in urls
)

sitemap = f'''<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
{entries}
</urlset>
'''

with open("sitemap.xml", "w", encoding="utf-8") as f:
    f.write(sitemap)

robots = f'''User-agent: *
Allow: /

Sitemap: {SITE_ORIGIN}/sitemap.xml
'''
with open("robots.txt", "w", encoding="utf-8") as f:
    f.write(robots)

print(f"{len(urls)} URLs dans le sitemap.")
