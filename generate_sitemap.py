#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Génère sitemap.xml pour LOCUS Scales — à re-exécuter chaque fois que le dossier guides/ change
(nouvelle espèce ajoutée, etc.). Utilise la date du jour comme lastmod pour tout — simple et honnête,
pas besoin de suivre la date exacte de modification de chaque fichier individuellement."""
import os
from datetime import date

SITE_ORIGIN = "https://app.locusscales.com"
TODAY = date.today().isoformat()
GUIDES_DIR = "guides"

urls = []

# Page d'accueil de l'app (priorité la plus haute)
urls.append({"loc": f"{SITE_ORIGIN}/", "priority": "1.0", "changefreq": "weekly"})

# Toutes les pages du dossier guides/
guide_files = sorted(f for f in os.listdir(GUIDES_DIR) if f.endswith(".html"))
for fname in guide_files:
    priority = "0.9" if fname == "index.html" else "0.8"
    urls.append({
        "loc": f"{SITE_ORIGIN}/guides/{fname}",
        "priority": priority,
        "changefreq": "monthly",
    })

entries = "\n".join(
    f'  <url>\n    <loc>{u["loc"]}</loc>\n    <lastmod>{TODAY}</lastmod>\n    <changefreq>{u["changefreq"]}</changefreq>\n    <priority>{u["priority"]}</priority>\n  </url>'
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
