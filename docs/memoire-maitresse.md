# LOCUS Scales — Mémoire maîtresse du projet

*Mis à jour le 12 août 2026 — document de référence unique.*

*Ce document consolide l'état actuel du projet sans répéter l'historique. Voir `journal-historique-sessions.md` pour le raisonnement et les péripéties de résolution de problèmes.*

## 1. Vue d'ensemble du projet

LOCUS Scales est une application web mono-fichier (HTML/JS) de gestion d'élevage de python royal (Ball Python), destinée à un lancement commercial SaaS. Elle remplace le suivi papier/post-it des éleveurs par un système complet : génétique, racks, ventes, incubation, administration.

**Positionnement d'Alex :** éducateur reptiles (Magazoo, 5 ans) + passionné en relance (3 serpents actuellement, ancien élevage de 20-30 serpents il y a 10-15 ans). Ne jamais présenter Alex comme un « éleveur expert X années d'expérience » dans du contenu marketing — c'est inexact.

**Slogan principal :** « Ni startup, ni stagiaire. Juste un passionné qui en avait marre des post-it. »

**Texte d'accroche support/communauté :** « Chez Locus Scales, vous êtes au bon endroit. Votre support nous permet d'évoluer tous ensemble afin d'offrir ce qu'il y a de mieux à nos compagnons à écailles. »

**Identité visuelle :** nom LOCUS Scales (LOCUS dominant, « Scales » en signature). Polices hébergées localement : Georgia (titres/logo/chiffres), Verdana (texte courant), Courier New (données techniques/tags). Décor SVG dans le header (feuillage + serpent stylisé). Sous-titre : « Gestion d'élevage — Python royal (Ball Python) ».

## 2. Architecture technique

### 2.1 Structure du code

- Fichier unique `index.html` (~8600+ lignes) — HTML + CSS + JS dans un seul fichier
- Base de données des gènes (`GENES`) centralisée tout en haut du fichier — aucun ID de gène en dur ailleurs
- Moteur de calcul génétique lit exclusivement depuis `GENES`
- 78 gènes actuellement, tous vérifiés sur Morphpedia/ReptiDex

### 2.2 Stockage et backend

- localStorage comme couche de base (`storage.load()`/`save()`), clés : `locus_snakes_v1`, `locus_elevage_v1`
- Supabase (Postgres + Auth + RLS + Storage) ACTIF et fonctionnel en production — projet ID `dkhmqkkmnexqixmkvzjo`, région ca-central-1
- Tables Supabase : `snakes`, `racks`, `pairings`, `clutches`, `expenses`, `customers`, `app_state`, `profiles`, `announcements`, `changelog` — chacune avec `user_id` + RLS activé
- Bucket Supabase Storage public `reptile-photos` — RLS : upload/modif/suppr limités au dossier `user_id`, lecture publique. Nécessaire pour l'export de masse MorphMarket (photos hébergées avec vraie URL publique, le base64 local n'étant pas utilisable dans leur import).
- `cloudMirrorSnakes()` synchronise localStorage → Supabase quand connecté ; `syncWithCloud()` tire les données au moment de la connexion (fusion par ID, jamais un écrasement pur)
- `requireAuthOrPrompt()` bloque les actions d'élevage/export si non connecté

### 2.3 Protection du code et propriété intellectuelle

- Bandeau de copyright bilingue en commentaire HTML + footer visible
- Clause « Interdiction de copie, d'extraction et d'ingénierie inverse » dans les CGU (FR+EN)
- Recommandé mais non exécuté : enregistrement OPIC/CIPO (~65$), dépôt de marque « LOCUS Scales »

### 2.4 Hébergement

- GitHub Pages sur app.locusscales.com — compte GitHub `vivelapeche39-cell`, dépôt `Locus-Scales`, fichier `index.html`
- CNAME configuré chez Namecheap
- Domaines : locusscales.com (principal) + locusscales.ca (redirige, protection de marque seulement)
- Courriel professionnel Zoho Mail actif : support@locusscales.com

