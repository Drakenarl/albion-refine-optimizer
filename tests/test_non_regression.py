"""Tests de non-régression de la V1.1 (checklist SPEC_FIX section 8).

Vérifie que l'optimiseur traverse tous les tiers supportés sans crash, que le
cas particulier sans plank T-1 est géré, et que les données périmées restent
correctement filtrées après l'introduction des recettes et de la pondération.
"""

from __future__ import annotations

from datetime import datetime

import pytest

from albion_refine import config
from albion_refine.models import PriceQuote, QuantityMode, VolumeData
from albion_refine.optimizer import OptimizerParams, optimize
from tests.conftest import load_fixture
from tests.test_optimizer import _quote

NOW = datetime(2026, 7, 19, 15, 20, 0)
WHEN = datetime(2026, 7, 19, 15, 0, 0)


def _market_for_tier(tier: int) -> tuple[list[PriceQuote], list[VolumeData]]:
    """Construit un marché synthétique complet pour un tier donné."""
    wood = config.wood_item_id(tier)
    output = config.plank_item_id(tier)
    quotes = [
        _quote(wood, "Martlock", sell=100, when=WHEN),
        _quote(wood, config.REFINING_CITY, sell=110, buy=90, when=WHEN),
        _quote(output, "Lymhurst", sell=1200, buy=1000, when=WHEN),
    ]
    volumes = [
        VolumeData(item_id=output, city="Lymhurst", total_volume_24h=1000),
        VolumeData(item_id=wood, city=config.REFINING_CITY, total_volume_24h=5000),
    ]
    if config.lower_plank_qty_per_plank(tier):
        lower = config.plank_item_id(tier - 1)
        quotes += [
            _quote(lower, "Martlock", sell=300, when=WHEN),
            _quote(lower, config.REFINING_CITY, sell=320, buy=280, when=WHEN),
        ]
        volumes.append(VolumeData(item_id=lower, city=config.REFINING_CITY, total_volume_24h=5000))
    return quotes, volumes


class TestAllTiers:
    @pytest.mark.parametrize("tier", config.SUPPORTED_TIERS)
    def test_optimize_runs_for_every_supported_tier(self, tier: int) -> None:
        quotes, volumes = _market_for_tier(tier)
        params = OptimizerParams(
            tier=tier,
            mode=QuantityMode.CAPITAL,
            capital=500_000,
            station_rate=50,
            seuil_marge_min_pct=-1000,
        )
        result = optimize(params, quotes, volumes, NOW)
        assert result.run_metadata.tier == tier
        route = result.routes[0]
        # Les quantités d'inputs suivent bien la recette du tier.
        wood_qty, lower_qty = config.plank_recipe(tier)
        assert route.achat_wood.quantite == route.quantite * wood_qty
        if lower_qty:
            assert route.achat_plank is not None
            assert route.achat_plank.quantite == route.quantite * lower_qty

    def test_tier_without_lower_plank_does_not_crash(self) -> None:
        # Recette T2 : aucun plank T-1, la phase 2 est court-circuitée.
        quotes = [
            _quote("T2_WOOD", "Martlock", sell=50, when=WHEN),
            _quote("T2_PLANKS", "Lymhurst", sell=400, buy=350, when=WHEN),
        ]
        volumes = [VolumeData(item_id="T2_PLANKS", city="Lymhurst", total_volume_24h=500)]
        params = OptimizerParams(
            tier=2,
            mode=QuantityMode.FIXED,
            quantite=50,
            station_rate=0,
            seuil_marge_min_pct=-1000,
        )
        # La nutrition du T2 n'est pas documentée : la formule de station lève un
        # KeyError explicite plutôt que d'inventer une valeur. La CLI borne donc
        # les tiers autorisés à 4-8 (config.SUPPORTED_TIERS).
        with pytest.raises(KeyError):
            optimize(params, quotes, volumes, NOW)
        assert 2 not in config.SUPPORTED_TIERS


class TestStaleData:
    def test_critical_cities_are_excluded(self) -> None:
        from albion_refine.aodp_client import _quote_from_entry

        quotes = [_quote_from_entry(entry) for entry in load_fixture("aodp_stale_data.json")]
        volumes = [
            VolumeData(item_id="T7_PLANKS", city=city, total_volume_24h=800)
            for city in ("Bridgewatch", "Thetford", "Martlock")
        ]
        params = OptimizerParams(
            tier=7,
            mode=QuantityMode.FIXED,
            quantite=64,
            station_rate=50,
            seuil_marge_min_pct=-1000,
        )
        result = optimize(params, quotes, volumes, NOW)
        # Bridgewatch (8h) ne doit jamais servir de source d'achat.
        for route in result.routes:
            assert route.achat_wood.city != "Bridgewatch"

    def test_stale_sale_is_discounted(self) -> None:
        vieux = _quote("T4_PLANKS", "Lymhurst", sell=600, buy=500, when=datetime(2026, 7, 19, 10))
        frais = _quote("T4_PLANKS", "Lymhurst", sell=600, buy=500, when=WHEN)
        base = [_quote("T4_WOOD", "Martlock", sell=100, when=WHEN)]
        base += [_quote("T3_PLANKS", "Martlock", sell=100, when=WHEN)]
        volumes = [VolumeData(item_id="T4_PLANKS", city="Lymhurst", total_volume_24h=1000)]
        params = OptimizerParams(
            tier=4,
            mode=QuantityMode.FIXED,
            quantite=100,
            station_rate=100,
            ignore_recup=True,
            seuil_marge_min_pct=-1000,
        )
        marge_vieille = optimize(params, [*base, vieux], volumes, NOW).routes[0].marge_pct
        marge_fraiche = optimize(params, [*base, frais], volumes, NOW).routes[0].marge_pct
        assert marge_vieille < marge_fraiche
