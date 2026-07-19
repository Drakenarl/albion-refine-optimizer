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

*[À remplir par Claude Code — sortie de `albion-refine optimize --help`]*

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

*[À remplir par Claude Code — arbre du projet + diagramme de flux]*

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
