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
    """Retourne le dossier de cache par defaut selon la plateforme.

    Priorite :
    1. ``ALBION_CACHE_DIR`` si explicitement configuree (echappement d'urgence).
    2. ``/tmp/albion-refine`` sur Vercel (``VERCEL=1``) ou tout runtime
       serverless connu : le reste du FS est read-only, seul ``/tmp`` accepte
       l'ecriture (max ~500MB, persistance ~limite au conteneur chaud).
    3. ``%LOCALAPPDATA%\\albion-refine`` sous Windows.
    4. ``~/.cache/albion-refine`` en fallback (Linux / macOS locaux).
    """
    import os

    explicit = os.environ.get("ALBION_CACHE_DIR")
    if explicit:
        return Path(explicit)
    if os.environ.get("VERCEL") or os.environ.get("AWS_LAMBDA_FUNCTION_NAME"):
        return Path("/tmp/albion-refine")
    local_app_data = os.environ.get("LOCALAPPDATA")
    if local_app_data:
        return Path(local_app_data) / "albion-refine"
    return Path.home() / ".cache" / "albion-refine"


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


from datetime import timedelta as _timedelta  # alias local pour eviter les imports circulaires


def _volume_from_entry(
    entry: dict[str, Any], now: datetime | None = None, window_hours: int = 24
) -> VolumeData:
    """Convertit une entrée brute de l'endpoint ``/history`` en ``VolumeData``.

    Depuis V2.8 : l'AODP renvoie un historique de ~10 jours de buckets. On
    filtre les points pour ne conserver que ceux tombant dans la fenetre
    ``[now - window_hours, now]``. ``total_volume_24h`` reflete donc bien
    l'activite des dernieres 24h (par defaut), pas 10 jours cumules.

    Args:
        entry: L'entree brute JSON d'AODP.
        now: Instant de reference (par defaut : ``datetime.utcnow()`` naive).
        window_hours: Largeur de la fenetre en heures (par defaut : 24).
    """
    reference = now or datetime.utcnow()
    cutoff = reference - _timedelta(hours=window_hours)
    points: list[dict[str, Any]] = entry.get("data") or []
    total = 0.0
    valid_timestamps: list[datetime] = []
    in_window = 0
    for point in points:
        ts = parse_aodp_date(point.get("timestamp"))
        if ts is not None:
            valid_timestamps.append(ts)
        # Ne cumule que les buckets tombant dans la fenetre de reference.
        if ts is not None and ts >= cutoff and ts <= reference:
            total += float(point.get("item_count", 0))
            in_window += 1
    return VolumeData(
        item_id=entry["item_id"],
        city=entry.get("location", entry.get("city", "")),
        total_volume_24h=total,
        latest_timestamp=max(valid_timestamps) if valid_timestamps else None,
        num_points=in_window,
    )


class AodpClient:
    """Client asynchrone pour les endpoints de prix et d'historique de l'AODP."""

    def __init__(
        self,
        *,
        server: str = "europe",
        cache_dir: Path | None = None,
        ttl_minutes: int = 5,
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
            # V2.8 : passe a time-scale=6 pour recevoir des buckets de 6h.
            # Une fenetre 24h reelle = 4 buckets de 6h ; c'est agrege plus tard
            # dans ``_volume_from_entry`` en filtrant sur ``now - 24h``.
            params["time-scale"] = 6

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

    async def get_history(
        self,
        item_ids: list[str],
        cities: list[str],
        *,
        now: datetime | None = None,
        window_hours: int = 24,
    ) -> list[VolumeData]:
        """Récupère les volumes sur une fenêtre glissante récente.

        L'AODP renvoie un historique de ~10 jours en buckets de 6h ; on filtre
        pour ne conserver que les buckets tombant dans les ``window_hours``
        heures precedant ``now``. Le champ ``total_volume_24h`` du ``VolumeData``
        represente donc bien l'activite recente, pas un cumul multi-jours.

        Args:
            item_ids: Liste d'item IDs.
            cities: Liste de villes.
            now: Instant de reference (defaut : ``datetime.utcnow()``).
            window_hours: Largeur de la fenetre (defaut : 24h).

        Returns:
            La liste des ``VolumeData`` correspondants.
        """
        raw = await self._fetch_json(config.HISTORY_PATH, item_ids, cities)
        return [_volume_from_entry(entry, now=now, window_hours=window_hours) for entry in raw]
