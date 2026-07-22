"""Tests de la filiere peau -> cuir (V2.2).

La logique metier est identique au bois, seuls changent les item IDs AODP et
la ville specialite. On verifie ici que :
1. L'abstraction Resource produit les bons IDs et pointe vers Martlock.
2. Un run complet avec ``resource=hide`` interroge bien T{tier}_HIDE et
   T{tier}_LEATHER, refine a Martlock, et ne regresse pas la logique wood.
"""

from __future__ import annotations

from datetime import datetime

from albion_refine import config, optimizer
from albion_refine.models import (
    PriceQuote,
    QuantityMode,
    RecupMode,
    ResourceKind,
    VolumeData,
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


class TestResourceAbstraction:
    """L'API config.resource() expose les bons IDs et villes."""

    def test_wood_default(self) -> None:
        res = config.resource(ResourceKind.WOOD)
        assert res.raw_item_id(7) == "T7_WOOD"
        assert res.refined_item_id(6) == "T6_PLANKS"
        assert res.refining_city == "Fort Sterling"
        assert res.display_raw == "bois"
        assert res.display_refined == "plank"

    def test_hide_maps_to_leather_at_martlock(self) -> None:
        res = config.resource(ResourceKind.HIDE)
        assert res.raw_item_id(7) == "T7_HIDE"
        assert res.refined_item_id(6) == "T6_LEATHER"
        assert res.refining_city == "Martlock"
        assert res.display_raw == "peau"
        assert res.display_refined == "cuir"

    def test_accepts_slug_string(self) -> None:
        # Utile pour l'API HTTP qui reçoit une string.
        assert config.resource("wood").kind is ResourceKind.WOOD
        assert config.resource("hide").kind is ResourceKind.HIDE
        assert config.resource("fiber").kind is ResourceKind.FIBER
        assert config.resource("ore").kind is ResourceKind.ORE
        assert config.resource("stone").kind is ResourceKind.STONE

    def test_fiber_maps_to_cloth_at_lymhurst(self) -> None:
        res = config.resource(ResourceKind.FIBER)
        assert res.raw_item_id(7) == "T7_FIBER"
        assert res.refined_item_id(6) == "T6_CLOTH"
        assert res.refining_city == "Lymhurst"
        assert res.display_raw == "fibre"
        assert res.display_refined == "tissu"

    def test_ore_maps_to_metalbar_at_thetford(self) -> None:
        res = config.resource(ResourceKind.ORE)
        assert res.raw_item_id(7) == "T7_ORE"
        assert res.refined_item_id(6) == "T6_METALBAR"
        assert res.refining_city == "Thetford"
        assert res.display_raw == "minerai"
        assert res.display_refined == "lingot"

    def test_stone_maps_to_stoneblock_at_bridgewatch(self) -> None:
        res = config.resource(ResourceKind.STONE)
        # Attention : la pierre brute est encodee "ROCK" (pas "STONE") cote AODP.
        assert res.raw_item_id(7) == "T7_ROCK"
        assert res.refined_item_id(6) == "T6_STONEBLOCK"
        assert res.refining_city == "Bridgewatch"
        assert res.display_raw == "pierre"
        assert res.display_refined == "bloc de pierre"


class TestHidePipeline:
    """Un run T4 hide doit interroger T4_HIDE + T3_LEATHER et refine a Martlock."""

    def _run(self) -> optimizer.OptimizationResult:
        now = datetime(2026, 7, 21, 15, 20, 0)
        when = datetime(2026, 7, 21, 15, 0, 0)
        quotes = [
            _quote("T4_HIDE", "Bridgewatch", sell=80, when=when),
            _quote("T3_LEATHER", "Bridgewatch", sell=150, when=when),
            _quote("T4_HIDE", "Martlock", sell=90, buy=70, when=when),
            _quote("T3_LEATHER", "Martlock", sell=180, buy=140, when=when),
            _quote("T4_LEATHER", "Lymhurst", sell=500, buy=420, when=when),
        ]
        volumes = [
            VolumeData(item_id="T4_LEATHER", city="Lymhurst", total_volume_24h=1000),
            VolumeData(item_id="T4_HIDE", city="Martlock", total_volume_24h=10_000),
            VolumeData(item_id="T3_LEATHER", city="Martlock", total_volume_24h=10_000),
            VolumeData(item_id="T4_HIDE", city="Lymhurst", total_volume_24h=10_000),
            VolumeData(item_id="T3_LEATHER", city="Lymhurst", total_volume_24h=10_000),
        ]
        params = OptimizerParams(
            tier=4,
            mode=QuantityMode.FIXED,
            quantite=100,
            station_rate=100,
            seuil_marge_min_pct=-1000,
            resource=ResourceKind.HIDE,
            recup_mode=RecupMode.LOCAL,
        )
        return optimize(params, quotes, volumes, now)

    def test_hide_route_uses_leather_items(self) -> None:
        route = self._run().routes[0]
        assert route.resource_kind is ResourceKind.HIDE
        assert route.achat_wood.item_id == "T4_HIDE"
        assert route.achat_plank is not None
        assert route.achat_plank.item_id == "T3_LEATHER"

    def test_hide_recup_local_targets_martlock(self) -> None:
        route = self._run().routes[0]
        # RecupMode.LOCAL doit valoriser au carnet Martlock (ville specialite peau).
        assert route.recup_city == "Martlock"


class TestWoodStillWorks:
    """Regression : wood avec le nouveau code doit se comporter comme avant."""

    def _run(self) -> optimizer.OptimizationResult:
        now = datetime(2026, 7, 21, 15, 20, 0)
        when = datetime(2026, 7, 21, 15, 0, 0)
        quotes = [
            _quote("T4_WOOD", "Martlock", sell=100, when=when),
            _quote("T3_PLANKS", "Martlock", sell=200, when=when),
            _quote("T4_WOOD", "Fort Sterling", sell=120, buy=90, when=when),
            _quote("T3_PLANKS", "Fort Sterling", sell=220, buy=180, when=when),
            _quote("T4_PLANKS", "Lymhurst", sell=600, buy=500, when=when),
        ]
        volumes = [
            VolumeData(item_id="T4_PLANKS", city="Lymhurst", total_volume_24h=1000),
            VolumeData(item_id="T4_WOOD", city="Fort Sterling", total_volume_24h=10_000),
        ]
        params = OptimizerParams(
            tier=4,
            mode=QuantityMode.FIXED,
            quantite=100,
            station_rate=100,
            seuil_marge_min_pct=-1000,
            recup_mode=RecupMode.LOCAL,
            # resource par defaut = WOOD
        )
        return optimize(params, quotes, volumes, now)

    def test_wood_default_still_uses_planks_at_fs(self) -> None:
        route = self._run().routes[0]
        assert route.resource_kind is ResourceKind.WOOD
        assert route.achat_wood.item_id == "T4_WOOD"
        assert route.achat_plank is not None
        assert route.achat_plank.item_id == "T3_PLANKS"
        assert route.recup_city == "Fort Sterling"
