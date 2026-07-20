"""Tests des accesseurs dérivés des modèles Pydantic."""

from __future__ import annotations

from datetime import datetime, timedelta

from albion_refine.models import (
    PriceQuote,
    QuantityMode,
    SellStrategy,
    VolumeData,
)


class TestPriceQuote:
    def test_has_offers(self) -> None:
        quote = PriceQuote(
            item_id="T7_WOOD",
            city="Martlock",
            sell_price_min=245,
            sell_price_min_date=datetime(2026, 7, 19, 15, 0, 0),
            buy_price_max=210,
            buy_price_max_date=datetime(2026, 7, 19, 15, 0, 0),
        )
        assert quote.has_sell_offer is True
        assert quote.has_buy_offer is True

    def test_no_offer_when_price_zero(self) -> None:
        quote = PriceQuote(item_id="T7_PLANKS", city="Brecilien")
        assert quote.has_sell_offer is False
        assert quote.has_buy_offer is False

    def test_no_offer_when_date_missing(self) -> None:
        quote = PriceQuote(item_id="T7_WOOD", city="X", sell_price_min=100)
        assert quote.has_sell_offer is False

    def test_ages(self) -> None:
        now = datetime(2026, 7, 19, 16, 0, 0)
        quote = PriceQuote(
            item_id="T7_WOOD",
            city="Martlock",
            sell_price_min=245,
            sell_price_min_date=datetime(2026, 7, 19, 15, 0, 0),
            buy_price_max=210,
            buy_price_max_date=datetime(2026, 7, 19, 13, 0, 0),
        )
        assert quote.sell_min_age(now) == timedelta(hours=1)
        assert quote.buy_max_age(now) == timedelta(hours=3)

    def test_age_none_when_no_date(self) -> None:
        quote = PriceQuote(item_id="T7_WOOD", city="X")
        assert quote.sell_min_age(datetime(2026, 7, 19)) is None
        assert quote.buy_max_age(datetime(2026, 7, 19)) is None


class TestVolumeData:
    def test_defaults(self) -> None:
        vol = VolumeData(item_id="T7_PLANKS", city="Caerleon")
        assert vol.total_volume_24h == 0.0
        assert vol.num_points == 0


class TestEnums:
    def test_quantity_mode_values(self) -> None:
        assert QuantityMode.CAPITAL == "capital"
        assert QuantityMode.FIXED == "fixed"
        assert QuantityMode.FOCUS == "focus"

    def test_sell_strategy_values(self) -> None:
        assert SellStrategy.INSTANT_SELL == "instant_sell"
        assert SellStrategy.SELL_ORDER == "sell_order"
