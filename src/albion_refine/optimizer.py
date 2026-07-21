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
from albion_refine.models import (
    DiscardedRoute,
    FreshnessLevel,
    OptimizationResult,
    PriceQuote,
    QuantityMode,
    RecupMode,
    RefreshChecklistItem,
    Route,
    RunMetadata,
    SalesScenario,
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
    # Où la récupération RRR est vendue. ``WITH_PLANKS`` (défaut V2) est
    # réaliste : tu transportes déjà les planks vers leur ville de vente, tu
    # emmènes la récup avec. ``LOCAL`` reste possible pour comparaison honnête
    # avec le comportement V1 (vente forcée à Fort Sterling).
    recup_mode: RecupMode = RecupMode.WITH_PLANKS
    top_n: int = 3

    def buy_cities(self) -> list[str]:
        """Villes autorisées à l'achat (toutes sauf les exclues)."""
        return [c for c in config.all_cities() if c not in self.excluded_buy_cities]

    def sell_cities(self) -> list[str]:
        """Villes autorisées à la vente (toutes sauf les exclues)."""
        return [c for c in config.all_cities() if c not in self.excluded_sell_cities]


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


def _make_leg(
    kind: str,
    tier: int,
    quote: PriceQuote,
    quantity: int,
    now: datetime,
    params: OptimizerParams,
) -> SourcingLeg:
    """Construit un ``SourcingLeg`` (achat bois ou plank) à partir d'un quote."""
    age = quote.sell_min_age(now)
    freshness = market.classify_freshness(
        age, params.freshness_warning_hours, params.freshness_critical_hours
    )
    return SourcingLeg(
        kind=kind,
        item_id=quote.item_id,
        tier=tier,
        city=quote.city,
        prix_unitaire=float(quote.sell_price_min),
        quantite=quantity,
        cout_total=quantity * quote.sell_price_min,
        data_age_hours=market.age_hours(age),
        freshness=freshness,
    )


def _recuperation(
    quote: PriceQuote | None,
    volume: VolumeData | None,
    retour: float,
    ignore: bool,
) -> market.RecoveryResult:
    """Valorise les retours RRR en instant sell dans la ville de vente choisie.

    L'AODP n'expose pas la profondeur des buy orders : on estime le stack
    absorbable par le **volume échangé sur 24h** de l'item dans la ville
    ciblée. Sans historique exploitable, on ne crédite rien plutôt que de
    supposer une profondeur infinie (choix conservateur, SPEC_FIX 5.3).

    En V2, la ville n'est plus figée à Fort Sterling : elle dépend de
    ``recup_mode`` et est choisie par ``_recup_destination``.

    Args:
        quote: Prix de l'item dans la ville où la récup sera vendue.
        volume: Volume 24h de l'item dans cette ville (profondeur estimée).
        retour: Quantité retournée par le RRR.
        ignore: Vrai pour désactiver complètement la récupération.

    Returns:
        Un ``RecoveryResult`` (valeur nette de taxe, quantité absorbée/demandée).
    """
    demande = int(retour)
    if ignore or quote is None or not quote.has_buy_offer:
        return market.RecoveryResult(valeur=0.0, absorbe=0, demande=demande)
    profondeur = int(volume.total_volume_24h) if volume is not None else 0
    book = [(float(quote.buy_price_max), profondeur)]
    return market.compute_recovery_value(retour, book)


def _recup_destination(params: OptimizerParams, sell_city: str) -> str:
    """Retourne la ville où la récupération RRR sera valorisée."""
    if params.recup_mode is RecupMode.LOCAL:
        return config.REFINING_CITY
    return sell_city


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


def _build_route(
    params: OptimizerParams,
    wood_quote: PriceQuote,
    plank_quote: PriceQuote | None,
    output_quote: PriceQuote,
    volume: VolumeData | None,
    quotes: QuoteIndex,
    volumes: VolumeIndex,
    now: datetime,
) -> Route | None:
    """Évalue une combinaison complète et retourne une ``Route`` (ou ``None``)."""
    tier = params.tier
    plank_price = float(plank_quote.sell_price_min) if plank_quote is not None else 0.0
    unit_gross = refining.unit_gross_cost(
        tier, float(wood_quote.sell_price_min), plank_price, params.station_rate
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

    wood_leg = _make_leg("wood", tier, wood_quote, refined.wood_utilise, now, params)
    plank_leg = (
        _make_leg("plank", tier - 1, plank_quote, refined.plank_moins_1_utilise, now, params)
        if plank_quote is not None
        else None
    )

    cout_focus = refined.focus_utilise * params.cost_per_focus
    cout_plank = plank_leg.cout_total if plank_leg is not None else 0.0
    cout_total = wood_leg.cout_total + cout_plank + refined.cout_station + cout_focus

    recup_city = _recup_destination(params, output_quote.city)
    recup_wood = _recuperation(
        quotes.get((wood_quote.item_id, recup_city)),
        volumes.get((wood_quote.item_id, recup_city)),
        refined.wood_retour,
        params.ignore_recup,
    )
    recup_plank = (
        _recuperation(
            quotes.get((plank_quote.item_id, recup_city)),
            volumes.get((plank_quote.item_id, recup_city)),
            refined.plank_moins_1_retour,
            params.ignore_recup,
        )
        if plank_quote is not None
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
    cities = {wood_quote.city, output_quote.city}
    legs_fresh = [wood_leg.freshness, chosen_fresh]
    if plank_leg is not None:
        cities.add(plank_leg.city)
        legs_fresh.append(plank_leg.freshness)
    warnings = _collect_warnings(cities, legs_fresh, volume, quantity)
    if recup_wood.partielle or recup_plank.partielle:
        warnings.append(WarningCode.RECUP_PARTIELLE)
    if _recup_saturates(recup_wood, recup_plank, wood_quote, plank_quote, recup_city, volumes):
        warnings.append(WarningCode.RECUP_SATURATION)

    return Route(
        tier=tier,
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
    wood_quote: PriceQuote,
    plank_quote: PriceQuote | None,
    recup_city: str,
    volumes: VolumeIndex,
) -> bool:
    """Vrai si la récup à écouler dépasse ``_SATURATION_RATIO`` du volume 24h.

    Levé quand tu comptes revendre un stack important dans la ville où tu
    viens d'acheter : tu risques d'écraser le carnet (buy_max qui s'effondre à
    mesure que tu remplis les ordres). Le walk_book gère la profondeur exacte
    quand elle est connue ; ce warning est un garde-fou qualitatif en amont.
    """

    def _saturates(res: market.RecoveryResult, item_id: str) -> bool:
        if res.demande <= 0:
            return False
        vol = volumes.get((item_id, recup_city))
        if vol is None or vol.total_volume_24h <= 0:
            return False
        return res.demande > _SATURATION_RATIO * vol.total_volume_24h

    if _saturates(recup_wood, wood_quote.item_id):
        return True
    return plank_quote is not None and _saturates(recup_plank, plank_quote.item_id)


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
    for route in routes:
        pairs = [
            (
                route.achat_wood.item_id,
                route.achat_wood.city,
                "critique, le prix du bois structure le coût",
            ),
        ]
        if route.achat_plank is not None:
            pairs.append(
                (route.achat_plank.item_id, route.achat_plank.city, "critique, prix du plank T-1")
            )
        pairs.append((config.plank_item_id(route.tier), route.vente.ville, "vente principale"))
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
    plank_src = f" + plank T-1 @ {route.achat_plank.city}" if route.achat_plank else ""
    description = (
        f"Bois T{route.tier} @ {route.achat_wood.city}{plank_src} "
        f"→ raffinage {config.REFINING_CITY} → vente @ {route.vente.ville}"
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
            f"Baisser --seuil-marge à {math.floor(route.marge_pct)} pour voir cette route",
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


def _plank_input_item(tier: int) -> str | None:
    """Retourne l'item ID du plank T-1 requis par la recette, ou ``None`` (T2)."""
    if config.lower_plank_qty_per_plank(tier) == 0:
        return None
    return config.plank_item_id(tier - 1)


def _plank_input_candidates(
    params: OptimizerParams,
    quotes: QuoteIndex,
    plank_input_item: str | None,
    now: datetime,
) -> list[PriceQuote | None]:
    """Liste les quotes de plank T-1 exploitables pour la phase 2 de sourcing.

    Si la recette du tier ne consomme aucun plank T-1 (cas du T2), la phase 2
    est court-circuitée : on retourne une unique branche ``None``.

    Args:
        params: Paramètres du run.
        quotes: Index des prix par ``(item_id, ville)``.
        plank_input_item: Item ID du plank T-1.
        now: Instant de référence pour la fraîcheur.

    Returns:
        La liste des quotes candidates, ou ``[None]`` si aucun plank n'est requis.
    """
    if plank_input_item is None:
        return [None]
    candidates: list[PriceQuote | None] = []
    for plank_city in params.buy_cities():
        quote = quotes.get((plank_input_item, plank_city))
        if quote is None or not quote.has_sell_offer:
            continue
        if _leg_is_critical(quote, now, params):
            continue
        candidates.append(quote)
    return candidates


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

    wood_item = config.wood_item_id(params.tier)
    plank_input_item = _plank_input_item(params.tier)
    output_item = config.plank_item_id(params.tier)

    candidates: list[Route] = []
    for wood_city in params.buy_cities():
        wood_quote = quotes.get((wood_item, wood_city))
        if wood_quote is None or not wood_quote.has_sell_offer:
            continue
        if _leg_is_critical(wood_quote, now, params):
            continue
        for plank_quote in _plank_input_candidates(params, quotes, plank_input_item, now):
            for sell_city in params.sell_cities():
                output_quote = quotes.get((output_item, sell_city))
                if output_quote is None:
                    continue
                route = _build_route(
                    params,
                    wood_quote,
                    plank_quote,
                    output_quote,
                    volumes.get((output_item, sell_city)),
                    quotes,
                    volumes,
                    now,
                )
                if route is not None:
                    candidates.append(route)

    passing = [r for r in candidates if r.marge_pct >= params.seuil_marge_min_pct]
    passing.sort(key=_sort_key(params), reverse=True)
    top = passing[: params.top_n]
    for rank, route in enumerate(top, start=1):
        route.rank = rank

    discarded_best: DiscardedRoute | None = None
    discarded_top: list[DiscardedRoute] = []
    if not top and candidates:
        discarded_top = _discarded_top(candidates, params, params.top_n)
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
    wood_item = config.wood_item_id(params.tier)
    plank_input_item = _plank_input_item(params.tier)
    output_item = config.plank_item_id(params.tier)

    items = [item for item in (wood_item, plank_input_item, output_item) if item is not None]
    all_buy = sorted(set(params.buy_cities()) | set(params.sell_cities()))
    # Les volumes servent à la fill probability (planks de sortie) et à estimer
    # la profondeur des buy orders pour la récupération RRR (inputs à FS).
    history_cities = sorted({*params.sell_cities(), config.REFINING_CITY})
    async with AodpClient(server=server, use_cache=use_cache) as client:
        quotes = await client.get_prices(items, all_buy)
        volumes = await client.get_history(items, history_cities)

    return optimize(params, quotes, volumes, reference)
