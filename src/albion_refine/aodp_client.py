"""Client HTTP asynchrone pour l'API de l'Albion Online Data Project.

Ce module ne contient **que** de l'I/O réseau et du cache : il interroge les
endpoints AODP, gère les retries/timeouts et retourne des modèles typés
(``PriceQuote``, ``VolumeData``). Toute la logique métier vit ailleurs.

Le cache (diskcache) est indexé par ``(endpoint, items, locations)`` avec un TTL
par défaut de 15 minutes (SPEC section 10.1).
"""

from __future__ import annotations

import asyncio
from datetime import datetime
from pathlib import Path
from types import TracebackType
from typing import Any, Self

import httpx
from diskcache import Cache

from albion_refine import config
from albion_refine.models import PriceQuote, VolumeData


class AodpError(RuntimeError):
    """Erreur levée quand l'AODP est indisponible ou renvoie une réponse invalide."""


def _default_cache_dir() -> Path:
    """Retourne le dossier de cache par défaut (``%LOCALAPPDATA%`` ou ``~/.cache``)."""
    import os

    base = os.environ.get("LOCALAPPDATA") or os.path.join(Path.home(), ".cache")
    return Path(base) / "albion-refine"


def parse_aodp_date(value: str | None) -> datetime | None:
    """Parse une date ISO 8601 de l'AODP en ``datetime`` (ou ``None``).

    L'AODP renvoie ``0001-01-01T00:00:00`` (année sentinelle) quand aucune
    donnée n'existe : ces valeurs sont converties en ``None``.

    Args:
        value: Chaîne ISO 8601 ou ``None``.

    Returns:
        Le ``datetime`` parsé, ou ``None`` si absent ou sentinelle.
    """
    if not value:
        return None
    normalized = value.replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError:
        return None
    if parsed.year <= 1:
        return None
    # On travaille en heure naïve (UTC) pour comparer avec un ``now`` naïf.
    if parsed.tzinfo is not None:
        parsed = parsed.replace(tzinfo=None)
    return parsed


def _quote_from_entry(entry: dict[str, Any]) -> PriceQuote:
    """Convertit une entrée brute de l'endpoint ``/prices`` en ``PriceQuote``."""
    return PriceQuote(
        item_id=entry["item_id"],
        city=entry["city"],
        quality=entry.get("quality", config.FORCED_QUALITY),
        sell_price_min=entry.get("sell_price_min", 0),
        sell_price_min_date=parse_aodp_date(entry.get("sell_price_min_date")),
        sell_price_max=entry.get("sell_price_max", 0),
        sell_price_max_date=parse_aodp_date(entry.get("sell_price_max_date")),
        buy_price_min=entry.get("buy_price_min", 0),
        buy_price_min_date=parse_aodp_date(entry.get("buy_price_min_date")),
        buy_price_max=entry.get("buy_price_max", 0),
        buy_price_max_date=parse_aodp_date(entry.get("buy_price_max_date")),
    )


def _volume_from_entry(entry: dict[str, Any]) -> VolumeData:
    """Convertit une entrée brute de l'endpoint ``/history`` en ``VolumeData``."""
    points: list[dict[str, Any]] = entry.get("data") or []
    total = float(sum(point.get("item_count", 0) for point in points))
    timestamps = [parse_aodp_date(point.get("timestamp")) for point in points]
    valid = [ts for ts in timestamps if ts is not None]
    return VolumeData(
        item_id=entry["item_id"],
        city=entry.get("location", entry.get("city", "")),
        total_volume_24h=total,
        latest_timestamp=max(valid) if valid else None,
        num_points=len(points),
    )


