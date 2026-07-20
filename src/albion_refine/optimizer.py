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
    RefreshChecklistItem,
    Route,
    RunMetadata,
    SalesScenario,
    SellStrategy,
    SourcingLeg,
    VolumeData,
    WarningCode,
)

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
    top_n: int = 5

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


def _recuperation(quote_fs: PriceQuote | None, retour: float, ignore: bool) -> float:
    """Crédite la revente des retours RRR en instant sell à Fort Sterling."""
    if ignore or quote_fs is None or not quote_fs.has_buy_offer:
        return 0.0
    return market.apply_instant_sell_tax(retour * quote_fs.buy_price_max)


def _evaluate_sales(
    output_quote: PriceQuote | None,
    volume: VolumeData | None,
    quantity: int,
    now: datetime,
    params: OptimizerParams,
) -> SalesScenario | None:
    """Évalue les scénarios A/B pour une ville de vente et retient le meilleur."""
    if output_quote is None:
        return None

    candidates: list[SalesScenario] = []

    # Scénario A — instant sell (on remplit les buy orders).
    buy_age = output_quote.buy_max_age(now)
    buy_fresh = market.classify_freshness(
        buy_age, params.freshness_warning_hours, params.freshness_critical_hours
    )
    if buy_fresh != FreshnessLevel.CRITICAL and output_quote.has_buy_offer:
        candidates.append(
            market.evaluate_instant_sell(
                output_quote.city,
                float(output_quote.buy_price_max),
                quantity,
                data_age_hours=market.age_hours(buy_age),
            )
        )

    # Scénario B — sell order (on place un ordre sous-coté).
    sell_age = output_quote.sell_min_age(now)
    sell_fresh = market.classify_freshness(
        sell_age, params.freshness_warning_hours, params.freshness_critical_hours
    )
    if sell_fresh != FreshnessLevel.CRITICAL and output_quote.has_sell_offer:
        volume_24h = volume.total_volume_24h if volume is not None else 0.0
        scenario_b = market.evaluate_sell_order(
            output_quote.city,
            float(output_quote.sell_price_min),
            quantity,
            volume_24h,
            undercut_pct=params.undercut_pct,
            data_age_hours=market.age_hours(sell_age),
        )
        # Filtre : on écarte le scénario B si la fill probability est trop faible.
        if scenario_b.fill_proba >= params.seuil_fill_probability_pct / 100.0:
            candidates.append(scenario_b)

    return market.best_scenario(candidates)


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
    plank_quote: PriceQuote,
    output_quote: PriceQuote,
    volume: VolumeData | None,
    quotes: QuoteIndex,
    now: datetime,
) -> Route | None:
    """Évalue une combinaison complète et retourne une ``Route`` (ou ``None``)."""
    tier = params.tier
    unit_gross = (
        wood_quote.sell_price_min
        + plank_quote.sell_price_min
        + config.nutrition_per_unit(tier) * (params.station_rate / 100.0)
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

    wood_leg = _make_leg("wood", tier, wood_quote, quantity, now, params)
    plank_leg = _make_leg("plank", tier - 1, plank_quote, quantity, now, params)

    cout_focus = refined.focus_utilise * params.cost_per_focus
    cout_total = wood_leg.cout_total + plank_leg.cout_total + refined.cout_station + cout_focus

    fs = config.REFINING_CITY
    recup_wood = _recuperation(
        quotes.get((wood_quote.item_id, fs)), refined.wood_retour, params.ignore_recup
    )
    recup_plank = _recuperation(
        quotes.get((plank_quote.item_id, fs)),
        refined.plank_moins_1_retour,
        params.ignore_recup,
    )
    recup_totale = recup_wood + recup_plank
    cout_net = cout_total - recup_totale

    benefice = sale.expected_revenu - cout_net
    marge_pct = benefice / cout_net * 100.0 if cout_net > 0 else _MARGE_INFINIE
    silver_par_focus = (
        benefice / refined.focus_utilise if params.focus and refined.focus_utilise > 0 else None
    )

    chosen_fresh = market.classify_freshness(
        output_quote.buy_max_age(now)
        if sale.strategy == SellStrategy.INSTANT_SELL
        else output_quote.sell_min_age(now),
        params.freshness_warning_hours,
        params.freshness_critical_hours,
    )
    warnings = _collect_warnings(
        {wood_quote.city, plank_quote.city, output_quote.city},
        [wood_leg.freshness, plank_leg.freshness, chosen_fresh],
        volume,
        quantity,
    )

    return Route(
        tier=tier,
        quantite=quantity,
        achat_wood=wood_leg,
        achat_plank=plank_leg,
        raffinage=refined,
        vente=sale,
        recup_wood=recup_wood,
        recup_plank=recup_plank,
        recup_totale=recup_totale,
        cout_total=cout_total,
        cout_net=cout_net,
        revenu_effectif=sale.expected_revenu,
        benefice=benefice,
        marge_pct=marge_pct,
        silver_par_focus=silver_par_focus,
        warnings=warnings,
    )


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
            (route.achat_wood.item_id, route.achat_wood.city),
            (route.achat_plank.item_id, route.achat_plank.city),
            (config.plank_item_id(route.tier), route.vente.city),
        ]
        for item_id, city in pairs:
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
                )
            )
    return checklist


