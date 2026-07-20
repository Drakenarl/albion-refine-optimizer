"""Tests exhaustifs des formules de raffinage (cible : 100% de couverture)."""

from __future__ import annotations

import pytest

from albion_refine import config, refining


class TestTotalBonus:
    def test_base_only(self) -> None:
        assert refining.total_bonus_pct(focus=False, daily_bonus_pct=0) == 58

    def test_focus_only(self) -> None:
        assert refining.total_bonus_pct(focus=True, daily_bonus_pct=0) == 117

    def test_focus_and_daily(self) -> None:
        assert refining.total_bonus_pct(focus=True, daily_bonus_pct=20) == 137

    def test_daily_without_focus(self) -> None:
        assert refining.total_bonus_pct(focus=False, daily_bonus_pct=10) == 68


class TestComputeRrr:
    def test_no_focus_no_daily(self) -> None:
        assert refining.compute_rrr(focus=False) == pytest.approx(0.3671, abs=1e-4)

    def test_focus_no_daily(self) -> None:
        assert refining.compute_rrr(focus=True) == pytest.approx(0.5392, abs=1e-4)

    def test_focus_daily_20(self) -> None:
        assert refining.compute_rrr(focus=True, daily_bonus_pct=20) == pytest.approx(
            0.5781, abs=1e-4
        )

    def test_focus_daily_10(self) -> None:
        # total = 58 + 59 + 10 = 127 → 1 - 1/2.27
        assert refining.compute_rrr(focus=True, daily_bonus_pct=10) == pytest.approx(
            0.5595, abs=1e-4
        )

    def test_rrr_bounds(self) -> None:
        rrr = refining.compute_rrr(focus=True, daily_bonus_pct=20)
        assert 0.0 < rrr < 1.0


class TestStationCost:
    @pytest.mark.parametrize(
        ("tier", "rate", "quantity", "expected"),
        [
            # coût = Q × nutrition_par_unité × (rate / 100)
            (4, 0, 100, 0.0),
            (7, 50, 100, 100 * 14.175 * 0.5),
            (7, 20, 128, 128 * 14.175 * 0.2),
            (8, 50, 64, 64 * 28.575 * 0.5),
            (4, 500, 100, 100 * 1.575 * 5.0),
        ],
    )
    def test_values(self, tier: int, rate: float, quantity: int, expected: float) -> None:
        assert refining.station_cost(quantity, tier, rate) == pytest.approx(expected)

    def test_rate_zero_is_free(self) -> None:
        assert refining.station_cost(128, 7, 0) == 0.0

    def test_unknown_tier_raises(self) -> None:
        with pytest.raises(KeyError):
            refining.station_cost(10, 3, 50)


class TestFocusUsed:
    def test_default_one_per_unit(self) -> None:
        assert refining.focus_used(128) == pytest.approx(128 * config.FOCUS_PER_REFINE)

    def test_zero(self) -> None:
        assert refining.focus_used(0) == 0.0


class TestRefine:
    def test_outputs_coherent(self) -> None:
        result = refining.refine(128, 7, focus=True, daily_bonus_pct=0, station_rate=50)
        rrr = refining.compute_rrr(focus=True)
        assert result.planks_produits == 128
        assert result.wood_retour == pytest.approx(128 * rrr)
        assert result.plank_moins_1_retour == pytest.approx(128 * rrr)
        assert result.rrr_effectif == pytest.approx(rrr)
        assert result.cout_station == pytest.approx(128 * 14.175 * 0.5)
        assert result.focus_utilise == pytest.approx(128 * config.FOCUS_PER_REFINE)

    def test_rrr_applies_to_both_inputs(self) -> None:
        result = refining.refine(100, 6, focus=False, station_rate=50)
        assert result.wood_retour == result.plank_moins_1_retour

    def test_no_focus_means_zero_focus_used(self) -> None:
        result = refining.refine(50, 5, focus=False, station_rate=30)
        assert result.focus_utilise == 0.0

    def test_daily_bonus_increases_rrr(self) -> None:
        without = refining.refine(100, 7, focus=True, daily_bonus_pct=0, station_rate=50)
        with_daily = refining.refine(100, 7, focus=True, daily_bonus_pct=20, station_rate=50)
        assert with_daily.rrr_effectif > without.rrr_effectif
