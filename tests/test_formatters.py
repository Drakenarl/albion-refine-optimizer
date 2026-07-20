"""Tests des formatters : export JSON et rendu terminal (sans crash)."""

from __future__ import annotations

import json
from datetime import datetime

from rich.console import Console

from albion_refine import formatters
from albion_refine.models import (
    DiscardedRoute,
    FreshnessLevel,
    OptimizationResult,
    QuantityMode,
    RunMetadata,
    VolumeData,
)
from albion_refine.optimizer import OptimizerParams, optimize
from tests.test_optimizer import _quote  # réutilise le helper contrôlé


def _sample_result() -> OptimizationResult:
    now = datetime(2026, 7, 19, 15, 20, 0)
    when = datetime(2026, 7, 19, 15, 0, 0)
    quotes = [
        _quote("T4_WOOD", "Martlock", sell=100, when=when),
        _quote("T3_PLANKS", "Martlock", sell=100, when=when),
        _quote("T4_PLANKS", "Caerleon", sell=600, buy=500, when=when),
    ]
    volumes = [VolumeData(item_id="T4_PLANKS", city="Caerleon", total_volume_24h=1000)]
    params = OptimizerParams(
        tier=4, mode=QuantityMode.FIXED, quantite=100, station_rate=100, focus=True
    )
    return optimize(params, quotes, volumes, now)


class TestFormatHelpers:
    def test_fmt_silver(self) -> None:
        assert formatters.fmt_silver(31360) == "31 360 s"
        assert formatters.fmt_silver(-500) == "-500 s"

    def test_fmt_age(self) -> None:
        assert formatters.fmt_age(0.2) == "12 min"
        assert formatters.fmt_age(4.5) == "4.5h"
        assert formatters.fmt_age(None) == "n/a"

    def test_freshness_icon(self) -> None:
        assert formatters.freshness_icon(FreshnessLevel.FRESH) == "✓"
        assert formatters.freshness_icon(FreshnessLevel.CRITICAL) == "✗"


class TestFormatJson:
    def test_valid_json_structure(self) -> None:
        result = _sample_result()
        payload = json.loads(formatters.format_json(result))
        assert "run_metadata" in payload
        assert "routes" in payload
        assert "refresh_checklist" in payload
        assert payload["run_metadata"]["tier"] == 4
        assert len(payload["routes"]) >= 1


class TestDoubleScenario:
    def test_json_export_has_both_scenarios(self) -> None:
        payload = json.loads(formatters.format_json(_sample_result()))
        vente = payload["routes"][0]["vente"]
        assert vente["scenario_a_instant_sell"] is not None
        assert vente["scenario_b_sell_order"] is not None
        assert vente["recommandation"] in {"instant_sell", "sell_order", "au_choix"}
        assert vente["scenario_a_instant_sell"]["certitude"] == "haute"
        assert vente["scenario_b_sell_order"]["certitude"] == "moyenne"
        assert vente["scenario_b_sell_order"]["gain_marginal_vs_a"] is not None

    def test_output_shows_both_scenarios(self) -> None:
        console = Console(record=True, width=120)
        formatters.render_report(_sample_result(), console)
        text = console.export_text()
        assert "INSTANT SELL (safe)" in text
        assert "SELL ORDER (attente)" in text
        assert "fill proba" in text
        assert "RECOMMANDATION" in text

    def test_route_title_uses_scenario_a_margin(self) -> None:
        result = _sample_result()
        route = result.routes[0]
        console = Console(record=True, width=120)
        formatters.render_report(result, console)
        text = console.export_text()
        assert f"Marge nette (safe) : {route.marge_pct:.1f}%" in text


class TestRenderReport:
    def test_render_does_not_crash(self) -> None:
        result = _sample_result()
        console = Console(record=True, width=100)
        formatters.render_report(result, console)
        text = console.export_text()
        assert "TOP 1" in text
        assert "CHECK-LIST" in text
        assert "CONSEILS TRADING" in text
        assert "vente principale" in text
        # La route passe par Caerleon → flag zone rouge attendu.
        assert "ZONE ROUGE" in text

    def test_render_no_routes(self) -> None:
        result = OptimizationResult(
            run_metadata=RunMetadata(
                timestamp=datetime(2026, 7, 19),
                tier=7,
                mode=QuantityMode.FIXED,
                params={"seuil_marge_min_pct": 30},
            ),
            routes=[],
            discarded_best=DiscardedRoute(
                description="Achat Martlock → Fort Sterling → Vente Caerleon",
                marge_pct=22.4,
                raison="marge 22.4% < seuil 30%",
                suggestions=["Baisser --seuil-marge à 20"],
            ),
        )
        console = Console(record=True, width=100)
        formatters.render_report(result, console)
        text = console.export_text()
        assert "Aucune route" in text
        assert "22.4" in text