## 3. Base de données génétique

Principe non négociable : rigueur génétique stricte. Un gène n'est ajouté que si son mode de transmission est vérifiable (Morphpedia, ReptiDex, ou recoupement de sources fiables). Refusé : Toffee (même allèle que Candy, fusionnés), Paradox/Scaleless Head (trait non confirmé génétiquement), identification visuelle par IA (risque de tromper des clients).

### 3.1 Complexes alléliques modélisés

- **spiderComplex** : Spider, Woma, HGW, Blackhead, Spotnose, Chocolate, Wookie, Cypress, Bongo, Champagne
- **lesserComplex (BEL)** : Lesser, Butter, Mojave, Phantom, Mystic, Russo, Special, Bamboo, Daddy Gene, Mocha
- **fireComplex** : Fire, Flame, Vanilla, Sulfur, Disco, Lemonback
- **cinnamonComplex** : Cinnamon, Black Pastel, Huffman, Jolt, Razor
- **yellowbellyComplex** : Yellow Belly, Specter, Gravel, Asphalt, Spark (Flare = alias de Yellow Belly, pas un gène distinct)
- **tAlbinoComplex** : Albino, Candy/Toffee (fusionnés), Ultramel

### 3.2 Sexe et logique spéciale

Banana / Coral Glow : logique Male Maker vs Female Maker via `sexLinkedMaker` — l'app demande le statut du parent mâle pour prédire le ratio des sexes de la portée (~90-95% du sexe correspondant, pas garanti à 100%).

### 3.3 Avertissements santé (visibles, jaune/rouge)

- Wobble syndrome : Spider, Woma, Champagne
- Malformations/microphtalmie : Super Cinnamon, Super Black Pastel (forme homozygote)
- `CROSS_WARNINGS` gère les combinaisons à risque (ex. Champagne × Spider)

### 3.4 Types de gènes gérés

Dominant, Codominant/Incomplet dominant, Récessif, Allélique (complexe), Freeway (identité non confirmée sur un locus), Possible (pourcentage de certitude optionnel, exclu du calcul mendélien tant que non confirmé), Unknown type (traçable mais exclu des calculs).

## 4. Monétisation

Philosophie clé : la ligne de démarcation est « élève-t-il ou pas », pas le nombre d'animaux. Pas de microtransactions, pas de limites artificielles qui ne coûtent rien à retirer.

**⚠️ Instruction comportementale permanente :** Alex a demandé à être rappelé à l'ordre si une proposition dérive vers une monétisation agressive/malhonnête.

