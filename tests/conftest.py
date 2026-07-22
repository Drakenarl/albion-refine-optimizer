"""Fixtures pytest partagées : chargement des snapshots AODP et données de test."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

import pytest

from albion_refine.aodp_client import _quote_from_entry, _volume_from_entry
from albion_refine.models import PriceQuote, VolumeData

FIXTURES_DIR = Path(__file__).parent / "fixtures"


def load_fixture(name: str) -> list[dict[str, Any]]:
    """Charge un fichier fixture JSON et ne garde que les entrées d'items.

    Certaines fixtures (ex. ``aodp_stale_data``) contiennent un objet de
    métadonnées en tête : on le filtre en ne conservant que les entrées
    possédant un ``item_id``.
    """
    with (FIXTURES_DIR / name).open(encoding="utf-8") as handle:
        data = json.load(handle)
    return [entry for entry in data if isinstance(entry, dict) and "item_id" in entry]


def load_fixture_raw(name: str) -> list[dict[str, Any]]:
    """Charge un fichier fixture JSON tel quel (sans filtrage)."""
    with (FIXTURES_DIR / name).open(encoding="utf-8") as handle:
        data: list[dict[str, Any]] = json.load(handle)
    return data


@pytest.fixture
def now_ref() -> datetime:
    """Instant de référence cohérent avec les fixtures T7 (données ~15:14)."""
    return datetime(2026, 7, 19, 15, 20, 0)


@pytest.fixture
def prices_raw_t7() -> list[dict[str, Any]]:
    """Contenu brut de la fixture de prix T7."""
    return load_fixture("aodp_prices_t7.json")


@pytest.fixture
def history_raw_t7() -> list[dict[str, Any]]:
    """Contenu brut de la fixture d'historique T7."""
    return load_fixture_raw("aodp_history_t7.json")


@pytest.fixture
def prices_t7() -> list[PriceQuote]:
    """Prix T7 parsés en ``PriceQuote``."""
    return [_quote_from_entry(entry) for entry in load_fixture("aodp_prices_t7.json")]


@pytest.fixture
def history_t7() -> list[VolumeData]:
    """Historique T7 parsé en ``VolumeData``.

    V2.8 : on ancre ``now`` sur la meme date que ``now_ref`` (2026-07-19 15:20)
    pour que la fenetre glissante 24h contienne bien les points du fixture
    (2026-07-18T16 -> 2026-07-19T12).
    """
    ref = datetime(2026, 7, 19, 15, 20, 0)
    return [
        _volume_from_entry(entry, now=ref)
        for entry in load_fixture_raw("aodp_history_t7.json")
    ]
