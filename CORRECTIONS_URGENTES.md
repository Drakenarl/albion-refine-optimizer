# CORRECTIONS URGENTES — À traiter avant toute implémentation

> **Claude Code** : lis ce fichier AVANT `SPEC.md`. Il contient des corrections identifiées après la rédaction initiale de la spec et du bundle. Applique ces corrections dans un commit dédié `fix(spec): applique les corrections urgentes identifiées avant dev` AVANT de commencer l'implémentation du module 1 (`config.py`).

---

## Contexte

Après recherches complémentaires (forums Albion, patch notes v19.000.1, threads de calcul du nutrition cost), deux points du bundle initial se sont révélés incorrects :

1. Les valeurs de `nutrition_cost_by_tier` dans `items.json` étaient basées sur une progression naïve 8/16/32/64/128 qui ne correspond à aucune donnée officielle.
2. La formule de coût de station dans `SPEC.md` section 3.4 utilise un multiplicateur en pourcentage (`× (1 + fee_owner_pct/100)`) qui ne correspond plus à l'UI actuelle du jeu depuis le patch v19.000.1.

## Correction 1 — Item Values et nutrition cost par tier

### Formule officielle
nutrition_consommée_par_unité_raffinée = Item_Value(tier) × 0.1125

Source : forum.albiononline.com Thread 128681 (tests empiriques par Bridgewatch stone refining), cross-vérifié avec les données de focus base cost du Thread 49690.

### Valeurs correctes à utiliser

| Tier | Item Value (refined) | Nutrition par unité raffinée |
|---|---|---|
| T4 | 14 | 1.575 |
| T5 | 30 | 3.375 |
| T6 | 62 | 6.975 |
| T7 | 126 | 14.175 |
| T8 | 254 | 28.575 |

⚠ Ces valeurs sont à reconfirmer en jeu par Duvalier quand il pourra se connecter (hover sur la station lumbermill de Fort Sterling, chaque tier affiche son nutrition cost par unité). Si les valeurs affichées en jeu diffèrent de plus de 5%, ouvre un `QUESTIONS.md` avant de continuer.

### Action à effectuer dans `items.json`

Supprimer complètement la section `nutrition_cost_by_tier` (lignes 96-105 environ) et la remplacer par les trois sections suivantes :

```json
  "refined_item_values": {
    "_note": "Item Value (IV) des planks raffinés par tier. À reconfirmer en jeu.",
    "_source": "forum.albiononline.com Thread 49690 + Thread 128681, cross-check avec patch v19.000.1",
    "T4": 14,
    "T5": 30,
    "T6": 62,
    "T7": 126,
    "T8": 254
  },
  "nutrition_per_refined_unit": {
    "_note": "Nutrition consommée par unité raffinée = IV × 0.1125. Valeurs approximatives à reconfirmer.",
    "T4": 1.575,
    "T5": 3.375,
    "T6": 6.975,
    "T7": 14.175,
    "T8": 28.575
  },
  "station_fee_format": {
    "_note": "Depuis patch v19.000.1, les station owners fixent leur fee en 'silver par 100 nutrition consommée', pas en pourcentage. Voir SPEC.md section 3.4 pour la formule corrigée.",
    "example": "Un owner fixe 50 silver/100 nutrition. Raffiner 100 T7 planks consomme 100 × 14.175 = 1417.5 nutrition. Coût station = 1417.5 × (50/100) = 708.75 silver.",
    "typical_range_silver_per_100_nutrition": "30 à 500"
  },
```

## Correction 2 — Formule de coût de station dans SPEC.md

### Formule incorrecte (à remplacer)
coût_station = nutrition_cost(tier) × (1 + fee_owner_pct/100) × quantité_raffinée

### Formule correcte (à appliquer)
coût_station_silver = quantité × nutrition_per_unit(tier) × (silver_per_100_nutrition / 100)

Où :
- `nutrition_per_unit(tier)` est la valeur de la table `nutrition_per_refined_unit` du `items.json` corrigé (voir Correction 1)
- `silver_per_100_nutrition` est un input utilisateur (le taux affiché dans l'UI de la station en jeu)

### Sections de `SPEC.md` à mettre à jour

**Section 3.4 (Coût de raffinage à la station)** : remplacer intégralement le contenu par :

> Le coût de la station en silver se calcule ainsi (depuis patch v19.000.1) :
>
> ```
> coût_station_silver = quantité × nutrition_per_unit(tier) × (silver_per_100_nutrition / 100)
> ```
>
> Le `silver_per_100_nutrition` est fixé par l'owner de la station et visible en jeu dans l'UI de la station (typiquement entre 30 et 500 silver par 100 nutrition). C'est un **input utilisateur** de la CLI.
>
> Voir `items.json` section `nutrition_per_refined_unit` pour les valeurs par tier.

**Section 6.4 (Paramètres par défaut)** : remplacer la mention du `station_fee` par un `silver_per_100_nutrition`. Il n'y a pas de valeur par défaut sensée pour ce paramètre — l'utilisateur DOIT le fournir.

**Section 7.4 (Coût d'une route)** : mettre à jour la ligne `coût_station` avec la nouvelle formule.

**Section 9.1 (Commande principale)** : remplacer l'option `--station-fee 18` par `--station-rate 50` (silver par 100 nutrition).

**Section 9.2 (Modes quantité)** : idem, `--station-fee` devient `--station-rate` dans les exemples.

**Section 15.1 (Informations à confirmer en jeu)** : mettre à jour le point 1 (nutrition cost) pour référer à la nouvelle table et le point 2 (fee station) pour référer au nouveau format silver/100 nutrition.

## Correction 3 — README.md exemples de commande

Dans `README.md`, remplacer tous les exemples `--station-fee X` par `--station-rate Y` (où Y est en silver par 100 nutrition, typiquement 50 pour un exemple).

## Correction 4 — Fixtures inchangées

Les fixtures dans `tests/fixtures/` ne contiennent pas de données de nutrition ni de fees, donc **rien à corriger** de ce côté-là.

## Ordre d'application recommandé

1. Lire ce fichier intégralement (fait)
2. Lire `SPEC.md` intégralement
3. Créer un commit `fix(spec): applique les corrections urgentes (nutrition cost + station fee format)` qui contient :
   - Modification de `items.json` (Correction 1)
   - Modification de `SPEC.md` (Correction 2)
   - Modification de `README.md` (Correction 3)
4. Confirmer que le SPEC est maintenant cohérent
5. Commencer l'implémentation module par module comme prévu dans `CLAUDE_CODE_PROMPT.md`

## Après application

Une fois les corrections appliquées et le commit fait, supprime ce fichier `CORRECTIONS_URGENTES.md` dans un commit séparé :
git rm CORRECTIONS_URGENTES.md
git commit -m "chore: retire le fichier de corrections urgentes après application"

Puis continue avec l'implémentation V1 normale.