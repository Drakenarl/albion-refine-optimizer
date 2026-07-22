"""Orchestrateur des phases 1 → 5 : sourcing, raffinage, vente, synthèse.

Ce module compose ``refining`` et ``market`` pour évaluer toutes les
combinaisons ``ville_bois × ville_plank × ville_vente``, applique les filtres et
le tri (SPEC sections 7.9 / 7.10) et retourne les meilleures routes.

La fonction pure ``optimize`` prend des données AODP déjà récupérées (donc
testable avec des fixtures, sans réseau). ``run_optimization`` ajoute la couche
réseau via ``AodpClient``.
"""

from __future__ import annotations

import math
from collections.abc import Callable
from datetime import UTC, datetime, timedelta

from pydantic import BaseModel, ConfigDict, Field

from albion_refine import config, market, refining
from albion_refine.aodp_client import AodpClient
from albion_refine.config import Resource, ResourceKind
from albion_refine.models import (
    DiscardedRoute,
    FreshnessLevel,
    OptimizationResult,
    PriceQuote,
    QuantityMode,
    RefreshChecklistItem,
    Route,
    RunMetadata,
    SalesScenario,
    SourcingAllocation,
    SourcingLeg,
    VenteBlock,
    VolumeData,
    WarningCode,
)

# Seuil de saturation : si la récup à vendre dépasse ce % du volume 24h de la
# ville de destination, on lève ``RECUP_SATURATION`` (tu risques d'écraser le
# carnet en dumpant tout d'un coup, notamment quand tu achètes et revends dans
# la même ville).
_SATURATION_RATIO: float = 0.50

# Marge sentinelle utilisée quand le coût net est nul ou négatif (route « gratuite »).
_MARGE_INFINIE = 1.0e9


class OptimizerParams(BaseModel):
    """Paramètres d'un run d'optimisation."""

    model_config = ConfigDict(frozen=True)

    tier: int
    mode: QuantityMode
    station_rate: float
    focus: bool = False
    daily_bonus_pct: int = 0
    capital: float | None = None
    quantite: int | None = None
    focus_available: float | None = None
    cost_per_focus: float = 0.0
    undercut_pct: float = float(config.DEFAULTS["sell_order_undercut_pct"])
    seuil_marge_min_pct: float = float(config.DEFAULTS["seuil_marge_min_pct"])
    seuil_fill_probability_pct: float = float(config.DEFAULTS["seuil_fill_probability_pct"])
    freshness_warning_hours: float = float(config.DEFAULTS["freshness_warning_hours"])
    freshness_critical_hours: float = float(config.DEFAULTS["freshness_critical_hours"])
    excluded_buy_cities: list[str] = Field(
        default_factory=lambda: list(config.DEFAULTS["excluded_buy_cities"])
    )
    excluded_sell_cities: list[str] = Field(
        default_factory=lambda: list(config.DEFAULTS["excluded_sell_cities"])
    )
    ignore_recup: bool = False
    # Filiere raffinee : bois (Fort Sterling) ou peau (Martlock). Ajoute en
    # V2.2 pour supporter plusieurs matieres sans changer la logique metier.
    resource: ResourceKind = ResourceKind.WOOD
    # Niveau d'enchantement (V2.3). 0 = base, 1..4 = .1 -> .4. La logique metier
    # est identique, seuls les item IDs demandes a l'AODP changent (suffixe
    # ``_LEVELn@n``). La recette (qte de matiere + qte de raffine T-1) reste
    # celle du tier.
    enchant: int = Field(default=0, ge=0, le=4)
    # V2.9 : sourcing multi-villes.
    # ``max_source_cities`` cap le nombre de villes visitees pour un meme input
    # (bois ou plank T-1). 1 = comportement V2.8 (mono-source), 3 = compromis
    # realiste, 6 = pas de cap. Contrainte reelle du joueur : temps de
    # transport et risque PvP entre villes.
    max_source_cities: int = Field(default=3, ge=1, le=6)
    # ``saturation_per_city`` = fraction du volume 24h qu'on est pret a racler
    # dans une ville avant de passer a la suivante (defaut 25%). Au-dela, on
    # ecrase le carnet et le slippage explose.
    saturation_per_city: float = Field(default=0.25, ge=0.05, le=1.0)
    top_n: int = 3

    def buy_cities(self) -> list[str]:
        """Villes autorisées à l'achat (toutes sauf les exclues)."""
        return [c for c in config.all_cities() if c not in self.excluded_buy_cities]

    def sell_cities(self) -> list[str]:
        """Villes autorisées à la vente (toutes sauf les exclues)."""
        return [c for c in config.all_cities() if c not in self.excluded_sell_cities]

    def resource_config(self) -> Resource:
        """Retourne la ``Resource`` derivee de ``self.resource``."""
        return config.resource(self.resource)


