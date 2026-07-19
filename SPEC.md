# Albion Refine Optimizer — Cahier des Charges

**Version du document** : 1.0
**Auteur du projet** : Duvalier (GitHub: Drakenarl)
**Cible d'exécution** : Claude Code
**Langue du projet** : Français (code en anglais, docs et CLI en français)
**Serveur cible** : Europe (Albion Online)

---

## 1. Vue d'ensemble

### 1.1. Objectif du projet

Construire un outil d'optimisation économique pour Albion Online qui répond à la question :

> *"Dans quelle ville acheter du bois brut et du T-1 plank, comment les raffiner à Fort Sterling, et dans quelle ville revendre les planks résultants, pour maximiser mon profit sur le serveur Europe ?"*

L'outil doit prendre en entrée un tier de raffinage cible (T4–T8) et des paramètres utilisateur, interroger l'API publique de l'Albion Online Data Project (AODP), et retourner les meilleures routes de raffinage avec calcul de marge nette, recommandations de vente (instant sell vs sell order), et alertes sur la fraîcheur des données.

### 1.2. Livraisons versionnées

- **V1 — CLI Python** (priorité absolue, cœur du projet)
- **V2 — Extensions** (récursion cascade tiers, split vente, fees scraping)
- **V3 — Frontend web** (Next.js + FastAPI backend, wrapping V2)

Chaque version est **fonctionnelle et livrable indépendamment**. Ne pas commencer V2 avant que V1 soit testée et validée.

### 1.3. Contraintes de conception

- **Zéro reverse engineering du client jeu** : uniquement l'API publique AODP. Toute autre méthode risque le ban du compte utilisateur.
- **Code lisible et documenté** : ce projet est un artefact portfolio, la qualité du code compte autant que la fonctionnalité.
- **Testable** : logique métier séparée des I/O, tests unitaires avec fixtures JSON mockées de l'AODP.
- **Extensible** : la V1 doit poser les bases sur lesquelles V2 puis V3 s'appuient sans réécriture majeure.

---

## 2. Glossaire

| Terme | Définition |
|---|---|
| **RRR** | Resource Return Rate — pourcentage de matières premières rendues après un raffinage. |
| **AODP** | Albion Online Data Project — API publique communautaire des prix marché. |
| **Bonus city** | Ville avec spécialité de raffinage (+40% RRR). Fort Sterling pour le bois. |
| **Focus** | Ressource jouable qui augmente le RRR de +59% et débloque des bonus de vitesse. |
| **Daily bonus** | Bonus quotidien de production (+10% ou +20%) sur certains items, affiché dans le menu Activités en jeu. |
| **Nutrition cost** | Coût de base consommé par la station de raffinage, dépend du tier. |
| **Station fee** | Multiplicateur (%) appliqué par l'owner de la station sur le nutrition cost. |
| **Instant sell** | Vendre en remplissant un buy order existant. Silver immédiat, tax 8% (no premium). |
| **Sell order** | Placer un ordre de vente et attendre un acheteur. Silver différé, tax totale ~13% (no premium). |
| **Order book walk** | Parcourir les ordres empilés dans le carnet pour absorber une quantité, en calculant un prix moyen pondéré. |
| **Fill probability** | Probabilité estimée qu'un sell order soit rempli dans les 24h, basée sur le volume quotidien historique. |
| **Freshness** | Âge d'un prix retourné par l'AODP. Peut aller de quelques minutes à plusieurs jours. |
| **Marge nette** | (Revenu_net − Coût_net) / Coût_net × 100. Le "gain %" que voit le joueur. |
| **Silver par focus** | Métrique de rentabilité quand le focus est le facteur limitant. |

---

## 3. Contexte fonctionnel — règles du jeu à respecter

### 3.1. Cascade des tiers de raffinage

Pour raffiner du bois de tier N ≥ 4, la recette est :

```
1 unité de bois T{N} + 1 plank T{N-1} → 1 plank T{N}
```

Exemples :
- Raffiner T4 plank : 1 T4 wood + 1 T3 plank
- Raffiner T7 plank : 1 T7 wood + 1 T6 plank
- Raffiner T8 plank : 1 T8 wood + 1 T7 plank

Cette cascade est **critique** : ignorer le coût du T-1 plank surestime la marge de 30–50%.

### 3.2. Resource Return Rate à Fort Sterling

Fort Sterling donne :
- Bonus général de ville : **+18%**
- Bonus spécialité bois : **+40%**
- Total permanent hors focus : **+58%**

Bonus additifs empilables :
- Focus activé : **+59%**
- Daily bonus wood (si affiché en jeu ce jour-là) : **+10%** ou **+20%**

Formule du RRR effectif :

```
total_bonus = 18 + 40 + (59 si focus else 0) + (daily_bonus if applicable else 0)
RRR = 1 − 1 / (1 + total_bonus / 100)
```

