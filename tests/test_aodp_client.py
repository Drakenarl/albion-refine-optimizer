"""Tests du client AODP : parsing, cache et gestion des erreurs (HTTP mocké)."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any

import httpx
import pytest
from pytest_httpx import HTTPXMock

from albion_refine.aodp_client import (
    AodpClient,
    AodpError,
    parse_aodp_date,
)


class TestParseDate:
    def test_nominal(self) -> None:
        assert parse_aodp_date("2026-07-19T14:32:15") == datetime(2026, 7, 19, 14, 32, 15)

    def test_sentinel_is_none(self) -> None:
        assert parse_aodp_date("0001-01-01T00:00:00") is None

    def test_empty_is_none(self) -> None:
        assert parse_aodp_date("") is None
        assert parse_aodp_date(None) is None

    def test_invalid_is_none(self) -> None:
        assert parse_aodp_date("pas-une-date") is None

    def test_strips_timezone(self) -> None:
        assert parse_aodp_date("2026-07-19T14:32:15Z") == datetime(2026, 7, 19, 14, 32, 15)


class TestClientInit:
    def test_unknown_server_raises(self, tmp_path: Path) -> None:
        with pytest.raises(AodpError):
            AodpClient(server="mars", cache_dir=tmp_path)


@pytest.mark.asyncio
class TestGetPrices:
    async def test_parses_quotes(
        self, httpx_mock: HTTPXMock, prices_raw_t7: list[dict[str, Any]], tmp_path: Path
    ) -> None:
        httpx_mock.add_response(json=prices_raw_t7)
        async with AodpClient(cache_dir=tmp_path, use_cache=False) as client:
            quotes = await client.get_prices(["T7_WOOD"], ["Martlock"])
        martlock_wood = next(q for q in quotes if q.item_id == "T7_WOOD" and q.city == "Martlock")
        assert martlock_wood.sell_price_min == 135
        assert martlock_wood.has_sell_offer is True

    async def test_uses_cache_on_second_call(
        self, httpx_mock: HTTPXMock, prices_raw_t7: list[dict[str, Any]], tmp_path: Path
    ) -> None:
        httpx_mock.add_response(json=prices_raw_t7)
        async with AodpClient(cache_dir=tmp_path, use_cache=True) as client:
            first = await client.get_prices(["T7_WOOD"], ["Martlock"])
            # Deuxième appel identique : servi par le cache, aucune 2e requête HTTP.
            second = await client.get_prices(["T7_WOOD"], ["Martlock"])
        assert len(httpx_mock.get_requests()) == 1
        assert len(first) == len(second)


@pytest.mark.asyncio
class TestGetHistory:
    async def test_parses_volume(
        self, httpx_mock: HTTPXMock, history_raw_t7: list[dict[str, Any]], tmp_path: Path
    ) -> None:
        httpx_mock.add_response(json=history_raw_t7)
        # V2.8 : la fixture couvre 2026-07-18T16 -> 2026-07-19T12 (20h) ; on
        # ancre ``now`` juste apres, tous les buckets tombent dans la fenetre 24h.
        now = datetime(2026, 7, 19, 14, 0, 0)
        async with AodpClient(cache_dir=tmp_path, use_cache=False) as client:
            volumes = await client.get_history(["T7_PLANKS"], ["Caerleon"], now=now)
        caerleon = next(v for v in volumes if v.city == "Caerleon")
        assert caerleon.total_volume_24h == pytest.approx(342 + 415 + 388 + 267 + 291 + 356)
        assert caerleon.num_points == 6


@pytest.mark.asyncio
class TestErrors:
    async def test_raises_after_retries(self, httpx_mock: HTTPXMock, tmp_path: Path) -> None:
        httpx_mock.add_exception(httpx.ConnectTimeout("timeout"))
        httpx_mock.add_exception(httpx.ConnectTimeout("timeout"))
        httpx_mock.add_exception(httpx.ConnectTimeout("timeout"))
        async with AodpClient(cache_dir=tmp_path, use_cache=False, max_retries=3) as client:
            with pytest.raises(AodpError):
                await client.get_prices(["T7_WOOD"], ["Martlock"])

    async def test_recovers_after_transient_error(
        self, httpx_mock: HTTPXMock, prices_raw_t7: list[dict[str, Any]], tmp_path: Path
    ) -> None:
        httpx_mock.add_exception(httpx.ConnectTimeout("timeout"))
        httpx_mock.add_response(json=prices_raw_t7)
        async with AodpClient(cache_dir=tmp_path, use_cache=False, max_retries=3) as client:
            quotes = await client.get_prices(["T7_WOOD"], ["Martlock"])
        assert len(quotes) > 0
