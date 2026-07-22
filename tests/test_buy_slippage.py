"""Tests du modele de slippage buy-side (V2.7).

L'AODP n'expose que ``sell_price_min`` sans profondeur : on inflate ce prix
avec deux composantes (ratio quantite / volume 24h, et age de la donnee) pour
que la ROI reflete plus honnetement ce que l'utilisateur paiera reellement.
"""

from __future__ import annotations

from datetime import datetime

import pytest

from albion_refine import market
from albion_refine.models import (
    PriceQuote,
    QuantityMode,
    ResourceKind,
    VolumeData,
    WarningCode,
)
from albion_refine.optimizer import OptimizerParams, optimize


def _q(item: str, city: str, *, sell: int = 0, buy: int = 0, when: datetime) -> PriceQuote:
    return PriceQuote(
        item_id=item,
        city=city,
        sell_price_min=sell,
        sell_price_min_date=when if sell else None,
        buy_price_max=buy,
        buy_price_max_date=when if buy else None,
    )


class TestBuyInflationBareme:
    """Le bareme de slippage tourne autour de deux composantes multiplicatives."""

    def test_no_slippage_when_qty_small_and_fresh(self) -> None:
        inflation = market.buy_side_inflation(
            quantity=100, volume_24h=10_000, age_hours_value=0.1
        )
        assert inflation.slippage_qty == 0.0
        assert inflation.inflation_age == 0.0
        assert inflation.total_factor == pytest.approx(1.0)
        assert inflation.capped is False

    def test_slippage_qty_only(self) -> None:
        # 40% du volume 24h -> palier 25-50 -> 5%.
        inflation = market.buy_side_inflation(
            quantity=4_000, volume_24h=10_000, age_hours_value=0.1
        )
        assert inflation.slippage_qty == pytest.approx(0.05)
        assert inflation.inflation_age == 0.0
        assert inflation.total_factor == pytest.approx(1.05)

    def test_inflation_age_only(self) -> None:
        # 2.5h -> palier 2-4h -> 10%.
        inflation = market.buy_side_inflation(
            quantity=100, volume_24h=10_000, age_hours_value=2.5
        )
        assert inflation.slippage_qty == 0.0
        assert inflation.inflation_age == pytest.approx(0.10)
        assert inflation.total_factor == pytest.approx(1.10)

    def test_combined_multiplicative(self) -> None:
        # Cas de la capture utilisateur : ~40% du volume + 2.3h de vieux.
        inflation = market.buy_side_inflation(
            quantity=3_879, volume_24h=10_000, age_hours_value=2.3
        )
        # 40% -> 5%, 2.3h -> 10%. Combine = (1.05 * 1.10) - 1 = 0.155.
        assert inflation.slippage_qty == pytest.approx(0.05)
        assert inflation.inflation_age == pytest.approx(0.10)
        assert inflation.total_factor == pytest.approx(1.155)
        assert inflation.capped is False

    def test_cap_at_25_pct(self) -> None:
        # Cas extreme : 200% du volume + 5h de vieux.
        # 200% -> 20%, 5h -> 15%. Combine = 1.20 * 1.15 - 1 = 0.38 > cap 0.25.
        inflation = market.buy_side_inflation(
            quantity=20_000, volume_24h=10_000, age_hours_value=5.0
        )
        assert inflation.total_factor == pytest.approx(1.25)
        assert inflation.capped is True

    def test_no_volume_data_no_qty_slippage(self) -> None:
        # Sans historique de volume, on ne double-penalise pas : la composante
        # profondeur est neutre, seule la freshness peut inflater.
        inflation = market.buy_side_inflation(
            quantity=100, volume_24h=0, age_hours_value=0.1
        )
        assert inflation.slippage_qty == 0.0
        assert inflation.total_factor == pytest.approx(1.0)

    def test_unknown_age_penalized(self) -> None:
        inflation = market.buy_side_inflation(
            quantity=100, volume_24h=10_000, age_hours_value=None
        )
        # None age -> max de la composante fraicheur (15%).
        assert inflation.inflation_age == pytest.approx(0.15)


