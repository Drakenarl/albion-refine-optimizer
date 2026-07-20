"""Formules de raffinage : RRR, outputs et coût de station.

Module de **math pure** : aucune I/O, aucune dépendance réseau. Toutes les
formules proviennent de ``SPEC.md`` sections 3.2, 3.4, 7.1 et 7.2 (après
correction du format de coût station en silver / 100 nutrition).
"""

from __future__ import annotations

from albion_refine import config
from albion_refine.models import RefiningResult


def total_bonus_pct(focus: bool, daily_bonus_pct: int = 0) -> int:
    """Calcule le bonus total (%) de Resource Return Rate à Fort Sterling.

    Args:
        focus: Vrai si le focus est activé (+59%).
        daily_bonus_pct: Bonus quotidien de production (0, 10 ou 20).

    Returns:
        Le bonus cumulé en pourcentage : 58 (base FS bois) + focus + daily.
    """
    return (
        config.BASE_REFINING_BONUS_PCT + (config.FOCUS_BONUS_PCT if focus else 0) + daily_bonus_pct
    )


def compute_rrr(focus: bool, daily_bonus_pct: int = 0) -> float:
    """Calcule le Resource Return Rate effectif à Fort Sterling.

    Formule : ``RRR = 1 - 1 / (1 + bonus_total / 100)``.

    Args:
        focus: Vrai si le focus est activé.
        daily_bonus_pct: Bonus quotidien (0, 10 ou 20).

    Returns:
        Le RRR effectif, entre 0 et 1. Exemples : ~0.367 sans focus,
        ~0.539 avec focus seul, ~0.578 avec focus + daily 20%.
    """
    bonus = total_bonus_pct(focus, daily_bonus_pct)
    return 1.0 - 1.0 / (1.0 + bonus / 100.0)


def station_cost(quantity: int, tier: int, station_rate: float) -> float:
    """Calcule le coût de station en silver (format post-patch v19.000.1).

    Formule : ``coût = quantité × nutrition_par_unité(tier) × (rate / 100)``.

    Args:
        quantity: Nombre d'unités raffinées.
        tier: Tier du plank produit (4 à 8).
        station_rate: Rate de la station en silver par 100 nutrition.

    Returns:
        Le coût de station en silver (float, non arrondi).
    """
    return quantity * config.nutrition_per_unit(tier) * (station_rate / 100.0)


def input_quantities(tier: int, planks: int) -> tuple[int, int]:
    """Calcule les quantités d'inputs nécessaires pour produire ``planks`` unités.

    Applique la recette réelle (SPEC_FIX section 1.2) : pour un plank T7 il faut
    5 bois T7 et 1 plank T6, pas 1 et 1 comme le supposait la V1.0.

    Args:
        tier: Tier du plank produit (2 à 8).
        planks: Nombre de planks à produire.

    Returns:
        Un tuple ``(bois nécessaire, planks T-1 nécessaires)``. Le second vaut 0
        pour le T2, qui n'a pas d'input plank.
    """
    wood_qty, lower_qty = config.plank_recipe(tier)
    return planks * wood_qty, planks * lower_qty


def compute_input_cost(
    tier: int,
    planks: int,
    wood_price: float,
    lower_plank_price: float,
) -> float:
    """Calcule le coût d'achat des inputs pour produire ``planks`` unités.

    Args:
        tier: Tier du plank produit.
        planks: Nombre de planks à produire.
        wood_price: Prix unitaire du bois T{tier}.
        lower_plank_price: Prix unitaire du plank T{tier-1} (ignoré si la
            recette n'en consomme pas).

    Returns:
        Le coût total d'achat des inputs, en silver.
    """
    wood_needed, lower_needed = input_quantities(tier, planks)
    return wood_needed * wood_price + lower_needed * lower_plank_price


def unit_gross_cost(
    tier: int,
    wood_price: float,
    lower_plank_price: float,
    station_rate: float,
) -> float:
    """Calcule le coût brut de production d'UN plank (inputs + station).

    Formule SPEC_FIX section 2.5 : ``(wood_qty × prix_bois) +
    (lower_plank_qty × prix_plank_T-1) + coût_station_unitaire``. Utilisée par
    le mode ``capital`` pour dimensionner la quantité maximale finançable.

    Args:
        tier: Tier du plank produit.
        wood_price: Prix unitaire du bois T{tier}.
        lower_plank_price: Prix unitaire du plank T{tier-1}.
        station_rate: Rate de la station en silver par 100 nutrition.

    Returns:
        Le coût brut d'un plank produit, en silver.
    """
    return compute_input_cost(tier, 1, wood_price, lower_plank_price) + station_cost(
        1, tier, station_rate
    )


def focus_used(quantity: int) -> float:
    """Estime le focus consommé pour raffiner ``quantity`` unités.

    En V1 on retient ``FOCUS_PER_REFINE`` (≈1) par unité (SPEC section 8.3).

    Args:
        quantity: Nombre d'unités raffinées.

    Returns:
        Le focus total consommé.
    """
    return quantity * config.FOCUS_PER_REFINE


def refine(
    quantity: int,
    tier: int,
    *,
    focus: bool,
    daily_bonus_pct: int = 0,
    station_rate: float,
) -> RefiningResult:
    """Simule le raffinage de ``quantity`` unités de bois T{tier} à Fort Sterling.

    Combine le RRR (formule 7.1), les outputs (formule 7.2) et le coût de
    station (formule 3.4).

    Le RRR s'applique à **chaque unité d'input consommée** (SPEC_FIX 2.3) :
    pour 100 planks T7 on consomme 500 bois et 100 planks T6, donc le retour
    bois est ``500 × RRR`` et non ``100 × RRR``.

    Args:
        quantity: Nombre de planks produits (= nombre d'actions de raffinage).
        tier: Tier du plank produit (4 à 8).
        focus: Vrai si le focus est activé.
        daily_bonus_pct: Bonus quotidien (0, 10 ou 20).
        station_rate: Rate de la station en silver par 100 nutrition.

    Returns:
        Un ``RefiningResult`` avec planks produits, inputs consommés, retours
        RRR sur les deux inputs, coût de station, RRR effectif et focus consommé.
    """
    rrr = compute_rrr(focus, daily_bonus_pct)
    wood_needed, lower_needed = input_quantities(tier, quantity)
    return RefiningResult(
        planks_produits=quantity,
        wood_utilise=wood_needed,
        plank_moins_1_utilise=lower_needed,
        wood_retour=wood_needed * rrr,
        plank_moins_1_retour=lower_needed * rrr,
        cout_station=station_cost(quantity, tier, station_rate),
        rrr_effectif=rrr,
        focus_utilise=focus_used(quantity) if focus else 0.0,
    )
