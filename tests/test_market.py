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


class TestWalkBookDescending:
    def test_absorbs_everything_when_deep_enough(self) -> None:
        result = market.walk_book_descending([(1000.0, 500)], 128)
        assert result.total_absorbed == 128
        assert result.total_cost == pytest.approx(128000.0)

    def test_partial_absorption_is_allowed(self) -> None:
        result = market.walk_book_descending([(1000.0, 50), (900.0, 30)], 128)
        assert result.total_absorbed == 80
        assert result.total_cost == pytest.approx(50 * 1000.0 + 30 * 900.0)

    def test_empty_book(self) -> None:
        result = market.walk_book_descending([], 128)
        assert result.total_absorbed == 0
        assert result.total_cost == 0.0
        assert result.prix_moyen == 0.0

    def test_zero_quantity(self) -> None:
        assert market.walk_book_descending([(1000.0, 50)], 0).total_absorbed == 0

    def test_skips_invalid_levels(self) -> None:
        result = market.walk_book_descending([(0.0, 50), (1000.0, 10)], 10)
        assert result.total_absorbed == 10
        assert result.prix_moyen == pytest.approx(1000.0)


class TestRecoveryValue:
    def test_recovery_walks_buy_book(self) -> None:
        recovery = market.compute_recovery_value(28, [(1000.0, 100)], data_age_hours=0.1)
        assert recovery.absorbe == 28
        assert recovery.demande == 28
        assert recovery.partielle is False
        assert recovery.valeur == pytest.approx(28 * 1000.0 * 0.92)

    def test_recovery_partial_when_stack_insufficient(self) -> None:
        recovery = market.compute_recovery_value(28, [(1000.0, 15)], data_age_hours=0.1)
        assert recovery.absorbe == 15
        assert recovery.demande == 28
        assert recovery.partielle is True
        assert recovery.valeur == pytest.approx(15 * 1000.0 * 0.92)

    def test_recovery_discounts_stale_buy_max(self) -> None:
        frais = market.compute_recovery_value(28, [(1000.0, 100)], data_age_hours=0.1)
        vieux = market.compute_recovery_value(28, [(1000.0, 100)], data_age_hours=13.0)
        # V2.6 : bareme durci, > 6h : facteur 0.40.
        assert vieux.valeur == pytest.approx(frais.valeur * 0.40)
        # Le nombre absorbé ne change pas, seule la valeur est escomptée.
        assert vieux.absorbe == frais.absorbe

    def test_recovery_zero_when_no_buy_order(self) -> None:
        recovery = market.compute_recovery_value(28, [])
        assert recovery.valeur == 0.0
        assert recovery.absorbe == 0

    def test_fractional_return_is_floored(self) -> None:
        recovery = market.compute_recovery_value(27.9, [(1000.0, 100)])
        assert recovery.demande == 27


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


