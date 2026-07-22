"""API HTTP FastAPI exposant l'optimiseur au frontend web.

Wrapper mince autour de ``run_optimization`` : reçoit ``OptimizerParams`` en
JSON, retourne un ``OptimizationResult`` sérialisé. La logique métier reste
dans ``optimizer.py`` — cette couche ne fait que du transport HTTP + CORS +
gestion d'erreurs. Lancement : ``albion-refine-api`` (ou ``uvicorn
albion_refine.api:app --reload`` en dev).
"""

from __future__ import annotations

import os
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from albion_refine import config
from albion_refine.aodp_client import AodpError
from albion_refine.config import ResourceKind
from albion_refine.models import OptimizationResult, QuantityMode
from albion_refine.optimizer import OptimizerParams, run_optimization

# Origines autorisées côté navigateur. En dev on ouvre Vite (5173) ; en prod on
# passe l'URL du frontend via ``ALBION_ALLOWED_ORIGINS`` (séparées par virgule).
_DEFAULT_DEV_ORIGINS: tuple[str, ...] = (
    "http://localhost:5173",
    "http://127.0.0.1:5173",
)


def _allowed_origins() -> list[str]:
    raw = os.environ.get("ALBION_ALLOWED_ORIGINS", "").strip()
    if not raw:
        return list(_DEFAULT_DEV_ORIGINS)
    return [origin.strip() for origin in raw.split(",") if origin.strip()]


app = FastAPI(
    title="Albion Refine Optimizer API",
    version="2.1.0",
    description=(
        "Endpoint JSON de l'optimiseur de raffinage bois. Wrappe la fonction "
        "``run_optimization`` sans modifier la logique métier."
    ),
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=_allowed_origins(),
    allow_credentials=False,
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)


class OptimizeRequest(BaseModel):
    """Payload accepté par ``POST /api/optimize``.

    Reprend les paramètres de la CLI en JSON. Les champs optionnels utilisent
    les défauts définis dans ``config.DEFAULTS`` / ``OptimizerParams``.
    """

    tier: int
    station_rate: float
    mode: QuantityMode = QuantityMode.FIXED
    capital: float | None = None
    quantite: int | None = None
    focus_available: float | None = None
    focus: bool = False
    daily_bonus_pct: int = 0
    cost_per_focus: float = 0.0
    seuil_marge_min_pct: float = float(config.DEFAULTS["seuil_marge_min_pct"])
    excluded_buy_cities: list[str] = []
    excluded_sell_cities: list[str] = []
    resource: ResourceKind = ResourceKind.WOOD
    enchant: int = 0
    max_source_cities: int = 3
    saturation_per_city: float = 0.25
    top_n: int = 3
    server: str = "europe"
    use_cache: bool = True


class ResourceOption(BaseModel):
    """Filiere raffinee exposee au frontend (peuple le selecteur)."""

    kind: ResourceKind
    display_raw: str
    display_refined: str
    refining_city: str


class ConfigResponse(BaseModel):
    """Réponse de ``GET /api/config`` : constantes utiles pour peupler l'UI."""

    tiers: list[int]
    cities: list[str]
    default_excluded: list[str]
    seuil_marge_default: float
    servers: list[str]
    resources: list[ResourceOption]
    enchants: list[int]


@app.get("/api/health")
def health() -> dict[str, str]:
    """Ping. Utile pour le healthcheck de la plateforme d'hébergement."""
    return {"status": "ok", "version": app.version}


@app.get("/api/config", response_model=ConfigResponse)
def get_config() -> ConfigResponse:
    """Constantes UI-friendly (tiers, villes, ressources, défauts). Alimente les dropdowns."""
    return ConfigResponse(
        tiers=list(config.SUPPORTED_TIERS),
        cities=config.all_cities(),
        default_excluded=list(config.DEFAULTS["excluded_buy_cities"]),
        seuil_marge_default=float(config.DEFAULTS["seuil_marge_min_pct"]),
        servers=list(config.AODP_BASE_URLS.keys()),
        resources=[
            ResourceOption(
                kind=res.kind,
                display_raw=res.display_raw,
                display_refined=res.display_refined,
                refining_city=res.refining_city,
            )
            for res in config.RESOURCES.values()
        ],
        enchants=list(config.SUPPORTED_ENCHANTS),
    )


@app.post("/api/optimize", response_model=OptimizationResult)
async def optimize(payload: OptimizeRequest) -> OptimizationResult:
    """Lance une optimisation. Wrapper direct de ``run_optimization``."""
    if payload.tier not in config.SUPPORTED_TIERS:
        raise HTTPException(
            status_code=422,
            detail=(
                f"Tier {payload.tier} non supporté. Tiers valides : "
                f"{list(config.SUPPORTED_TIERS)}."
            ),
        )
    _validate_mode_inputs(payload)

    params_kwargs: dict[str, Any] = payload.model_dump(exclude={"server", "use_cache"})
    # En mode focus, le focus est nécessairement actif (parité avec la CLI).
    if payload.mode is QuantityMode.FOCUS:
        params_kwargs["focus"] = True
    # Fusion des exclusions par défaut avec celles fournies par l'utilisateur.
    params_kwargs["excluded_buy_cities"] = _merge_exclusions(
        payload.excluded_buy_cities, list(config.DEFAULTS["excluded_buy_cities"])
    )
    params_kwargs["excluded_sell_cities"] = _merge_exclusions(
        payload.excluded_sell_cities, list(config.DEFAULTS["excluded_sell_cities"])
    )

    params = OptimizerParams(**params_kwargs)
    try:
        return await run_optimization(
            params, server=payload.server, use_cache=payload.use_cache
        )
    except AodpError as error:
        raise HTTPException(status_code=502, detail=f"AODP indisponible : {error}") from error


def _validate_mode_inputs(payload: OptimizeRequest) -> None:
    """Vérifie que le champ requis par le mode choisi est présent."""
    if payload.mode is QuantityMode.CAPITAL and not payload.capital:
        raise HTTPException(status_code=422, detail="Le mode capital exige un capital > 0.")
    if payload.mode is QuantityMode.FIXED and not payload.quantite:
        raise HTTPException(status_code=422, detail="Le mode fixed exige une quantité > 0.")
    if payload.mode is QuantityMode.FOCUS and not payload.focus_available:
        raise HTTPException(
            status_code=422, detail="Le mode focus exige un focus disponible > 0."
        )


def _merge_exclusions(user: list[str], defaults: list[str]) -> list[str]:
    """Union sans doublons, en respectant l'ordre des défauts puis des ajouts."""
    seen: set[str] = set()
    merged: list[str] = []
    for city in [*defaults, *user]:
        if city not in seen:
            merged.append(city)
            seen.add(city)
    return merged


def run() -> None:
    """Point d'entrée console : ``albion-refine-api``.

    Écoute sur ``0.0.0.0:$PORT`` (défaut 8000) pour rester compatible avec
    Railway / Render qui fournissent le port via l'env ``PORT``.
    """
    import uvicorn

    host = os.environ.get("ALBION_API_HOST", "0.0.0.0")
    port = int(os.environ.get("PORT", "8000"))
    uvicorn.run("albion_refine.api:app", host=host, port=port, log_level="info")


if __name__ == "__main__":  # pragma: no cover
    run()
