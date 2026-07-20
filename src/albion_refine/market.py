"""Logique de carnet d'ordres et de scénarios de vente.

Ce module prend des prix (primitifs ou ``PriceQuote``) et produit des
``SalesScenario`` évalués. Il contient :

- le *walker* de carnet d'ordres (formule SPEC 7.3) ;
- l'application des taxes (SPEC 3.3 / 6.5) ;
- l'estimation de *fill probability* (SPEC 7.7) ;
- l'évaluation des scénarios A (instant sell) et B (sell order).

Aucune I/O réseau ici.
"""

from __future__ import annotations

from datetime import timedelta
from typing import NamedTuple

from albion_refine import config
from albion_refine.models import FreshnessLevel, SalesScenario, SellStrategy


class WalkResult(NamedTuple):
    """Résultat d'un parcours de carnet d'ordres."""

    prix_moyen: float
    total_cost: float
    total_absorbed: int


def walk_book(book: list[tuple[float, int]], quantity_needed: int) -> WalkResult | None:
    """Parcourt un carnet d'ordres pour absorber ``quantity_needed`` unités.

    Le carnet est une liste de tuples ``(prix, quantité_disponible)`` déjà
    ordonnés (ascendant pour un achat, descendant pour une vente).

    Args:
        book: Carnet d'ordres, liste de ``(prix, quantité)``.
        quantity_needed: Quantité à absorber.

    Returns:
        Un ``WalkResult`` avec le prix moyen pondéré et le coût total, ou
        ``None`` si le carnet est vide, la quantité demandée est nulle/négative,
        ou la profondeur est insuffisante.
    """
    if quantity_needed <= 0:
        return None

    total_cost = 0.0
    total_absorbed = 0
    for prix, qte_disponible in book:
        if qte_disponible <= 0:
            continue
        prendre = min(qte_disponible, quantity_needed - total_absorbed)
        total_cost += prendre * prix
        total_absorbed += prendre
        if total_absorbed >= quantity_needed:
            break

    if total_absorbed < quantity_needed:
        return None

    return WalkResult(
        prix_moyen=total_cost / total_absorbed,
        total_cost=total_cost,
        total_absorbed=total_absorbed,
    )


# ---------------------------------------------------------------------------
# Fraîcheur des données
# ---------------------------------------------------------------------------


def classify_freshness(
    age: timedelta | None,
    warning_hours: float,
    critical_hours: float,
) -> FreshnessLevel:
    """Classe la fraîcheur d'un prix selon son âge.

    Args:
        age: Âge du prix (``None`` = timestamp manquant → traité comme critique).
        warning_hours: Seuil jaune (au-delà : ⚠).
        critical_hours: Seuil rouge (au-delà : ✗, exclu par défaut).

    Returns:
        Le niveau de fraîcheur correspondant.
    """
    if age is None:
        return FreshnessLevel.CRITICAL
    hours = age.total_seconds() / 3600.0
    if hours >= critical_hours:
        return FreshnessLevel.CRITICAL
    if hours >= warning_hours:
        return FreshnessLevel.WARNING
    return FreshnessLevel.FRESH


def age_hours(age: timedelta | None) -> float | None:
    """Convertit un ``timedelta`` en heures (ou ``None``)."""
    if age is None:
        return None
    return age.total_seconds() / 3600.0


# ---------------------------------------------------------------------------
# Taxes
# ---------------------------------------------------------------------------


def apply_instant_sell_tax(gross: float) -> float:
    """Applique la taxe d'instant sell (8%) à un revenu brut."""
    return gross * (1.0 - config.TAX_INSTANT_SELL)


def apply_sell_order_tax(gross: float) -> float:
    """Applique la taxe totale de sell order (5% setup + 8% sale = 13%)."""
    return gross * (1.0 - config.TAX_SELL_ORDER_TOTAL)


# ---------------------------------------------------------------------------
# Fill probability
# ---------------------------------------------------------------------------


def fill_probability(volume_24h: float, planks: int) -> float:
    """Estime la probabilité qu'un sell order soit rempli sous 24h.

    Approximation V1 : ``min(1.0, volume_24h / planks)`` (SPEC 7.7).

    Args:
        volume_24h: Volume échangé sur 24h dans la ville de vente.
        planks: Quantité de planks à écouler.

    Returns:
        Une probabilité entre 0 et 1. Vaut 0 si le volume ou la quantité est nul.
    """
    if planks <= 0 or volume_24h <= 0:
        return 0.0
    return min(1.0, volume_24h / planks)