Valeurs de référence à Fort Sterling (bois) :
- Sans focus, sans daily bonus : **~36.7%**
- Avec focus, sans daily bonus : **~53.9%**
- Avec focus + daily bonus 20% : **~58.6%**

Le RRR s'applique **aux deux inputs** de la recette (wood ET T-1 plank), pas seulement au wood.

### 3.3. Taxes de marché (joueur sans premium)

| Action | Tax |
|---|---|
| Instant sell (fill buy order) | **8%** sur le revenu |
| Placer un sell order — setup fee | **5%** à l'avance (non-remboursable) |
| Placer un sell order — sale tax | **8%** quand rempli |
| **Total sell order si rempli** | **~13%** |

Tous les revenus sont calculés **nets de tax**. Le setup fee du sell order est perdu même si l'ordre expire non-rempli.

### 3.4. Coût de raffinage à la station

```
coût_station = nutrition_per_unit(tier) × quantité × (silver_per_100_nutrition / 100)
```

Le nutrition cost par tier (à vérifier en jeu, valeurs approximatives) :

| Tier | Nutrition cost (par unité) |
|---|---|
| T4 | 8 |
| T5 | 16 |
| T6 | 32 |
| T7 | 64 |
| T8 | 128 |

⚠ **Action requise avant dev** : Duvalier doit confirmer ces valeurs en jeu ou depuis le wiki officiel Albion. Voir section 15.

### 3.5. Villes Royal du continent

| Ville | Notes |
|---|---|
| Fort Sterling | ✓ Ville de raffinage bois (imposée) |
| Lymhurst | Royal safe |
| Bridgewatch | Royal safe |
| Martlock | Royal safe |
| Thetford | Royal safe |
| Caerleon | ⚠ **Zone rouge autour** — route dangereuse à signaler |
| Brécilien | ✗ Exclue par défaut (transport cher, faible volume) |

### 3.6. Qualité des items

Pour le bois brut et les planks, la qualité est **toujours Normal**. Forcer `qualities=1` dans tous les appels AODP.

---

## 4. Périmètre par version

### 4.1. V1 — CLI Python (MVP)

**Doit inclure** :

- Client AODP fonctionnel sur le serveur Europe avec cache 15 min
- Sourcing bois tier N dans toutes les villes autorisées (Phase 1)
- Sourcing plank T{N-1} par achat au marché uniquement (Phase 2A, pas de récursion)
- Calcul RRR et output de raffinage (Phase 3)
- Deux scénarios de vente : instant sell + sell order (Phase 4)
- Synthèse combinatoire, filtrage, tri, top 5 (Phase 5)
- Trois modes d'input quantité : capital, quantité fixe, focus
- Interface CLI avec `argparse` ou `typer`
- Sortie tableau formaté (rich/tabulate) + JSON en option
- Flag "zone rouge" sur toute route impliquant Caerleon
- Checklist des pages marché à rafraîchir en jeu
- Alertes de fraîcheur (jaune > 3h, rouge > 6h par défaut, configurable)
- Tests unitaires sur les formules et l'order book walker

**Ne doit PAS inclure en V1** :

- Récursion cascade des tiers (production maison du T-1 plank)
- Split vente (instant partiel + sell order pour le reste)
- Scraping automatique des station fees
- Considération du transport risk (autre que le flag Caerleon)
- Frontend web
- Persistence (DB, historique de recherches)

### 4.2. V2 — Extensions

**Ajoute** :

- **Récursion cascade tiers avec memoization** : le moteur peut décider s'il vaut mieux acheter le T-1 plank ou le produire soi-même en descendant récursivement jusqu'au tier plancher (T2 ou T3 selon prix).
- **Split vente** : possibilité de vendre une partie du stock en instant sell et le reste en sell order, ville par ville, pour maximiser l'espérance de gain.
- **Scraping station fees** : tenter d'automatiser la récupération des fees depuis tools4albion.com ou source équivalente. Si impossible techniquement, ajouter un système de "profils de station" sauvegardés localement.
- **Sauvegarde locale des runs** : historique JSON des recherches précédentes pour comparaison.
- **Mode batch** : lancer plusieurs tiers en une commande (`--tiers 6,7,8`) et sortir un rapport comparatif.

### 4.3. V3 — Frontend web

**Ajoute** :

- Backend FastAPI qui expose la logique V2 sous forme d'API REST
- Frontend Next.js 15 + TypeScript + Tailwind CSS (stack Duvalier)
- Formulaire interactif avec tous les paramètres, radios pour le mode quantité
- Tableau de résultats trié, avec badges de fraîcheur colorés
- Vue détail d'une route (breakdown complet des coûts et revenus)
- Persistence utilisateur légère (localStorage) : préférences par défaut, dernière recherche
- Déploiement : frontend Vercel, backend Railway ou Render
- Optionnel : bouton "Explique-moi cette route" qui appelle l'API Anthropic (Claude) pour générer une analyse en prose