class AodpClient:
    """Client asynchrone pour les endpoints de prix et d'historique de l'AODP."""

    def __init__(
        self,
        *,
        server: str = "europe",
        cache_dir: Path | None = None,
        ttl_minutes: int = 15,
        use_cache: bool = True,
        timeout: float = config.HTTP_TIMEOUT_SECONDS,
        max_retries: int = config.HTTP_MAX_RETRIES,
    ) -> None:
        """Initialise le client.

        Args:
            server: Serveur AODP (``europe``, ``west`` ou ``east``).
            cache_dir: Dossier de cache (défaut : dossier système).
            ttl_minutes: Durée de vie du cache en minutes.
            use_cache: Désactive le cache si ``False`` (option ``--no-cache``).
            timeout: Timeout HTTP en secondes.
            max_retries: Nombre de tentatives sur erreur réseau.

        Raises:
            AodpError: Si le serveur demandé est inconnu.
        """
        if server not in config.AODP_BASE_URLS:
            raise AodpError(f"Serveur AODP inconnu : {server!r}")
        self.base_url = config.AODP_BASE_URLS[server]
        self.timeout = timeout
        self.max_retries = max_retries
        self.ttl_seconds = ttl_minutes * 60
        self.use_cache = use_cache
        self._cache: Cache | None = None
        if use_cache:
            path = cache_dir or _default_cache_dir()
            path.mkdir(parents=True, exist_ok=True)
            self._cache = Cache(str(path))

    async def __aenter__(self) -> Self:
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        self.close()

    def close(self) -> None:
        """Ferme le cache disque s'il est ouvert."""
        if self._cache is not None:
            self._cache.close()

    def clear_cache(self) -> None:
        """Vide entièrement le cache local."""
        if self._cache is not None:
            self._cache.clear()

    @staticmethod
    def _cache_key(path: str, items_csv: str, locations_csv: str) -> str:
        return f"{path}|{items_csv}|{locations_csv}"

    async def _fetch_json(
        self, path_template: str, item_ids: list[str], cities: list[str]
    ) -> list[dict[str, Any]]:
        """Récupère (avec cache + retries) le JSON d'un endpoint AODP.

        Args:
            path_template: Gabarit d'URL (``PRICES_PATH`` ou ``HISTORY_PATH``).
            item_ids: Liste d'item IDs à demander.
            cities: Liste de villes (locations).

        Returns:
            La liste brute d'objets JSON renvoyée par l'AODP.

        Raises:
            AodpError: Si l'API est injoignable après tous les retries.
        """
        items_csv = ",".join(item_ids)
        locations_csv = ",".join(cities)
        path = path_template.format(items=items_csv)
        key = self._cache_key(path, items_csv, locations_csv)

        if self._cache is not None:
            cached = self._cache.get(key)
            if cached is not None:
                return list(cached)

        url = f"{self.base_url}{path}"
        params: dict[str, Any] = {
            "locations": locations_csv,
            "qualities": config.FORCED_QUALITY,
        }
        if "history" in path_template:
            params["time-scale"] = 24

        payload = await self._request_with_retries(url, params)

        if self._cache is not None:
            self._cache.set(key, payload, expire=self.ttl_seconds)
        return payload

    async def _request_with_retries(self, url: str, params: dict[str, Any]) -> list[dict[str, Any]]:
        """Effectue la requête HTTP avec retries et backoff exponentiel."""
        last_error: Exception | None = None
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            for attempt in range(self.max_retries):
                try:
                    response = await client.get(url, params=params)
                    response.raise_for_status()
                    data = response.json()
                    if not isinstance(data, list):
                        raise AodpError("Réponse AODP inattendue (liste attendue)")
                    return data
                except (httpx.HTTPError, ValueError) as error:
                    last_error = error
                    if attempt < self.max_retries - 1:
                        await asyncio.sleep(2**attempt)
        raise AodpError(
            f"AODP indisponible après {self.max_retries} tentatives : {last_error}"
        ) from last_error

    async def get_prices(self, item_ids: list[str], cities: list[str]) -> list[PriceQuote]:
        """Récupère les prix courants d'items dans plusieurs villes.

        Args:
            item_ids: Liste d'item IDs (ex. ``["T7_WOOD", "T6_PLANKS"]``).
            cities: Liste de villes.

        Returns:
            La liste des ``PriceQuote`` correspondants.
        """
        raw = await self._fetch_json(config.PRICES_PATH, item_ids, cities)
        return [_quote_from_entry(entry) for entry in raw]

    async def get_history(self, item_ids: list[str], cities: list[str]) -> list[VolumeData]:
        """Récupère les volumes 24h d'items dans plusieurs villes.

        Args:
            item_ids: Liste d'item IDs.
            cities: Liste de villes.

        Returns:
            La liste des ``VolumeData`` correspondants.
        """
        raw = await self._fetch_json(config.HISTORY_PATH, item_ids, cities)
        return [_volume_from_entry(entry) for entry in raw]
