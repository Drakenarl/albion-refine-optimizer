"""Tests de l'enchantement (.0 -> .4) sur bois et peau (V2.3).

L'enchant ne change PAS la logique metier : recette identique, memes formules
de raffinage. Il change uniquement les item IDs demandes a l'AODP (suffixe
``_LEVELn@n``). On verifie donc trois choses :
1. Les IDs generes par Resource sont corrects pour tous les niveaux.
2. Un run T5 .1 wood interroge bien T5_WOOD_LEVEL1@1 + T4_PLANKS_LEVEL1@1.
3. Un enchant hors [0, 4] est rejete par Pydantic.
"""

from __future__ import annotations

from datetime import datetime

import pytest
from pydantic import ValidationError

from albion_refine import config
from albion_refine.config import Resource
from albion_refine.models import (
    PriceQuote,
    QuantityMode,
    ResourceKind,
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


class TestEnchantItemIds:
    """L'API Resource.raw_item_id/refined_item_id ajoute le suffixe attendu."""

    def test_base_enchant_unchanged(self) -> None:
        res = config.resource(ResourceKind.WOOD)
        assert res.raw_item_id(7, enchant=0) == "T7_WOOD"
        assert res.refined_item_id(7, enchant=0) == "T7_PLANKS"
        # Defaut = 0 : ne casse pas les appels existants sans enchant.
        assert res.raw_item_id(5) == "T5_WOOD"
        assert res.refined_item_id(5) == "T5_PLANKS"

    def test_wood_enchant_1_to_4(self) -> None:
        res = config.resource(ResourceKind.WOOD)
        assert res.raw_item_id(7, 1) == "T7_WOOD_LEVEL1@1"
        assert res.refined_item_id(7, 2) == "T7_PLANKS_LEVEL2@2"
        assert res.raw_item_id(5, 3) == "T5_WOOD_LEVEL3@3"
        assert res.refined_item_id(8, 4) == "T8_PLANKS_LEVEL4@4"

    def test_hide_enchant_maps_to_leather(self) -> None:
        res = config.resource(ResourceKind.HIDE)
        assert res.raw_item_id(6, 2) == "T6_HIDE_LEVEL2@2"
        assert res.refined_item_id(7, 1) == "T7_LEATHER_LEVEL1@1"

    def test_supported_range(self) -> None:
        assert config.SUPPORTED_ENCHANTS == (0, 1, 2, 3, 4)


class TestOptimizerParamsEnchantValidation:
    """Pydantic doit rejeter les niveaux hors [0, 4]."""

    def test_default_is_zero(self) -> None:
        params = OptimizerParams(
            tier=5, mode=QuantityMode.FIXED, quantite=10, station_rate=50
        )
        assert params.enchant == 0

    def test_valid_levels_accepted(self) -> None:
        for level in (0, 1, 2, 3, 4):
            params = OptimizerParams(
                tier=5,
                mode=QuantityMode.FIXED,
                quantite=10,
                station_rate=50,
                enchant=level,
            )
            assert params.enchant == level

    def test_rejects_out_of_range(self) -> None:
        with pytest.raises(ValidationError):
            OptimizerParams(
                tier=5, mode=QuantityMode.FIXED, quantite=10, station_rate=50, enchant=5
            )
        with pytest.raises(ValidationError):
            OptimizerParams(
                tier=5, mode=QuantityMode.FIXED, quantite=10, station_rate=50, enchant=-1
            )


class TestEnchantedPipelineWood:
    """Un run T5 wood enchant .1 utilise les IDs enchantes de bout en bout."""

    def test_wood_enchant_1_uses_enchanted_ids(self) -> None:
        now = datetime(2026, 7, 22, 15, 20, 0)
        when = datetime(2026, 7, 22, 15, 0, 0)
        quotes = [
            # Bois brut enchante .1
            _q("T5_WOOD_LEVEL1@1", "Bridgewatch", sell=200, when=when),
            _q("T5_WOOD_LEVEL1@1", "Fort Sterling", sell=250, buy=180, when=when),
            # Plank T-1 enchante .1
            _q("T4_PLANKS_LEVEL1@1", "Fort Sterling", sell=400, buy=300, when=when),
            _q("T4_PLANKS_LEVEL1@1", "Martlock", sell=450, when=when),
            # Plank T5 enchante .1 (sortie)
            _q("T5_PLANKS_LEVEL1@1", "Lymhurst", sell=1200, buy=1000, when=when),
        ]
        volumes = [
            VolumeData(item_id="T5_PLANKS_LEVEL1@1", city="Lymhurst", total_volume_24h=500),
            VolumeData(item_id="T5_WOOD_LEVEL1@1", city="Fort Sterling", total_volume_24h=5000),
            VolumeData(item_id="T4_PLANKS_LEVEL1@1", city="Fort Sterling", total_volume_24h=5000),
        ]
        params = OptimizerParams(
            tier=5,
            mode=QuantityMode.FIXED,
            quantite=100,
            station_rate=100,
            seuil_marge_min_pct=-1000,
            resource=ResourceKind.WOOD,
            enchant=1,
        )
        result = optimize(params, quotes, volumes, now)
        assert result.routes, "au moins une route doit exister"
        r = result.routes[0]
        assert r.enchant == 1
        assert r.resource_kind is ResourceKind.WOOD
        assert r.achat_wood.item_id == "T5_WOOD_LEVEL1@1"
        assert r.achat_plank is not None
        assert r.achat_plank.item_id == "T4_PLANKS_LEVEL1@1"

    def test_hide_enchant_2_uses_enchanted_leather_ids(self) -> None:
        now = datetime(2026, 7, 22, 15, 20, 0)
        when = datetime(2026, 7, 22, 15, 0, 0)
        quotes = [
            _q("T5_HIDE_LEVEL2@2", "Bridgewatch", sell=300, when=when),
            _q("T5_HIDE_LEVEL2@2", "Martlock", sell=400, buy=280, when=when),
            _q("T4_LEATHER_LEVEL2@2", "Martlock", sell=600, buy=500, when=when),
            _q("T5_LEATHER_LEVEL2@2", "Lymhurst", sell=1800, buy=1500, when=when),
        ]
        volumes = [
            VolumeData(item_id="T5_LEATHER_LEVEL2@2", city="Lymhurst", total_volume_24h=300),
            VolumeData(item_id="T5_HIDE_LEVEL2@2", city="Martlock", total_volume_24h=3000),
            VolumeData(item_id="T4_LEATHER_LEVEL2@2", city="Martlock", total_volume_24h=3000),
        ]
        params = OptimizerParams(
            tier=5,
            mode=QuantityMode.FIXED,
            quantite=50,
            station_rate=100,
            seuil_marge_min_pct=-1000,
            resource=ResourceKind.HIDE,
            enchant=2,
        )
        result = optimize(params, quotes, volumes, now)
        assert result.routes
        r = result.routes[0]
        assert r.enchant == 2
        assert r.resource_kind is ResourceKind.HIDE
        assert r.achat_wood.item_id == "T5_HIDE_LEVEL2@2"
        assert r.achat_plank is not None
        assert r.achat_plank.item_id == "T4_LEATHER_LEVEL2@2"


class TestNoRegressionOnBase:
    """L'enchant=0 (defaut) doit produire exactement le comportement d'avant V2.3."""

    def test_base_run_uses_unenchanted_ids(self) -> None:
        now = datetime(2026, 7, 22, 15, 20, 0)
        when = datetime(2026, 7, 22, 15, 0, 0)
        quotes = [
            _q("T5_WOOD", "Bridgewatch", sell=100, when=when),
            _q("T5_WOOD", "Fort Sterling", sell=120, buy=90, when=when),
            _q("T4_PLANKS", "Fort Sterling", sell=200, buy=150, when=when),
            _q("T5_PLANKS", "Lymhurst", sell=600, buy=500, when=when),
        ]
        volumes = [
            VolumeData(item_id="T5_PLANKS", city="Lymhurst", total_volume_24h=500),
            VolumeData(item_id="T5_WOOD", city="Fort Sterling", total_volume_24h=5000),
        ]
        params = OptimizerParams(
            tier=5,
            mode=QuantityMode.FIXED,
            quantite=50,
            station_rate=100,
            seuil_marge_min_pct=-1000,
            # enchant par defaut = 0
        )
        result = optimize(params, quotes, volumes, now)
        assert result.routes
        r = result.routes[0]
        assert r.enchant == 0
        assert r.achat_wood.item_id == "T5_WOOD"
        assert r.achat_plank is not None
        assert r.achat_plank.item_id == "T4_PLANKS"
