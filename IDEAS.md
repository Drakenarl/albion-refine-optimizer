# Idées pour V2 / V3 (hors périmètre V1)

Notes prises pendant l'implémentation de la V1. **Rien de ceci n'est implémenté** —
à traiter dans les versions ultérieures conformément au SPEC (sections 4.2, 4.3, 13).

## V2

- **Profondeur de carnet réelle** : l'endpoint `/prices` de l'AODP ne renvoie
  qu'un seul niveau de prix. Le module `market.walk_book` sait déjà parcourir un
  carnet multi-niveaux ; il suffira de le brancher sur une vraie source de
  profondeur (ou d'approximer via l'historique) pour lever le flag
  `PROFONDEUR_INCERTAINE`.
- **Coût de focus précis** : `config.FOCUS_PER_REFINE = 1.0` est une
  approximation (SPEC 8.3). En V2, calculer le focus réel par action à partir du
  niveau de spécialisation Plankmaster (Destiny Board) et du tier.
- **Récursion cascade des tiers** : décider ville par ville s'il vaut mieux
  acheter le plank T{N-1} ou le produire soi-même en descendant récursivement
  (memoization). Le découpage actuel (`SourcingLeg`) est déjà prêt à accueillir
  une branche « production ».
- **Split vente** : vendre une partie en instant sell et le reste en sell order.
  `market.best_scenario` choisit aujourd'hui le meilleur des deux ; un
  `split_sell_strategy` calculerait le mélange optimal.
- **Scraping des station fees** ou profils de station sauvegardés localement.
- **Mode batch** (`--tiers 6,7,8`) avec rapport comparatif.
- **Sauvegarde locale des runs** (historique JSON pour comparaison).
- **Afficher les deux scénarios (A et B) côte à côte** systématiquement, pas
  juste le meilleur. Le spread entre le top buy order (scénario A) et le sell
  order (scénario B) est une info critique pour évaluer le risque : quand le
  spread est énorme, la marge affichée du scénario B est théorique et suppose
  que le sell order sera rempli — ce qui n'est pas garanti à court terme.
  Actuellement l'outil masque cette info en ne retenant que le meilleur des
  deux.

## V3

- Backend FastAPI qui expose `optimize()` sans réécriture (la logique pure est
  déjà isolée du réseau et du terminal).
- Frontend Next.js 15 + Tailwind, badges de fraîcheur colorés, vue détail route.
- Bouton « Explique-moi cette route » via l'API Anthropic.

## Petites améliorations transverses

- Affiner la `fill_probability` (courbe de décroissance, saisonnalité) plutôt que
  le simple `min(1, volume/quantité)`.
- Créditer la récupération RRR même quand elle n'est pas revendable localement en
  la valorisant à un prix de référence (option `--recup-mode`).
