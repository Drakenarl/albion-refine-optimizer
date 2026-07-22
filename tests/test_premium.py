"""Tests du statut premium (V3.0).

Le premium modifie les taxes de vente : 4% instant sell / 6.5% sell order au
lieu de 8% / 10.5%. On verifie que le flag se propage bien de OptimizerParams
jusqu'au revenu final, et que l'effet cumule sur un run donne bien un
benefice superieur.
"""

from __future__ import annotations

from datetime import datetime

import pytest

from albion_refine.models import (
    PriceQuote,
    QuantityMode,
    VolumeData,
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


def _fixture() -> tuple[list[PriceQuote], list[VolumeData], datetime]:
    now = datetime(2026, 7, 22, 15, 20, 0)
    when = datetime(2026, 7, 22, 15, 0, 0)
    quotes = [
        _q("T4_WOOD", "Martlock", sell=100, when=when),
        _q("T3_PLANKS", "Martlock", sell=200, when=when),
        _q("T4_PLANKS", "Lymhurst", sell=600, buy=500, when=when),
    ]
    volumes = [
        VolumeData(item_id="T4_PLANKS", city="Lymhurst", total_volume_24h=1000),
        VolumeData(item_id="T4_WOOD", city="Martlock", total_volume_24h=100_000),
        VolumeData(item_id="T3_PLANKS", city="Martlock", total_volume_24h=100_000),
    ]
    return quotes, volumes, now


class TestPremiumImpact:
    """Verifie que le flag premium se traduit bien en un revenu superieur."""

    def _run(self, premium: bool) -> object:
        quotes, volumes, now = _fixture()
        params = OptimizerParams(
            tier=4,
            mode=QuantityMode.FIXED,
            quantite=100,
            station_rate=100,
            focus=False,
            ignore_recup=True,
            seuil_marge_min_pct=-10_000,
            premium=premium,
        )
        return optimize(params, quotes, volumes, now).routes[0]

    def test_premium_reduces_instant_sell_tax(self) -> None:
        std = self._run(premium=False)
        prm = self._run(premium=True)
        # Non-premium : 8% de taxe -> revenu_net = 50000 * 0.92 = 46000.
        # Premium : 4% -> 50000 * 0.96 = 48000.
        # (top buy 500 × 100 = 50000 brut)
        assert std.revenu_effectif == pytest.approx(46000.0)
        assert prm.revenu_effectif == pytest.approx(48000.0)
        # Gain premium = 2000 silver de revenu supplementaire.
        assert prm.revenu_effectif - std.revenu_effectif == pytest.approx(2000.0)

    def test_premium_increases_benefice_and_roi(self) -> None:
        std = self._run(premium=False)
        prm = self._run(premium=True)
        assert prm.benefice > std.benefice
        assert prm.marge_pct > std.marge_pct
        assert prm.benefice - std.benefice == pytest.approx(2000.0)

    def test_premium_reduces_sell_order_tax(self) -> None:
        std = self._run(premium=False)
        prm = self._run(premium=True)
        std_scen_b = std.vente.scenario_b_sell_order
        prm_scen_b = prm.vente.scenario_b_sell_order
        assert std_scen_b is not None
        assert prm_scen_b is not None
        # Meme prix listing, revenu brut identique. Taxe : 10.5% vs 6.5%.
        assert prm_scen_b.revenu_net > std_scen_b.revenu_net


class TestPremiumDefaultIsFalse:
    """Retrocompat : sans preciser premium, comportement non-premium par defaut."""

    def test_default(self) -> None:
        params = OptimizerParams(
            tier=5, mode=QuantityMode.FIXED, quantite=10, station_rate=50
        )
        assert params.premium is False