def _discarded_report(best_below: Route | None, params: OptimizerParams) -> DiscardedRoute | None:
    """Construit le rapport du meilleur candidat écarté par le seuil de marge."""
    if best_below is None:
        return None
    description = (
        f"Achat {best_below.achat_wood.city} → {config.REFINING_CITY} "
        f"→ Vente {best_below.vente.city}"
    )
    return DiscardedRoute(
        description=description,
        marge_pct=round(best_below.marge_pct, 1),
        raison=f"marge {best_below.marge_pct:.1f}% < seuil {params.seuil_marge_min_pct:.0f}%",
        suggestions=[
            f"Baisser --seuil-marge à {math.floor(best_below.marge_pct)} pour voir cette route",
            "Attendre un rafraîchissement des prix (données trop vieilles)",
            "Essayer un autre tier",
        ],
    )


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
    plank_input_item = config.plank_item_id(params.tier - 1)
    output_item = config.plank_item_id(params.tier)

    candidates: list[Route] = []
    for wood_city in params.buy_cities():
        wood_quote = quotes.get((wood_item, wood_city))
        if wood_quote is None or not wood_quote.has_sell_offer:
            continue
        if _leg_is_critical(wood_quote, now, params):
            continue
        for plank_city in params.buy_cities():
            plank_quote = quotes.get((plank_input_item, plank_city))
            if plank_quote is None or not plank_quote.has_sell_offer:
                continue
            if _leg_is_critical(plank_quote, now, params):
                continue
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
                    now,
                )
                if route is not None:
                    candidates.append(route)

    passing = [r for r in candidates if r.marge_pct >= params.seuil_marge_min_pct]
    passing.sort(key=_sort_key(params), reverse=True)
    top = passing[: params.top_n]
    for rank, route in enumerate(top, start=1):
        route.rank = rank

    discarded = None
    if not top and candidates:
        best_below = max(candidates, key=lambda r: r.marge_pct)
        discarded = _discarded_report(best_below, params)

    return OptimizationResult(
        run_metadata=RunMetadata(
            timestamp=now,
            tier=params.tier,
            mode=params.mode,
            params=params.model_dump(mode="json"),
        ),
        routes=top,
        refresh_checklist=_build_checklist(top, quotes, now, params),
        discarded_best=discarded,
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
    plank_input_item = config.plank_item_id(params.tier - 1)
    output_item = config.plank_item_id(params.tier)

    all_buy = sorted(set(params.buy_cities()) | set(params.sell_cities()))
    async with AodpClient(server=server, use_cache=use_cache) as client:
        quotes = await client.get_prices([wood_item, plank_input_item, output_item], all_buy)
        volumes = await client.get_history([output_item], params.sell_cities())

    return optimize(params, quotes, volumes, reference)