class TestFreshnessConfidence:
    """Pondération des revenus par l'âge de la donnée (SPEC_FIX section 6)."""

    def test_freshness_factor_1_0_for_fresh_data(self) -> None:
        assert market.freshness_confidence_factor(0.2) == 1.0

    def test_freshness_factor_0_4_for_stale_data(self) -> None:
        # Bareme durci V2.6 : au-dela de 6h la confiance tombe a 0.40.
        assert market.freshness_confidence_factor(8) == 0.40

    @pytest.mark.parametrize(
        ("age", "expected"),
        [
            (0.0, 1.0),
            (0.4, 1.0),
            (0.5, 0.95),
            (0.9, 0.95),
            (1.0, 0.85),
            (1.9, 0.85),
            (2.0, 0.70),
            (3.9, 0.70),
            (4.0, 0.55),
            (5.9, 0.55),
            (6.0, 0.40),
        ],
    )
    def test_palier_values(self, age: float, expected: float) -> None:
        assert market.freshness_confidence_factor(age) == pytest.approx(expected)

    def test_unknown_age_is_low_confidence(self) -> None:
        assert market.freshness_confidence_factor(None) == 0.5

    def test_revenue_penalized_by_stale_freshness(self) -> None:
        frais = market.evaluate_instant_sell("Lymhurst", 1000.0, 100, data_age_hours=0.2)
        vieux = market.evaluate_instant_sell("Lymhurst", 1000.0, 100, data_age_hours=3.1)
        assert frais.revenu_net == pytest.approx(vieux.revenu_net)
        # V2.6 : 3.1h tombe dans le palier 2-4h -> 0.70.
        assert vieux.freshness_factor == pytest.approx(0.70)
        assert vieux.expected_revenu == pytest.approx(frais.expected_revenu * 0.70)

    def test_sell_order_revenue_is_weighted_too(self) -> None:
        scenario = market.evaluate_sell_order(
            "Lymhurst", 1500.0, 100, volume_24h=200, data_age_hours=5.7
        )
        # V2.6 : 5.7h tombe dans le palier 4-6h -> 0.55.
        assert scenario.freshness_factor == pytest.approx(0.55)
        assert scenario.revenu_net_pondere == pytest.approx(scenario.revenu_net * 0.55)
        assert scenario.expected_revenu == pytest.approx(
            scenario.revenu_net_pondere * scenario.fill_proba
        )


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
    """Formule à trois facteurs (SPEC_FIX section 4)."""

    def test_fill_proba_never_exceeds_85_pct(self) -> None:
        proba = market.compute_fill_probability(
            quantity_to_sell=1,
            volume_24h=1_000_000,
            position_in_book=1,
            listing_price=990.0,
            top_sell_order_price=1000.0,
        )
        assert proba <= market.FILL_PROBABILITY_CAP

    def test_fill_proba_penalized_when_not_top(self) -> None:
        commun = {
            "quantity_to_sell": 128,
            "volume_24h": 300.0,
            "listing_price": 990.0,
            "top_sell_order_price": 1000.0,
        }
        top = market.compute_fill_probability(position_in_book=1, **commun)
        enterre = market.compute_fill_probability(position_in_book=3, **commun)
        assert enterre < top
        assert enterre == pytest.approx(top * (0.55 / 0.85))

    def test_fill_proba_penalized_when_price_worse_than_book(self) -> None:
        # Lister plus cher que le top applique un price_factor de 0.5.
        proba = market.compute_fill_probability(
            quantity_to_sell=128,
            volume_24h=300.0,
            position_in_book=3,
            listing_price=1010.0,
            top_sell_order_price=1000.0,
        )
        reference = market.compute_fill_probability(
            quantity_to_sell=128,
            volume_24h=300.0,
            position_in_book=3,
            listing_price=990.0,
            top_sell_order_price=1000.0,
        )
        assert proba == pytest.approx(reference * 0.5)

    def test_timid_undercut_is_penalized(self) -> None:
        proba = market.compute_fill_probability(
            quantity_to_sell=128,
            volume_24h=300.0,
            position_in_book=1,
            listing_price=999.0,  # undercut 0.1% < 0.5%
            top_sell_order_price=1000.0,
        )
        assert proba == pytest.approx(0.85 * 0.85 * 0.7)

    def test_fill_proba_realistic_for_high_volume_case(self) -> None:
        # 128 unités, volume 300/jour, undercut de 1% : ni 100%, ni négligeable.
        proba = market.compute_fill_probability(
            quantity_to_sell=128,
            volume_24h=300.0,
            position_in_book=1,
            listing_price=990.0,
            top_sell_order_price=1000.0,
        )
        assert 0.6 <= proba <= 0.8

    def test_zero_volume(self) -> None:
        assert market.compute_fill_probability(100, 0.0, 1, 990.0, 1000.0) == 0.0

    def test_no_reference_price(self) -> None:
        assert market.compute_fill_probability(100, 500.0, 1, 990.0, 0.0) == 0.0

    def test_low_volume_stays_low(self) -> None:
        proba = market.compute_fill_probability(
            quantity_to_sell=5000,
            volume_24h=300.0,
            position_in_book=1,
            listing_price=990.0,
            top_sell_order_price=1000.0,
        )
        assert proba < 0.05


class TestPositionInBook:
    def test_undercut_makes_us_top(self) -> None:
        assert market.estimate_position_in_book(990.0, 1000.0) == 1

    def test_overpriced_is_buried(self) -> None:
        assert market.estimate_position_in_book(1010.0, 1000.0) == 3


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
        # volume 200 / 100 unités, top du carnet, undercut 1% : 0.85 × 0.85 × 1.0
        assert scenario.fill_proba == pytest.approx(0.7225)
        # Sans âge connu, la confiance fraîcheur tombe à 0.50.
        assert scenario.freshness_factor == pytest.approx(0.50)
        assert scenario.expected_revenu == pytest.approx(scenario.revenu_net * 0.7225 * 0.50)

    def test_low_volume_reduces_expected(self) -> None:
        scenario = market.evaluate_sell_order("Lymhurst", 1500.0, 200, volume_24h=100)
        # ratio 0.5 → volume_factor 0.3, puis pénalité de position 0.85.
        assert scenario.fill_proba == pytest.approx(0.255)
        assert scenario.expected_revenu == pytest.approx(scenario.revenu_net_pondere * 0.255)

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
