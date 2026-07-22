"""Tests du module de configuration.

Vérifie la cohérence des constantes (item IDs, villes, taxes, nutrition) et
leur alignement avec le fichier ``items.json`` embarqué.
"""

from __future__ import annotations

from albion_refine import config


class TestTiers:
    def test_supported_tiers(self) -> None:
        assert config.SUPPORTED_TIERS == (4, 5, 6, 7, 8)
        assert config.MIN_TIER == 4
        assert config.MAX_TIER == 8


class TestItemIds:
    def test_wood_ids(self) -> None:
        assert config.wood_item_id(7) == "T7_WOOD"
        assert config.WOOD_ITEM_IDS[4] == "T4_WOOD"
        assert set(config.WOOD_ITEM_IDS) == {4, 5, 6, 7, 8}

    def test_plank_ids_include_t3(self) -> None:
        # Le T3 est nécessaire comme input du T4 (cascade des tiers).
        assert config.plank_item_id(3) == "T3_PLANKS"
        assert config.plank_item_id(6) == "T6_PLANKS"
        assert set(config.PLANK_ITEM_IDS) == {3, 4, 5, 6, 7, 8}

    def test_ids_match_items_json(self) -> None:
        data = config.load_items_data()
        for tier, item_id in config.WOOD_ITEM_IDS.items():
            assert data["wood"][item_id]["tier"] == tier
        for tier, item_id in config.PLANK_ITEM_IDS.items():
            assert data["planks"][item_id]["tier"] == tier


class TestCities:
    def test_refining_and_red_zone(self) -> None:
        assert config.REFINING_CITY == "Fort Sterling"
        assert config.RED_ZONE_CITY == "Caerleon"
        assert config.CITIES["Fort Sterling"]["wood_refining_bonus"] is True
        assert config.CITIES["Caerleon"]["safe"] is False

    def test_helpers(self) -> None:
        assert "Fort Sterling" in config.all_cities()
        assert "Caerleon" not in config.safe_cities()
        assert "Fort Sterling" in config.safe_cities()


class TestRefiningBonuses:
    def test_base_bonus_is_58(self) -> None:
        assert config.CITY_BONUS_PCT == 18
        assert config.WOOD_SPECIALTY_BONUS_PCT == 40
        assert config.BASE_REFINING_BONUS_PCT == 58
        assert config.FOCUS_BONUS_PCT == 59

    def test_allowed_daily_bonus(self) -> None:
        assert config.ALLOWED_DAILY_BONUS_PCT == (0, 10, 20)


class TestNutrition:
    def test_values_match_correction(self) -> None:
        assert config.nutrition_per_unit(7) == 14.175
        assert config.NUTRITION_PER_REFINED_UNIT == {
            4: 1.575,
            5: 3.375,
            6: 6.975,
            7: 14.175,
            8: 28.575,
        }

    def test_nutrition_equals_item_value_times_factor(self) -> None:
        # Nutrition = Item Value × 0.1125 (voir CORRECTIONS_URGENTES).
        for tier, iv in config.REFINED_ITEM_VALUES.items():
            expected = round(iv * 0.1125, 4)
            assert round(config.nutrition_per_unit(tier), 4) == expected

    def test_matches_items_json(self) -> None:
        data = config.load_items_data()
        for tier, value in config.NUTRITION_PER_REFINED_UNIT.items():
            assert data["nutrition_per_refined_unit"][f"T{tier}"] == value


class TestTaxes:
    def test_rates_non_premium(self) -> None:
        # V3.0 : setup fee corrige a 2.5% (etait 5% dans un ancien patch).
        import pytest

        assert config.TAX_INSTANT_SELL == pytest.approx(0.08)
        assert config.TAX_SELL_ORDER_SETUP == pytest.approx(0.025)
        assert config.TAX_SELL_ORDER_SALE == pytest.approx(0.08)
        assert config.TAX_SELL_ORDER_TOTAL == pytest.approx(0.105)

    def test_rates_premium(self) -> None:
        # V3.0 : ajout du support premium.
        import pytest

        assert config.instant_sell_tax(premium=True) == pytest.approx(0.04)
        assert config.instant_sell_tax(premium=False) == pytest.approx(0.08)
        # Sell order = 2.5% setup + sale variable
        assert config.sell_order_total_tax(premium=True) == pytest.approx(0.065)
        assert config.sell_order_total_tax(premium=False) == pytest.approx(0.105)


class TestEndpoints:
    def test_base_urls(self) -> None:
        assert config.AODP_BASE_URLS["europe"] == "https://europe.albion-online-data.com"
        assert "west" in config.AODP_BASE_URLS
        assert config.FORCED_QUALITY == 1


class TestDefaults:
    def test_required_keys(self) -> None:
        for key in (
            "seuil_marge_min_pct",
            "seuil_fill_probability_pct",
            "freshness_warning_hours",
            "freshness_critical_hours",
            "cache_ttl_minutes",
            "server",
            "refining_city",
        ):
            assert key in config.DEFAULTS
        assert config.DEFAULTS["refining_city"] == "Fort Sterling"
        assert config.DEFAULTS["server"] == "europe"

    def test_no_default_station_rate(self) -> None:
        # Le rate de station doit être fourni par l'utilisateur (pas de défaut).
        assert "station_rate" not in config.DEFAULTS
        assert "silver_per_100_nutrition" not in config.DEFAULTS
