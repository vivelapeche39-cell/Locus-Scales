# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

# LOCUS Scales

## Vue d'ensemble

LOCUS Scales est une application web mono-fichier (HTML/JS) de gestion d'élevage de python royal (Ball Python), déployée en SaaS commercial. Elle remplace le suivi papier/post-it des éleveurs par un système complet : génétique, racks, ventes, incubation, administration.

**Fondateur/développeur solo :** Alexandre Young (Alex), basé à Laval, Québec. Éducateur reptiles (Magazoo, 5 ans) + passionné en relance (3 serpents actuellement, ancien élevage de 20-30 serpents il y a 10-15 ans).

**Ne jamais présenter Alex comme un « éleveur expert avec X années d'expérience »** dans du contenu marketing ou dans le ton de l'app — c'est inexact et à l'opposé du positionnement voulu.

**Slogan :** « Ni startup, ni stagiaire. Juste un passionné qui en avait marre des post-it. »

## Stack technique

- **Fichier unique** `index.html` — HTML + CSS + JS dans un seul fichier (~8600+ lignes), pas de build step, pas de bundler
- **Hébergement :** GitHub Pages sur app.locusscales.com (dépôt `vivelapeche39-cell/Locus-Scales`, CNAME chez Namecheap)
- **Backend :** Supabase (Postgres + Auth + RLS + Storage) — projet ID `dkhmqkkmnexqixmkvzjo`, région ca-central-1
- **Paiements :** Stripe Connect (mode Express, "La plateforme") — 3 Edge Functions Supabase (stripe-connect-onboard, stripe-create-payment, stripe-webhook)
- **Domaines :** locusscales.com (principal), locusscales.ca (redirige, protection de marque)
- **Email :** Zoho Mail Lite — support@locusscales.com
- **Dépendances externes (CDN, aucune installée localement) :** `@supabase/supabase-js@2` (client Supabase) et `xlsx@0.18.5` (SheetJS, exports Excel) — chargées en `<script src>` en tête de fichier.

## Commandes de développement

Pas de `package.json`, pas de dépôt Git initialisé localement, pas de build/lint/test tooling — le projet est un `index.html` statique ouvrable directement dans un navigateur.

- **Aperçu local :** ouvrir `index.html` directement (double-clic) ou servir le dossier avec un serveur statique (ex. `npx serve .`) si le comportement diffère entre `file://` et `https://` (Supabase, service workers, etc.).
- **Validation post-édition (attendu après chaque patch) :** `node --check index.html` échouera car le fichier n'est pas du JS pur (HTML+CSS+JS) — pour valider seulement le JS, extraire le contenu entre `<script>` (ligne ~1608) et `</script>` (fin de fichier) avant de passer à `node --check`, ou utiliser un linter JS capable de cibler ce bloc.
- **Déploiement :** push vers `main` sur le dépôt `vivelapeche39-cell/Locus-Scales` → GitHub Pages republie automatiquement sur app.locusscales.com.

## Architecture du code

