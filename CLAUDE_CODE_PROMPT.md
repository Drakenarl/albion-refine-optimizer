# Prompt d'ouverture Claude Code

AVANT TOUT : lis d'abord CORRECTIONS_URGENTES.md à la racine du projet et applique les corrections qu'il contient dans un commit dédié. Ensuite seulement, lis SPEC.md et commence l'implémentation.

Bonjour Claude Code.

Je te confie l'implémentation d'un projet Python complet : **albion-refine-optimizer**, un outil d'optimisation économique pour le jeu Albion Online.

Le cahier des charges complet est dans le fichier `SPEC.md` à la racine du projet. **Lis-le intégralement avant de commencer quoi que ce soit** — il fait environ 900 lignes et couvre l'architecture, les formules mathématiques, la structure des fichiers, les tests, et le périmètre V1/V2/V3.

## Ta mission — V1 uniquement

Implémente **la V1 telle que définie dans la section 4.1 du SPEC.md**. Ne commence PAS V2 ou V3. Si tu as des idées d'améliorations qui appartiennent à V2 ou V3, note-les dans un fichier `IDEAS.md` sans les implémenter.

## Ressources déjà fournies

À la racine du projet tu trouveras :

- `SPEC.md` — cahier des charges complet, source de vérité
- `items.json` — extract réduit des items bois/planks T4-T8 avec recipes et cities (utilisable directement, pas besoin de télécharger le fichier AODP complet)
- `pyproject.toml` — configuration projet avec toutes les dépendances déclarées
- `.gitignore` — configuré pour Python + spécificités du projet
- `README.md` — template avec quelques sections à compléter (marquées `[À remplir par Claude Code]`)
- `fixtures/` — 3 fixtures JSON réalistes de réponses AODP pour bootstrap les tests unitaires :
  - `aodp_prices_t7.json` — prix T7_WOOD, T6_PLANKS, T7_PLANKS toutes villes
  - `aodp_history_t7.json` — historique 24h volumes T7_PLANKS toutes villes
  - `aodp_stale_data.json` — cas limites (données vieilles, prix à zéro)

## Ordre de travail imposé

Développe module par module dans cet ordre strict. Ne passe au suivant qu'une fois les tests du module courant écrits et verts.

1. `src/albion_refine/config.py` — constantes, item IDs, cities, tax rates, defaults
2. `src/albion_refine/models.py` — dataclasses/Pydantic : `PriceQuote`, `Route`, `RefiningResult`, `SalesScenario`, etc.
3. `src/albion_refine/aodp_client.py` — client HTTP async httpx + cache diskcache 15min
4. `src/albion_refine/refining.py` — formules RRR, outputs, coût station (math pure, tests exhaustifs)
5. `src/albion_refine/market.py` — order book walker, calcul scénarios A/B, tax application
6. `src/albion_refine/optimizer.py` — orchestrateur des phases 1→5, filtrage, tri
7. `src/albion_refine/formatters.py` — rendu rich (tableaux, checklist) + export JSON
8. `src/albion_refine/cli.py` — entrée typer avec toutes les options du SPEC section 9

Après chaque module, écris ses tests unitaires dans `tests/test_<module>.py`. Utilise les fixtures fournies.

## Contraintes techniques

- **Python 3.11+** (utilise les features modernes : `match/case`, `Self`, `type X = ...`)
- **uv** pour la gestion des dépendances (`uv sync`, `uv add`, `uv run`)
- **Type hints stricts partout** — mypy strict doit passer sans erreur
- **Ruff** doit passer sans warning (lint + format)
- **Zéro `# type: ignore`** sauf commentaire justifiant pourquoi
- **httpx.AsyncClient** avec context manager pour le HTTP
- **Docstrings** en français, style Google, sur toutes les fonctions publiques
- **Code en anglais** (variables, fonctions, classes), **docs et messages utilisateur en français**
- **Zéro dépendance sur des libs propriétaires** ou APIs payantes

## Contraintes de qualité

- Coverage cible : refining.py 100%, market.py 90%+, optimizer.py 80%+
- Tests unitaires isolés (pas d'appels réseau réels — mocke via `pytest-httpx` + les fixtures)
- Commits atomiques, un par module ou sous-fonctionnalité
- Messages de commit en français, format conventionnel : `feat(refining): implement RRR calculation with focus and daily bonus`

## Règles de conduite

- **Ne devine JAMAIS** un point ambigu du SPEC. Si quelque chose n'est pas clair ou semble contradictoire, arrête-toi et écris ta question dans un fichier `QUESTIONS.md` à la racine, puis attends ma réponse.
- **Ne modifie pas le SPEC.md** de ta propre initiative. Si tu penses qu'un ajustement est nécessaire, propose-le dans `QUESTIONS.md`.
- **Ne prends pas de raccourcis** sur les tests. Un module sans tests est un module non-livré.
- **Ne fais pas de V2/V3.** Si tu es tenté d'ajouter une feature qui n'est pas dans le périmètre V1, note-la dans `IDEAS.md`.
- **Vérifie les item IDs contre `items.json`** au démarrage, mais fais confiance à ce fichier — les IDs y sont validés (`T{n}_WOOD` et `T{n}_PLANKS`).

## Vérifications finales avant de me remettre le projet

Avant de considérer V1 terminée :

1. ✓ `uv run pytest` : tous les tests passent
2. ✓ `uv run pytest --cov` : coverage aux cibles définies
3. ✓ `uv run ruff check .` : zéro warning
4. ✓ `uv run ruff format --check .` : zéro reformatage nécessaire
5. ✓ `uv run mypy src/` : zéro erreur en mode strict
6. ✓ `README.md` : toutes les sections `[À remplir]` sont remplies
7. ✓ Un run réel `albion-refine optimize --tier 7 --mode fixed --quantite 128 --station-fee 18` retourne un résultat cohérent (peu importe la marge — juste que ça ne crash pas et que la sortie est bien formatée)
8. ✓ Git : historique de commits propre, chaque module dans un commit distinct

Une fois tous ces checks verts, résume-moi en français ce que tu as livré, les décisions notables prises, et push sur `main`.

Question ouverte pour toi maintenant : après avoir lu le SPEC intégralement, y a-t-il un point que tu voudrais clarifier avant de démarrer ? Si oui, mets-le dans `QUESTIONS.md`. Si non, commence par le module 1 (`config.py`) et lance-toi.

Bon travail.
