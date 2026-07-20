# SPEC_FIX — Corrections critiques V1

**Version cible** : V1.1.0
**Branche de travail** : fix/critical-bugs (déjà créée)
**Merge cible** : main
**Contexte** : Après un test réel en jeu sur T7 planks le 20/07/2026, plusieurs bugs critiques ont été identifiés dans la V1.0. Ce document liste les 5 corrections à appliquer, dans l'ordre, avec leurs tests de validation.

---

## Table des matières

1. [Contexte et validation empirique](#1-contexte)
2. [BUG #1 — Recettes de raffinage fausses](#2-bug-1-recettes)
3. [BUG #2 — Absence du scénario A dans la sortie](#3-bug-2-double-scenario)
4. [BUG #3 — Fill probability irréaliste](#4-bug-3-fill-probability)
5. [BUG #4 — Récup RRR sans walk du carnet](#5-bug-4-recup-walk)
6. [BUG #5 — Pas de pondération fraîcheur dans les revenus](#6-bug-5-freshness-weighting)
7. [Format de sortie CLI mis à jour](#7-cli-output)
8. [Checklist de non-régression](#8-non-regression)
9. [Livrables et workflow git](#9-livrables)

---

## 1. Contexte

### 1.1. Test réel effectué

Le 20/07/2026, un run `optimize --tier 7 --mode capital --capital 500000 --station-rate 50` a été effectué contre l'API AODP live. L'outil a recommandé une route T7 avec **marge nette affichée de 147%**.

Vérification manuelle en jeu sur les marchés de Lymhurst et Fort Sterling :
- Lymhurst T7 Planks : top sell 12 340 s, top buy 10 924 s (spread 11.5%)
- Fort Sterling T7 Planks : top sell 12 154 s, top buy 10 501 s (spread 13.6%)
- Prix moyen 24h stable ~12 060 s (marché fonctionnel, pas de bulle)

### 1.2. Recettes réelles confirmées in-game


|
 Tier plank produit 
|
 Bois T{N} requis 
|
 Plank T{N-1} requis 
|
|
---
|
---
|
---
|
|
 T2 
|
 1 
|
 0 (pas d'input plank) 
|
|
 T3 
|
 2 
|
 1 
|
|
 T4 
|
 2 
|
 1 
|
|
 T5 
|
 3 
|
 1 
|
|
 T6 
|
 4 
|
 1 
|
|
 T7 
|
 5 
|
 1 
|
|
 T8 
|
 5 
|
 1 
|

L'outil V1.0 hardcode `wood_qty=1` et `lower_plank_qty=1` pour tous les tiers, ce qui sous-estime massivement le coût en bois brut aux tiers 5-8.

### 1.3. Impact du bug #1 sur la rentabilité affichée vs réelle

Pour T7 planks avec les vraies recettes :
- Coût d'inputs par plank : 5 × 3 048 + 1 × 3 300 = 18 540 s
- Revenu instant sell : 10 924 × 0.92 = 10 050 s
- Marge réelle : **négative de ~-20%**, pas +147% comme affiché

**La V1.0 ne doit plus être utilisée pour trader tant que ces corrections ne sont pas mergées.**

---

## 2. BUG #1 — Recettes de raffinage fausses

### 2.1. Localisation

- `data/items.json` (ou emplacement équivalent dans `src/albion_refine/data/`)
- `src/albion_refine/config.py` (constantes de recette si dupliquées)
- `src/albion_refine/refining.py` (utilisation des quantités dans les calculs)
- `src/albion_refine/optimizer.py` (phases 1 et 2 : sourcing bois et plank T-1)

### 2.2. Correction requise

Remplacer la table des recettes par les valeurs correctes. Ajouter un dictionnaire de référence dans `config.py` :

```python
# Recettes de raffinage confirmées in-game (20/07/2026)
# Format : tier_plank -> (wood_qty, lower_plank_qty)
PLANK_RECIPES: dict[int, tuple[int, int]] = {
    2: (1, 0),
    3: (2, 1),
    4: (2, 1),
    5: (3, 1),
    6: (4, 1),
    7: (5, 1),
    8: (5, 1),
}
```

Adapter également le `items.json` en conséquence dans la section `planks`.

### 2.3. Propagation dans le code

Toutes les fonctions qui calculent des coûts d'inputs doivent utiliser cette table :

**Phase 1 (sourcing bois)** : la quantité de bois à acheter n'est plus `Q` (nombre de planks visé) mais `Q × PLANK_RECIPES[tier][0]`.

**Phase 2 (sourcing plank T-1)** : quantité `Q × PLANK_RECIPES[tier][1]`. Pour T2 spécifiquement, cette quantité est 0 → skip complètement la phase 2.

**Phase 3 (raffinage)** : le nombre d'actions de raffinage reste `Q` (une action produit un plank), mais la nutrition consommée par action est basée sur le tier du plank produit (inchangé). Focus consommé = `Q` (inchangé).

**Récupération RRR** : le RRR s'applique **sur chaque unité d'input**, pas seulement sur les planks produits. Pour raffiner Q planks T7, on utilise 5Q bois T7 et Q planks T6. La récup RRR retourne :
- `5 × Q × RRR` bois T7 (pas Q × RRR)
- `Q × RRR` planks T6 (inchangé)

### 2.4. Cas particulier T2

`PLANK_RECIPES[2] = (1, 0)`. Pour T2 :
- Pas d'achat de plank T-1
- Pas de récup RRR sur plank T-1
- Le mode `capital` doit gérer la division par zéro correctement (input coût par plank = coût de 1 bois T2 seulement)

### 2.5. Mode capital — recalcul de la quantité optimale

Pour le mode `--mode capital --capital X`, la formule de quantité max devient :

coût_par_plank_produit = (wood_qty × prix_bois) + (lower_plank_qty × prix_plank_T-1) + coût_station_unitaire
quantité_max = floor(capital / coût_par_plank_produit)


Le coût unitaire de station = `nutrition_per_unit(tier) × silver_per_100_nutrition / 100`.

### 2.6. Tests obligatoires

Créer `tests/test_recipes.py` :

```python
def test_recipe_t7_requires_5_wood():
    assert PLANK_RECIPES[7] == (5, 1)

def test_recipe_t2_has_no_lower_plank():
    assert PLANK_RECIPES[2] == (1, 0)

def test_all_tiers_defined():
    for tier in range(2, 9):
        assert tier in PLANK_RECIPES

def test_refining_cost_t7_uses_5_wood():
    # Vérifier que refining.compute_input_cost(tier=7, qty=100) 
    # multiplie bien par 5 pour le bois
    ...

def test_rrr_return_scales_with_recipe():
    # Pour T7 avec RRR=0.5 et 100 planks produits :
    # wood retour = 5 * 100 * 0.5 = 250
    # plank T6 retour = 1 * 100 * 0.5 = 50
    ...

def test_capital_mode_t2_no_division_error():
    # Le mode capital pour T2 ne doit pas crasher
    # (lower_plank_qty=0 dans le coût)
    ...
```

Adapter également les fixtures existantes si elles hardcodaient l'ancienne formule.

---

## 3. BUG #2 — Absence du scénario A dans la sortie

### 3.1. Symptôme

La V1.0 calcule les deux scénarios (A = instant sell, B = sell order) mais n'affiche **que le meilleur** dans le tableau final. Comme le scénario B a une fill probability à 100% (bug #3), il gagne systématiquement, masquant le scénario A instant sell qui est en réalité l'option safe.

### 3.2. Correction requise

**Toujours afficher les deux scénarios côte à côte**, pour chaque route retenue. Laisser l'utilisateur décider selon son profil de risque.

### 3.3. Nouveau format d'affichage par route

Dans `src/albion_refine/formatters.py`, remplacer le bloc "VENTE" par :

VENTE @ Lymhurst
► INSTANT SELL (safe) revenu net : X s marge Y% immédiat
top buy 10 924 s, absorbable 100/128 unités (walk carnet requis)
► SELL ORDER (attente) revenu net : X s marge Y% fill proba Z%
undercut à 12 339 s, gain marginal vs instant : +N s (+M%)


Les deux lignes doivent être visuellement distinctes (par exemple, la ligne A en couleur neutre, la ligne B avec un léger dimming si sa fill probability est basse).

### 3.4. Marge affichée dans le titre de la route

Le titre de la route (`TOP 1 — Marge nette : X%`) doit utiliser la **marge du scénario A (instant sell)**, pas celle du scénario B. C'est la marge safe, honnête, celle sur laquelle on peut compter.

Optionnel : ajouter en sous-titre `(potentiel jusqu'à Y% en sell order)`.

### 3.5. Tri des routes

Le tri des top 5 utilise désormais la **marge du scénario A** comme critère primaire, pas la marge du meilleur scénario. Les routes rentables uniquement en scénario B (marge A < seuil, marge B > seuil) sont écartées.

### 3.6. Filtre du seuil marge

Le filtre `--seuil-marge` s'applique à la marge du scénario A. Si aucune route ne passe le seuil en A, afficher le meilleur candidat écarté avec sa marge A ET B, pour aider l'utilisateur à ajuster.

### 3.7. Sortie JSON

La structure JSON doit exposer les deux scénarios complets pour chaque route :

```json
{
  "route_rank": 1,
  "achat_wood": {...},
  "achat_plank": {...},
  "raffinage": {...},
  "vente": {
    "ville": "Lymhurst",
    "scenario_a_instant_sell": {
      "revenu_brut": ...,
      "revenu_net": ...,
      "marge_pct": ...,
      "top_buy_price": ...,
      "walk_du_carnet": [
        {"prix": 10924, "qte_absorbee": 100},
        {"prix": 10923, "qte_absorbee": 28}
      ],
      "certitude": "haute"
    },
    "scenario_b_sell_order": {
      "revenu_brut_if_filled": ...,
      "revenu_net_if_filled": ...,
      "marge_pct_if_filled": ...,
      "prix_listing_undercut": ...,
      "fill_probability_24h": ...,
      "expected_revenue": ...,
      "gain_marginal_vs_a": ...,
      "certitude": "moyenne"
    },
    "recommandation": "instant_sell" | "sell_order" | "au_choix"
  }
}
```

### 3.8. Tests

```python
def test_output_shows_both_scenarios():
    # Vérifier que le formatter affiche les deux blocs A et B
    ...

def test_route_title_uses_scenario_a_margin():
    ...

def test_json_export_has_both_scenarios():
    ...

def test_filter_uses_scenario_a_margin():
    # Une route avec marge A=15%, marge B=200% doit être écartée si seuil=30%
    ...
```

---

## 4. BUG #3 — Fill probability irréaliste

### 4.1. Symptôme

La formule V1.0 : `fill_proba = min(1.0, volume_24h / quantité)`

Résultat en pratique : dès que le volume 24h dépasse la quantité à écouler, la fill proba est à 100%. Pour 5000 T7 planks à Lymhurst avec un volume de 300/jour, ça donnait 100% (à cause du min), ce qui est absurde.

### 4.2. Correction requise

Nouvelle formule à trois composantes :

```python
def compute_fill_probability(
    quantity_to_sell: int,
    volume_24h: float,
    position_in_book: int,  # nombre d'ordres empilés au-dessus (moins chers)
    listing_price: float,
    top_sell_order_price: float,
) -> float:
    # Facteur 1 : ratio volume/quantité, plafonné plus bas que 100%
    ratio = volume_24h / max(quantity_to_sell, 1)
    volume_factor = min(0.85, ratio * 0.6)  # plafond dur à 85%
    
    # Facteur 2 : position dans le carnet
    # Si notre listing est le nouveau top → pas de pénalité
    # Si on est 5ème ou plus → forte pénalité
    position_penalty = max(0.3, 1.0 - (position_in_book * 0.15))
    
    # Facteur 3 : compétitivité du prix
    # Undercut agressif → meilleur, undercut trop timide → pire
    undercut_pct = (top_sell_order_price - listing_price) / top_sell_order_price
    if undercut_pct < 0:
        price_factor = 0.5  # on est plus cher que le top, très mauvais
    elif undercut_pct < 0.005:
        price_factor = 0.7  # undercut < 0.5%, peu compétitif
    else:
        price_factor = 1.0
    
    fill_proba = volume_factor * position_penalty * price_factor
    return min(0.85, max(0.0, fill_proba))  # jamais 100%, jamais négatif
```

### 4.3. Position dans le carnet — approximation V1

L'endpoint AODP `/prices/` ne donne que le top sell order, pas la profondeur complète. Approximation V1 :

```python
# Si notre listing_price >= top_sell_order → position = 1 (on est le nouveau top après undercut)
# Sinon on suppose position = 3 (on est enterré dans le carnet)
if listing_price <= top_sell_order_price:
    position_in_book = 1
else:
    position_in_book = 3
```

Cette approximation est conservative. Une vraie profondeur du carnet est une amélioration V2 déjà listée dans IDEAS.md.

### 4.4. Impact sur expected_revenue du scénario B

expected_revenue_B = revenu_net_B_if_filled × fill_probability


Cette valeur pondérée est celle utilisée pour comparer avec le scénario A dans les recommandations.

### 4.5. Affichage

Dans le format CLI, la fill probability doit apparaître explicitement pour le scénario B :

► SELL ORDER (attente) revenu net si rempli : 826 000 s marge 147% fill proba 42%
espérance pondérée : 346 920 s (0.42 × 826 000)


L'espérance pondérée aide l'utilisateur à comparer honnêtement avec le scénario A.

### 4.6. Tests

```python
def test_fill_proba_never_exceeds_85_pct():
    # Même avec volume infini, fill_proba <= 0.85
    ...

def test_fill_proba_penalized_when_not_top():
    # listing_price > top_sell → position=3, fill_proba baissée
    ...

def test_fill_proba_zero_when_price_worse_than_book():
    # Si on liste plus cher que le top, price_factor = 0.5
    ...

def test_fill_proba_realistic_for_high_volume_case():
    # 128 unités, volume 300/jour, top price undercut de 1%
    # Résultat attendu : ~0.6-0.8, pas 1.0
    ...
```

---

## 5. BUG #4 — Récup RRR sans walk du carnet

### 5.1. Symptôme

La V1.0 crédite la récup RRR au **top buy order price × quantité retournée**, sans vérifier que le stack du top order absorbe effectivement la quantité. Pour 2696 T7 wood retournés (mode focus 5000), c'est irréaliste : aucun buy order n'a un stack de 2696.

### 5.2. Correction requise

Utiliser le même `walk_book` que pour la vente principale, mais côté buy orders cette fois (walk du top vers le bas).

```python
def compute_recovery_value(
    quantity_returned: float,
    buy_orders_at_refining_city: list[tuple[float, int]],  # [(prix, stack)]
    tax_instant_sell: float,
) -> float:
    walk_result = walk_book_descending(
        quantity=int(quantity_returned),
        book=buy_orders_at_refining_city
    )
    if walk_result is None:
        # Stack insuffisant pour tout écouler
        # Créditer seulement ce qui est absorbable, ignorer le reste
        return walk_result_partial.total_revenue * (1 - tax_instant_sell)
    return walk_result.total_revenue * (1 - tax_instant_sell)
```

### 5.3. Fallback quand aucun buy order n'existe

Si l'AODP ne retourne pas de buy order pour un item à Fort Sterling (ou prix = 0), créditer la récup à **0 silver**. Le stock retourné reste dans l'inventaire du joueur, mais on ne le valorise pas dans le calcul.

Alternative optionnelle : valoriser à un pourcentage conservateur du prix moyen 7 jours (par exemple 70%), mais V1 reste sur 0 pour être safe.

### 5.4. Affichage

Le format doit indiquer si la récup a été partiellement absorbée :

RÉCUP (retours) : 164 427 s (28/28 wood absorbés, 28/28 T6 planks absorbés)


ou en cas d'absorption partielle :

RÉCUP (retours) : 89 200 s (15/28 wood absorbés, stack insuffisant ; 28/28 T6 planks absorbés)
⚠ 13 T7 wood restent dans l'inventaire, non valorisés


### 5.5. Tests

```python
def test_recovery_walks_buy_book():
    ...

def test_recovery_partial_when_stack_insufficient():
    ...

def test_recovery_zero_when_no_buy_order():
    ...
```

---

## 6. BUG #5 — Pas de pondération fraîcheur dans les revenus

### 6.1. Symptôme

La V1.0 traite un prix vieux de 5h comme aussi certain qu'un prix de 30 min. Sur un marché volatil, ce n'est pas honnête.

### 6.2. Correction requise

Appliquer un discount progressif sur les revenus attendus en fonction de l'âge des données. Le coût d'achat n'est pas pondéré (on prend le prix affiché comme référence, il sera confirmé en jeu). Seul le **revenu de vente attendu** est pondéré, car c'est là que la volatilité impacte le résultat final.

Formule :

```python
def freshness_confidence_factor(age_hours: float) -> float:
    if age_hours < 0.5:
        return 1.0
    elif age_hours < 2:
        return 0.95
    elif age_hours < 4:
        return 0.85
    elif age_hours < 6:
        return 0.70
    else:
        return 0.50  # au-delà de 6h, très basse confiance
```

Application :

revenu_net_A_pondere = revenu_net_A × freshness_confidence_factor(âge_sell_data_ville_vente)
revenu_net_B_pondere = revenu_net_B × freshness_confidence_factor(âge_sell_data_ville_vente)


### 6.3. Affichage

Le facteur de confiance doit apparaître dans la sortie :

► INSTANT SELL (safe) revenu net brut : 1 286 400 s
× confiance fraîcheur (data 3.1h ⚠) : 0.85
= revenu net pondéré : 1 093 440 s
marge pondérée : 101%


### 6.4. Marge affichée

C'est la **marge pondérée** qui est utilisée pour le titre de la route et le filtrage par seuil. La marge brute reste consultable en JSON pour debug.

### 6.5. Tests

```python
def test_freshness_factor_1_0_for_fresh_data():
    assert freshness_confidence_factor(0.2) == 1.0

def test_freshness_factor_0_5_for_stale_data():
    assert freshness_confidence_factor(8) == 0.5

def test_revenue_penalized_by_stale_freshness():
    ...

def test_margin_uses_weighted_revenue():
    ...
```

---

## 7. Format de sortie CLI mis à jour

### 7.1. Exemple complet de la nouvelle sortie

╭─── TOP 1 — Marge nette (safe) : 88% — potentiel jusqu'à 137% ──────╮
│ │
│ ACHAT BOIS T7 Lymhurst 3048 s × 385 = 1 173 480 s │
│ fraîcheur : 3.1h ⚠ (facteur 0.85) │
│ ACHAT PLANK T6 Bridgewatch 3382 s × 77 = 260 414 s │
│ fraîcheur : 5.7h ⚠ (facteur 0.70) │
│ RAFFINAGE FS nutrition × 77 × rate/100 = 546 s │
│ │
│ RRR effectif : 36.7% | Retours : 141 T7 wood + 28 T6 planks │
│ │
│ VENTE @ Lymhurst │
│ ► INSTANT SELL (safe) │
│ revenu net brut : 773 000 s │
│ × facteur fraîcheur : 656 000 s │
│ marge pondérée : 88% │
│ │
│ ► SELL ORDER (attente) │
│ revenu si rempli : 826 000 s fill proba 62% │
│ espérance pondérée : 435 000 s │
│ marge espérée : 25% │
│ │
│ RÉCUP retours : 89 200 s (walk carnet, 141/141 absorbés) │
│ COÛT NET (safe) : 1 344 694 s − 89 200 = 1 255 494 s │
│ │
│ BÉNÉFICE SAFE : +... s │
│ POTENTIEL SO : +... s (si sell order rempli) │
│ │
│ RECOMMANDATION : INSTANT SELL (gain marginal SO insuffisant │
│ vs risque d'attente et undercut) │
╰────────────────────────────────────────────────────────────────────╯


### 7.2. Contraintes d'affichage

- Utiliser `rich` pour les cadres et couleurs
- Palette : neutre par défaut, vert pour marge safe positive > 50%, jaune pour 20-50%, rouge pour < 20%
- Freshness : ✓ (< 3h), ⚠ (3-6h), ✗ (> 6h)
- Aucun emoji autre que ces trois symboles

### 7.3. Checklist finale mise à jour

Après le top 5, afficher :

━━━ CHECK-LIST FRAÎCHEUR ━━━
[ ] Lymhurst : T7_WOOD (data 3.1h ⚠) — critique, prix bois est structurant
[ ] Bridgewatch : T6_PLANKS (data 5.7h ⚠) — critique, prix plank T-1
[ ] Lymhurst : T7_PLANKS (data 4.4h ⚠) — vente principale
...

━━━ CONSEILS TRADING ━━━

Ouvrir en jeu les pages listées ci-dessus pour rafraîchir la data
Relancer l'outil 30-60 secondes après pour obtenir les vrais prix
Confirmer le top buy order en jeu avant de committer sur instant sell
Ne jamais placer un sell order sans vérifier la profondeur du carnet

---

## 8. Checklist de non-régression

Avant de merger dans `main`, tous ces points doivent être verts :

- [ ] `uv run pytest` (ou `py -m pytest`) : 100% des tests existants passent
- [ ] Nouveaux tests des 5 fixes : tous verts
- [ ] Coverage maintenue ou améliorée : refining ≥ 100%, market ≥ 90%, optimizer ≥ 80%
- [ ] `ruff check .` : 0 warning
- [ ] `ruff format --check .` : 0 reformatage requis
- [ ] `mypy src/` en strict : 0 erreur
- [ ] Run réel `optimize --tier 7 --mode capital --capital 500000 --station-rate 50` : ne crash pas, sortie cohérente
- [ ] Run réel sur T4, T5, T6, T8 : ne crash pas
- [ ] Le mode T2 (`--tier 2`) ne crash pas (cas particulier sans plank T-1)
- [ ] Le JSON output contient bien les deux scénarios A et B pour chaque route
- [ ] Le README.md est à jour avec les nouvelles options et le nouveau format
- [ ] Un CHANGELOG.md est créé et documente V1.1.0

---

## 9. Livrables et workflow git

### 9.1. Commits attendus

Un commit atomique par fix, dans cet ordre imposé :

1. `fix(recipes): corrige les recettes de raffinage (bug critique wood_qty)`
2. `fix(output): affiche systematiquement les scenarios A et B cote a cote`
3. `fix(market): remplace la fill probability naive par une formule realiste`
4. `fix(recovery): applique le walk du carnet a la recuperation RRR`
5. `fix(freshness): pondere les revenus par un facteur de confiance fraicheur`

Plus les commits de doc et release :

6. `test: adapte les fixtures existantes aux nouvelles recettes et formules`
7. `docs(readme): met a jour le README avec le nouveau format de sortie`
8. `docs(changelog): ajoute CHANGELOG.md pour la V1.1.0`

### 9.2. Contraintes techniques

- Python 3.11+
- Chaque commit doit passer les checks (pytest, ruff, mypy) individuellement
- Zéro `# type: ignore` sans commentaire justifiant
- Type hints stricts partout
- Docstrings en français sur toutes les fonctions publiques modifiées

### 9.3. Fin de session — actions automatiques attendues

Une fois les 8 commits faits et tous les checks verts, Claude Code doit :

1. Push sur `origin fix/critical-bugs`
2. Créer un merge commit vers `main` : `git checkout main && git merge fix/critical-bugs --no-ff -m "Merge branch 'fix/critical-bugs' : corrections critiques post-test reel"`
3. Push `main` sur origin
4. Créer un tag `v1.1.0` : `git tag -a v1.1.0 -m "V1.1.0 : recettes corrigees, double scenario A/B, fill proba realiste"`
5. Push le tag : `git push origin v1.1.0`
6. Supprimer la branche `fix/critical-bugs` locale : `git branch -d fix/critical-bugs`
7. Optionnel : supprimer la branche distante : `git push origin --delete fix/critical-bugs`

### 9.4. Rapport final attendu

À la fin, Claude Code produit un résumé en français dans le terminal :

- Les 5 bugs fixés avec leur commit hash
- La couverture de tests finale par module
- Le résultat d'un run réel `optimize --tier 7 --mode capital --capital 500000 --station-rate 50` avant/après les fixes
- Le tag créé et le lien GitHub attendu

### 9.5. Aucune ambiguïté ne doit rester

Si un point de cette spec est ambigu ou contradictoire avec le SPEC.md original, Claude Code doit :
- Créer un `QUESTIONS.md` à la racine
- Stopper le travail
- Attendre validation manuelle avant de continuer

Pas de deviner, pas de raccourci.

---

**Fin du SPEC_FIX v1.0**