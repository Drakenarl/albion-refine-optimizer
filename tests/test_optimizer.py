"""Tests d'intégration de l'optimiseur (données mockées via fixtures)."""

from __future__ import annotations

from datetime import datetime, timedelta

import pytest

from albion_refine import optimizer
from albion_refine.models import (
    PriceQuote,
    QuantityMode,
    SellStrategy,
    VolumeData,
    WarningCode,
)
from albion_refine.optimizer import OptimizerParams, optimize


def _quote(item: str, city: str, *, sell: int = 0, buy: int = 0, when: datetime) -> PriceQuote:
    return PriceQuote(
        item_id=item,
        city=city,
        sell_price_min=sell,
        sell_price_min_date=when if sell else None,
        buy_price_max=buy,
        buy_price_max_date=when if buy else None,
    )


class TestControlledRoute:
    """Route unique entièrement contrôlée : marge calculée à la main."""

    def _run(self) -> optimizer.OptimizationResult:
        now = datetime(2026, 7, 19, 15, 20, 0)
        when = datetime(2026, 7, 19, 15, 0, 0)
        quotes = [
            _quote("T4_WOOD", "Martlock", sell=100, when=when),
            _quote("T3_PLANKS", "Martlock", sell=200, when=when),
            _quote("T4_PLANKS", "Lymhurst", sell=600, buy=500, when=when),
        ]
        # V2.8 : on ajoute des volumes epais aux items d'achat pour eviter que
        # le slippage V2.7 gonfle les prix et casse les valeurs attendues.
        volumes = [
            VolumeData(item_id="T4_PLANKS", city="Lymhurst", total_volume_24h=1000),
            VolumeData(item_id="T4_WOOD", city="Martlock", total_volume_24h=100_000),
            VolumeData(item_id="T3_PLANKS", city="Martlock", total_volume_24h=100_000),
        ]
        params = OptimizerParams(
            tier=4,
            mode=QuantityMode.FIXED,
            quantite=100,
            station_rate=100,
            focus=False,
            ignore_recup=True,
            undercut_pct=1.0,
            seuil_marge_min_pct=0,
        )
        return optimize(params, quotes, volumes, now)

    def test_single_route_margin(self) -> None:
        result = self._run()
        assert len(result.routes) == 1
        route = result.routes[0]
        assert route.rank == 1
        # Recette T4 : 2 bois + 1 plank T3 par unité.
        # Coût net = (200*100) + (100*200) + 100*1.575*1.0 = 40157.5
        assert route.achat_wood.quantite == 200
        assert route.achat_plank is not None
        assert route.achat_plank.quantite == 100
        assert route.cout_net == pytest.approx(40157.5)
        # Scénario A (safe) : top buy 500 × 100 = 50000, net = 46000.
        scenario_a = route.vente.scenario_a_instant_sell
        assert scenario_a is not None
        assert scenario_a.strategy == SellStrategy.INSTANT_SELL
        assert route.revenu_effectif == pytest.approx(46000.0)
        assert route.benefice == pytest.approx(5842.5)
        assert route.marge_pct == pytest.approx(14.55, abs=0.01)

    def test_both_scenarios_present(self) -> None:
        route = self._run().routes[0]
        scenario_b = route.vente.scenario_b_sell_order
        assert scenario_b is not None
        # V3.0 : taxe non-premium sell_order = 10.5% (setup 2.5% + sale 8%).
        # Listing 594 × 100 = 59400 → net = 59400 × 0.895 = 53163.
        assert scenario_b.strategy == SellStrategy.SELL_ORDER
        assert scenario_b.revenu_net == pytest.approx(53163.0)
        # Fill proba realiste : 0.85 × 0.85 = 0.7225.
        assert scenario_b.fill_proba == pytest.approx(0.7225)
        # Esperance = 53163 × 0.7225 ≈ 38410.3 (tolerance sur arrondi flottant).
        assert scenario_b.expected_revenu == pytest.approx(38410.3, abs=1.0)
        assert route.marge_pct_b == pytest.approx(-4.35, abs=0.05)
        # Le sell order rapporte moins en espérance : on reste sur l'instant sell.
        assert route.vente.recommandation == "instant_sell"

    def test_title_margin_is_scenario_a(self) -> None:
        route = self._run().routes[0]
        scenario_a = route.vente.scenario_a_instant_sell
        assert scenario_a is not None
        # La marge affichée est celle du scénario A, pas la meilleure des deux.
        assert route.marge_pct == pytest.approx(scenario_a.marge_pct)
        assert route.marge_pct_b is not None
        assert route.marge_pct_b != pytest.approx(route.marge_pct)