---

## 5. Architecture technique V1

### 5.1. Stack

- **Langage** : Python 3.11+
- **Gestionnaire de deps** : `uv` (recommandé) ou `pip` + `pyproject.toml`
- **HTTP client** : `httpx` (async natif, retry, timeouts propres)
- **CLI framework** : `typer` (basé sur click, syntaxe moderne)
- **Formatting sortie** : `rich` (tableaux colorés, checklists)
- **Cache** : `diskcache` ou implémentation maison JSON simple
- **Tests** : `pytest` + `pytest-httpx` pour mocker les appels AODP
- **Lint/format** : `ruff` (lint + format en un outil)

### 5.2. Structure de projet

```
albion-refine-optimizer/
├── README.md                    # Doc utilisateur (usage, install, exemples)
├── SPEC.md                      # Ce document (référence complète)
├── pyproject.toml               # Config projet + deps
├── uv.lock                      # Lock file
├── .env.example                 # Template de config env vars
├── .gitignore
├── src/
│   └── albion_refine/
│       ├── __init__.py
│       ├── cli.py               # Point d'entrée typer
│       ├── config.py            # Constantes: item IDs, cities, tax rates, tiers
│       ├── models.py            # Dataclasses: PriceQuote, Route, RefiningResult, etc.
│       ├── aodp_client.py       # HTTP client + cache 15 min
│       ├── refining.py          # Formules RRR, output, coûts station
│       ├── market.py            # Order book walker, scénarios A et B
│       ├── optimizer.py         # Orchestrateur des phases 1→5
│       ├── formatters.py        # Rendu tableaux rich + JSON export
│       └── data/
│           └── nutrition_costs.json
└── tests/
    ├── __init__.py
    ├── conftest.py              # Fixtures pytest partagées
    ├── test_refining.py         # Tests des formules RRR et output
    ├── test_market.py           # Tests order book walker + scénarios
    ├── test_optimizer.py        # Tests d'intégration avec AODP mocké
    └── fixtures/
        ├── aodp_prices_t7.json
        ├── aodp_history_t7.json
        └── aodp_stale_data.json
```

### 5.3. Séparation des responsabilités

- `aodp_client.py` : **uniquement I/O réseau**. Aucune logique métier. Retourne des `PriceQuote` typés.
- `refining.py` : **uniquement math pure**. Aucun I/O. Prend des inputs, sort des dataclasses.
- `market.py` : **logique de carnet d'ordres**. Prend des `PriceQuote`, sort des scénarios évalués.
- `optimizer.py` : **orchestration**. Compose les modules ci-dessus, applique filtres et tris.
- `cli.py` : **uniquement UX terminal**. Parse args, appelle optimizer, formatte via `formatters.py`.

Cette séparation permet : (a) tests unitaires faciles, (b) réutilisation directe en V3 (le backend FastAPI importe optimizer.py sans modification).

---

## 6. Constantes et données de référence

### 6.1. Item IDs AODP

Format : `T{tier}_WOOD` pour le bois brut, `T{tier}_PLANKS` pour les planks.

⚠ **À vérifier** : L'ID exact des planks pourrait être `T{tier}_PLANKS`, `T{tier}_WOOD_LEVEL0@0`, ou une autre variante. La source de vérité est le fichier `items.json` de l'AODP disponible sur https://www.albion-online-data.com/. **Claude Code doit** au démarrage télécharger et parser ce fichier pour confirmer les IDs corrects, et logger les IDs utilisés.

Constantes à hardcoder après vérification :

```python
WOOD_ITEM_IDS = {
    4: "T4_WOOD",
    5: "T5_WOOD",
    6: "T6_WOOD",
    7: "T7_WOOD",
    8: "T8_WOOD",
}

PLANK_ITEM_IDS = {
    4: "T4_PLANKS",   # à confirmer
    5: "T5_PLANKS",
    6: "T6_PLANKS",
    7: "T7_PLANKS",
    8: "T8_PLANKS",
}
```

### 6.2. Cities

```python
CITIES = {
    "Caerleon":     {"safe": False, "warning": "zone rouge autour"},
    "Fort Sterling": {"safe": True,  "wood_refining_bonus": True},
    "Lymhurst":     {"safe": True},
    "Bridgewatch":  {"safe": True},
    "Martlock":     {"safe": True},
    "Thetford":     {"safe": True},
    "Brecilien":    {"safe": True, "excluded_default": True},
}
```

Les IDs de villes pour l'AODP sont les noms exacts ci-dessus (en anglais, sans accent).

### 6.3. Endpoints AODP

Base URL Europe : `https://europe.albion-online-data.com`

