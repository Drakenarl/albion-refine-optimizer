# Albion Refine Optimizer

> Outil d'optimisation économique pour Albion Online. Trouve les meilleures routes de raffinage de bois à Fort Sterling en interrogeant l'API publique de l'Albion Online Data Project.

[![Python](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Code style: ruff](https://img.shields.io/badge/code%20style-ruff-000000.svg)](https://github.com/astral-sh/ruff)

---

## Fonctionnalités (V1)

- Analyse combinatoire complète : bois × plank T-1 × ville de vente × scénario de vente
- Recettes de raffinage réelles (un plank T7 consomme **5 bois T7** + 1 plank T6)
- Trois modes d'input : capital silver disponible, quantité fixe, ou budget focus
- Les **deux** scénarios de vente affichés côte à côte pour chaque route : instant sell (safe, immédiat) vs sell order (potentiel, conditionnel)
- Fill probability réaliste (jamais 100%) et revenus escomptés selon l'âge de la donnée
- Récupération RRR valorisée au carnet d'achat réel, absorption partielle signalée
- Calcul du RRR effectif à Fort Sterling en tenant compte du focus, daily bonus, et récupération sur les deux inputs
- Application correcte des taxes joueur sans premium (8% instant, 13% sell order total)
- Filtrage par seuil de marge (30% par défaut) et fraîcheur des données (< 6h par défaut)
- Alerte "zone rouge" sur toute route impliquant Caerleon
- Checklist des pages marché à rafraîchir en jeu pour améliorer la précision
- Cache local 15 min pour économiser les appels AODP

---

## Installation

### Prérequis

- Python 3.11 ou supérieur
- [uv](https://docs.astral.sh/uv/) (recommandé) ou pip

### Avec uv (recommandé)

```bash
git clone https://github.com/Drakenarl/albion-refine-optimizer.git
cd albion-refine-optimizer
uv sync
```

### Avec pip

```bash
git clone https://github.com/Drakenarl/albion-refine-optimizer.git
cd albion-refine-optimizer
python -m venv .venv
source .venv/bin/activate  # Linux/macOS
# .venv\Scripts\activate    # Windows
pip install -e ".[dev]"
```

---

## Utilisation rapide

### Optimiser un raffinage T7 avec focus

```bash
albion-refine optimize \
  --tier 7 \
  --mode focus \
  --focus-available 10000 \
  --station-rate 50
```

### Optimiser sur un budget capital

```bash
albion-refine optimize \
  --tier 6 \
  --mode capital \
  --capital 500000 \
  --station-rate 50
```

### Optimiser une quantité fixe avec daily bonus

```bash
albion-refine optimize \
  --tier 8 \
  --mode fixed \
  --quantite 64 \
  --daily-bonus 20 \
  --station-rate 50
```

### Sortie JSON pour intégration

```bash
albion-refine optimize --tier 7 --mode focus --focus-available 10000 --format json > result.json
```


### Exemple de sortie

```
┌────── TOP 1 — Marge nette (safe) : 42.1% — potentiel jusqu'à 68.4% ─────────┐
│ ACHAT BOIS T7   Lymhurst       3045 s × 640 = 1 948 800 s                   │
│                  fraîcheur : 3.7h ⚠                                         │
│ ACHAT PLANK T6  Lymhurst       3200 s × 128 = 409 600 s                     │
│                  fraîcheur : 2.1h ✓                                         │
│ RAFFINAGE FS     coût station = 907 s                                       │
│ RRR effectif : 53.9% | Output : 128 planks + 345 bois + 69 plank T-1 retour │
│                                                                             │
│ VENTE @ Martlock                                                            │
│ ► INSTANT SELL (safe)                                                       │
│       top buy 10624 s × 128 unités                                          │
│       revenu net brut  : 1 251 082 s                                        │
│       × confiance      : 0.95 (data 1.4h ✓)                                 │
│       revenu pondéré   : 1 188 528 s                                        │
│       marge pondérée   : 42.1%                                              │
│ ► SELL ORDER (attente)                                                      │
│       undercut à 13258 s | fill proba 72%                                   │
│       revenu si rempli : 1 476 419 s                                        │
│       × confiance      : 0.95 (data 45 min ✓)                               │
│       espérance pondérée : 1 013 428 s (0.72 × 1 402 598 s)                 │
│       marge espérée    : 21.2%                                              │
│       gain vs instant  : -175 100 s (-14.7%)                                │
│                                                                             │
│ RÉCUP (retours)  : 987 120 s (345/345 bois absorbés, 69/69 planks absorbés) │
│ COÛT NET (safe)  : 836 402 s                                                │
│ BÉNÉFICE SAFE    : +352 126 s                                               │
│ POTENTIEL SO     : +177 026 s (espérance sell order)                        │
│ RECOMMANDATION   : INSTANT SELL (gain marginal du sell order insuffisant)   │
└───────────────────────── TIER 7 PLANKS — 128 unités ────────────────────────┘

━━━ CHECK-LIST FRAÎCHEUR — Pages marché à ouvrir en jeu ━━━
[ ] Lymhurst : T7_WOOD (data 3.7h ⚠) — critique, le prix du bois structure le coût
[ ] Lymhurst : T6_PLANKS (data 2.1h ✓) — critique, prix du plank T-1
[ ] Martlock : T7_PLANKS (data 1.4h ✓) — vente principale

━━━ CONSEILS TRADING ━━━
  - Ouvrir en jeu les pages listées ci-dessus pour rafraîchir la data
  - Relancer l'outil 30-60 secondes après pour obtenir les vrais prix
  - Confirmer le top buy order en jeu avant de committer sur instant sell
  - Ne jamais placer un sell order sans vérifier la profondeur du carnet
```

> Les chiffres ci-dessus sont illustratifs. Sur un marché réel, une route peut très bien ressortir **négative** : c'est le comportement attendu depuis la V1.1, la V1.0 surestimait massivement les marges.

---

## Options CLI complètes

### `albion-refine optimize`

| Option | Type | Défaut | Description |
|---|---|---|---|
| `--tier` | int | *(requis)* | Tier du plank à produire (4-8). |
| `--station-rate` | float | *(requis)* | Rate de la station en silver / 100 nutrition. |
| `--mode` | `capital` \| `fixed` \| `focus` | `fixed` | Mode de dimensionnement de la quantité. |
| `--capital` | float | — | Budget silver (mode `capital`). |
| `--quantite` | int | — | Quantité de bois (mode `fixed`). |
| `--focus-available` | float | — | Budget focus disponible (mode `focus`). |
| `--focus` / `--no-focus` | flag | `--no-focus` | Active le focus (+59% RRR). Toujours actif en mode `focus`. |
| `--daily-bonus` | `none` \| `10` \| `20` | `none` | Bonus quotidien de production. |
| `--cost-per-focus` | float | `0.0` | Coût silver d'un point de focus (coût d'opportunité). |
| `--seuil-marge` | float | `30` | Marge nette minimale en % pour retenir une route. |
| `--exclude-vente` | str | — | Ville à exclure de la vente (répétable). |
| `--exclude-achat` | str | — | Ville à exclure de l'achat (répétable). |
| `--format` | `table` \| `json` | `table` | Format de sortie. |
| `--no-cache` | flag | off | Ignore le cache local et force le refresh AODP. |
| `--server` | str | `europe` | Serveur AODP (`europe`, `west`, `east`). |

> **Note** : le `--station-rate` est le taux affiché dans l'UI de la station en jeu, exprimé en silver par 100 nutrition (format depuis le patch v19.000.1). Il est obligatoire car il n'a pas de valeur par défaut sensée.

### Commandes utilitaires

```bash
albion-refine check-item-ids     # vérifie les item IDs contre items.json
albion-refine test-api           # ping l'AODP et vérifie qu'un prix revient
albion-refine clear-cache        # vide le cache local
albion-refine dump-nutrition     # affiche la table nutrition par tier
```

---

## Concepts métier

### Cascade des tiers et recettes

Pour raffiner un plank de tier N, il faut à la fois du bois brut T{N} ET un plank T{N-1}. Les quantités ne sont pas de 1 pour 1 — c'est l'erreur qui faussait la V1.0 :

| Plank produit | Bois T{N} | Plank T{N-1} |
|---|---|---|
| T2 | 1 | 0 |
| T3 | 2 | 1 |
| T4 | 2 | 1 |
| T5 | 3 | 1 |
| T6 | 4 | 1 |
| T7 | 5 | 1 |
| T8 | 5 | 1 |

Le RRR s'applique à **chaque unité d'input consommée** : raffiner 100 planks T7 consomme 500 bois et retourne `500 × RRR` bois.

### Double scénario de vente

Chaque route affiche les deux options, sans en masquer aucune :

- **Scénario A — instant sell** : on remplit les buy orders existants. Revenu immédiat et certain. C'est **cette marge** qui donne le titre de la route, qui pilote le tri du top 5 et qui est comparée à `--seuil-marge`.
- **Scénario B — sell order** : on place un ordre sous-coté. Revenu supérieur mais conditionnel au remplissage, donc pondéré par une fill probability. Affiché en potentiel, jamais en marge principale.

Une ligne `RECOMMANDATION` tranche entre les deux : le sell order n'est conseillé que si son gain marginal dépasse 10% de l'espérance de l'instant sell.

### Fill probability

La probabilité qu'un sell order parte sous 24h combine trois facteurs : le ratio volume/quantité (plafonné à 0.85), la position estimée dans le carnet et l'agressivité de l'undercut. Elle ne vaut **jamais 100%**.

### Confiance fraîcheur

Le revenu de vente attendu est escompté selon l'âge de la donnée de prix : `< 30 min` → 1.00, `< 2h` → 0.95, `< 4h` → 0.85, `< 6h` → 0.70, au-delà → 0.50. Les coûts d'achat ne sont pas pondérés (ils seront confirmés en jeu avant l'achat), mais un prix d'achat de plus de 6h exclut la ville du sourcing.

### Resource Return Rate (RRR) à Fort Sterling

- Bonus de base ville : **+18%**
- Spécialité bois : **+40%**
- Focus (si utilisé) : **+59%**
- Daily bonus (si présent) : **+10% ou +20%**

Formule : `RRR = 1 - 1 / (1 + total_bonus / 100)`

Sans focus : ~37% des matières premières reviennent. Avec focus : ~54%.

### Taxes de marché (joueur sans premium)

- **Instant sell** : 8% de tax
- **Sell order** : 5% setup fee (non-remboursable) + 8% sale tax = **13% total si rempli**

L'outil calcule les deux scénarios pour chaque ville de vente et retient le plus rentable.

### Fraîcheur des données

L'API AODP est alimentée par les joueurs qui font tourner le client AODP en jeu. Un prix a un timestamp indiquant quand un joueur l'a vu pour la dernière fois. L'outil affiche :

- ✓ **vert** : < 3h
- ⚠ **jaune** : entre 3h et 6h
- ✗ **rouge** : > 6h (exclu à l'achat, fortement escompté à la vente)

Pour améliorer la fraîcheur des données sur les items qui t'intéressent, installe le [client AODP](https://www.albion-online-data.com/) et va ouvrir les pages marché correspondantes en jeu.

---

## Architecture

### Arbre du projet

```
albion-refine-optimizer/
├── src/albion_refine/
│   ├── config.py         # Constantes : item IDs, villes, taxes, nutrition, endpoints
│   ├── models.py         # Modèles Pydantic : PriceQuote, Route, RefiningResult, …
│   ├── aodp_client.py    # Client HTTP async httpx + cache diskcache 15 min (I/O pur)
│   ├── refining.py       # Formules RRR, outputs, coût station (math pure)
│   ├── market.py         # Order book walker, taxes, scénarios de vente A/B
│   ├── optimizer.py      # Orchestrateur des phases 1→5, filtrage, tri, top 5
│   ├── formatters.py     # Rendu rich (panneaux + check-list) et export JSON
│   ├── cli.py            # Entrée typer (optimize + commandes utilitaires)
│   └── data/items.json   # Extract items bois/planks embarqué
└── tests/                # pytest + pytest-httpx, fixtures AODP réalistes
```

### Séparation des responsabilités

Chaque module a une seule responsabilité, ce qui rend la logique métier testable
sans réseau et réutilisable telle quelle par un futur backend (V3) :

- `aodp_client` fait **uniquement** de l'I/O réseau et du cache ;
- `refining` et `market` sont de la **logique pure** (aucun I/O) ;
- `optimizer` **compose** ces modules et applique filtres/tris ;
- `cli`/`formatters` ne font que de l'**UX terminal**.

### Flux d'une optimisation

```
CLI (typer)
   │  parse les options → OptimizerParams
   ▼
run_optimization ──► AodpClient ──► endpoints AODP /prices + /history (cache 15 min)
   │                                    │
   │                              PriceQuote, VolumeData
   ▼
optimize (pur)
   1. Sourcing bois T{N}         (par ville, filtre fraîcheur)
   2. Sourcing plank T{N-1}      (achat marché)
   3. Raffinage à Fort Sterling  (RRR, outputs, coût station)
   4. Évaluation ventes A/B      (instant sell vs sell order, taxes, fill proba)
   5. Synthèse combinatoire      (récup RRR, marge nette, filtres, tri, top 5)
   ▼
OptimizationResult ──► formatters ──► tableau rich ou JSON
```


---

## Développement

### Lancer les tests

```bash
uv run pytest
```

### Lancer avec couverture

```bash
uv run pytest --cov
```

### Linter et formater

```bash
uv run ruff check .
uv run ruff format .
```

### Vérification de types

```bash
uv run mypy src/
```

---

## Roadmap

- **V1.1** ✓ — recettes corrigées, double scénario A/B, fill probability réaliste, walk du carnet sur la récup, pondération fraîcheur (voir [CHANGELOG.md](CHANGELOG.md))
- **V1** ✓ — CLI Python avec toutes les fonctionnalités de base
- **V2** — Récursion cascade des tiers (produire soi-même le T-1 plank si moins cher que l'acheter), split vente, scraping automatique des fees
- **V3** — Frontend Next.js + backend FastAPI, déploiement web

---

## Contributing

Ce projet est développé personnellement mais les issues et suggestions sont bienvenues.

---

## Licence

MIT © Duvalier

---

## Remerciements

- [Albion Online Data Project](https://www.albion-online-data.com/) pour l'API publique communautaire
- [Albion Codex](https://www.albioncodex.com/) et le [wiki officiel](https://wiki.albiononline.com/) pour la documentation des mécaniques
- Sandbox Interactive GmbH pour Albion Online

**Disclaimer** : Cet outil n'est pas affilié à Albion Online ni à Sandbox Interactive GmbH. Il utilise uniquement des données publiques fournies par les joueurs via l'AODP. Aucune méthode d'extraction directe du client jeu n'est utilisée.
