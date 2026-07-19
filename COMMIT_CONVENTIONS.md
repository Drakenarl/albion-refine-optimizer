# Charte de commits conventionnels — albion-refine-optimizer

Format inspiré de [Conventional Commits](https://www.conventionalcommits.org/) mais adapté en français.

## Format général

```
<type>(<scope>): <description courte en français, impératif, sans point final>

<corps optionnel — plusieurs paragraphes possibles>

<footer optionnel — refs issues, breaking changes>
```

## Types autorisés

| Type | Usage |
|---|---|
| `feat` | Nouvelle fonctionnalité (nouvel endpoint, nouvelle option CLI, nouvelle formule) |
| `fix` | Correction de bug |
| `refactor` | Restructuration de code sans changement de comportement |
| `perf` | Amélioration de performance |
| `test` | Ajout ou modification de tests uniquement |
| `docs` | Documentation (SPEC, README, docstrings) |
| `style` | Formatage, indentation, imports (pas de changement de code exécutable) |
| `chore` | Tâches de maintenance (deps, config, gitignore, CI) |
| `build` | Changements liés au build (pyproject.toml, hatchling, uv.lock) |
| `ci` | Configuration CI/CD (GitHub Actions) |

## Scopes suggérés (modules du projet)

- `config` — src/albion_refine/config.py
- `models` — src/albion_refine/models.py
- `aodp` — src/albion_refine/aodp_client.py
- `refining` — src/albion_refine/refining.py
- `market` — src/albion_refine/market.py
- `optimizer` — src/albion_refine/optimizer.py
- `formatters` — src/albion_refine/formatters.py
- `cli` — src/albion_refine/cli.py
- `tests` — dossier tests/
- `deps` — pyproject.toml, dépendances
- `docs` — README.md, SPEC.md, docs/

Le scope est optionnel mais fortement recommandé quand un commit touche un module précis.

## Règles de rédaction

- **Impératif présent** : "ajoute la formule RRR", pas "ajouté" ni "ajout de"
- **Minuscule au début** de la description
- **Pas de point final**
- **Maximum 72 caractères** pour la ligne de titre
- **Corps facultatif** pour expliquer le pourquoi si non-évident, séparé du titre par une ligne vide
- **Un commit = un changement logique** — ne pas mélanger refactor + feat + fix

## Exemples

### Bons exemples

```
feat(refining): implémente le calcul du RRR avec focus et daily bonus

Formule : RRR = 1 - 1 / (1 + total_bonus/100)
Total bonus = 58 (FS wood) + 59 (focus) + daily_bonus_pct

Testé avec les valeurs de référence de la section 3.2 du SPEC :
- sans focus : 36.7%
- focus seul : 53.9%
- focus + daily 20% : 57.8%
```

```
feat(market): ajoute le walker d'order book pour les scénarios de vente
```

```
fix(aodp): gère correctement les timestamps AODP au format "0001-01-01"

L'AODP retourne ce timestamp sentinel quand aucune donnée n'a jamais été
uploadée pour cet item/cette ville. Ces cas sont maintenant traités comme
"pas de prix disponible" au lieu de crash sur le parse ISO 8601.
```

```
test(refining): ajoute tests exhaustifs pour toutes les combinaisons de bonus
```

```
refactor(optimizer): extrait la logique de filtrage dans une fonction dédiée
```

```
docs(readme): remplit la section architecture avec l'arbre du projet
```

```
chore(deps): met à jour httpx vers 0.27.2
```

```
build(pyproject): ajoute pytest-cov aux deps dev
```

### Mauvais exemples

```
❌ update code
❌ fix bug
❌ WIP
❌ misc changes
❌ ajout de la fonctionnalité X (préférer l'impératif)
❌ Feat: Ajoute Le RRR. (majuscules, point final, préfixe capitalisé)
```

## Commits multi-lignes — quand utiliser un corps

Ajoute un corps quand :
- La motivation du changement n'est pas évidente au lecteur
- Il y a un compromis technique à expliquer
- Le changement touche plusieurs fichiers pour une même feature
- Une décision remonte à une discussion (référence dans le corps)

Exemple :

```
feat(market): implémente le scénario B avec fill probability

Le scénario B (placer un sell order) nécessite d'estimer la probabilité
que l'ordre soit rempli dans les 24h. En V1, on utilise une approximation
simple : fill_proba = min(1.0, volume_24h / quantite_a_ecouler).

Cette approche est volontairement conservative — un raffinement plus
précis (courbe de décroissance, saisonnalité) est prévu pour V2.

Voir SPEC.md section 7.7 pour la formule complète.
```

## Breaking changes

En V1 le projet n'est pas encore publié donc pas de breaking change à annoncer.

Pour V2+, format :

```
feat(cli)!: renomme --quantite en --quantity pour cohérence i18n

BREAKING CHANGE: L'option --quantite est renommée en --quantity.
Les scripts existants doivent être mis à jour.
```

## Références aux issues GitHub

Si un commit résout une issue :

```
fix(aodp): corrige la gestion des retries sur timeout

Closes #12
```

Ou pour référence sans fermeture :

```
refactor(optimizer): prépare l'extension récursive pour V2

Refs #24
```