# ---------------------------------------------------------------------------
# Scénarios de vente
# ---------------------------------------------------------------------------


def evaluate_instant_sell(
    city: str,
    buy_price_max: float,
    planks: int,
    *,
    data_age_hours: float | None = None,
) -> SalesScenario:
    """Évalue le scénario A (instant sell) : on remplit les buy orders existants.

    Args:
        city: Ville de vente.
        buy_price_max: Meilleur prix d'achat (top buy order) dans la ville.
        planks: Quantité de planks à vendre.
        data_age_hours: Âge du prix en heures (pour le rapport).

    Returns:
        Un ``SalesScenario`` de stratégie ``INSTANT_SELL``. ``stack_suffisant``
        est faux s'il n'existe aucun buy order exploitable.
    """
    walk = walk_book([(buy_price_max, planks)], planks) if buy_price_max > 0 else None
    if walk is None:
        return SalesScenario(
            strategy=SellStrategy.INSTANT_SELL,
            city=city,
            planks=planks,
            prix_unitaire_ref=buy_price_max,
            revenu_brut=0.0,
            revenu_net=0.0,
            fill_proba=1.0,
            expected_revenu=0.0,
            stack_suffisant=False,
            data_age_hours=data_age_hours,
        )
    revenu_net = apply_instant_sell_tax(walk.total_cost)
    return SalesScenario(
        strategy=SellStrategy.INSTANT_SELL,
        city=city,
        planks=planks,
        prix_unitaire_ref=buy_price_max,
        revenu_brut=walk.total_cost,
        revenu_net=revenu_net,
        fill_proba=1.0,
        expected_revenu=revenu_net,
        stack_suffisant=True,
        data_age_hours=data_age_hours,
    )


def evaluate_sell_order(
    city: str,
    min_sell_price: float,
    planks: int,
    volume_24h: float,
    *,
    undercut_pct: float = 1.0,
    data_age_hours: float | None = None,
) -> SalesScenario:
    """Évalue le scénario B (sell order) : on place un ordre sous-coté.

    Args:
        city: Ville de vente.
        min_sell_price: Prix du sell order le plus bas actuel.
        planks: Quantité de planks à écouler.
        volume_24h: Volume 24h de l'item dans la ville (pour la fill probability).
        undercut_pct: Sous-cote appliquée au prix de listing (défaut 1%).
        data_age_hours: Âge du prix en heures (pour le rapport).

    Returns:
        Un ``SalesScenario`` de stratégie ``SELL_ORDER``. ``stack_suffisant``
        est faux s'il n'existe aucun sell order de référence.
    """
    if min_sell_price <= 0:
        return SalesScenario(
            strategy=SellStrategy.SELL_ORDER,
            city=city,
            planks=planks,
            prix_unitaire_ref=min_sell_price,
            revenu_brut=0.0,
            revenu_net=0.0,
            fill_proba=0.0,
            expected_revenu=0.0,
            stack_suffisant=False,
            data_age_hours=data_age_hours,
        )
    prix_listing = min_sell_price * (1.0 - undercut_pct / 100.0)
    revenu_brut = prix_listing * planks
    revenu_net_if_filled = apply_sell_order_tax(revenu_brut)
    proba = fill_probability(volume_24h, planks)
    return SalesScenario(
        strategy=SellStrategy.SELL_ORDER,
        city=city,
        planks=planks,
        prix_unitaire_ref=prix_listing,
        revenu_brut=revenu_brut,
        revenu_net=revenu_net_if_filled,
        fill_proba=proba,
        expected_revenu=revenu_net_if_filled * proba,
        stack_suffisant=True,
        data_age_hours=data_age_hours,
    )


def best_scenario(scenarios: list[SalesScenario]) -> SalesScenario | None:
    """Retourne le scénario au meilleur revenu espéré (ou ``None`` si aucun).

    En cas d'égalité, l'instant sell (revenu certain) est préféré.

    Args:
        scenarios: Liste de scénarios candidats.

    Returns:
        Le meilleur scénario exploitable, ou ``None`` si la liste est vide ou
        qu'aucun scénario n'a de stack suffisant.
    """
    viables = [s for s in scenarios if s.stack_suffisant and s.expected_revenu > 0]
    if not viables:
        return None
    return max(
        viables,
        key=lambda s: (s.expected_revenu, s.strategy == SellStrategy.INSTANT_SELL),
    )