QuoteIndex = dict[tuple[str, str], PriceQuote]
VolumeIndex = dict[tuple[str, str], VolumeData]


def _index_quotes(quotes: list[PriceQuote]) -> QuoteIndex:
    return {(q.item_id, q.city): q for q in quotes}


def _index_volumes(volumes: list[VolumeData]) -> VolumeIndex:
    return {(v.item_id, v.city): v for v in volumes}


def _representative_age(quote: PriceQuote, now: datetime) -> timedelta | None:
    """Retourne l'âge le plus récent parmi les prix datés d'un quote."""
    ages = [a for a in (quote.sell_min_age(now), quote.buy_max_age(now)) if a is not None]
    return min(ages) if ages else None


def _resolve_quantity(params: OptimizerParams, unit_gross_cost: float) -> int:
    """Détermine la quantité à raffiner selon le mode.

    Args:
        params: Paramètres du run.
        unit_gross_cost: Coût brut par unité (utilisé en mode capital).

    Returns:
        La quantité entière à raffiner (0 si non calculable).
    """
    match params.mode:
        case QuantityMode.FIXED:
            return params.quantite or 0
        case QuantityMode.FOCUS:
            if not params.focus_available:
                return 0
            return int(params.focus_available // config.FOCUS_PER_REFINE)
        case QuantityMode.CAPITAL:
            if not params.capital or unit_gross_cost <= 0:
                return 0
            return int(params.capital // unit_gross_cost)


def _build_allocation(
    quote: PriceQuote,
    take_qty: int,
    volume_24h: float,
    now: datetime,
    params: OptimizerParams,
) -> SourcingAllocation:
    """Construit une ``SourcingAllocation`` avec slippage recalcule."""
    age = quote.sell_min_age(now)
    age_hours_value = market.age_hours(age)
    freshness = market.classify_freshness(
        age, params.freshness_warning_hours, params.freshness_critical_hours
    )
    inflation = market.buy_side_inflation(
        quantity=take_qty,
        volume_24h=volume_24h,
        age_hours_value=age_hours_value,
    )
    prix_ref = float(quote.sell_price_min)
    prix_effectif = prix_ref * inflation.total_factor
    return SourcingAllocation(
        city=quote.city,
        quantite=take_qty,
        prix_ref=prix_ref,
        prix_unitaire=prix_effectif,
        cout_total=take_qty * prix_effectif,
        slippage_pct=(inflation.total_factor - 1.0) * 100.0,
        slippage_qty_pct=inflation.slippage_qty * 100.0,
        slippage_age_pct=inflation.inflation_age * 100.0,
        data_age_hours=age_hours_value,
        freshness=freshness,
    )


def _allocate_input(
    item_id: str,
    quantity_needed: int,
    params: OptimizerParams,
    quotes: QuoteIndex,
    volumes: VolumeIndex,
    now: datetime,
) -> list[SourcingAllocation]:
    """Alloue ``quantity_needed`` unites de ``item_id`` sur plusieurs villes.

    Algorithme (Option A greedy simple, V2.9) :
    1. Rassemble les villes candidates (quote valide + non critique).
    2. Trie par ``sell_price_min`` ascendant.
    3. Iteratif : prend ``min(qte_restante, volume_24h × saturation_per_city)``
       a chaque ville puis passe a la suivante, jusqu'a ``max_source_cities``
       villes atteintes ou quantite comblee.
    4. S'il reste de la quantite non allouee apres saturation naturelle des
       villes autorisees, on repartit le reste sur les allocations existantes
       (par ordre inverse de prix, en acceptant plus de slippage).

    Returns:
        La liste des allocations (potentiellement vide si aucun candidat).
    """
    candidates: list[tuple[PriceQuote, float]] = []
    for city in params.buy_cities():
        quote = quotes.get((item_id, city))
        if quote is None or not quote.has_sell_offer:
            continue
        if _leg_is_critical(quote, now, params):
            continue
        vol = volumes.get((item_id, city))
        vol_24h = vol.total_volume_24h if vol is not None else 0.0
        candidates.append((quote, vol_24h))

    if not candidates:
        return []

    candidates.sort(key=lambda c: c[0].sell_price_min)

    remaining = quantity_needed
    allocations: list[SourcingAllocation] = []
    # Index (city -> (quote, vol_24h)) pour retrouver vite les infos d'une ville.
    by_city = {q.city: (q, v) for q, v in candidates}

    for quote, vol_24h in candidates:
        if remaining <= 0:
            break
        if len(allocations) >= params.max_source_cities:
            break
        if vol_24h > 0:
            city_cap = max(1, int(vol_24h * params.saturation_per_city))
            take = min(remaining, city_cap)
        else:
            take = min(remaining, max(1, quantity_needed // 10))
        if take <= 0:
            continue

        # Proposition : ajouter une nouvelle allocation dans cette ville.
        proposed = _build_allocation(quote, take, vol_24h, now, params)

        # Alternative : etendre la derniere allocation (rester dans la meme ville
        # cheapest, meme si le slippage grimpe). On garde ce qui coute le moins
        # en cout marginal (nouveau cout - cout deja engage).
        if allocations:
            last = allocations[-1]
            last_quote, last_vol = by_city[last.city]
            extended_qty = last.quantite + take
            extended = _build_allocation(last_quote, extended_qty, last_vol, now, params)
            marginal_cost_extend = extended.cout_total - last.cout_total
            if marginal_cost_extend <= proposed.cout_total:
                # Rester dans la ville precedente est plus economique -> on
                # etend au lieu d'ouvrir un nouveau front.
                allocations[-1] = extended
                remaining -= take
                continue

        allocations.append(proposed)
        remaining -= take

    if remaining > 0 and allocations:
        # Reste a placer apres saturation des villes autorisees : on etend la
        # derniere allocation en acceptant plus de slippage (cape a +25%).
        last = allocations[-1]
        last_quote, last_vol = by_city[last.city]
        new_qty = last.quantite + remaining
        allocations[-1] = _build_allocation(last_quote, new_qty, last_vol, now, params)
        remaining = 0

    return allocations


def _leg_from_allocations(
    kind: str, item_id: str, tier: int, allocations: list[SourcingAllocation]
) -> SourcingLeg:
    """Agrege une liste d'allocations en un ``SourcingLeg`` (V2.9).

    Les champs de synthese (``prix_unitaire``, ``prix_ref``, ``slippage_pct``,
    ``data_age_hours``) sont des moyennes ponderees par la quantite. La ville
    principale est celle qui porte le plus gros volume alloue. La fraicheur
    est la pire des allocations (conservateur).
    """
    total_qty = sum(a.quantite for a in allocations)
    if total_qty == 0:
        raise ValueError("Allocations vides ou quantite nulle")
    total_cost = sum(a.cout_total for a in allocations)
    prix_ref_pondere = sum(a.quantite * a.prix_ref for a in allocations) / total_qty
    slippage_pondere = sum(a.quantite * a.slippage_pct for a in allocations) / total_qty
    slippage_qty_pondere = sum(a.quantite * a.slippage_qty_pct for a in allocations) / total_qty
    slippage_age_pondere = sum(a.quantite * a.slippage_age_pct for a in allocations) / total_qty
    # Age moyen pondere sur les allocations qui ont une donnee d'age.
    ages_valides = [(a.quantite, a.data_age_hours) for a in allocations if a.data_age_hours is not None]
    age_pondere: float | None = None
    if ages_valides:
        total_valid_qty = sum(q for q, _ in ages_valides)
        age_pondere = sum(q * age for q, age in ages_valides) / total_valid_qty
    # Fraicheur = la pire (ordre CRITICAL > WARNING > UNKNOWN > FRESH).
    fresh_priority = {
        FreshnessLevel.CRITICAL: 3,
        FreshnessLevel.WARNING: 2,
        FreshnessLevel.UNKNOWN: 1,
        FreshnessLevel.FRESH: 0,
    }
    worst_fresh = max(allocations, key=lambda a: fresh_priority[a.freshness]).freshness
    # Ville principale = celle qui porte le plus gros.
    main_city = max(allocations, key=lambda a: a.quantite).city
    return SourcingLeg(
        kind=kind,
        item_id=item_id,
        tier=tier,
        city=main_city,
        prix_unitaire=total_cost / total_qty,
        prix_ref=prix_ref_pondere,
        slippage_pct=slippage_pondere,
        slippage_qty_pct=slippage_qty_pondere,
        slippage_age_pct=slippage_age_pondere,
        quantite=total_qty,
        cout_total=total_cost,
        data_age_hours=age_pondere,
        freshness=worst_fresh,
        allocations=allocations,
    )


def _recuperation(
    quote: PriceQuote | None,
    volume: VolumeData | None,
    retour: float,
    ignore: bool,
    now: datetime,
) -> market.RecoveryResult:
    """Valorise les retours RRR en instant sell dans la ville de vente choisie.

    L'AODP n'expose pas la profondeur des buy orders : on estime le stack
    absorbable par le **volume échangé sur 24h** de l'item dans la ville
    ciblée. Sans historique exploitable, on ne crédite rien plutôt que de
    supposer une profondeur infinie (choix conservateur, SPEC_FIX 5.3).

    En V2, la ville n'est plus figée à Fort Sterling : la récup est vendue
    dans la même ville que les raffinés finis (workflow réaliste). L'âge du
    ``buy_max`` est propagé pour appliquer le facteur de confiance fraîcheur
    (V2.1), sans quoi un carnet vieux de 13h avec un prix élevé gonflerait
    artificiellement la récup et biaiserait le choix de la ville de vente.

    Args:
        quote: Prix de l'item dans la ville où la récup sera vendue.
        volume: Volume 24h de l'item dans cette ville (profondeur estimée).
        retour: Quantité retournée par le RRR.
        ignore: Vrai pour désactiver complètement la récupération.
        now: Instant de référence pour calculer l'âge du ``buy_max``.

    Returns:
        Un ``RecoveryResult`` (valeur nette de taxe, quantité absorbée/demandée).
    """
    demande = int(retour)
    if ignore or quote is None or not quote.has_buy_offer:
        return market.RecoveryResult(valeur=0.0, absorbe=0, demande=demande)
    profondeur = int(volume.total_volume_24h) if volume is not None else 0
    book = [(float(quote.buy_price_max), profondeur)]
    return market.compute_recovery_value(
        retour, book, data_age_hours=market.age_hours(quote.buy_max_age(now))
    )


def _evaluate_sales(
    output_quote: PriceQuote | None,
    volume: VolumeData | None,
    quantity: int,
    now: datetime,
    params: OptimizerParams,
) -> VenteBlock | None:
    """Évalue les deux scénarios de vente d'une ville et les retourne côte à côte.

    Contrairement à la V1.0, aucun des deux n'est masqué : le scénario A est le
    revenu safe, le scénario B le potentiel conditionnel (SPEC_FIX section 3).

    Côté vente, une donnée périmée n'exclut plus la ville : elle est escomptée
    par le facteur de confiance fraîcheur, qui descend à 0.50 au-delà de 6h
    (SPEC_FIX section 6). L'exclusion dure reste appliquée aux prix d'achat,
    qui ne sont pas pondérés.

    Returns:
        Un ``VenteBlock``, ou ``None`` si le scénario A n'est pas exploitable
        (sans buy order il n'existe pas de marge safe, donc pas de route).
    """
    if output_quote is None:
        return None

    # Scénario A — instant sell (on remplit les buy orders).
    buy_age = output_quote.buy_max_age(now)
    if not output_quote.has_buy_offer:
        return None
    scenario_a = market.evaluate_instant_sell(
        output_quote.city,
        float(output_quote.buy_price_max),
        quantity,
        data_age_hours=market.age_hours(buy_age),
    )

    # Scénario B — sell order (on place un ordre sous-coté).
    scenario_b: SalesScenario | None = None
    sell_age = output_quote.sell_min_age(now)
    if output_quote.has_sell_offer:
        volume_24h = volume.total_volume_24h if volume is not None else 0.0
        scenario_b = market.evaluate_sell_order(
            output_quote.city,
            float(output_quote.sell_price_min),
            quantity,
            volume_24h,
            undercut_pct=params.undercut_pct,
            data_age_hours=market.age_hours(sell_age),
        )
        gain = scenario_b.expected_revenu - scenario_a.expected_revenu
        scenario_b.gain_marginal_vs_a = gain
        scenario_b.gain_marginal_pct = (
            gain / scenario_a.expected_revenu * 100.0 if scenario_a.expected_revenu > 0 else None
        )

    return VenteBlock(
        ville=output_quote.city,
        scenario_a_instant_sell=scenario_a,
        scenario_b_sell_order=scenario_b,
        recommandation=market.recommend_strategy(
            scenario_a,
            scenario_b,
            min_fill_proba=params.seuil_fill_probability_pct / 100.0,
        ),
    )


def _annotate_margins(
    scenario: SalesScenario | None, cout_total: float, cout_net: float
) -> None:
    """Renseigne bénéfice, ROI capital et marge efficacité d'un scénario.

    Deux marges sont calculées :
    - ``marge_pct`` = ROI sur capital dépensé (bénéfice / ``cout_total``) — la
      marge que le trader voit sur sa banque, et celle qui pilote le tri V2.
    - ``marge_efficacite_pct`` = ancienne formule V1 (bénéfice / ``cout_net``
      après récup) — laissée en secondaire pour comparaison honnête.

    Args:
        scenario: Scénario à annoter (ignoré s'il est ``None``).
        cout_total: Coût brut dépensé (matériel + station + focus).
        cout_net: Coût total moins récupération RRR.
    """
    if scenario is None:
        return
    scenario.benefice = scenario.expected_revenu - cout_net
    scenario.marge_pct = (
        scenario.benefice / cout_total * 100.0 if cout_total > 0 else _MARGE_INFINIE
    )
    scenario.marge_efficacite_pct = (
        scenario.benefice / cout_net * 100.0 if cout_net > 0 else _MARGE_INFINIE
    )


def _collect_warnings(
    cities: set[str],
    legs_fresh: list[FreshnessLevel],
    volume: VolumeData | None,
    quantity: int,
) -> list[WarningCode]:
    """Rassemble les avertissements d'une route (zone rouge, data jaune, profondeur)."""
    warnings: list[WarningCode] = []
    if config.RED_ZONE_CITY in cities:
        warnings.append(WarningCode.ROUTE_ZONE_ROUGE)
    if any(f == FreshnessLevel.WARNING for f in legs_fresh):
        warnings.append(WarningCode.DATA_JAUNE)
    if volume is not None and volume.total_volume_24h < quantity:
        warnings.append(WarningCode.PROFONDEUR_INCERTAINE)
    return warnings


def _cheapest_candidate(
    item_id: str | None,
    params: OptimizerParams,
    quotes: QuoteIndex,
    now: datetime,
) -> PriceQuote | None:
    """Retourne le quote au sell_price_min le plus bas parmi les villes valides."""
    if item_id is None:
        return None
    best: PriceQuote | None = None
    for city in params.buy_cities():
        q = quotes.get((item_id, city))
        if q is None or not q.has_sell_offer:
            continue
        if _leg_is_critical(q, now, params):
            continue
        if best is None or q.sell_price_min < best.sell_price_min:
            best = q
    return best


def _build_route(
    params: OptimizerParams,
    *,
    wood_item: str,
    plank_input_item: str | None,
    output_quote: PriceQuote,
    volume: VolumeData | None,
    quotes: QuoteIndex,
    volumes: VolumeIndex,
    now: datetime,
) -> Route | None:
    """Evalue une route complete et retourne une ``Route`` (ou ``None``).

    V2.9 : le sourcing est desormais multi-villes. Au lieu d'une paire fixee
    (wood_city, plank_city), on alloue automatiquement la quantite requise sur
    plusieurs villes via ``_allocate_input`` (greedy tri par prix + saturation
    per city).
    """
    tier = params.tier

    # Bootstrap de la quantite : on utilise le prix le plus bas des candidats
    # trouves (approximation raisonnable ; l'allocation reelle peut coûter
    # marginalement plus mais l'ordre de grandeur reste bon en mode capital).
    cheapest_wood = _cheapest_candidate(wood_item, params, quotes, now)
    if cheapest_wood is None:
        return None
    cheapest_plank: PriceQuote | None = None
    if plank_input_item is not None:
        cheapest_plank = _cheapest_candidate(plank_input_item, params, quotes, now)
        if cheapest_plank is None:
            return None
    plank_price_boot = float(cheapest_plank.sell_price_min) if cheapest_plank else 0.0
    unit_gross = refining.unit_gross_cost(
        tier, float(cheapest_wood.sell_price_min), plank_price_boot, params.station_rate
    )
    quantity = _resolve_quantity(params, unit_gross)
    if quantity <= 0:
        return None

    refined = refining.refine(
        quantity,
        tier,
        focus=params.focus,
        daily_bonus_pct=params.daily_bonus_pct,
        station_rate=params.station_rate,
    )

    sale = _evaluate_sales(output_quote, volume, quantity, now, params)
    if sale is None:
        return None

    # V2.9 : allocation multi-villes de chaque input.
    wood_allocations = _allocate_input(
        wood_item, refined.wood_utilise, params, quotes, volumes, now
    )
    if not wood_allocations:
        return None
    wood_leg = _leg_from_allocations("wood", wood_item, tier, wood_allocations)

    plank_leg: SourcingLeg | None = None
    if plank_input_item is not None and refined.plank_moins_1_utilise > 0:
        plank_allocations = _allocate_input(
            plank_input_item, refined.plank_moins_1_utilise, params, quotes, volumes, now
        )
        if not plank_allocations:
            return None
        plank_leg = _leg_from_allocations("plank", plank_input_item, tier - 1, plank_allocations)

    cout_focus = refined.focus_utilise * params.cost_per_focus
    cout_plank = plank_leg.cout_total if plank_leg is not None else 0.0
    cout_total = wood_leg.cout_total + cout_plank + refined.cout_station + cout_focus

    # La recup RRR est toujours vendue dans la meme ville que les raffines finis.
    recup_city = output_quote.city
    recup_wood = _recuperation(
        quotes.get((wood_item, recup_city)),
        volumes.get((wood_item, recup_city)),
        refined.wood_retour,
        params.ignore_recup,
        now,
    )
    recup_plank = (
        _recuperation(
            quotes.get((plank_input_item, recup_city)),
            volumes.get((plank_input_item, recup_city)),
            refined.plank_moins_1_retour,
            params.ignore_recup,
            now,
        )
        if plank_input_item is not None
        else market.RecoveryResult(valeur=0.0, absorbe=0, demande=0)
    )
    recup_totale = recup_wood.valeur + recup_plank.valeur
    cout_net = cout_total - recup_totale

    scenario_a = sale.scenario_a_instant_sell
    if scenario_a is None:  # pragma: no cover - garanti par _evaluate_sales
        return None
    _annotate_margins(scenario_a, cout_total, cout_net)
    _annotate_margins(sale.scenario_b_sell_order, cout_total, cout_net)

    # La marge « safe » (scénario A) pilote le tri et le filtrage. Depuis V2,
    # la marge principale est la ROI sur capital dépensé (pas l'ancienne
    # formule benefice / cout_net, qui gonflait artificiellement le %).
    benefice = scenario_a.expected_revenu - cout_net
    marge_pct = scenario_a.marge_pct if scenario_a.marge_pct is not None else _MARGE_INFINIE
    marge_efficacite_pct = (
        scenario_a.marge_efficacite_pct
        if scenario_a.marge_efficacite_pct is not None
        else _MARGE_INFINIE
    )
    scenario_b = sale.scenario_b_sell_order
    silver_par_focus = (
        benefice / refined.focus_utilise if params.focus and refined.focus_utilise > 0 else None
    )

    chosen_fresh = market.classify_freshness(
        output_quote.buy_max_age(now),
        params.freshness_warning_hours,
        params.freshness_critical_hours,
    )
    # V2.9 : les villes visitees sont l'union des allocations + la ville de vente.
    cities = {output_quote.city}
    cities.update(a.city for a in wood_leg.allocations)
    legs_fresh = [wood_leg.freshness, chosen_fresh]
    if plank_leg is not None:
        cities.update(a.city for a in plank_leg.allocations)
        legs_fresh.append(plank_leg.freshness)
    warnings = _collect_warnings(cities, legs_fresh, volume, quantity)
    if recup_wood.partielle or recup_plank.partielle:
        warnings.append(WarningCode.RECUP_PARTIELLE)
    if _recup_saturates(recup_wood, recup_plank, wood_item, plank_input_item, recup_city, volumes):
        warnings.append(WarningCode.RECUP_SATURATION)
    # V2.7 : signale un slippage buy > 8% sur au moins une jambe.
    wood_slippage = wood_leg.slippage_pct or 0.0
    plank_slippage = plank_leg.slippage_pct or 0.0 if plank_leg is not None else 0.0
    if max(wood_slippage, plank_slippage) >= 8.0:
        warnings.append(WarningCode.BUY_SLIPPAGE_ELEVE)
    # V2.8 : marche mort si au moins une allocation a un volume 24h nul (le
    # slippage_qty_pct de la composante y vaut alors son max, 20%).
    wood_inactive = any(a.slippage_qty_pct >= 20.0 for a in wood_leg.allocations)
    plank_inactive = plank_leg is not None and any(
        a.slippage_qty_pct >= 20.0 for a in plank_leg.allocations
    )
    if wood_inactive or plank_inactive:
        warnings.append(WarningCode.MARCHE_INACTIF)

    return Route(
        tier=tier,
        resource_kind=params.resource,
        enchant=params.enchant,
        quantite=quantity,
        achat_wood=wood_leg,
        achat_plank=plank_leg,
        raffinage=refined,
        vente=sale,
        recup_wood=recup_wood.valeur,
        recup_plank=recup_plank.valeur,
        recup_wood_absorbe=recup_wood.absorbe,
        recup_wood_demande=recup_wood.demande,
        recup_plank_absorbe=recup_plank.absorbe,
        recup_plank_demande=recup_plank.demande,
        recup_totale=recup_totale,
        recup_city=recup_city,
        cout_total=cout_total,
        cout_net=cout_net,
        revenu_effectif=scenario_a.expected_revenu,
        benefice=benefice,
        marge_pct=marge_pct,
        marge_efficacite_pct=marge_efficacite_pct,
        benefice_b=scenario_b.benefice if scenario_b is not None else None,
        marge_pct_b=scenario_b.marge_pct if scenario_b is not None else None,
        marge_efficacite_pct_b=(
            scenario_b.marge_efficacite_pct if scenario_b is not None else None
        ),
        silver_par_focus=silver_par_focus,
        warnings=warnings,
    )


def _recup_saturates(
    recup_wood: market.RecoveryResult,
    recup_plank: market.RecoveryResult,
    wood_item: str,
    plank_input_item: str | None,
    recup_city: str,
    volumes: VolumeIndex,
) -> bool:
    """Vrai si la récup à écouler dépasse ``_SATURATION_RATIO`` du volume 24h."""

    def _saturates(res: market.RecoveryResult, item_id: str) -> bool:
        if res.demande <= 0:
            return False
        vol = volumes.get((item_id, recup_city))
        if vol is None or vol.total_volume_24h <= 0:
            return False
        return res.demande > _SATURATION_RATIO * vol.total_volume_24h

    if _saturates(recup_wood, wood_item):
        return True
    return plank_input_item is not None and _saturates(recup_plank, plank_input_item)


def _sort_key(params: OptimizerParams) -> Callable[[Route], tuple[float, float]]:
    """Retourne la clé de tri adaptée au mode (focus vs marge)."""
    if params.focus:
        return lambda r: (r.silver_par_focus or 0.0, r.marge_pct)
    return lambda r: (r.marge_pct, r.benefice)


def _build_checklist(
    routes: list[Route], quotes: QuoteIndex, now: datetime, params: OptimizerParams
) -> list[RefreshChecklistItem]:
    """Construit la check-list des pages marché à rafraîchir (par ordre d'apparition)."""
    seen: set[tuple[str, str]] = set()
    checklist: list[RefreshChecklistItem] = []
    res = params.resource_config()
    for route in routes:
        pairs = [
            (
                route.achat_wood.item_id,
                route.achat_wood.city,
                f"critique, le prix du {res.display_raw} structure le coût",
            ),
        ]
        if route.achat_plank is not None:
            pairs.append(
                (
                    route.achat_plank.item_id,
                    route.achat_plank.city,
                    f"critique, prix du {res.display_refined} T-1",
                )
            )
        pairs.append(
            (
                res.refined_item_id(route.tier, route.enchant),
                route.vente.ville,
                "vente principale",
            )
        )
        for item_id, city, role in pairs:
            if (item_id, city) in seen:
                continue
            seen.add((item_id, city))
            quote = quotes.get((item_id, city))
            age = _representative_age(quote, now) if quote is not None else None
            checklist.append(
                RefreshChecklistItem(
                    city=city,
                    item_id=item_id,
                    age_hours=market.age_hours(age),
                    freshness=market.classify_freshness(
                        age,
                        params.freshness_warning_hours,
                        params.freshness_critical_hours,
                    ),
                    role=role,
                )
            )
    return checklist


def _discarded_report(route: Route, params: OptimizerParams) -> DiscardedRoute:
    """Convertit une route écartée en rapport lisible avec suggestions."""
    res = params.resource_config()
    plank_src = (
        f" + {res.display_refined} T-1 @ {route.achat_plank.city}" if route.achat_plank else ""
    )
    description = (
        f"{res.display_raw.capitalize()} T{route.tier} @ {route.achat_wood.city}{plank_src} "
        f"→ raffinage {res.refining_city} → vente @ {route.vente.ville}"
    )
    return DiscardedRoute(
        description=description,
        marge_pct=round(route.marge_pct, 1),
        marge_pct_b=(round(route.marge_pct_b, 1) if route.marge_pct_b is not None else None),
        marge_efficacite_pct=round(route.marge_efficacite_pct, 1),
        raison=(
            f"ROI capital {route.marge_pct:.1f}% < seuil {params.seuil_marge_min_pct:.0f}%"
        ),
        suggestions=[
            f"Baisser le seuil ROI à {math.floor(route.marge_pct)}% pour voir cette route",
            "Attendre un rafraîchissement des prix (données trop vieilles)",
            "Essayer un autre tier",
        ],
    )


def _discarded_top(
    candidates: list[Route], params: OptimizerParams, n: int
) -> list[DiscardedRoute]:
    """Retourne les ``n`` meilleurs candidats écartés, triés par ROI décroissante."""
    ordered = sorted(candidates, key=lambda r: r.marge_pct, reverse=True)
    return [_discarded_report(route, params) for route in ordered[:n]]


def _plank_input_item(tier: int, res: Resource, enchant: int = 0) -> str | None:
    """Retourne l'item ID du raffine T-1 requis par la recette, ou ``None`` (T2).

    Le T-1 herite du meme enchant que le tier produit : un T7 .2 plank consomme
    du T6 .2 plank, pas du T6 base.
    """
    if config.lower_plank_qty_per_plank(tier) == 0:
        return None
    return res.refined_item_id(tier - 1, enchant)


def optimize(
    params: OptimizerParams,
    quotes_list: list[PriceQuote],
    volumes_list: list[VolumeData],
    now: datetime,
) -> OptimizationResult:
    """Calcule les meilleures routes à partir de données AODP déjà récupérées.

    Args:
        params: Paramètres du run.
        quotes_list: Prix courants (tous items/villes nécessaires).
        volumes_list: Volumes 24h des planks de sortie.
        now: Instant de référence pour la fraîcheur.

    Returns:
        Un ``OptimizationResult`` avec les routes triées (top N), la check-list
        de fraîcheur et, le cas échéant, le meilleur candidat écarté.
    """
    quotes = _index_quotes(quotes_list)
    volumes = _index_volumes(volumes_list)

    res = params.resource_config()
    wood_item = res.raw_item_id(params.tier, params.enchant)
    plank_input_item = _plank_input_item(params.tier, res, params.enchant)
    output_item = res.refined_item_id(params.tier, params.enchant)

    # V2.9 : plus de boucle wood_city/plank_city. L'allocation multi-villes
    # est calculee UNE fois pour chaque input, puis on boucle uniquement sur
    # les sell_cities (car chaque destination donne un revenu different et une
    # ville de recup differente).
    candidates: list[Route] = []
    for sell_city in params.sell_cities():
        output_quote = quotes.get((output_item, sell_city))
        if output_quote is None:
            continue
        route = _build_route(
            params,
            wood_item=wood_item,
            plank_input_item=plank_input_item,
            output_quote=output_quote,
            volume=volumes.get((output_item, sell_city)),
            quotes=quotes,
            volumes=volumes,
            now=now,
        )
        if route is not None:
            candidates.append(route)

    # V2.8.1 : on garde toujours les top_n meilleures routes par ROI, meme si
    # elles ne passent pas le seuil. Le seuil devient purement informationnel
    # (le header du frontend colore "rentable" vs "deficitaire"). Cela evite
    # que les runs qui deviendraient tres serres (apres recalibrage slippage
    # V2.8) affichent 0 ou 1 route au lieu des 3 attendues.
    all_sorted = sorted(candidates, key=_sort_key(params), reverse=True)
    top = all_sorted[: params.top_n]
    for rank, route in enumerate(top, start=1):
        route.rank = rank

    discarded_best: DiscardedRoute | None = None
    discarded_top: list[DiscardedRoute] = []
    # ``discarded_top`` reste utile pour les cas ou meme les top_n sont trop
    # mauvaises (par ex. tous negatifs) : on expose les alternatives pour aider
    # l'utilisateur a arbitrer. On les prend parmi les candidats sous seuil.
    below_seuil = [r for r in candidates if r.marge_pct < params.seuil_marge_min_pct]
    if not top and below_seuil:
        discarded_top = _discarded_top(below_seuil, params, params.top_n)
        discarded_best = discarded_top[0] if discarded_top else None

    return OptimizationResult(
        run_metadata=RunMetadata(
            timestamp=now,
            tier=params.tier,
            mode=params.mode,
            params=params.model_dump(mode="json"),
        ),
        routes=top,
        refresh_checklist=_build_checklist(top, quotes, now, params),
        discarded_best=discarded_best,
        discarded_top=discarded_top,
    )


def _leg_is_critical(quote: PriceQuote, now: datetime, params: OptimizerParams) -> bool:
    """Vrai si le prix d'achat (sell order) est trop vieux (rouge critique)."""
    freshness = market.classify_freshness(
        quote.sell_min_age(now),
        params.freshness_warning_hours,
        params.freshness_critical_hours,
    )
    return freshness == FreshnessLevel.CRITICAL


async def run_optimization(
    params: OptimizerParams,
    *,
    server: str = "europe",
    use_cache: bool = True,
    now: datetime | None = None,
) -> OptimizationResult:
    """Récupère les données AODP puis lance l'optimisation.

    Args:
        params: Paramètres du run.
        server: Serveur AODP.
        use_cache: Active/désactive le cache local.
        now: Instant de référence (défaut : ``datetime.utcnow()``).

    Returns:
        Le résultat complet de l'optimisation.
    """
    # AODP fournit des timestamps UTC naïfs : on aligne notre référence dessus.
    reference = now or datetime.now(tz=UTC).replace(tzinfo=None)
    res = params.resource_config()
    wood_item = res.raw_item_id(params.tier, params.enchant)
    plank_input_item = _plank_input_item(params.tier, res, params.enchant)
    output_item = res.refined_item_id(params.tier, params.enchant)

    items = [item for item in (wood_item, plank_input_item, output_item) if item is not None]
    all_buy = sorted(set(params.buy_cities()) | set(params.sell_cities()))
    # Les volumes servent a :
    # - fill probability (planks de sortie a la sell_city)
    # - recuperation RRR (retours du raffinage vendus a la sell_city)
    # - slippage buy-side V2.7 (profondeur estimee du carnet au buy_city)
    # On les demande donc sur toutes les villes candidates.
    history_cities = all_buy
    async with AodpClient(server=server, use_cache=use_cache) as client:
        quotes = await client.get_prices(items, all_buy)
        # V2.8 : fenetre glissante 24h ancree sur ``reference`` (evite de
        # cumuler ~10 jours d'historique et de surestimer 10x le volume).
        volumes = await client.get_history(items, history_cities, now=reference)

    return optimize(params, quotes, volumes, reference)
