"""Tests d'intégration de l'optimiseur (données mockées via fixtures)."""

from __future__ import annotations

from datetime import datetime

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
        volumes = [VolumeData(item_id="T4_PLANKS", city="Lymhurst", total_volume_24h=1000)]
        params = OptimizerParams(
            tier=4,
            mode=QuantityMode.FIXED,
            quantite=100,
            station_rate=100,
            focus=False,
            ignore_recup=True,
            undercut_pct=1.0,
        )
        return optimize(params, quotes, volumes, now)

    def test_single_route_margin(self) -> None:
        result = self._run()
        assert len(result.routes) == 1
        route = result.routes[0]
        assert route.rank == 1
        # Coût net = 100*100 + 100*200 + 100*1.575*1.0 = 30157.5
        assert route.cout_net == pytest.approx(30157.5)
        # Sell order gagne : listing 594, net = 59400*0.87 = 51678
        assert route.vente.strategy == SellStrategy.SELL_ORDER
        assert route.revenu_effectif == pytest.approx(51678.0)
        assert route.benefice == pytest.approx(21520.5)
        assert route.marge_pct == pytest.approx(71.36, abs=0.01)


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
            cities = {route.achat_wood.city, route.achat_plank.city, route.vente.city}
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
        result = optimize(
            self._params(seuil_marge_min_pct=100000),
            prices_t7,
            history_t7,
            now_ref,
        )
        assert result.routes == []
        assert result.discarded_best is not None
        assert "seuil" in result.discarded_best.raison

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
