"""Tests des recettes de raffinage corrigées (SPEC_FIX section 2).

La V1.0 supposait ``wood_qty = 1`` pour tous les tiers, ce qui sous-estimait
massivement le coût en bois brut aux tiers 5 à 8.
"""

from __future__ import annotations

import pytest

from albion_refine import config, refining
from albion_refine.config import PLANK_RECIPES
from albion_refine.models import QuantityMode
from albion_refine.optimizer import OptimizerParams, _resolve_quantity


class TestRecipeTable:
    def test_recipe_t7_requires_5_wood(self) -> None:
        assert PLANK_RECIPES[7] == (5, 1)

    def test_recipe_t2_has_no_lower_plank(self) -> None:
        assert PLANK_RECIPES[2] == (1, 0)

    def test_all_tiers_defined(self) -> None:
        for tier in range(2, 9):
            assert tier in PLANK_RECIPES

    @pytest.mark.parametrize(
        ("tier", "expected"),
        [(3, (2, 1)), (4, (2, 1)), (5, (3, 1)), (6, (4, 1)), (7, (5, 1)), (8, (5, 1))],
    )
    def test_full_table(self, tier: int, expected: tuple[int, int]) -> None:
        assert config.plank_recipe(tier) == expected

    def test_helpers(self) -> None:
        assert config.wood_qty_per_plank(6) == 4
        assert config.lower_plank_qty_per_plank(6) == 1
        assert config.lower_plank_qty_per_plank(2) == 0

    def test_matches_items_json(self) -> None:
        data = config.load_items_data()
        for tier, (wood_qty, lower_qty) in PLANK_RECIPES.items():
            entry = data["planks"].get(f"T{tier}_PLANKS")
            if entry is None:  # pragma: no cover - toutes les entrées existent
                continue
            assert entry["recipe"]["wood_qty"] == wood_qty
            assert entry["recipe"]["lower_plank_qty"] == lower_qty


class TestInputQuantities:
    def test_refining_cost_t7_uses_5_wood(self) -> None:
        wood_needed, lower_needed = refining.input_quantities(7, 100)
        assert wood_needed == 500
        assert lower_needed == 100
        cost = refining.compute_input_cost(7, 100, wood_price=3048, lower_plank_price=3300)
        assert cost == pytest.approx(500 * 3048 + 100 * 3300)

    def test_t2_consumes_no_lower_plank(self) -> None:
        assert refining.input_quantities(2, 50) == (50, 0)
        # Le prix du plank T-1 n'entre pas dans le coût.
        assert refining.compute_input_cost(2, 50, 100.0, 9999.0) == pytest.approx(5000.0)

    def test_unit_gross_cost_t7(self) -> None:
        expected = 5 * 3048 + 1 * 3300 + 14.175 * 0.5
        assert refining.unit_gross_cost(7, 3048, 3300, 50) == pytest.approx(expected)


class TestRrrScaling:
    def test_rrr_return_scales_with_recipe(self) -> None:
        result = refining.refine(100, 7, focus=True, station_rate=50)
        rrr = result.rrr_effectif
        assert result.wood_utilise == 500
        assert result.plank_moins_1_utilise == 100
        assert result.wood_retour == pytest.approx(500 * rrr)
        assert result.plank_moins_1_retour == pytest.approx(100 * rrr)

    def test_station_cost_unchanged_by_recipe(self) -> None:
        # Le coût station dépend du nombre d'actions (= planks), pas des inputs.
        result = refining.refine(100, 7, focus=False, station_rate=50)
        assert result.cout_station == pytest.approx(100 * 14.175 * 0.5)

    def test_focus_unchanged_by_recipe(self) -> None:
        result = refining.refine(100, 8, focus=True, station_rate=50)
        assert result.focus_utilise == pytest.approx(100 * config.FOCUS_PER_REFINE)


class TestCapitalMode:
    def test_capital_mode_uses_new_unit_cost(self) -> None:
        params = OptimizerParams(
            tier=7, mode=QuantityMode.CAPITAL, capital=500_000, station_rate=50
        )
        unit = refining.unit_gross_cost(7, 3048, 3300, 50)
        assert _resolve_quantity(params, unit) == int(500_000 // unit)

    def test_capital_mode_t2_no_division_error(self) -> None:
        params = OptimizerParams(tier=2, mode=QuantityMode.CAPITAL, capital=10_000, station_rate=50)
        # Aucun plank T-1 : le prix passé est ignoré, pas de division par zéro.
        # La nutrition du T2 n'est pas documentée dans items.json, donc on ne
        # dimensionne ici que sur le coût d'inputs (la CLI reste bornée aux T4-T8).
        unit = refining.compute_input_cost(2, 1, 100.0, 9999.0)
        assert unit == pytest.approx(100.0)
        assert _resolve_quantity(params, unit) == 100

    def test_capital_mode_zero_unit_cost_returns_zero(self) -> None:
        params = OptimizerParams(tier=2, mode=QuantityMode.CAPITAL, capital=10_000, station_rate=50)
        assert _resolve_quantity(params, 0.0) == 0
