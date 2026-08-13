# LOCUS Scales — Journal historique des sessions

*Consolidé le 6 août 2026*

*Ce document conserve le raisonnement, les décisions marquantes et les péripéties de résolution de problèmes des sessions passées — utile pour comprendre le « pourquoi » derrière une décision, ou reconnaître un symptôme déjà rencontré. L'état actuel des faits (architecture, fonctionnalités, monétisation, ce qu'il reste à faire) se trouve dans `memoire-maitresse.md` — pas répété ici.*

## Session 1 — Fonctionnalités, légal, sécurité, traduction (phases 1-3)

Première grande session de construction : tableau de bord, arbre généalogique, gestion de nourriture, menu principal, et le chantier légal le plus substantiel du projet.

**Légal :** deux documents LawDepot.ca fournis par Alex ont servi de base (Conditions d'utilisation, Politique de confidentialité). 14 avertissements spécifiques ajoutés à la demande explicite d'Alex — « mieux vaut trop que pas assez ». La Politique de confidentialité décrivait une architecture future (comptes, Supabase, Stripe) pas encore active : Alex a choisi explicitement de garder ce contenu « en avance » plutôt que de le réécrire pour l'état du moment, sachant qu'il deviendrait exact avec le temps.

**Sécurité :** demande explicite d'Alex de corriger les failles pendant qu'elles sont à faible risque (avant qu'un futur catalogue communautaire ne les rende dangereuses pour d'autres utilisateurs). Vulnérabilité XSS trouvée : texte libre inséré via innerHTML sans nettoyage — `escapeHtml()` appliqué à 35+ points.

**Traduction :** décision de portée prise avant de commencer — ne jamais tenter une traduction complète en un seul passage vu la taille du fichier. Plan en phases exécuté jusqu'à la Phase 3 (125 clés à la fin de cette session), Légal/FAQ restant pour une session future.

**Recherche CITES/permis :** clarifié que CITES est fédéral (ECCC), pas provincial, et ne s'applique qu'aux transactions internationales. Python regius confirmé Annexe II. Recherche par province partiellement complétée (Québec et Ontario clarifiés, BC/Alberta à confirmer).

*Recherche sur le domaine .ca interrompue avant d'aboutir à des recommandations concrètes de registraires — reprise à la session suivante.*

## Session 2 — Protection du code, traduction (phase 4), domaines, tentative Supabase

### Fuite d'IP via Google Fonts — trouvée et corrigée

Le fichier chargeait trois polices via `@import` depuis fonts.googleapis.com, envoyant l'IP de chaque utilisateur à Google à chaque ouverture (risque RGPD documenté, jurisprudence allemande 2022+). Décision : héberger les polices localement plutôt que simplement divulguer le risque. Remplacement retenu après comparaison visuelle : Space Grotesk → Georgia, Manrope → Verdana, JetBrains Mono → Courier New.

**Bug découvert pendant l'opération :** le remplacement en masse de 'JetBrains Mono' par 'Courier New' a cassé l'échappement d'apostrophes dans 15 chaînes JavaScript (attributs style imbriqués dans des chaînes délimitées par apostrophes). Détecté par validation Node.js, confirmé par test dans un navigateur headless réel (clic sur tous les onglets/modales/changement de langue) avant d'être déclaré résolu.

### Traduction — Phase 4 (Légal/FAQ) complétée

Dernière phase du plan de traduction initial : modale Aide (tutoriel complet par onglet), Nous contacter, FAQ, Conditions d'utilisation, Politique de confidentialité, modale Configuration (pas encore localisée avant cette session), toast de confirmation de changement de langue (annonçait à tort une traduction « partielle »).

### Protection du code — mesures immédiates

Alex a réalisé qu'un simple clic-droit « Afficher le code source » permet de copier l'app entière, incluant la base de gènes vérifiés et le moteur de calcul. Mesures appliquées : bandeau de copyright (commentaire HTML + footer visible), clause anti-copie/scraping/ingénierie inverse dans les Conditions d'utilisation.

*Limite technique rencontrée : aucun outil de minification/obfuscation disponible dans l'environnement (accès réseau bash désactivé, installation impossible), et une minification maison par regex jugée trop risquée sur un fichier de 5500+ lignes. Alternative proposée : minifieur en ligne au choix d'Alex, la vraie solution long terme étant la migration Supabase (logique sensible déplacée côté serveur).*

### Nouvelle fonctionnalité : Annonces & Notes de mise à jour

Posée explicitement par Alex comme l'ancêtre volontaire du futur forum communautaire. Tableaux codés en dur au départ (pas encore de backend) — le schéma Supabase préparé plus tard dans la session inclut déjà des tables `announcements` et `changelog` pour rendre ceci dynamique.

### Domaines

locusscales.com ET locusscales.ca achetés simultanément chez Namecheap. Clarification apportée : un domaine .ca ne freine pas les visiteurs américains (seul l'enregistrement exige une présence canadienne, pas la visite). locusscales.com choisi comme domaine principal ; .ca redirige automatiquement, gardé pour la protection de marque.

### Courriel professionnel — premier blocage

Zoho Mail retenu comme solution (vraie boîte séparée, envoi/réception sous la vraie adresse). Transaction Mastercard bloquée par la banque pour suspicion de fraude — cause identifiée : domaine acheté depuis le cellulaire (Laval, QC) puis inscription Zoho tentée depuis un ordinateur connecté au VPN du travail (localisation apparente Ontario), deux localisations différentes en quelques minutes avec la même carte. Chantier mis en pause au profit de la migration Supabase.

*Résolu depuis (session ultérieure) : support@locusscales.com actif et fonctionnel.*

### Première tentative de migration Supabase — connecteur défaillant

Le connecteur officiel Supabase (MCP) a été installé (flux OAuth complété par Alex), mais est resté inaccessible dans cette conversation précise, statut « unknown » malgré plusieurs tentatives (y compris depuis un ordinateur différent). Conclusion : limite propre à cette conversation, pas à la façon dont Alex autorise le connecteur — recommandation d'ouvrir une toute nouvelle conversation.

*Travail réalisé en parallèle malgré le connecteur bloqué : schéma SQL complet conçu à partir de la structure localStorage existante, livré en fichier téléchargeable prêt à coller dans l'éditeur SQL de Supabase — ce schéma a servi de base à la migration réussie de la session suivante.*

## Session 3 — Supabase en production, hébergement, monétisation, traduction finale

Le connecteur Supabase a fonctionné dès le début de cette session (confirmant que le blocage précédent était bien propre à l'ancienne conversation). Migration complète réalisée de bout en bout : base de données, authentification, synchronisation cloud.

### Débogage de la phase de test — péripéties notables

- Bouton « Créer un compte » ne faisait rien → init du SDK Supabase non défensive, plantait silencieusement si le CDN externe tardait à charger
- « Load failed » répété sur tiiny.host (hébergement de test temporaire) → restriction réseau de WebKit sur les pages file:// ou contextes non-https stricts
- « email rate limit exceeded » répété → limite très basse du service de courriel gratuit intégré à Supabase ; désactiver « Confirm email » ne réglait pas les comptes déjà en attente — comptes confirmés manuellement par SQL, un compte de test même créé directement en base pour contourner l'envoi de courriel
- « Invalid login credentials » malgré un mot de passe vérifié correct en base (requête crypt()) → cause réelle : autocorrecteur du clavier iPhone modifiant le texte tapé, pas un bug de code
- Synchronisation cloud silencieuse si une session était déjà active à l'ouverture de la page (pas seulement au moment de la connexion) → corrigé
- Race condition trouvée : une donnée ajoutée pendant le rapatriement du cloud pouvait être écrasée → remplacé par une fusion par ID plutôt qu'un écrasement pur

*Comptes de test créés durant cette phase nettoyés de la base une fois les tests validés. Conclu avec un reptile de test synchronisé avec succès (« Lâche pas Claude »).*

### Hébergement — pourquoi GitHub Pages plutôt que Cloudflare

Cloudflare Pages exige de transférer les nameservers du domaine complet pour un domaine apex — risque de casser les MX de Zoho Mail déjà configurés. GitHub Pages accepte un sous-domaine via un simple CNAME chez le registrar, sans toucher aux autres enregistrements DNS. Le connecteur Cloudflare Developer Platform disponible ne supporte de toute façon pas le déploiement Pages ni la gestion DNS (seulement Workers/D1/R2/KV), donc inutilisable même pour automatiser.

Piège rencontré en cours de route : l'app Fichiers iOS ajoutait une majuscule ou dupliquait l'extension du fichier renommé (« Index.html.html ») — corrigé en renommant directement sur l'appareil avant l'upload plutôt que dans l'interface GitHub mobile.

### Monétisation — arbitrage entre Alex et sa conjointe

Discussion approfondie sur l'approche à adopter, chacun avec des idées différentes (accès gratuit prolongé aux 100 premiers membres, catalogue photo avec preuve de mue, devenir une plateforme de vente). Claude a servi d'arbitre technique et stratégique, validant certaines idées (l'offre de lancement n'a pas le risque de seuil collectif d'un concours classique) et nuançant d'autres (rivaliser avec MorphMarket maintenant serait perdant d'avance vu l'écart de trafic, mais faciliter un paiement entre deux parties déjà en contact via Stripe Connect reste viable même à petite échelle).

*Résultat : la ligne de démarcation finale retenue est « élève-t-il ou pas », pas un chiffre — voir `memoire-maitresse.md` section 4 pour la grille complète.*

### Traduction — complétion et audit de contenu

Une révision poussée a révélé que malgré la Phase 4 « complétée » à la session précédente, des pans entiers du module Élevage restaient en français codé en dur dans le rendu dynamique JavaScript (Fiscal, Valeur/Assurance, Racks/Terrariums, Incubation, Calendrier, Clients, fiche reptile complète) — la traduction précédente avait couvert la structure HTML statique et les onglets, mais pas tout le contenu généré dynamiquement. Traduit au complet durant cette session, portant le total à environ 300 clés.

**Bonus trouvé en marge de la traduction :** l'Aide et la FAQ affirmaient encore, dans les deux langues, que les données restent uniquement locales et que la synchronisation multi-appareils n'existe pas — vrai avant Supabase, faux depuis. Corrigé aux 5 endroits concernés (pas juste une traduction manquante, un vrai bug de contenu périmé).

## Session 4 — Légal, mobile, Stripe Connect, fonctionnalités, revue de code

*Session la plus longue et la plus dense à ce jour — de la validation légale au déploiement complet de Stripe Connect (bout en bout, avec paiements réels testés), en passant par une douzaine de nouvelles fonctionnalités et une revue de code complète.*

### Audit légal et bugs de contenu périmé

Sur demande explicite d'Alex, audit complet des documents légaux (CGU, Politique de confidentialité) : nom/courriel/adresse cohérents partout, plus aucune trace du domaine .ca périmé, 14 avertissements confirmés, traduction FR/EN complète (aucune clé orpheline).

**Deux bugs de contenu périmé trouvés et corrigés** (même famille que le bug « données locales seulement » corrigé en session 3) :
- La section Cookies de la Politique de confidentialité disait encore « une fois l'authentification activée » — au futur, alors que Supabase Auth est en production depuis longtemps.
- La clause « Perte de données locales » des CGU affirmait que les données sont « stockées uniquement sur l'appareil » — faux depuis Supabase. Corrigée pour refléter la réalité (sync cloud + copie locale hors ligne).

Politique de rétention des données décidée et intégrée dans la Politique de confidentialité : non-paiement/essai expiré → accès verrouillé seulement, jamais suppression des données ; comptes dormants (18-24 mois sans connexion, pas sans paiement) → préavis 30 jours puis suppression/archivage.

### Optimisation mobile de fond en comble

- Anti-zoom iOS : tous les champs de saisie forcés à 16px sur mobile.
- Zones tactiles agrandies (minimum 44px recommandé par Apple).
- Zone sécurisée iPhone (encoche/barre d'accueil) ajoutée aux toasts et au bas de page via `env(safe-area-inset-bottom)`.
- Bouton de fermeture (×) des fenêtres modales agrandi.

### Stripe Connect — intégration complète

Alex a créé son compte Stripe, activé Connect (mode « La plateforme »), et trois Edge Functions Supabase ont été construites : `stripe-connect-onboard`, `stripe-create-payment`, `stripe-webhook`.

*Bug marquant : la clé secrète a d'abord été mal copiée (pk_test au lieu de sk_test) — diagnostiqué via une table debug_logs temporaire.*

*Deuxième bug marquant, plus long à isoler : les deux destinations de webhook avaient été créées dans le mauvais bac à sable Stripe (différent de celui utilisé par les clés API et les paiements) — aucune erreur, juste un silence total. Diagnostiqué en comparant le préfixe exact de la clé publique entre les deux environnements.*

Test de paiement réel effectué avec la carte de test 4242 4242 4242 4242 — confirmé fonctionnel côté Stripe (paiement, transfert, commission).

### Bug critique trouvé et corrigé : "Cannot access uninitialized variable"

Cause réelle : la constante `DEFAULT_FEEDING_INTERVAL` était déclarée (`const`) après le point où `renderDashboard()` — appelée immédiatement au chargement — en avait besoin. Classique piège de « temporal dead zone » JavaScript. Corrigé en déplaçant la déclaration tout en haut du script.

### Nouvelles fonctionnalités livrées (session 4)

- Case à cocher "Python royal" (espèce libre sinon), tracker de quarantaine, étiquettes personnalisées, type de proie vivant/décongelé, journal vétérinaire, historique de santé par génétique, actions en lot, import MorphMarket (CSV/TSV).
- Champ "Début du cooling", dossier "Référence — l'an dernier", rappels personnalisés, correspondance automatique liste d'attente ↔ éclosion.
- Lexique de taille des proies, FAQ husbandry structurée (30 questions), dossiers "Mythes vs Réalité" et "Checklist pré-achat", sous-onglet Outils (convertisseurs), recherche unifiée.
- Bilan annuel enrichi (commission LOCUS/Stripe), export .ics.

### Comparaison MorphMarket et positionnement

Positionnement retenu : LOCUS n'est pas un concurrent de MorphMarket — eux excellent dans le marketplace, LOCUS excelle dans la gestion d'élevage et le bien-être animal (avertissements automatiques pré-accouplement, quarantaine, décongelé recommandé par défaut).

### Revue de code complète

Bugs trouvés et corrigés : fuite de données silencieuse (champ "notes" orphelin dans l'import MorphMarket), trou de sécurité (fonction de débogage temporaire restée publique), table debug_logs oubliée en production, gap de traduction (`renderTimeline()` pas rappelée au changement de langue).

## Note sur la continuité entre conversations

*La mémoire à long terme de Claude est spécifique à chaque Project — les décisions et le contexte enregistrés dans une conversation d'un Project sont disponibles dans les conversations suivantes du même Project, mais pas dans un Project différent. Si un connecteur (Supabase ou autre) semble bloqué ou indisponible dans une conversation, ouvrir une toute nouvelle conversation a résolu le problème par le passé plutôt que d'insister dans la même conversation.*