class TestScenarioAFiltering:
    """Le seuil de marge porte sur le scénario A (SPEC_FIX 3.5 / 3.6)."""

    def _run(self, seuil: float) -> optimizer.OptimizationResult:
        now = datetime(2026, 7, 19, 15, 20, 0)
        when = datetime(2026, 7, 19, 15, 0, 0)
        quotes = [
            _quote("T4_WOOD", "Martlock", sell=100, when=when),
            _quote("T3_PLANKS", "Martlock", sell=200, when=when),
            # Spread énorme : marge A ~15%, marge B ~29%.
            _quote("T4_PLANKS", "Lymhurst", sell=600, buy=500, when=when),
        ]
        # V2.8 : volumes epais pour eviter slippage.
        volumes = [
            VolumeData(item_id="T4_PLANKS", city="Lymhurst", total_volume_24h=1000),
            VolumeData(item_id="T4_WOOD", city="Martlock", total_volume_24h=100_000),
            VolumeData(item_id="T3_PLANKS", city="Martlock", total_volume_24h=100_000),
        ]
        params = OptimizerParams(
            tier=4,
            mode=QuantityMode.FIXED,
            quantite=100,
            station_rate=100,
            ignore_recup=True,
            seuil_marge_min_pct=seuil,
        )
        return optimize(params, quotes, volumes, now)

    def test_seuil_is_informational_not_a_filter(self) -> None:
        # V2.8.1 : le seuil ne filtre plus les routes. Meme si aucune ne le
        # depasse, on garde les top_n meilleures et le frontend affiche
        # "toutes deficitaires" en header.
        r_seuil_haut = self._run(seuil=100)
        r_seuil_bas = self._run(seuil=-100)
        # Meme nombre de routes affichees quel que soit le seuil.
        assert len(r_seuil_haut.routes) == len(r_seuil_bas.routes)
        # Les routes sont identiques (memes candidats, meme tri).
        assert [r.marge_pct for r in r_seuil_haut.routes] == [
            r.marge_pct for r in r_seuil_bas.routes
        ]

    def test_discarded_only_populated_when_no_candidates_pass(self) -> None:
        # Puisqu'on garde toujours les top_n meilleures, discarded_best est
        # None tant qu'on a au moins une route en output.
        result = self._run(seuil=20)
        assert result.routes  # on a bien des routes
        assert result.discarded_best is None


class TestFreshnessWeighting:
    """La marge affichée est la marge pondérée par la confiance (SPEC_FIX 6.4)."""

    def _run(self, age_vente_heures: float) -> optimizer.OptimizationResult:
        now = datetime(2026, 7, 19, 15, 20, 0)
        achat = datetime(2026, 7, 19, 15, 0, 0)
        vente = now - timedelta(hours=age_vente_heures)
        quotes = [
            _quote("T4_WOOD", "Martlock", sell=100, when=achat),
            _quote("T3_PLANKS", "Martlock", sell=100, when=achat),
            _quote("T4_PLANKS", "Lymhurst", sell=600, buy=500, when=vente),
        ]
        # V2.8 : volumes epais pour eviter slippage.
        volumes = [
            VolumeData(item_id="T4_PLANKS", city="Lymhurst", total_volume_24h=1000),
            VolumeData(item_id="T4_WOOD", city="Martlock", total_volume_24h=100_000),
            VolumeData(item_id="T3_PLANKS", city="Martlock", total_volume_24h=100_000),
        ]
        params = OptimizerParams(
            tier=4,
            mode=QuantityMode.FIXED,
            quantite=100,
            station_rate=100,
            ignore_recup=True,
            seuil_marge_min_pct=-1000,
        )
        return optimize(params, quotes, volumes, now)

    def test_margin_uses_weighted_revenue(self) -> None:
        route = self._run(age_vente_heures=0.2).routes[0]
        scenario_a = route.vente.scenario_a_instant_sell
        assert scenario_a is not None
        assert scenario_a.freshness_factor == 1.0
        # cout_net = 20000 + 10000 + 157.5 ; revenu net = 46000
        assert route.benefice == pytest.approx(15842.5)

    def test_revenue_penalized_by_stale_freshness(self) -> None:
        frais = self._run(age_vente_heures=0.2).routes[0]
        vieux = self._run(age_vente_heures=3.1).routes[0]
        scenario = vieux.vente.scenario_a_instant_sell
        assert scenario is not None
        # V2.6 : bareme durci, 3.1h tombe dans le palier 2-4h -> 0.70.
        assert scenario.freshness_factor == pytest.approx(0.70)
        assert vieux.revenu_effectif == pytest.approx(frais.revenu_effectif * 0.70)
        assert vieux.marge_pct < frais.marge_pct

    def test_purchase_cost_is_not_weighted(self) -> None:
        frais = self._run(age_vente_heures=0.2).routes[0]
        vieux = self._run(age_vente_heures=5.7).routes[0]
        # Seul le revenu est escompté : le coût d'achat reste identique.
        assert vieux.cout_net == pytest.approx(frais.cout_net)


