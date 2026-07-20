# Albion Refine Optimizer

> Outil d'optimisation économique pour Albion Online. Trouve les meilleures routes de raffinage de bois à Fort Sterling en interrogeant l'API publique de l'Albion Online Data Project.

[![Python](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Code style: ruff](https://img.shields.io/badge/code%20style-ruff-000000.svg)](https://github.com/astral-sh/ruff)

---

## Fonctionnalités (V1)

- Analyse combinatoire complète : bois × plank T-1 × ville de vente × scénario de vente
- Trois modes d'input : capital silver disponible, quantité fixe, ou budget focus
- Deux scénarios de vente évalués par ville : instant sell (fill buy orders) vs sell order (placement avec undercut)
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

### Cascade des tiers

Pour raffiner du bois de tier N, il faut à la fois du bois brut T{N} ET un plank T{N-1}. L'outil calcule le coût réel en prenant en compte cet input caché souvent oublié par les calculateurs simples.

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
- ✗ **rouge** : > 6h (exclu par défaut)

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

- **V1** ✓ (ou en cours) — CLI Python avec toutes les fonctionnalités de base
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
