# Albion Refine Optimizer — Contexte projet

> Document préparé pour reprise de discussion dans une nouvelle session
> Claude. Résume l'état V3.0 de l'outil, les décisions clés du modèle, et les
> deux extensions envisagées (Black Market flip, crafting équipement).

---

## 1. Vision et positionnement

**Utilisateur** : joueur Albion Online, serveur Europe, statut Premium, 
premium actif, cherche à optimiser son économie de raffinage/crafting.

**Domaine actuel** : outil web pour identifier les meilleures routes de
raffinage de matières premières (bois, peau, fibre, minerai, pierre) sur
les 6 villes Royal du continent.

**Reframing V3.0** : après un cycle complet (V1 → V2.9), il est devenu clair
que le refining pur ne génère PAS de gros pourcentages de ROI en Albion. Les
raffineurs réels gagnent leur vie sur :
- **Silver / focus** (métrique désormais promue en hero dans l'UI)
- **Volume** (des milliers d'unités par session)
- **Timing** (fenêtres de marché)
- Marges modestes (+2 à +5% ROI) sur gros débit

L'outil affiche maintenant la réalité (grâce à V2.6-V2.9), qui est modeste
comparée aux illusions initiales.

---

## 2. Architecture technique

### Stack
- **Backend** : Python 3.12, FastAPI, uvicorn, pydantic, httpx, diskcache
- **Frontend** : React 18 + Vite 6 + TypeScript 5 strict + Tailwind 3 +
  Framer Motion + Lucide + clsx + axios
- **Data source** : Albion Online Data Project (AODP) API v2
- **Déploiement** : Vercel monorepo (Python serverless + React static), URL
  albion-refine-optimizer.vercel.app
- **Tests** : pytest (~230 tests), mypy strict

### Structure
```
src/albion_refine/
├── config.py          # Constantes : villes, taxes, tiers, resources, enchants
├── models.py          # Pydantic : PriceQuote, VolumeData, Route, SourcingLeg,
│                      #   SourcingAllocation, SalesScenario, RefiningResult
├── aodp_client.py     # HTTP client AODP + cache diskcache (5 min TTL)
├── refining.py        # Formules refining pures (RRR, quantité, coût station)
├── market.py          # Taxes, walk_book, freshness_factor, buy_side_inflation,
│                      #   evaluate_instant_sell / evaluate_sell_order
├── optimizer.py       # Orchestrateur : allocation multi-villes, tri, filtrage
├── formatters.py      # Rich (CLI)
├── cli.py             # Typer CLI
├── api.py             # FastAPI endpoints (/api/health, /config, /optimize)
└── data/items.json    # IDs AODP + recettes de refining

web/src/
├── App.tsx            # Racine + modal guide + refresh handling
├── components/
│   ├── OptimizeForm.tsx      # Formulaire (tier, mode, resource, enchant, etc.)
│   ├── RouteCard.tsx         # Une card par route retenue
│   ├── ScenarioBlock.tsx     # Bloc vente instant/order
│   ├── HowItWorksModal.tsx   # Guide pédagogique 12 sections
│   ├── WarningBadge.tsx      # Badge par WarningCode
│   ├── AlternativesList.tsx  # Discarded routes fallback
│   ├── ChecklistPanel.tsx    # Pages AODP à rafraîchir en jeu
│   ├── FreshnessBadge.tsx    # Badge âge de la donnée
│   └── InfoTooltip.tsx       # Info-bulle réutilisable
├── lib/
│   ├── glossary.tsx   # Définitions pédagogiques centralisées
│   └── cn.ts          # clsx wrapper
└── types/optimizer.ts # Types TypeScript miroir des modèles Pydantic

api/[[...path]].py     # Handler Vercel serverless (catch-all → app FastAPI)
```

### Pièges de déploiement (documentés dans DEPLOYMENT.md)
1. **Framework detection Vercel** : `"framework": null` dans vercel.json
   (sinon Vercel prend le projet pour une app FastAPI et le build meurt avant
   d'exécuter buildCommand). Ne PAS ajouter `[tool.vercel]` dans pyproject.
2. **Cache dir serverless** : `_default_cache_dir()` détecte `VERCEL=1` et
   bascule sur `/tmp/albion-refine` (Vercel FS est read-only sauf /tmp).
3. **buildCommand** : `rm -rf api/albion_refine && cp -r src/albion_refine
   api/albion_refine && cd web && npm install && npm run build`. Le `rm -rf`
   est crucial (cp -r imbrique si la cible existe).

---

## 3. Modèle métier — Refining V3.0

### Chaîne de valeur
```
Ressources brutes (bois/peau/fibre/minerai/pierre)  ← achetées en villes
    ↓
+ Ressources T-1 raffinées                          ← achetées en villes
    ↓
Raffinage à la ville spécialité (+40% RRR)
    ↓
Ressources raffinées + retours RRR
    ↓
Vente ressources raffinées + Vente retours          ← en villes
```

### 5 filières supportées (V2.4)
| Filière | Brut ID  | Raffiné ID     | Ville spécialité |
|---------|----------|----------------|------------------|
| bois    | T{N}_WOOD  | T{N}_PLANKS      | Fort Sterling    |
| peau    | T{N}_HIDE  | T{N}_LEATHER     | Martlock         |
| fibre   | T{N}_FIBER | T{N}_CLOTH       | Lymhurst         |
| minerai | T{N}_ORE   | T{N}_METALBAR    | Thetford         |
| pierre  | T{N}_ROCK  | T{N}_STONEBLOCK  | Bridgewatch      |

**⚠️ Attention** : la pierre brute est encodée "ROCK" côté AODP (pas STONE).

### Bonus RRR (tous confirmés en jeu)
- Base station : +15.2%
- Ville de crafting (général) : +18%
- Spécialité ville : +40% (matériau matching seulement)
- Focus : +59%
- Avec spé + focus : ~54% de retour effectif

### Enchantements (V2.3)
- .0 (base) → .4
- IDs AODP : T7_WOOD_LEVEL1@1, T7_WOOD_LEVEL2@2, etc.
- Recette identique (T7 .1 wood → T7 .1 plank + T6 .1 plank comme input T-1)
- Marchés moins liquides, marges souvent meilleures mais volumes plus faibles

### Formules
- **ROI capital** = bénéfice / capital total dépensé (métrique principale)
- **Marge efficacité** (legacy V1) = bénéfice / (capital - récup RRR)
- **Silver / focus** = bénéfice / focus utilisé (**hero V3.0** quand focus actif)
- **Bénéfice safe** = revenu scénario A (instant sell) − coût net

### Taxes marché (V3.0 corrigé)
| Cas | Setup fee | Sale tax | Total |
|---|---|---|---|
| Non-premium instant sell | — | 8% | 8% |
| Non-premium sell order | 2.5% | 8% | 10.5% |
| Premium instant sell | — | 4% | 4% |
| Premium sell order | 2.5% | 4% | 6.5% |

*Note* : la V1 avait 5% setup, corrigé à 2.5% en V3.0. Le premium fait ~120k
silver d'écart sur 3M de revenu.

### Slippage buy-side (V2.7)
Le sell_price_min AODP est le prix du meilleur ordre, sans info de profondeur.
Modèle d'inflation appliqué au prix d'achat :

- **Composante profondeur** (ratio qty demandée / volume 24h) :
  0-5% → 0% | 5-15% → 2% | 15-30% → 5% | 30-60% → 10% | 60-100% → 15% | >100% → 20%
- **Composante fraîcheur** (âge donnée) :
  <30 min → 0% | 30 min-1h → 2% | 1-2h → 5% | 2-4h → 10% | >4h → 15%
- **Cap combiné** : +25% max (multiplicatif)
- **volume_24h=0** (marché mort) → composante profondeur à 20% + warning

### Volume 24h glissant (V2.8)
Fix majeur : l'endpoint `/history` AODP renvoie ~10 jours de buckets. Notre
code sommait TOUT en appelant ça "volume_24h" → ratios ~10× sous-estimés.
Corrigé en V2.8 : `time-scale=6` + filtrage par `[now - 24h, now]` sur les
buckets. C'est ce fix qui a fait chuter les ROI affichées de +43% théoriques
à +3% honnêtes.

### Sourcing multi-villes (V2.9)
Au lieu de choisir UNE ville par input et de racler tout son carnet, l'algo
alloue la quantité sur jusqu'à 3 villes (paramétrable) :

1. Tri par sell_price_min ascendant.
2. Greedy : prendre `min(qty_restante, volume_24h × saturation_per_city)` à
   chaque ville.
3. **Comparaison de coût marginal** : à chaque étape, on compare étendre
   l'allocation actuelle vs ouvrir une nouvelle dans la prochaine ville. On
   garde le moins cher. Ça évite de partir chercher du bois plus cher quand
   la ville cheapest supporte encore le débit.
4. Reste éventuel → gonfle la dernière allocation (slippage capé à +25%).

Paramètres : `max_source_cities` (1-6, défaut 3), `saturation_per_city`
(défaut 0.25 = 25% du volume 24h par ville).

### Warnings (WarningCode enum)
- `ROUTE_ZONE_ROUGE` : passage par Caerleon
- `DATA_JAUNE` : au moins une jambe avec fraîcheur 3-6h
- `PROFONDEUR_INCERTAINE` : volume 24h < quantité
- `RECUP_PARTIELLE` : carnet acheteur n'absorbe pas toute la récup
- `RECUP_SATURATION` : récup > 50% du volume 24h ville de destination
- `BUY_SLIPPAGE_ELEVE` : slippage combiné > 8% sur au moins une jambe
- `MARCHE_INACTIF` : aucun trade dans les dernières 24h sur au moins une jambe d'achat

---

## 4. Historique des versions

| Version | Contenu |
|---------|---------|
| V1.0 | Refining bois uniquement, formules initiales |
| V2.0 | ROI capital comme métrique principale (fix formule) |
| V2.1 | Freshness confidence factor |
| V2.2 | Filière peau (Martlock) |
| V2.3 | Enchantements .0-.4 |
| V2.4 | Filières fibre / minerai / pierre |
| V2.5 | Suppression recup_mode (redondant avec exploration exhaustive) |
| V2.6 | Cache TTL 15→5 min, barème freshness durci, bouton Refresh |
| V2.7 | Slippage buy-side (profondeur + fraîcheur, capé +25%) |
| V2.8 | Fix volume 24h glissant (bug majeur découvert), barème recalibré, marché mort |
| V2.8.1 | Toujours afficher top_n routes (seuil devient informationnel) |
| V2.9 | Sourcing multi-villes greedy avec coût marginal |
| **V3.0** | **Support premium, silver/focus promu en hero, setup fee corrigé (5%→2.5%)** |

---

## 5. Idées d'extension — feuille de route

### Extension A : Black Market flip pur (buy → resell)

**Principe** : identifier des équipements achetables dans les villes royales
et revendables plus cher au Black Market de Caerleon (NPC-driven, distinct
du marché normal de Caerleon).

**Faisabilité vérifiée** :
- AODP couvre bien le Black Market (`city="Black Market"`), avec les qualités
  1-5. Sonde live du 2026-07-22 : T5_HEAD_LEATHER_SET1 Q1 à Bridgewatch =
  9086s sell, Black Market buy = 10902s → arbitrage brut ~20%.
- Item IDs : hundreds d'équipements (armes, armures, accessoires, mounts,
  artifacts, tomes) × 5 tiers × 4 enchants × 5 qualités.
- Volatilité : le Black Market bouge très vite (NPCs changent d'humeur), donc
  le refresh critique.

**Scope estimé** : 1-2 sessions. C'est plus simple que le refining actuel
(pas de raffinage, pas de recettes, juste `buy(city) × 1.04 < BM_buy × 0.96`).

**Ce qu'il faut** :
- Liste d'items équipements (l'utilisateur va la fournir, catégories × tiers ×
  enchants × qualités)
- Fetch multi-item vers AODP (50+ items par requête)
- UI filtre : catégorie, tier, enchant, qualité min
- Formule : `profit = BM_buy_price × (1 - premium_tax) - city_sell_price × 1.0`
- Warning si data BM > 15 min
- Bouton refresh manuel (le BM bouge à la minute)

### Extension B : Crafting équipement → Black Market

**Principe** : au lieu d'acheter l'équipement fini, on l'achète brut+refined
et on le crafte, puis on vend au Black Market.

**Faisabilité** :
- Nécessite modéliser tout le pipeline crafting (recettes, RRR crafting,
  ville spé par catégorie d'équipement, coût station, focus, qualité de sortie)
- Qualité de sortie aléatoire dépend du RRR et de la station
- Beaucoup plus complexe que le refining à cause des dimensions supplémentaires

**Scope estimé** : 4-6 sessions.

### Extension C : Crafting équipement → villes royales

**Principe** : même que B mais vente en villes royales (moins volatile).

**Scope estimé** : 3-4 sessions. Extension naturelle du refining actuel
appliquée à un niveau supérieur (matériaux raffinés → équipement).

### Ordre recommandé

1. **A avant tout** : rapide à livrer, résultat immédiat exploitable,
   confirme la fraîcheur AODP sur le BM en pratique.
2. Ensuite **C** (crafting → villes royales) : plus prévisible, valide le
   modèle crafting sur marché stable.
3. Enfin **B** (crafting → BM) : greffe la volatilité BM au-dessus du modèle
   crafting déjà validé.

### Questions ouvertes à trancher avec l'utilisateur

1. **Format des données à fournir** — L'utilisateur va fournir la liste
   des équipements et leurs recettes. Format proposé :
   ```json
   {
     "T5_2H_BOW": {
       "category": "weapon_bow",
       "tier": 5,
       "recipe": {"T5_PLANKS": 20},
       "crafting_city": "Fort Sterling"
     }
   }
   ```

2. **Qualité côté équipement** — Q4 se vend beaucoup plus cher que Q1 mais
   la qualité qui sort de la station est aléatoire. Options :
   - Supposer Q1 pour rester conservateur (V1 de l'extension)
   - Modéliser la proba par qualité (nécessite données, V2 de l'extension)

3. **UI séparée ou intégrée ?** — Les extensions ont assez de différence pour
   mériter un menu / onglet différent dans l'app. Proposition :
   - Onglet "Raffinage" : outil actuel
   - Onglet "Black Market flip" : extension A
   - Onglet "Crafting équipement" : extensions B et C combinées

---

## 6. Où en est le code au moment de ce document

- **Branche** : `main` (déployée sur Vercel)
- **Dernier commit V3.0** : (à noter au moment du push)
- **Tests** : 227+ passing, mypy clean
- **Bundle web** : ~121 KB gzip
- **Fonctionnalités qui marchent bien** :
  - Multi-source (V2.9), slippage (V2.7), volume 24h réel (V2.8)
  - Guide "Comment ça marche" complet (12+ sections)
  - Info-bulles pédagogiques
  - 5 filières + 5 niveaux d'enchant × 5 tiers = 125 combinaisons possibles
  - Premium (V3.0)
- **Ce qui pourrait être amélioré (V3.x avant de partir sur les extensions)** :
  - Contrôle `max_source_cities` exposé dans le formulaire web (aujourd'hui
    seulement CLI/API)
  - Mode "surveillance" (poll toutes les X min, notification browser sur
    fenêtre d'opportunité) — le vrai truc qui rendrait l'outil utile en
    background pendant qu'on joue
  - Historique perso (voir comment le marché a bougé sur les runs précédents)
- **Ce qui reste douloureux** :
  - Fraîcheur AODP dépend d'autres joueurs avec le client AODP installé
  - Pas de vue "depth" du carnet côté AODP (on ne peut que proxifier via volume)
  - Sur certains matériaux/villes, la data est très stale et biaise tout

---

## 7. Références utiles

- Wiki Albion : https://wiki.albiononline.com
- AODP API : https://www.albion-online-data.com
- Client AODP à installer : https://albion-online-data.com/client
- Repo GitHub : https://github.com/Drakenarl/albion-refine-optimizer
- URL prod : https://albion-refine-optimizer.vercel.app

---

*Dernière mise à jour : 2026-07-22, fin V3.0.*