class TestRecuperationWalk:
    """La récup RRR passe par le carnet d'achat de la ville de vente (V2.5).

    Depuis V2.5, il n'existe plus qu'un seul mode : la récup est vendue dans
    la même ville que les raffinés finis (workflow réel). L'ancien mode
    ``local`` était un cas particulier redondant avec l'exploration exhaustive
    des ``sell_city``.
    """

    def _run(self, volume_lym: float | None) -> optimizer.OptimizationResult:
        now = datetime(2026, 7, 19, 15, 20, 0)
        when = datetime(2026, 7, 19, 15, 0, 0)
        quotes = [
            _quote("T4_WOOD", "Martlock", sell=100, when=when),
            _quote("T3_PLANKS", "Martlock", sell=200, when=when),
            # Lymhurst = ville de vente = ville de récup depuis V2.5.
            _quote("T4_WOOD", "Lymhurst", sell=140, buy=90, when=when),
            _quote("T3_PLANKS", "Lymhurst", sell=250, buy=180, when=when),
            _quote("T4_PLANKS", "Lymhurst", sell=600, buy=500, when=when),
        ]
        volumes = [VolumeData(item_id="T4_PLANKS", city="Lymhurst", total_volume_24h=1000)]
        if volume_lym is not None:
            volumes += [
                VolumeData(item_id="T4_WOOD", city="Lymhurst", total_volume_24h=volume_lym),
                VolumeData(item_id="T3_PLANKS", city="Lymhurst", total_volume_24h=volume_lym),
            ]
        params = OptimizerParams(
            tier=4,
            mode=QuantityMode.FIXED,
            quantite=100,
            station_rate=100,
            seuil_marge_min_pct=-1000,
        )
        return optimize(params, quotes, volumes, now)

    def test_recovery_credited_when_book_is_deep(self) -> None:
        route = self._run(volume_lym=10_000).routes[0]
        assert route.recup_city == "Lymhurst"
        assert route.recup_wood_absorbe == route.recup_wood_demande
        assert route.recup_wood > 0
        assert route.recup_plank > 0
        assert WarningCode.RECUP_PARTIELLE not in route.warnings

    def test_recovery_partial_when_volume_is_thin(self) -> None:
        route = self._run(volume_lym=10).routes[0]
        assert route.recup_wood_absorbe == 10
        assert route.recup_wood_absorbe < route.recup_wood_demande
        assert WarningCode.RECUP_PARTIELLE in route.warnings

    def test_recovery_zero_without_history(self) -> None:
        route = self._run(volume_lym=None).routes[0]
        assert route.recup_totale == 0.0
        assert route.recup_wood_absorbe == 0

    def test_recovery_lowers_net_cost(self) -> None:
        riche = self._run(volume_lym=10_000).routes[0]
        pauvre = self._run(volume_lym=None).routes[0]
        assert riche.cout_net < pauvre.cout_net
        assert riche.marge_pct > pauvre.marge_pct


class TestRecupSaturationWarning:
    """Le warning ``RECUP_SATURATION`` protège contre l'écrasement de carnet."""

    def _run(self, volume_lym: float) -> optimizer.OptimizationResult:
        now = datetime(2026, 7, 19, 15, 20, 0)
        when = datetime(2026, 7, 19, 15, 0, 0)
        quotes = [
            _quote("T4_WOOD", "Lymhurst", sell=140, buy=95, when=when),
            _quote("T3_PLANKS", "Lymhurst", sell=250, buy=180, when=when),
            _quote("T4_PLANKS", "Lymhurst", sell=600, buy=500, when=when),
        ]
        volumes = [
            VolumeData(item_id="T4_PLANKS", city="Lymhurst", total_volume_24h=1000),
            VolumeData(item_id="T4_WOOD", city="Lymhurst", total_volume_24h=volume_lym),
            VolumeData(item_id="T3_PLANKS", city="Lymhurst", total_volume_24h=volume_lym),
        ]
        params = OptimizerParams(
            tier=4,
            mode=QuantityMode.FIXED,
            quantite=1000,
            station_rate=100,
            seuil_marge_min_pct=-1000,
        )
        return optimize(params, quotes, volumes, now)

    def test_saturation_flagged_when_recup_exceeds_half_volume(self) -> None:
        route = self._run(volume_lym=100).routes[0]
        assert WarningCode.RECUP_SATURATION in route.warnings

    def test_no_saturation_when_volume_is_deep(self) -> None:
        route = self._run(volume_lym=100_000).routes[0]
        assert WarningCode.RECUP_SATURATION not in route.warnings