| Palier | Contenu |
|---|---|
| Gratuit | Calculateur complet, nourriture complet, 3-5 reptiles, sync cloud incluse. ZÉRO élevage (pas de racks/pairing/incubation/vente/QR/export). |
| Collection — 5$/mois | Reptiles illimités, Mode Tournée complet. TOUJOURS zéro élevage. |
| Pro — 8-10$/mois | Tout illimité + accès complet élevage (racks, pairing, incubation, ventes, générateur d'annonces MorphMarket, QR codes, exports PDF/Excel, sync cloud). |

- Cloud sync GRATUIT pour tous les paliers (filet de sécurité Safari iOS, pas un levier payant)
- Accès public sans compte : calculateur seulement (vitrine)

### 4.1 Commission transactionnelle

Stripe Connect (mode Express) — l'argent va directement chez l'éleveur, LOCUS prélève automatiquement ~1% via `application_fee_amount`.

### 4.2 Offre de lancement (envisagée, pas encore tranchée)

100 premiers utilisateurs → 3 mois gratuits, jusqu'à une date limite. Techniquement confirmé réalisable sans carte de crédit via `payment_method_collection:'if_required'` + `trial_period_days`.

### 4.3 Politique de rétention des données (décidée)

- Ne jamais effacer les données pour non-paiement ou fin d'essai — seul l'accès se verrouille (même logique que le palier gratuit), données réapparaissent au réabonnement.
- Comptes dormants (18-24 mois SANS CONNEXION, pas sans paiement) → préavis 30 jours puis suppression/archivage.

## 5. Stripe Connect — état d'implémentation

Intégration complète réalisée en session 4 :
- `stripe-connect-onboard` — crée le compte Connect Express de l'éleveur
- `stripe-create-payment` — session Stripe Checkout avec commission LOCUS + transfert direct
- `stripe-webhook` — reçoit `checkout.session.completed` (marque le reptile vendu) et `account.updated`

Test de paiement réel effectué avec la carte 4242 4242 4242 4242 — confirmé fonctionnel côté Stripe.

**⚠️ En suspens :** les deux destinations de webhook doivent être recréées dans le bon bac à sable Stripe pour fermer la boucle de confirmation automatique des ventes (bug identifié en session 4, pas encore corrigé).

## 6. Conformité légale

Base : deux documents LawDepot.ca (Conditions d'utilisation, Politique de confidentialité), corrigés et enrichis.

### 6.1 Conditions d'utilisation

14 avertissements dédiés couvrant : liens externes (permis/CITES), exactitude du calculateur génétique, suivi de santé (ne remplace pas un vétérinaire), non-affiliation à MorphMarket, contenu utilisateur, LOCUS jamais partie à une vente, disponibilité du service, âge minimum, outils fiscal/réglementaire, rapport de valeur, statuts génétiques incertains, perte de données locales, notifications non garanties, base de gènes tierces. Clause anti-copie/scraping/ingénierie inverse séparée.

### 6.2 Politique de confidentialité

- Loi 25 (Québec) nommée explicitement ; résidents américains couverts génériquement (20+ États en 2026)
- PIPEDA (Canada) et RGPD (UE) couverts
- Exception documentée : QR code transmet nom + génétique à qrserver.com (tiers)
- Section cookies reformulée pour l'authentification par compte

### 6.3 Exigences checkout Stripe (à appliquer à la construction)

- Case à cocher de consentement explicite (opt-in, NON précochée) — Loi 25
- Mention claire de la récurrence de l'abonnement
- Aucun frais caché
- Lien de désabonnement facilement accessible

### 6.4 Page Permis (recherche réglementaire, non un avis juridique)

- CITES fédéral (ECCC), transactions internationales seulement — Python regius Annexe II
- Québec : permis non requis a priori. Ontario : aucune loi provinciale, dépend de la municipalité
- BC/Alberta à confirmer, reste du Canada non vérifié

## 7. Traduction FR/EN

Architecture i18n complète : dictionnaire `I18N` (fr/en), `t(clé)`/`tLang(clé,langue)`, système `data-i18n`, `applyTranslations()`.

**État actuel :** ~370 clés de traduction par langue, parité vérifiée. Scan automatique ne trouve plus de texte français en dur non traduit dans le code JS.

**Règle technique permanente :** toute nouvelle section de contenu générée dynamiquement en JS doit être ajoutée à `applyTranslations()` dès sa création, pas seulement au changement d'onglet — sinon elle reste figée dans l'ancienne langue au changement FR/EN.

## 8. Sécurité (auditée)

- RLS Supabase vérifié — aucune alerte critique
- XSS : `escapeHtml()` appliqué à 40+ points d'insertion de texte libre
- `showToast()` utilise `textContent`, jamais `innerHTML`
- Balises `<title>`, meta description, favicon, Open Graph ajoutées

## 9. Fonctionnalités principales déjà construites

- Calculateur génétique multi-locus avec Punnett, gestion Freeway/Possible/Unknown
- Tableau de bord, Racks & Terrariums (Mode Tournée), calendrier de reproduction automatique
- Incubation avec compte à rebours, auto-création des bébés à l'éclosion
- Fiches reptiles complètes : pedigree, arbre généalogique (détection consanguinité), journal de bord, historique de poids ET de longueur, calendrier de nourrissage, QR code, export PDF
- Gestion de nourriture, Ventes (génération annonce MorphMarket FR/EN, fiches clients)
- Section légale : Fiscal, Valeur/Assurance, Permis
- Export/Import JSON complet, import CSV MorphMarket
- Notifications navigateur, recherche globale unifiée
- Onboarding, Utilitaire → Communauté (référence proies, FAQ husbandry, Mythes vs Réalité, Checklist pré-achat, Outils)
- **Mode simplifié débutant** (toggle manuel dans Mon profil — cache Élevage/Incubation)
- **Calculateur de coût pré-achat** (Communauté > Outils, connectés seulement)
- **Suivi de longueur** par reptile (pattern identique au poids)
- **Journal de mue enrichi** (qualité complète/incomplète/en morceaux + note) et **journal de nettoyage terrarium**
- **Suivi folliculaire** sur les accouplements (précurseur à l'ovulation, en mm)
- **Journal de défécation** par reptile
- **Vue "Outcomes" combinée** — projection du total de bébés attendus par morph, agrégeant tous les accouplements avec prédiction liée
- **Quantité de repas** (complet vs partiel)
- **Export de masse MorphMarket** — CSV compatible Bulk Import 2.0, upload automatique des photos vers Supabase Storage pour obtenir de vraies URLs publiques

## 10. Backlog restant

### 10.1 Prochain item (nécessite décisions de conception d'Alex)

- Comptes assistant/employé à accès limité — compte séparé vs code partagé, niveau d'accès, palier tarifaire

### 10.2 Autres items en attente

- Tableau comparatif formel LOCUS vs MorphMarket + lien dédié dans l'app
- Changement d'eau (mineur, pas prioritaire)

### 10.3 À valider par Alex avec de vraies données

- Format exact de colonnes de l'import CSV MorphMarket (deviné depuis leur doc publique — Alex doit tester avec un vrai export)
- Export de masse MorphMarket — valeurs exactes Category/Status à confirmer (page d'import bloquée aux robots pour Claude, devinées depuis la doc support)
- Recréer les deux destinations de webhook Stripe dans le bon bac à sable

### 10.4 Idées futures (pas commencées, aucune décision de conception prise)

- Catalogue photo communautaire centralisant les photos de tous les utilisateurs, éventuellement réutilisé comme référence visuelle des gènes dans le calculateur — Alex a évoqué l'idée mais n'a rien tranché sur le comment/où
- PWA (installation sans App Store) — manifest.json + service worker, architecture actuelle déjà adaptée
- Tableau de bord admin caché (statistiques d'usage par éleveur) — techniquement déjà possible via SQL direct
- Multi-espèces (gecko léopard, gecko à crête, boa) — pas une priorité immédiate. Calculateurs déjà existants pour gecko léopard et boa ; le gecko à crête est le cas le plus ouvert (traits polygéniques, peu de calculateurs fiables)
- Alexa, thermostats Bluetooth, simulateur de ponte enregistrable, vrai forum communautaire

## 11. Préférences et façons de travailler

- Livraison de code : toujours des patchs ciblés (`str_replace`), jamais de réécriture complète sauf demande explicite
- Vérification post-édition systématique : validation syntaxique JS (`node --check`), absence d'ID/fonctions dupliqués, clés i18n FR/EN synchronisées
- **Identifiants/mots de passe toujours en texte clair, gros caractères** — Alex a une très mauvaise vue
- Sources de vérification génétique exclusives : Morphpedia et ReptiDex
- Alex veut être rappelé à l'ordre si une proposition de monétisation dérive vers l'agressif/malhonnête
- **Présenter les décisions avec des options claires avant d'agir**, surtout pour les choix d'architecture ou de conception produit
- Communication habituelle en français québécois informel, souvent via dictée vocale (accepter les approximations phonétiques de termes anglais)
- Alex gère son budget de tokens consciemment — préférer l'efficacité
