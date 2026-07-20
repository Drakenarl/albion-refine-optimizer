"""Tests du walker d'order book, des taxes et des scénarios de vente."""

from __future__ import annotations

from datetime import timedelta

import pytest

from albion_refine import config, market
from albion_refine.models import FreshnessLevel, SellStrategy


class TestWalkBook:
    def test_single_level_exact(self) -> None:
        result = market.walk_book([(1000.0, 128)], 128)
        assert result is not None
        assert result.total_cost == pytest.approx(128000.0)
        assert result.prix_moyen == pytest.approx(1000.0)
        assert result.total_absorbed == 128

    def test_multi_level_weighted_average(self) -> None:
        # 50 @ 1000 + 30 @ 1100 = 50000 + 33000 = 83000 pour 80 unités
        result = market.walk_book([(1000.0, 50), (1100.0, 100)], 80)
        assert result is not None
        assert result.total_cost == pytest.approx(83000.0)
        assert result.prix_moyen == pytest.approx(83000.0 / 80)
        assert result.total_absorbed == 80

    def test_stops_when_satisfied(self) -> None:
        result = market.walk_book([(1000.0, 200), (2000.0, 200)], 100)
        assert result is not None
        assert result.total_cost == pytest.approx(100000.0)

    def test_insufficient_stack_returns_none(self) -> None:
        assert market.walk_book([(1000.0, 50)], 128) is None

    def test_empty_book_returns_none(self) -> None:
        assert market.walk_book([], 10) is None

    def test_zero_quantity_returns_none(self) -> None:
        assert market.walk_book([(1000.0, 50)], 0) is None

    def test_skips_empty_levels(self) -> None:
        result = market.walk_book([(1000.0, 0), (1100.0, 100)], 50)
        assert result is not None
        assert result.prix_moyen == pytest.approx(1100.0)


class TestFreshness:
    def test_fresh(self) -> None:
        level = market.classify_freshness(timedelta(hours=1), 3, 6)
        assert level == FreshnessLevel.FRESH

    def test_warning(self) -> None:
        level = market.classify_freshness(timedelta(hours=4, minutes=30), 3, 6)
        assert level == FreshnessLevel.WARNING

    def test_critical(self) -> None:
        level = market.classify_freshness(timedelta(hours=8), 3, 6)
        assert level == FreshnessLevel.CRITICAL

    def test_missing_timestamp_is_critical(self) -> None:
        assert market.classify_freshness(None, 3, 6) == FreshnessLevel.CRITICAL

    def test_boundary_warning_inclusive(self) -> None:
        assert market.classify_freshness(timedelta(hours=3), 3, 6) == FreshnessLevel.WARNING

    def test_boundary_critical_inclusive(self) -> None:
        assert market.classify_freshness(timedelta(hours=6), 3, 6) == FreshnessLevel.CRITICAL

    def test_age_hours(self) -> None:
        assert market.age_hours(timedelta(hours=2, minutes=30)) == pytest.approx(2.5)
        assert market.age_hours(None) is None


class TestTaxes:
    def test_instant_sell_tax(self) -> None:
        assert market.apply_instant_sell_tax(100000.0) == pytest.approx(92000.0)

    def test_sell_order_tax(self) -> None:
        # 13% total
        assert market.apply_sell_order_tax(100000.0) == pytest.approx(87000.0)

    def test_sell_order_tax_uses_config_total(self) -> None:
        expected = 100000.0 * (1 - config.TAX_SELL_ORDER_TOTAL)
        assert market.apply_sell_order_tax(100000.0) == pytest.approx(expected)


class TestFillProbability:
    def test_capped_at_one(self) -> None:
        assert market.fill_probability(1000, 100) == 1.0

    def test_partial(self) -> None:
        assert market.fill_probability(50, 100) == pytest.approx(0.5)

    def test_zero_volume(self) -> None:
        assert market.fill_probability(0, 100) == 0.0

    def test_zero_planks(self) -> None:
        assert market.fill_probability(100, 0) == 0.0


class TestInstantSell:
    def test_nominal(self) -> None:
        scenario = market.evaluate_instant_sell("Caerleon", 1420.0, 128, data_age_hours=0.2)
        assert scenario.strategy == SellStrategy.INSTANT_SELL
        assert scenario.stack_suffisant is True
        assert scenario.revenu_brut == pytest.approx(1420.0 * 128)
        assert scenario.revenu_net == pytest.approx(1420.0 * 128 * 0.92)
        assert scenario.expected_revenu == pytest.approx(scenario.revenu_net)
        assert scenario.fill_proba == 1.0

    def test_no_buy_offer(self) -> None:
        scenario = market.evaluate_instant_sell("Thetford", 0.0, 128)
        assert scenario.stack_suffisant is False
        assert scenario.expected_revenu == 0.0


class TestSellOrder:
    def test_nominal_with_undercut(self) -> None:
        scenario = market.evaluate_sell_order(
            "Martlock", 1500.0, 100, volume_24h=200, undercut_pct=1.0
        )
        prix_listing = 1500.0 * 0.99
        assert scenario.strategy == SellStrategy.SELL_ORDER
        assert scenario.prix_unitaire_ref == pytest.approx(prix_listing)
        assert scenario.revenu_brut == pytest.approx(prix_listing * 100)
        assert scenario.revenu_net == pytest.approx(prix_listing * 100 * 0.87)
        assert scenario.fill_proba == 1.0  # volume 200 >= 100
        assert scenario.expected_revenu == pytest.approx(scenario.revenu_net)

    def test_low_volume_reduces_expected(self) -> None:
        scenario = market.evaluate_sell_order("Lymhurst", 1500.0, 200, volume_24h=100)
        assert scenario.fill_proba == pytest.approx(0.5)
        assert scenario.expected_revenu == pytest.approx(scenario.revenu_net * 0.5)

    def test_no_sell_reference(self) -> None:
        scenario = market.evaluate_sell_order("Thetford", 0.0, 100, volume_24h=200)
        assert scenario.stack_suffisant is False
        assert scenario.expected_revenu == 0.0

    def test_zero_volume_excludes(self) -> None:
        scenario = market.evaluate_sell_order("Thetford", 1500.0, 100, volume_24h=0)
        assert scenario.fill_proba == 0.0
        assert scenario.expected_revenu == 0.0


class TestBestScenario:
    def test_prefers_higher_expected(self) -> None:
        a = market.evaluate_instant_sell("Caerleon", 1000.0, 100)
        b = market.evaluate_sell_order("Caerleon", 2000.0, 100, volume_24h=1000)
        best = market.best_scenario([a, b])
        assert best is b  # sell order rapporte plus ici

    def test_instant_preferred_on_tie(self) -> None:
        a = market.evaluate_instant_sell("Caerleon", 1000.0, 100)
        # Construit un sell order avec exactement le même expected que l'instant.
        b = a.model_copy(update={"strategy": SellStrategy.SELL_ORDER})
        best = market.best_scenario([a, b])
        assert best is not None
        assert best.strategy == SellStrategy.INSTANT_SELL

    def test_returns_none_when_all_unviable(self) -> None:
        a = market.evaluate_instant_sell("Thetford", 0.0, 100)
        b = market.evaluate_sell_order("Thetford", 0.0, 100, volume_24h=0)
        assert market.best_scenario([a, b]) is None

    def test_returns_none_on_empty(self) -> None:
        assert market.best_scenario([]) is None
