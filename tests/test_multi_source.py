"""Tests du sourcing multi-villes (V2.9).

L'algo greedy alloue une quantite demandee sur plusieurs villes classees par
prix ascendant, en s'arretant a ``saturation_per_city × volume_24h`` par
ville. On verifie ici les proprietes attendues et quelques cas limites.
"""

from __future__ import annotations

from datetime import datetime

import pytest

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


class TestGreedyAllocation:
    """L'allocation doit prioriser les villes les moins cheres et respecter les caps."""

    def _run(
        self, max_source_cities: int, saturation: float
    ) -> list["object"]:
        now = datetime(2026, 7, 22, 15, 20, 0)
        when = datetime(2026, 7, 22, 15, 0, 0)
        # 3 villes candidates pour le bois avec prix croissants et volumes decroissants.
        quotes = [
            _q("T4_WOOD", "Caerleon", sell=100, when=when),
            _q("T4_WOOD", "Bridgewatch", sell=110, when=when),
            _q("T4_WOOD", "Lymhurst", sell=130, when=when),
            _q("T3_PLANKS", "Fort Sterling", sell=200, buy=180, when=when),
            _q("T4_PLANKS", "Lymhurst", sell=600, buy=500, when=when),
        ]
        volumes = [
            VolumeData(item_id="T4_PLANKS", city="Lymhurst", total_volume_24h=1000),
            # Caerleon peu profond, les autres plus.
            VolumeData(item_id="T4_WOOD", city="Caerleon", total_volume_24h=400),
            VolumeData(item_id="T4_WOOD", city="Bridgewatch", total_volume_24h=2_000),
            VolumeData(item_id="T4_WOOD", city="Lymhurst", total_volume_24h=10_000),
            VolumeData(item_id="T3_PLANKS", city="Fort Sterling", total_volume_24h=100_000),
        ]
        params = OptimizerParams(
            tier=4,
            mode=QuantityMode.FIXED,
            quantite=100,  # -> 200 bois demandes
            station_rate=100,
            seuil_marge_min_pct=-10_000,
            max_source_cities=max_source_cities,
            saturation_per_city=saturation,
        )
        return optimize(params, quotes, volumes, now).routes

    def test_mono_source_when_max_is_1(self) -> None:
        """max=1 : tout part sur Caerleon (la moins chere)."""
        routes = self._run(max_source_cities=1, saturation=0.25)
        route = routes[0]
        assert len(route.achat_wood.allocations) == 1
        assert route.achat_wood.allocations[0].city == "Caerleon"
        assert route.achat_wood.allocations[0].quantite == 200

    def test_split_across_cheapest_cities(self) -> None:
        """Avec saturation 25%, 200 bois > 100 (25% de 400 Caerleon) -> split."""
        routes = self._run(max_source_cities=3, saturation=0.25)
        route = routes[0]
        allocs = route.achat_wood.allocations
        # Au moins 2 villes visitees.
        assert len(allocs) >= 2
        cities = [a.city for a in allocs]
        # Caerleon (la moins chere) doit etre la premiere allocation.
        assert cities[0] == "Caerleon"
        # Sa quantite est limitee par le cap 25% × 400 = 100.
        assert allocs[0].quantite == 100
        # Le total doit sommer a 200.
        assert sum(a.quantite for a in allocs) == 200

    def test_saturation_100pct_uses_only_cheapest(self) -> None:
        """Saturation 100% : Caerleon peut absorber la totalite -> mono-source."""
        routes = self._run(max_source_cities=3, saturation=1.0)
        route = routes[0]
        allocs = route.achat_wood.allocations
        # Caerleon peut absorber 100% × 400 = 400, on demande 200 -> tout Caerleon.
        assert len(allocs) == 1
        assert allocs[0].city == "Caerleon"
        assert allocs[0].quantite == 200

    def test_blended_price_is_weighted_average(self) -> None:
        routes = self._run(max_source_cities=3, saturation=0.25)
        route = routes[0]
        allocs = route.achat_wood.allocations
        total_qty = sum(a.quantite for a in allocs)
        total_cost = sum(a.cout_total for a in allocs)
        expected_blend = total_cost / total_qty
        assert route.achat_wood.prix_unitaire == pytest.approx(expected_blend, abs=0.01)
        assert route.achat_wood.cout_total == pytest.approx(total_cost, abs=0.01)


class TestParamValidation:
    """Pydantic valide les bornes des nouveaux params."""

    def test_max_source_cities_range(self) -> None:
        # 1 -> 6 valides.
        for n in (1, 3, 6):
            OptimizerParams(
                tier=5,
                mode=QuantityMode.FIXED,
                quantite=10,
                station_rate=50,
                max_source_cities=n,
            )
        # Hors bornes.
        from pydantic import ValidationError

        with pytest.raises(ValidationError):
            OptimizerParams(
                tier=5,
                mode=QuantityMode.FIXED,
                quantite=10,
                station_rate=50,
                max_source_cities=0,
            )
        with pytest.raises(ValidationError):
            OptimizerParams(
                tier=5,
                mode=QuantityMode.FIXED,
                quantite=10,
                station_rate=50,
                max_source_cities=7,
            )

    def test_saturation_range(self) -> None:
        for s in (0.05, 0.25, 1.0):
            OptimizerParams(
                tier=5,
                mode=QuantityMode.FIXED,
                quantite=10,
                station_rate=50,
                saturation_per_city=s,
            )
        from pydantic import ValidationError

        with pytest.raises(ValidationError):
            OptimizerParams(
                tier=5,
                mode=QuantityMode.FIXED,
                quantite=10,
                station_rate=50,
                saturation_per_city=0.01,
            )
        with pytest.raises(ValidationError):
            OptimizerParams(
                tier=5,
                mode=QuantityMode.FIXED,
                quantite=10,
                station_rate=50,
                saturation_per_city=1.5,
            )


class TestResourceCompat:
    """Test rapide : le multi-source marche sur toutes les filieres."""

    def test_hide_multi_source(self) -> None:
        now = datetime(2026, 7, 22, 15, 20, 0)
        when = datetime(2026, 7, 22, 15, 0, 0)
        quotes = [
            _q("T4_HIDE", "Bridgewatch", sell=80, when=when),
            _q("T4_HIDE", "Caerleon", sell=90, when=when),
            _q("T3_LEATHER", "Martlock", sell=180, buy=160, when=when),
            _q("T4_LEATHER", "Lymhurst", sell=500, buy=420, when=when),
        ]
        volumes = [
            VolumeData(item_id="T4_LEATHER", city="Lymhurst", total_volume_24h=1000),
            VolumeData(item_id="T4_HIDE", city="Bridgewatch", total_volume_24h=150),
            VolumeData(item_id="T4_HIDE", city="Caerleon", total_volume_24h=1_000),
            VolumeData(item_id="T3_LEATHER", city="Martlock", total_volume_24h=10_000),
        ]
        params = OptimizerParams(
            tier=4,
            mode=QuantityMode.FIXED,
            quantite=100,
            station_rate=100,
            resource=ResourceKind.HIDE,
            seuil_marge_min_pct=-10_000,
            max_source_cities=3,
            saturation_per_city=0.25,
        )
        result = optimize(params, quotes, volumes, now)
        route = result.routes[0]
        assert len(route.achat_wood.allocations) >= 2  # split car Bridgewatch trop mince
        # La moins chere en tete.
        assert route.achat_wood.allocations[0].city == "Bridgewatch"