- Base de données des gènes (`GENES`) centralisée tout en haut du fichier — **aucun ID de gène en dur ailleurs**. Toute logique de calcul lit exclusivement depuis ce tableau.
- 78 gènes actuellement, chacun vérifié individuellement (Morphpedia, ReptiDex, ou source communautaire fiable) — sources de vérification exclusives.
- `CROSS_WARNINGS` gère les combinaisons multi-locus dangereuses (ex. Champagne × Spider → Wobble).
- `sexLinkedMaker` sur le gène Banana gère la logique Male Maker/Female Maker de façon générique (extensible à d'autres gènes sex-linked sans hardcoder).
- Stockage local : `locus_snakes_v1` (animaux), `locus_elevage_v1` (racks, pairings, layout, clutches, waitlists).
- Supabase : tables `snakes`, `racks`, `pairings`, `clutches`, `expenses`, `customers`, `app_state`, `profiles`, `announcements`, `changelog` — chacune avec `user_id` + RLS.
- `cloudMirrorSnakes()` pousse localStorage → Supabase ; `syncWithCloud()` tire au login (fusion par ID, jamais un écrasement pur).
- Bucket Supabase Storage public `reptile-photos` (RLS : upload/modif/suppr limités au dossier `user_id`, lecture publique) — nécessaire pour les URLs de photos dans l'export MorphMarket (base64 non utilisable).
- i18n : dictionnaire `I18N` (fr/en), `t(clé)`/`tLang(clé,langue)`, `applyTranslations()`. ~370 clés par langue.

### Repères dans le fichier (~12 845 lignes — rafraîchi le 1er septembre 2026)

Fichier volumineux à un seul `<script>` (ouvre ligne 1858) — ces repères évitent de tout relire à chaque fois (numéros approximatifs, dérivent avec les patches — au moindre doute, `grep -n` directement plutôt que de se fier à ce tableau) :

| Zone | ~Ligne |
|---|---|
| `<style>` (CSS) | 61–883 |
| Chargement CDN (`supabase-js`, `xlsx`) | 884–885 |
| `SUPABASE_URL` / `SUPABASE_ANON_KEY` / init client `sb` (`createClient`) | 2036–2044 |
| Auth (`requireAuthOrPrompt`, `currentUser`, `onAuthStateChange`) | 1744, 2198–2343 |
| `STORAGE_KEY` (`locus_snakes_v1`) | 2583 |
| `GENES` (base de données des gènes) | 2384 |
| `CROSS_WARNINGS` | 2438 |
| `I18N` (dictionnaire fr/en) | 3341 |
| `t()` / `tLang()` / `applyTranslations()` | 4210–4237 |
| Calculateur génétique (`crossLocus`, `runCross`, `renderPunnett`, `simulateClutch`) | 5636–6075 |
| `escapeHtml()` | 6166 |
| Suivi de santé animal (`addVetVisit` et fonctions de journal associées) | ~6100–6400 |
| `ELEVAGE_KEY` (`locus_elevage_v1`) | 7132 |
| Sync cloud (`dirtySyncIds`/`trackLocalChanges` déclarés tôt en 2592–2606 ; `mergeById`, `snakeToRow`/`rowToSnake`, `syncPushAll`/`syncPullAll` plus loin) | 2592–2606, 7216–7376 |
| Export/import backup JSON (`exportBackup`) | 7479 |
| Racks / terrariums (`renderRackGrid`, `renderTerrariumCleaningModalBody`, `renderTerrariumList`, `tourSelection`) | 4493 (var tourSelection), 8389–8978 |
| Stripe Connect (`startStripeConnectOnboarding`, invoke `stripe-create-payment`) | 3064, 11227 |
| Ventes, clients, export MorphMarket (`exportMorphMarketBulk`, `renderSalesView`) | 11315–11527 |
| Export Excel (SheetJS / `XLSX.utils`) | 12163 |

## Règle technique permanente — i18n

Toute nouvelle section de contenu générée dynamiquement en JS (pas via `data-i18n` statique) doit être ajoutée à `applyTranslations()` (ou équivalent) **dès sa création**, pas seulement au changement d'onglet. Sinon elle reste figée dans l'ancienne langue au changement FR/EN. Bug déjà rencontré et corrigé plusieurs fois — toujours vérifier ce point par défaut lors de l'ajout de contenu dynamique.

## Monétisation (décidée le 25 août 2026 — voir docs/memoire-maitresse.md section 4)

Structure à 4 paliers, ligne de démarcation combinant nombre d'animaux ET fonction (changement de principe assumé par rapport à l'ancienne règle "jamais bloquer sur le nombre") :

| Palier | Prix | Cible | Limite animaux | Accès |
|---|---|---|---|---|
| Gratuit | 0$ | Découverte | À déterminer | Zéro élevage, suivi minimal |
| Passionné | 5$/mois | Collectionneur sans élevage | 20 | Presque tout SAUF vente et reproduction |
| Première ponte | 5$/mois | Petit éleveur débutant | 10 | Élevage/vente à l'unité (pas en masse) |
| Illimité | 10$/mois | Éleveur sérieux | Aucune | Tout, sans limite de volume |

**🔴 Pas encore codé** — tout le monde a accès à tout gratuitement actuellement ; reste le principal bloquant de lancement.

