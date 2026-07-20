"""Tests de la CLI via le runner typer (optimisation mockée, sans réseau)."""

from __future__ import annotations

from datetime import datetime
from typing import Any

import pytest
from typer.testing import CliRunner

from albion_refine import cli
from albion_refine.models import OptimizationResult, QuantityMode, RunMetadata, VolumeData
from albion_refine.optimizer import OptimizerParams, optimize
from tests.test_optimizer import _quote

runner = CliRunner()


def _sample_result() -> OptimizationResult:
    now = datetime(2026, 7, 19, 15, 20, 0)
    when = datetime(2026, 7, 19, 15, 0, 0)
    quotes = [
        _quote("T7_WOOD", "Martlock", sell=100, when=when),
        _quote("T6_PLANKS", "Fort Sterling", sell=400, when=when),
        _quote("T7_PLANKS", "Caerleon", sell=1520, buy=1420, when=when),
    ]
    volumes = [VolumeData(item_id="T7_PLANKS", city="Caerleon", total_volume_24h=2000)]
    params = OptimizerParams(
        tier=7, mode=QuantityMode.FIXED, quantite=128, station_rate=50, focus=True
    )
    return optimize(params, quotes, volumes, now)


@pytest.fixture
def patched_run(monkeypatch: pytest.MonkeyPatch) -> None:
    async def fake_run(*_args: Any, **_kwargs: Any) -> OptimizationResult:
        return _sample_result()

    monkeypatch.setattr(cli, "run_optimization", fake_run)


class TestOptimizeCommand:
    def test_table_output(self, patched_run: None) -> None:
        result = runner.invoke(
            cli.app,
            ["optimize", "--tier", "7", "--station-rate", "50", "--quantite", "128"],
        )
        assert result.exit_code == 0
        assert "TOP 1" in result.stdout

    def test_json_output(self, patched_run: None) -> None:
        result = runner.invoke(
            cli.app,
            [
                "optimize",
                "--tier",
                "7",
                "--station-rate",
                "50",
                "--quantite",
                "128",
                "--format",
                "json",
            ],
        )
        assert result.exit_code == 0
        assert '"run_metadata"' in result.stdout

    def test_station_rate_required(self) -> None:
        result = runner.invoke(cli.app, ["optimize", "--tier", "7", "--quantite", "128"])
        assert result.exit_code != 0

    def test_invalid_tier(self, patched_run: None) -> None:
        result = runner.invoke(
            cli.app,
            ["optimize", "--tier", "3", "--station-rate", "50", "--quantite", "128"],
        )
        assert result.exit_code != 0

    def test_fixed_mode_requires_quantite(self, patched_run: None) -> None:
        result = runner.invoke(
            cli.app, ["optimize", "--tier", "7", "--station-rate", "50", "--mode", "fixed"]
        )
        assert result.exit_code != 0


class TestUtilityCommands:
    def test_check_item_ids(self) -> None:
        result = runner.invoke(cli.app, ["check-item-ids"])
        assert result.exit_code == 0
        assert "valides" in result.stdout

    def test_dump_nutrition(self) -> None:
        result = runner.invoke(cli.app, ["dump-nutrition"])
        assert result.exit_code == 0
        assert "T7" in result.stdout

    def test_run_metadata_shape(self) -> None:
        # Vérifie que RunMetadata se sérialise correctement (garde-fou).
        meta = RunMetadata(
            timestamp=datetime(2026, 7, 19), tier=7, mode=QuantityMode.FIXED, params={}
        )
        assert meta.model_dump(mode="json")["mode"] == "fixed"