class TestFixtureIntegration:
    def _params(self, **overrides: object) -> OptimizerParams:
        base: dict[str, object] = {
            "tier": 7,
            "mode": QuantityMode.FIXED,
            "quantite": 128,
            "station_rate": 50,
            "focus": True,
        }
        base.update(overrides)
        return OptimizerParams(**base)  # type: ignore[arg-type]

    def test_produces_routes(
        self,
        prices_t7: list[PriceQuote],
        history_t7: list[VolumeData],
        now_ref: datetime,
    ) -> None:
        result = optimize(self._params(), prices_t7, history_t7, now_ref)
        assert len(result.routes) > 0
        assert len(result.routes) <= 5

    def test_ranks_are_contiguous(
        self,
        prices_t7: list[PriceQuote],
        history_t7: list[VolumeData],
        now_ref: datetime,
    ) -> None:
        result = optimize(self._params(), prices_t7, history_t7, now_ref)
        assert [r.rank for r in result.routes] == list(range(1, len(result.routes) + 1))

    def test_sorted_by_silver_per_focus_desc(
        self,
        prices_t7: list[PriceQuote],
        history_t7: list[VolumeData],
        now_ref: datetime,
    ) -> None:
        result = optimize(self._params(focus=True), prices_t7, history_t7, now_ref)
        values = [r.silver_par_focus or 0.0 for r in result.routes]
        assert values == sorted(values, reverse=True)
        assert all(r.silver_par_focus is not None for r in result.routes)

    def test_caerleon_routes_flagged(
        self,
        prices_t7: list[PriceQuote],
        history_t7: list[VolumeData],
        now_ref: datetime,
    ) -> None:
        result = optimize(self._params(), prices_t7, history_t7, now_ref)
        for route in result.routes:
            assert route.achat_plank is not None
            cities = {route.achat_wood.city, route.achat_plank.city, route.vente.ville}
            if "Caerleon" in cities:
                assert WarningCode.ROUTE_ZONE_ROUGE in route.warnings

    def test_checklist_not_empty(
        self,
        prices_t7: list[PriceQuote],
        history_t7: list[VolumeData],
        now_ref: datetime,
    ) -> None:
        result = optimize(self._params(), prices_t7, history_t7, now_ref)
        assert len(result.refresh_checklist) > 0

    def test_high_threshold_discards_all(
        self,
        prices_t7: list[PriceQuote],
        history_t7: list[VolumeData],
        now_ref: datetime,
    ) -> None:
        # V2.8.1 : le seuil ne filtre plus, les top_n meilleures sont toujours
        # retournees. On verifie donc que les routes sont bien retournees mais
        # sont toutes sous le seuil (100 000% est irreatteignable).
        result = optimize(
            self._params(seuil_marge_min_pct=100_000),
            prices_t7,
            history_t7,
            now_ref,
        )
        assert result.routes  # top_n toujours renseigne
        assert all(r.marge_pct < 100_000 for r in result.routes)
        # discarded_best reste None puisqu'on a des routes.
        assert result.discarded_best is None

    def test_sort_by_margin_when_no_focus(
        self,
        prices_t7: list[PriceQuote],
        history_t7: list[VolumeData],
        now_ref: datetime,
    ) -> None:
        result = optimize(self._params(focus=False), prices_t7, history_t7, now_ref)
        marges = [r.marge_pct for r in result.routes]
        assert marges == sorted(marges, reverse=True)


class TestFreshnessFiltering:
    def test_critical_wood_excluded(self) -> None:
        now = datetime(2026, 7, 19, 16, 0, 0)
        old = datetime(2026, 7, 19, 7, 0, 0)  # 9h → critique
        fresh = datetime(2026, 7, 19, 15, 45, 0)
        quotes = [
            _quote("T4_WOOD", "Martlock", sell=100, when=old),  # critique → exclu
            _quote("T3_PLANKS", "Martlock", sell=200, when=fresh),
            _quote("T4_PLANKS", "Lymhurst", sell=600, buy=500, when=fresh),
        ]
        volumes = [VolumeData(item_id="T4_PLANKS", city="Lymhurst", total_volume_24h=1000)]
        params = OptimizerParams(tier=4, mode=QuantityMode.FIXED, quantite=100, station_rate=100)
        result = optimize(params, quotes, volumes, now)
        assert result.routes == []
