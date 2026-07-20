# Changelog

Toutes les évolutions notables du projet sont documentées ici.
Le format suit [Keep a Changelog](https://keepachangelog.com/fr/1.1.0/) et le
versionnage suit [SemVer](https://semver.org/lang/fr/).

## [1.1.0] — 2026-07-20

Corrections critiques identifiées lors d'un test réel en jeu sur les planks T7
(voir `SPEC_FIX.md`). **La V1.0 ne doit plus être utilisée pour trader** : elle
surestimait massivement les marges.

### Corrigé

- **Recettes de raffinage** — les quantités d'inputs étaient codées en dur à
  `(1 bois, 1 plank T-1)` pour tous les tiers. Les vraies recettes sont
  désormais dans `config.PLANK_RECIPES` (T7 : **5 bois** + 1 plank T6, T8 : 5+1,
  T6 : 4+1, T5 : 3+1, T4/T3 : 2+1, T2 : 1+0). Le coût en bois brut était
  sous-estimé d'un facteur 5 au T7.
- **Retours RRR** — le RRR s'applique à chaque unité d'input consommée : pour
  100 planks T7, le retour est de `500 × RRR` bois et non `100 × RRR`.
- **Scénario A masqué** — l'outil n'affichait que le meilleur des deux scénarios
  de vente. Comme le scénario B avait une fill probability à 100%, il gagnait
  systématiquement et cachait l'instant sell, pourtant la seule option sûre.
  Les deux scénarios sont maintenant toujours affichés côte à côte, avec une
  ligne `RECOMMANDATION`.
- **Fill probability irréaliste** — `min(1, volume/quantité)` renvoyait 100% dès
  que le volume dépassait la quantité. Remplacée par une formule à trois
  facteurs (ratio volume plafonné, position estimée dans le carnet,
  compétitivité de l'undercut), plafonnée à 85%.
- **Récupération RRR sans vérification de profondeur** — la récup était créditée
  à `top_buy_price × quantité`, ce qui supposait qu'un buy order absorbe des
  milliers d'unités. Elle passe désormais par un walk du carnet d'achat et ne
  crédite que la part absorbable ; le reste est signalé comme non valorisé.
- **Absence de pondération par la fraîcheur** — un prix de 5h était traité comme
  aussi certain qu'un prix de 30 minutes. Le revenu de vente attendu est
  escompté par un facteur de confiance (1.00 / 0.95 / 0.85 / 0.70 / 0.50).

### Modifié

- La **marge affichée**, le **tri du top 5** et le filtre `--seuil-marge`
  portent désormais sur la marge **pondérée du scénario A**. Une route rentable
  uniquement en sell order est écartée ; son potentiel reste visible en titre.
- Une route sans buy order exploitable dans la ville de vente n'est plus
  produite : sans instant sell possible, il n'existe pas de marge sûre.
- Côté vente, une donnée de plus de 6h n'exclut plus la ville : elle est
  escomptée à 0.50. L'exclusion dure reste appliquée aux **prix d'achat**, qui
  ne sont pas pondérés. Sans ce changement, un marché aux buy orders anciens
  (cas observé sur T7 le 20/07/2026) ne retournait plus aucun candidat.
- La check-list de fraîcheur précise le rôle de chaque page marché et le rapport
  se termine par une section « conseils trading ».
- Le rapport du meilleur candidat écarté expose les marges A **et** B.

### Ajouté

- `refining.input_quantities`, `compute_input_cost`, `unit_gross_cost`.
- `market.compute_fill_probability`, `estimate_position_in_book`,
  `walk_book_descending`, `compute_recovery_value`,
  `freshness_confidence_factor`, `recommend_strategy`.
- Modèle `VenteBlock` exposant `scenario_a_instant_sell`,
  `scenario_b_sell_order` et `recommandation` dans la sortie JSON.
- Code d'avertissement `RECUP_PARTIELLE`.
- Suites de tests `tests/test_recipes.py` et `tests/test_non_regression.py`.

### Notes de compatibilité

- La structure JSON change : `routes[].vente` n'est plus un scénario unique mais
  un bloc à deux scénarios. `routes[].marge_pct` désigne la marge safe pondérée,
  `routes[].marge_pct_b` le potentiel sell order.
- L'endpoint `/history` est désormais interrogé pour les inputs à Fort Sterling
  (estimation de la profondeur du carnet pour la récup RRR).

### Limites connues

- L'AODP n'expose pas la profondeur réelle des carnets. La profondeur des buy
  orders est approximée par le volume 24h de l'item dans la ville, et la
  position dans le carnet de vente par une heuristique (1 si undercut, 3 sinon).
  Une vraie profondeur reste une amélioration V2 (voir `IDEAS.md`).
- Les tiers supportés par la CLI restent 4 à 8 : la nutrition des T2/T3 n'est
  pas documentée dans `items.json`. La table des recettes couvre malgré tout
  T2 à T8 et le code gère le cas sans plank T-1.

## [1.0.0] — 2026-07-19

Première version : CLI Python complète (config, modèles, client AODP, raffinage,
marché, optimiseur, formatters, CLI), 110 tests, sortie rich et JSON.