Endpoints utilisés :

| Endpoint | Usage |
|---|---|
| `/api/v2/stats/prices/{items}.json?locations={locs}&qualities=1` | Prix courants min sell / max buy |
| `/api/v2/stats/history/{items}.json?locations={locs}&time-scale=24&qualities=1` | Historique volume 24h |
| `/api/v2/stats/charts/{items}.json?locations={locs}&time-scale=24&qualities=1` | Charts si besoin pour V2/V3 |

Les items multiples se passent en CSV : `T7_WOOD,T7_PLANKS,T6_PLANKS`.
Idem pour les locations : `Caerleon,Martlock,Thetford`.

### 6.4. Paramètres par défaut (config.py)

```python
DEFAULTS = {
    "seuil_marge_min_pct": 30,
    "seuil_fill_probability_pct": 20,
    "freshness_warning_hours": 3,    # jaune
    "freshness_critical_hours": 6,   # rouge, exclu par défaut
    "cache_ttl_minutes": 15,
    "sell_order_undercut_pct": 1,    # sous-cote 1% pour scénario B
    "premium": False,
    "server": "europe",
    "refining_city": "Fort Sterling",
    "excluded_sell_cities": ["Brecilien"],
    "excluded_buy_cities": ["Brecilien"],
}
```

### 6.5. Tax rates (no premium)

```python
TAX_INSTANT_SELL = 0.08
TAX_SELL_ORDER_SETUP = 0.05
TAX_SELL_ORDER_SALE = 0.08
TAX_SELL_ORDER_TOTAL = TAX_SELL_ORDER_SETUP + TAX_SELL_ORDER_SALE  # 0.13
```

---

## 7. Formules mathématiques (référence)

### 7.1. RRR

```
total_bonus_pct = 58 + (59 if focus else 0) + (daily_bonus_pct if daily_bonus else 0)
RRR = 1 - 1 / (1 + total_bonus_pct / 100)
```

Exemple avec focus + daily 20% :
```
total = 58 + 59 + 20 = 137
RRR = 1 - 1 / 2.37 = 0.5781 = 57.8%
```

### 7.2. Output d'un raffinage

Pour raffiner `Q` unités de bois T{N} avec `Q` unités de plank T{N-1} :

```
planks_produits         = Q         # 1 plank par unité, retour vient du RRR
wood_TN_retournés       = Q × RRR
plank_TN_moins_1_retour = Q × RRR
```

### 7.3. Order book walk (fill d'une quantité Q)

Pour un carnet ordonné (ascendant pour achat, descendant pour vente) de tuples `[(prix_i, qté_i), ...]` :

```python
def walk_book(book, quantity_needed):
    total_cost = 0
    total_absorbed = 0
    for prix, qte_disponible in book:
        prendre = min(qte_disponible, quantity_needed - total_absorbed)
        total_cost += prendre * prix
        total_absorbed += prendre
        if total_absorbed >= quantity_needed:
            break
    if total_absorbed < quantity_needed:
        return None  # stack insuffisant
    prix_moyen = total_cost / total_absorbed
    return {"prix_moyen": prix_moyen, "total_cost": total_cost}
```

### 7.4. Coût d'une route

```
coût_bois          = walk_book(sell_orders_wood_ville_A, Q) → total_cost
coût_plank_T-1     = walk_book(sell_orders_plank_ville_B, Q) → total_cost
coût_station       = nutrition_cost(N) × (1 + fee_owner_pct/100) × Q
coût_focus_silver  = focus_utilisé × prix_silver_par_focus (paramètre user)

coût_total = coût_bois + coût_plank_T-1 + coût_station + coût_focus_silver
```

### 7.5. Récupération secondaire

Les retours RRR sont crédités contre le coût s'ils sont revendables localement (à Fort Sterling en instant sell) :

```
récup_wood     = wood_retournés × prix_max_buy_wood_FS × (1 - TAX_INSTANT_SELL)
récup_plank_-1 = plank_retour × prix_max_buy_plank_TN-1_FS × (1 - TAX_INSTANT_SELL)
récup_totale   = récup_wood + récup_plank_-1

coût_net = coût_total − récup_totale
```

Si le buy order n'existe pas ou est absurdement bas à FS, la récup peut être ignorée (option) ou le stock cumulé pour un usage futur (noté dans le rapport).

### 7.6. Revenu scénario A (instant sell)

```
walk_result_buy = walk_book(buy_orders_ville_vente, planks_produits)
revenu_brut     = walk_result_buy.total_cost
revenu_net_A    = revenu_brut × (1 - TAX_INSTANT_SELL)
```

Si `walk_result_buy` est None → écarter cette combinaison (stack insuffisant).

### 7.7. Revenu scénario B (sell order)