- Cloud sync **gratuit pour tous les paliers** (Safari iOS efface localStorage après 7 jours d'inactivité).
- Commission transactionnelle ~1% via Stripe Connect (`application_fee_amount`) — revenu indépendant.
- **Politique de rétention :** ne jamais effacer les données pour non-paiement/essai expiré — seul l'accès se verrouille. Comptes dormants (18-24 mois sans connexion, pas sans paiement) → préavis 30j puis suppression/archivage.

**⚠️ Instruction comportementale permanente :** Alex a demandé à être rappelé à l'ordre si une proposition dérive vers une monétisation agressive/malhonnête envers les clients ("greedy").

## Sécurité

- RLS Supabase vérifié sur toutes les tables.
- `escapeHtml()` appliqué à tous les points d'insertion de texte libre (noms, notes, provenance, clients...) — jamais d'`innerHTML` avec du texte non nettoyé.
- `showToast()` utilise `textContent`, jamais `innerHTML`.
- Google Fonts retiré (fuite d'IP) — polices système uniquement (Georgia, Verdana, Courier New).
- QR code transmet des données à qrserver.com (tiers) — documenté dans la Politique de confidentialité comme exception.

## Préférences de travail (Alex)

- **Patchs ciblés (`str_replace`) plutôt que réécriture complète** du fichier, sauf demande explicite — fichier volumineux, économie de tokens.
- **Identifiants/mots de passe toujours en texte clair, gros caractères** — Alex a une très mauvaise vue. Jamais de bloc de code ou style compact pour un identifiant/mot de passe.
- Vérification systématique post-édition : validation syntaxique JS (`node --check`), absence d'ID/fonctions dupliqués, clés i18n FR/EN synchronisées.
- Communication habituelle en français québécois informel (souvent via dictée vocale — accepter les approximations phonétiques de termes anglais).
- **Présenter les décisions avec des options claires avant d'agir**, surtout pour tout ce qui touche à l'architecture ou au design produit (ex. via des questions à choix courtes) plutôt que de deviner et foncer.
- Alex gère son budget de tokens consciemment — préférer l'efficacité, éviter le remplissage inutile.

## Bugs déjà rencontrés (éviter de les reproduire)

- **Temporal dead zone JS** : une constante utilisée par une fonction de rendu appelée au chargement doit être déclarée **avant** cette fonction, tout en haut du script. Piège déjà répété avec `renderDashboard()` (appelée avant `HEALTH_FLAG_DAYS_SINCE_FED`/`FEEDING_THRESHOLDS`) et `tourSelection` — pas spécifique à un navigateur, plante sur n'importe quel moteur JS dès qu'un utilisateur a des données existantes au chargement.
- **WebKit — variable globale masquant un `id` HTML** : une globale déclarée en `let`/`const` qui porte le même nom qu'un attribut `id` ailleurs sur la page plante silencieusement sur Safari/Chrome iOS (« Can't create duplicate variable that shadows a global property »). **Toujours `var` pour les déclarations globales dans `index.html`, jamais `let`/`const`.**
- **WebKit — variable nommée `t` masquant la fonction globale `t()`** : déclenche « Cannot access uninitialized variable » sur Safari/Chrome iOS, même dans du code sans lien avec la traduction (ex. `for(let t=...)`, `.find(t=>...)`). **Ne jamais nommer une variable/paramètre `t`.**
- **Webhooks Stripe** : toujours vérifier que les destinations de webhook sont créées dans le **même bac à sable Stripe** que les clés API utilisées — sinon échec silencieux, aucune erreur visible.
- **iOS Safari** : cache agressif après redéploiement — **réglé** via un mécanisme d'auto-détection de version (`APP_VERSION` dans `index.html` comparé à `version.txt` via `fetch({cache:'no-store'})`, rechargement forcé si différent). **Incrémenter `APP_VERSION` ET `version.txt` à chaque déploiement significatif**, sinon aucune détection. Format depuis le 31 août : `AAAA.MM.JJ.X.NN`, où `X.NN` est un compteur global de déploiements qui ne se remet **jamais** à zéro (continuer depuis la dernière valeur connue, ex. `1.99` → `2.00`). Champs de saisie sous 16px provoquent toujours un zoom automatique intempestif (non lié au cache).
- **MorphMarket bulk import** : le champ Photo URLs exige une vraie URL publique — le base64 local ne fonctionne pas. Ils ne supportent qu'**une seule photo par annonce** actuellement.

## État actuel / backlog restant

Voir [`docs/memoire-maitresse.md`](docs/memoire-maitresse.md) (état consolidé du projet — architecture, fonctionnalités livrées, monétisation, légal) et [`docs/journal-historique-sessions.md`](docs/journal-historique-sessions.md) (raisonnement et péripéties de résolution de problèmes par session) pour l'historique complet des décisions passées.

**Backlog en attente :**
- Comptes assistant/employé à accès limité (nécessite décisions de conception : compte séparé vs code partagé, niveau d'accès, palier tarifaire)
- Tableau comparatif formel LOCUS vs MorphMarket + lien dédié dans l'app
- Changement d'eau (mineur, pas prioritaire)

**Idées futures non décidées :**
- Catalogue photo communautaire + référence visuelle des gènes dans le calculateur (aucune conception encore tranchée)
- PWA (installation sans App Store)
- Tableau de bord admin caché (stats d'usage)
- Multi-espèces (gecko léopard, gecko à crête, boa) — pas une priorité immédiate

**À valider par Alex avec de vraies données réelles :**
- Format exact de colonnes de l'import CSV MorphMarket (deviné depuis leur doc publique)
- Export de masse MorphMarket (CSV Bulk Import 2.0) — valeurs exactes Category/Status à confirmer avec un vrai test d'import