class TestSlippageAppliedInRoute:
    """Le slippage s'applique bien au prix d'achat et gonfle le cout total."""

    def _run(self, buy_volume: float) -> None:
        now = datetime(2026, 7, 22, 15, 20, 0)
        # 2.3h de retard pour matcher la capture utilisateur (Caerleon 2.3h).
        when = datetime(2026, 7, 22, 13, 0, 0)
        quotes = [
            _q("T4_WOOD", "Caerleon", sell=100, when=when),
            _q("T3_PLANKS", "Fort Sterling", sell=200, buy=180, when=now),
            _q("T4_PLANKS", "Lymhurst", sell=800, buy=700, when=now),
        ]
        volumes = [
            VolumeData(item_id="T4_PLANKS", city="Lymhurst", total_volume_24h=5_000),
            # T3_PLANKS achete a Fort Sterling avec un carnet epais : pas de
            # slippage sur cette jambe.
            VolumeData(item_id="T3_PLANKS", city="Fort Sterling", total_volume_24h=50_000),
            # C'est celui-ci qu'on fait varier : le T4_WOOD a Caerleon.
            VolumeData(item_id="T4_WOOD", city="Caerleon", total_volume_24h=buy_volume),
        ]
        params = OptimizerParams(
            tier=4,
            mode=QuantityMode.FIXED,
            quantite=200,  # 200 planks -> 400 bois consommes
            station_rate=100,
            seuil_marge_min_pct=-10_000,
        )
        return optimize(params, quotes, volumes, now)

    def test_thin_market_inflates_buy_price(self) -> None:
        # 400 bois demandes sur volume 500 = 80% -> slippage 10%.
        # + age 2.3h -> inflation 10%. Total = 1.10 * 1.10 = 1.21.
        result = self._run(buy_volume=500)
        route = result.routes[0]
        assert route.achat_wood.prix_ref == pytest.approx(100.0)
        assert route.achat_wood.prix_unitaire == pytest.approx(121.0)
        assert route.achat_wood.slippage_pct == pytest.approx(21.0)
        # Warning declenche (slippage > 8%).
        assert WarningCode.BUY_SLIPPAGE_ELEVE in route.warnings

    def test_deep_market_only_freshness_inflates(self) -> None:
        # 400 bois demandes sur volume 100_000 = 0.4% -> pas de slippage qty.
        # Reste juste la freshness 2.3h -> 10%.
        result = self._run(buy_volume=100_000)
        route = result.routes[0]
        assert route.achat_wood.slippage_qty_pct == pytest.approx(0.0)
        assert route.achat_wood.slippage_age_pct == pytest.approx(10.0)
        assert route.achat_wood.prix_unitaire == pytest.approx(110.0)
        # 10% > 8% donc warning encore leve.
        assert WarningCode.BUY_SLIPPAGE_ELEVE in route.warnings

    def test_slippage_lowers_roi(self) -> None:
        thin = self._run(buy_volume=500).routes[0]
        deep = self._run(buy_volume=100_000).routes[0]
        # Un marche epais -> cout plus bas -> ROI plus haute.
        assert deep.marge_pct > thin.marge_pct


class TestSlippageBackwardsCompat:
    """Sans volume, l'ancien comportement (prix_ref = prix_unitaire) est preserve."""

    def test_no_volume_no_qty_slippage(self) -> None:
        now = datetime(2026, 7, 22, 15, 20, 0)
        when = datetime(2026, 7, 22, 15, 0, 0)  # fresh
        quotes = [
            _q("T4_WOOD", "Martlock", sell=100, when=when),
            _q("T3_PLANKS", "Martlock", sell=200, when=when),
            _q("T4_PLANKS", "Lymhurst", sell=600, buy=500, when=when),
        ]
        # AUCUN volume pour les items d'achat.
        volumes = [VolumeData(item_id="T4_PLANKS", city="Lymhurst", total_volume_24h=1000)]
        params = OptimizerParams(
            tier=4,
            mode=QuantityMode.FIXED,
            quantite=100,
            station_rate=100,
            seuil_marge_min_pct=-1000,
        )
        result = optimize(params, quotes, volumes, now)
        route = result.routes[0]
        # Sans volume + donnee fraiche -> aucune inflation.
        assert route.achat_wood.prix_unitaire == pytest.approx(100.0)
        assert route.achat_wood.prix_ref == pytest.approx(100.0)
        assert route.achat_wood.slippage_pct == pytest.approx(0.0)
        assert WarningCode.BUY_SLIPPAGE_ELEVE not in route.warnings


class TestResourceKindStillWorks:
    """Regression : le slippage marche sur toutes les filieres (test hide)."""

    def test_hide_run_carries_slippage_fields(self) -> None:
        now = datetime(2026, 7, 22, 15, 20, 0)
        when = datetime(2026, 7, 22, 15, 0, 0)
        quotes = [
            _q("T4_HIDE", "Bridgewatch", sell=80, when=when),
            _q("T3_LEATHER", "Martlock", sell=180, buy=160, when=when),
            _q("T4_LEATHER", "Lymhurst", sell=500, buy=420, when=when),
        ]
        volumes = [
            VolumeData(item_id="T4_LEATHER", city="Lymhurst", total_volume_24h=1000),
            # Volume fin cote achat -> slippage qty va s'activer.
            VolumeData(item_id="T4_HIDE", city="Bridgewatch", total_volume_24h=200),
            VolumeData(item_id="T3_LEATHER", city="Martlock", total_volume_24h=10_000),
        ]
        params = OptimizerParams(
            tier=4,
            mode=QuantityMode.FIXED,
            quantite=100,  # 200 hide demandes = 100% du volume
            station_rate=100,
            resource=ResourceKind.HIDE,
            seuil_marge_min_pct=-10_000,
        )
        result = optimize(params, quotes, volumes, now)
        route = result.routes[0]
        assert route.achat_wood.item_id == "T4_HIDE"
        # 200 hide demandes / 200 volume = 100% -> palier >= 100% -> 20% qty.
        assert route.achat_wood.slippage_qty_pct == pytest.approx(20.0)