```
prix_listing   = min_sell_order_actuel × (1 - undercut_pct/100)
revenu_brut    = prix_listing × planks_produits
revenu_net_B_if_filled = revenu_brut × (1 - TAX_SELL_ORDER_TOTAL)

volume_24h    = history_endpoint(ville_vente, T{N}_PLANKS).avg_daily_volume
fill_ratio    = volume_24h / planks_produits
fill_proba    = min(1.0, fill_ratio)   # approximation simple, raffinable en V2

expected_revenue_B = revenu_net_B_if_filled × fill_proba
```

Si `fill_proba < seuil_fill_probability_pct/100` → écarter.

### 7.8. Marge finale

```
revenu_effectif = max(revenu_net_A, expected_revenue_B)   # si les deux existent
marge_pct       = (revenu_effectif − coût_net) / coût_net × 100

silver_par_focus = (revenu_effectif − coût_net) / focus_used   # si focus > 0
```

### 7.9. Filtrage

Écarter une route si :
- `marge_pct < seuil_marge_min_pct` (default 30%)
- toutes les données prix ont un âge > `freshness_critical_hours` (default 6h)
- scénario A retenu mais stack insuffisant
- scénario B retenu mais `fill_proba < seuil_fill_probability_pct`

### 7.10. Tri

- Si `focus=True` : tri primaire par `silver_par_focus` DESC, secondaire par `marge_pct` DESC
- Si `focus=False` : tri primaire par `marge_pct` DESC, secondaire par `revenu_effectif − coût_net` DESC

Retourner les **top 5** routes.

---

## 8. Spécification par phase (V1)

### 8.1. Phase 1 — Sourcing bois tier N

**Input** : `tier N`, `villes_autorisées_achat`, `quantité_cible`

**Traitement** :

1. Requête AODP `/api/v2/stats/prices/T{N}_WOOD.json?locations=...&qualities=1`
2. Pour chaque ville dans la réponse :
   - Extraire `sell_price_min`, `sell_price_min_date`
   - Extraire buy orders empilés (l'endpoint retourne un seul niveau, donc walk du carnet limité en V1 — voir remarque ci-dessous)
   - Calculer l'âge = `now() - sell_price_min_date`
   - Flag stale si âge > `freshness_critical_hours`
3. Pour chaque ville non stale :
   - Si stack ≥ Q → coût_bois_ville = Q × sell_price_min
   - Si stack < Q → en V1, refuser cette ville (walk multi-niveaux requiert un endpoint non exposé par AODP en v2 sur un seul call ; approximer en V2 via l'historique)

**Output** : `dict[ville] → {coût_bois: int, âge_data: timedelta, prix_moyen: float}`

⚠ **Note importante sur la profondeur du carnet** : l'endpoint `/prices/` de l'AODP retourne un seul prix par ville (le meilleur). Pour un vrai order book walk multi-niveaux, il faut soit sniffer soi-même (interdit), soit se contenter du prix top + supposer volume disponible via l'endpoint `/history/`. **V1 : utiliser uniquement le top price, et si volume 24h < Q, flag "profondeur incertaine".**

### 8.2. Phase 2 — Sourcing plank T{N-1}

**V1** : identique à Phase 1 mais pour l'item `T{N-1}_PLANKS`. Une seule branche : achat marché.

**V2** : ajouter branche récursive (voir section 13).

### 8.3. Phase 3 — Raffinage à Fort Sterling

**Input** : `Q`, `tier N`, `focus`, `daily_bonus_pct`, `fee_owner_pct`

**Traitement** :
1. Calculer `RRR` selon formule 7.1
2. Calculer outputs selon formule 7.2
3. Calculer `coût_station` selon formule 3.4

**Output** :
```python
RefiningResult(
    planks_produits: int,
    wood_retour: float,
    plank_moins_1_retour: float,
    coût_station: int,
    rrr_effectif: float,
    focus_utilisé: int  # calculable, ~1 par action, à vérifier
)
```

### 8.4. Phase 4 — Évaluation ventes

Pour chaque `ville_vente ∈ villes_autorisées_vente` :

1. Requête AODP prix + history pour `T{N}_PLANKS` dans cette ville
2. Calculer scénario A (formule 7.6)
3. Calculer scénario B (formule 7.7)
4. Retenir le max des deux, ou marker la ville "à split" si les deux passent (V2)

### 8.5. Phase 5 — Synthèse

1. Générer le produit cartésien `villes_achat_wood × villes_achat_plank × villes_vente`
2. Pour chaque combinaison, appeler Phase 3 puis 4, calculer coût_net et marge_pct
3. Appliquer filtres (7.9)
4. Trier (7.10)
5. Retourner top 5 avec toutes les métadonnées
6. Générer la checklist des pages marché à rafraîchir (items × villes qui apparaissent dans les 5 routes retenues, ordre par ordre d'apparition)

---

## 9. Interface CLI (V1)

### 9.1. Commande principale

```bash
albion-refine optimize \
  --tier 7 \
  --mode focus \
  --focus-available 10000 \
  --daily-bonus none \
  --station-fee 18 \
  --seuil-marge 30 \
  --exclude-vente Brecilien \
  --format table
```

### 9.2. Modes quantité (mutuellement exclusifs)

- `--mode capital --capital 500000` → optimize pour un budget silver donné
- `--mode fixed --quantite 128` → optimize pour une quantité de bois précise
- `--mode focus --focus-available 10000` → optimize pour un budget focus donné

### 9.3. Sortie table (rich)

```
┌─ TOP 1 — Marge nette : 68.7% ─────────────────────────────────┐
│ TIER 7 PLANKS — 128 unités                                    │
├───────────────────────────────────────────────────────────────┤
│ ACHAT BOIS T7     Martlock       245 s × 128    = 31 360 s   │
│                   fraîcheur : 12 min ✓                        │
│ ACHAT PLANK T6    Fort Sterling  890 s × 128    = 113 920 s  │
│                   fraîcheur : 45 min ✓                        │
│ RAFFINAGE FS      fee 18% + nutrition           = 2 100 s     │
│ FOCUS             10 000 focus                                │
│                                                               │
│ RRR effectif : 54% (focus ON, daily bonus OFF)                │
│ Output       : 128 planks + 69 wood + 69 T6 plank retour      │
│                                                               │
│ VENTE  ► INSTANT SELL @ Caerleon                              │
│         top buy order 1420 s, stack 340u ✓                    │
│         revenu net (8% tax) : 148 019 s                       │
│         ⚠ ROUTE PAR ZONE ROUGE                                │
│                                                               │
│ COÛT NET         : 143 380 s (après récup wood + plank -1)    │
│ REVENU NET       : 242 019 s                                  │
│ BÉNÉFICE         : +98 639 s                                  │
│ SILVER / FOCUS   : 9.86 s                                     │
└───────────────────────────────────────────────────────────────┘

... TOP 2, TOP 3, TOP 4, TOP 5 ...

━━━ CHECK-LIST FRAÎCHEUR — Pages marché à ouvrir en jeu ━━━
[ ] Caerleon : T7_PLANKS (dernière data 4h ⚠)
[ ] Bridgewatch : T7_PLANKS (dernière data 7h ✗)
[ ] Thetford : T7_WOOD (dernière data 3h)
```

### 9.4. Sortie JSON

```bash
albion-refine optimize --tier 7 --mode focus --focus-available 10000 --format json
```

Structure JSON complète, exploitable par un futur frontend :

```json
{
  "run_metadata": {
    "timestamp": "2026-07-19T15:20:00Z",
    "tier": 7,
    "mode": "focus",
    "params": {...}
  },
  "routes": [
    {
      "rank": 1,
      "marge_pct": 68.7,
      "achat_wood": {...},
      "achat_plank": {...},
      "raffinage": {...},
      "vente": {...},
      "warnings": ["ROUTE_ZONE_ROUGE"]
    },
    ...
  ],
  "refresh_checklist": [...]
}
```

### 9.5. Commandes utilitaires

```bash
albion-refine check-item-ids       # vérifie les IDs contre items.json AODP
albion-refine test-api             # ping AODP + check status
albion-refine clear-cache          # vide le cache local
albion-refine dump-nutrition       # affiche la table nutrition_cost
```

---

## 10. Cache et fraîcheur des données

### 10.1. Cache local

- Chaque appel AODP est cachable par `(endpoint, item_ids, locations)`.
- TTL par défaut : **15 minutes**.
- Path du cache : `~/.cache/albion-refine/` (respecter XDG sur Linux, `%LOCALAPPDATA%` sur Windows).
- Commande `--no-cache` pour bypasser (utile en debug ou pour forcer refresh).
- Commande `clear-cache` pour vider.

### 10.2. Fraîcheur des données AODP

Les prix retournés par AODP ont un timestamp. Ce timestamp est **différent** de la fraîcheur du cache local :

- Cache local : quand la réponse HTTP a été fetchée par notre app
- Timestamp AODP : quand un joueur en jeu a vu ce prix et l'a uploadé via le client AODP

C'est le **timestamp AODP** qui compte pour la freshness métier. Le cache local est juste une optimisation de bande passante.

Codes de fraîcheur affichés dans les rapports :

- ✓ vert : < `freshness_warning_hours` (default 3h)
- ⚠ jaune : entre warning et critical
- ✗ rouge : > `freshness_critical_hours` (default 6h) → exclu par défaut

---

## 11. Gestion des erreurs

### 11.1. Erreurs réseau

- Timeout AODP : 10s par défaut, 3 retry avec backoff exponentiel
- Si AODP down : afficher message clair "AODP indisponible, réessayer plus tard" et sortir en code 2
- Si un item retourne 404 : logger et continuer avec les autres

### 11.2. Erreurs de données

- Prix à 0 (valeur AODP quand pas de data) : traiter comme "pas de prix disponible", exclure de la combinaison
- Timestamp manquant : traiter comme stale critique
- Volume 24h manquant : `fill_proba = 0`, écarte scénario B

### 11.3. Aucune route ne passe le seuil

Afficher un rapport détaillé du **meilleur candidat écarté** avec la raison exacte, plutôt qu'un message vide. Exemple :

```
Aucune route ne passe le seuil de 30%.
Meilleure route trouvée :
  Achat Martlock → FS → Vente Caerleon = marge 22.4%
  Écartée car : marge < seuil.
Suggestions :
  - Baisser --seuil-marge à 20 pour voir cette route
  - Attendre un rafraîchissement des prix (data > 4h sur T7_PLANKS Caerleon)
  - Essayer un autre tier
```

---

## 12. Tests

### 12.1. Coverage cible

- `refining.py` : 100% (math pure, facile à tester)
- `market.py` : 90%+
- `optimizer.py` : 80%+ (integration tests avec fixtures)
- `aodp_client.py` : 70%+ (mock HTTP)

### 12.2. Cas de tests obligatoires

**refining.py** :
- RRR sans focus sans daily : ~36.7%
- RRR avec focus sans daily : ~53.9%
- RRR avec focus + daily 20% : ~57.8%
- Coût station T4, T7, T8 avec fee 0%, 20%, 50%
- Outputs cohérents (planks_produits = Q, wood_retour = Q × RRR)

**market.py** :
- Order book walk exact avec stack suffisant
- Walk avec stack insuffisant → None
- Walk sur book vide → None
- Tax instant sell appliquée correctement
- Tax sell order (5% + 8%) appliquée correctement
- Fill probability capée à 100%

**optimizer.py** :
- Un run complet avec fixtures JSON → produit exactement le top 5 attendu
- Filtre seuil marge respecté
- Filtre freshness respecté
- Tri par silver/focus vs marge selon mode

### 12.3. Fixtures

Snapshots réels de l'AODP capturés au moment du dev, stockés en JSON dans `tests/fixtures/`. Permet de tester sans dépendre de la disponibilité de l'API.

---

## 13. V2 — Détails additions

### 13.1. Récursion cascade tiers (Phase 2B)

Ajouter dans `optimizer.py` une fonction récursive :

```python
def get_plank_cost(tier: int, quantity: int, ...) -> PlankSourcing:
    if tier == 2:  # ou T3, tier plancher à confirmer
        return market_only(tier, quantity, ...)

    market_price = market_only(tier, quantity, ...)
    produce_price = simulate_full_route(tier, quantity, ...)  # récursif

    return min(market_price, produce_price)
```

Utiliser `@lru_cache` ou memoization manuelle pour éviter le recalcul (une même combinaison peut apparaître plusieurs fois dans l'arbre).

### 13.2. Split vente

Ajouter dans `market.py` :

```python
def split_sell_strategy(planks_produits, buy_orders_ville, sell_order_price, volume_24h):
    """
    Calcule le split optimal entre instant sell (fill buy orders top-down)
    et sell order pour le reliquat.
    """
    ...
```

### 13.3. Scraping station fees

Deux implémentations tentables :
- Scraping HTML de tools4albion.com avec `httpx` + `selectolax` (rapide)
- API AODP alternative si elle existe (à investiguer)

Fallback : "profils de station" locaux — l'utilisateur sauvegarde `--save-station FS_lumbermill_18pct` et peut réutiliser `--station-profile FS_lumbermill_18pct`.

---

## 14. V3 — Détails frontend

Sera spécifié séparément dans un `SPEC_V3.md` une fois V2 stable. Placeholder :

- Backend : FastAPI qui expose `POST /optimize` avec le même schéma que le CLI JSON output
- Frontend : Next.js 15 App Router, TS strict, Tailwind, composants shadcn/ui
- Auth : none en V3 initial (outil personnel), potentiellement Clerk plus tard
- Déploiement : Vercel + Railway
- Domaine : à choisir (albion-refine.dev par exemple)

---

## 15. Ce que Duvalier doit fournir à Claude Code

### 15.1. Informations à confirmer en jeu

1. **Nutrition cost par tier** : ouvrir la station de raffinage à FS, hover chaque tier, noter le nutrition cost affiché. Confirmer ou corriger la table de la section 3.4.
2. **Fee actuel de la station FS** (juste pour tester, sera un input CLI).
3. **Niveau de spécialisation Plankmaster par tier** dans le Destiny Board (screenshot des tiers T4 à T8 sous Toolmaker → Planks). Utile pour V2 quand on calculera précisément le focus cost par action.
4. **Focus disponible actuel** (juste pour tester le mode focus).
5. **Cost-per-focus estimation** : combien de silver coûte 1 point de focus en équivalent (souvent estimé à 0 en gameplay solo, ou à un coût d'opportunité selon le joueur).

### 15.2. Accès à fournir à Claude Code

- Le repo GitHub cible (créer un nouveau repo `albion-refine-optimizer` sous `Drakenarl`)
- Ce `SPEC.md` (unique instruction principale)
- Accès en écriture pour push les commits
- Idéalement Claude Code tourne dans Desktop Commander avec accès à `C:\Users\duval\projets\` ou équivalent

### 15.3. Instructions à donner à Claude Code (prompt d'ouverture)

Exemple à copier-coller :

> Bonjour Claude Code. Voici le cahier des charges complet du projet **albion-refine-optimizer** dans `SPEC.md`. Ta mission : implémenter **V1 uniquement** conformément à la spec. Ne commence PAS V2 ou V3. Ordre de travail :
>
> 1. Lis intégralement le SPEC.md
> 2. Crée la structure de projet section 5.2
> 3. Vérifie les item IDs contre `items.json` de l'AODP (section 6.1)
> 4. Implémente dans l'ordre : `config.py`, `models.py`, `aodp_client.py`, `refining.py`, `market.py`, `optimizer.py`, `formatters.py`, `cli.py`
> 5. Écris les tests au fur et à mesure (chaque module a ses tests avant de passer au suivant)
> 6. Rédige le `README.md` utilisateur avec exemples concrets
> 7. Commit atomique par module, messages en français
> 8. Push sur le repo à la fin
>
> Contraintes : Python 3.11+, uv pour les deps, ruff pour le format, typer pour la CLI, rich pour l'affichage, httpx pour HTTP, pytest pour les tests. Zéro dépendance sur des libs propriétaires ou APIs payantes.
>
> Si un point du SPEC est ambigu ou impossible techniquement, arrête-toi et pose la question dans un fichier `QUESTIONS.md` en attendant réponse. Ne devine pas.

---

## 16. Ce que Claude (chat) peut préparer en amont pour alléger Claude Code

Actions déjà réalisées ou réalisables **par Claude en conversation** (pas Claude Code) :

- ✓ Ce document `SPEC.md` complet
- ✓ Formules mathématiques validées et documentées
- ✓ Structure de projet définie
- ✓ Endpoints AODP identifiés et validés (Europe base URL confirmé)
- ✓ Liste des villes + flags de zone rouge
- ✓ Valeurs de RRR calculées et cross-vérifiées avec Albion Codex et wiki

Actions **restantes que Claude peut faire avant le lancement de Claude Code** (demander à Duvalier) :

- Générer un fichier `items.json` extract limité aux items bois/planks T4-T8 pour éviter à Claude Code de downloader le fichier complet AODP au premier lancement
- Générer 2-3 fixtures JSON réalistes (snapshot AODP) pour bootstrap les tests
- Rédiger le prompt d'ouverture Claude Code (section 15.3) déjà pré-formaté
- Préparer un `README.md` template avec sections vides à remplir par Claude Code
- Recommander une charte de commits git conventionnels (`feat:`, `fix:`, `docs:`, etc.)
- Générer un `.gitignore` Python complet
- Générer un `pyproject.toml` template avec toutes les deps déjà déclarées

Duvalier n'a qu'à demander : *"Claude, prépare-moi les X éléments ci-dessus"* et je génère tout avant que Claude Code démarre.

---

## 17. Roadmap de développement recommandée

**Semaine 1 — V1 CLI**
- J1-J2 : structure projet, config, models, aodp_client + tests
- J3 : refining + tests
- J4 : market + tests
- J5 : optimizer + tests d'intégration
- J6 : formatters + cli
- J7 : README, polish, run réel avec vraies data, ajustements

**Semaine 2 — V1 → V2**
- Ajout récursion cascade
- Ajout split vente
- Ajout scraping fees (best effort)
- Tests étendus

**Semaine 3+ — V3 web**
- Backend FastAPI (wrapping direct de V2)
- Frontend Next.js
- Déploiement

---

## 18. Références externes

- Albion Online Data Project : https://www.albion-online-data.com/
- Wiki refining : https://wiki.albiononline.com/wiki/Refining
- Wiki Resource Return Rate : https://wiki.albiononline.com/wiki/Resource_return_rate
- Wiki Local Production Bonus : https://wiki.albiononline.com/wiki/Local_Production_Bonus
- Albion Codex refining guide : https://www.albioncodex.com/guides/albion-online-refining-guide
- Albion Marketplace refining guide : https://www.albionmarket.app/guides/refining-guide

---

**Fin du cahier des charges V1.0**
