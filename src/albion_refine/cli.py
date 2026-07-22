"""Interface en ligne de commande (typer).

Point d'entrée utilisateur : parse les options, appelle l'optimiseur et délègue
l'affichage aux ``formatters``. Aucune logique métier ici (SPEC section 5.3).
"""

from __future__ import annotations

import asyncio
import sys
from enum import StrEnum
from typing import Annotated

import typer
from rich.console import Console

from albion_refine import config, formatters
from albion_refine.aodp_client import AodpClient, AodpError
from albion_refine.config import ResourceKind
from albion_refine.models import QuantityMode, RecupMode
from albion_refine.optimizer import OptimizerParams, run_optimization


def _ensure_utf8_output() -> None:
    """Force stdout/stderr en UTF-8 pour éviter les crashs sur console Windows cp1252.

    Les icônes de fraîcheur (✓/⚠/✗) et les flèches ne sont pas encodables en
    cp1252 : sans ce reconfiguré, une sortie redirigée lèverait ``UnicodeEncodeError``.
    """
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is not None:
            reconfigure(encoding="utf-8", errors="replace")


_ensure_utf8_output()

app = typer.Typer(
    help="Optimiseur économique de raffinage de bois pour Albion Online (serveur Europe).",
    add_completion=False,
    no_args_is_help=True,
)
console = Console()
err_console = Console(stderr=True)


class OutputFormat(StrEnum):
    """Format de sortie de la commande ``optimize``."""

    TABLE = "table"
    JSON = "json"


class DailyBonus(StrEnum):
    """Bonus quotidien de production sélectionnable."""

    NONE = "none"
    TEN = "10"
    TWENTY = "20"

    def as_pct(self) -> int:
        """Convertit le choix en pourcentage entier."""
        return 0 if self is DailyBonus.NONE else int(self.value)


def _validate_tier(tier: int) -> int:
    if tier not in config.SUPPORTED_TIERS:
        raise typer.BadParameter(
            f"Tier {tier} non supporté. Tiers valides : {list(config.SUPPORTED_TIERS)}."
        )
    return tier


def _build_params(
    tier: int,
    mode: QuantityMode,
    station_rate: float,
    focus: bool,
    daily_bonus_pct: int,
    capital: float | None,
    quantite: int | None,
    focus_available: float | None,
    cost_per_focus: float,
    seuil_marge: float,
    exclude_vente: list[str],
    exclude_achat: list[str],
    recup_mode: RecupMode,
    resource: ResourceKind,
    enchant: int,
) -> OptimizerParams:
    """Assemble et valide les paramètres d'optimisation selon le mode choisi."""
    if mode is QuantityMode.CAPITAL and not capital:
        raise typer.BadParameter("Le mode capital exige --capital.")
    if mode is QuantityMode.FIXED and not quantite:
        raise typer.BadParameter("Le mode fixed exige --quantite.")
    if mode is QuantityMode.FOCUS and not focus_available:
        raise typer.BadParameter("Le mode focus exige --focus-available.")
    if enchant not in config.SUPPORTED_ENCHANTS:
        raise typer.BadParameter(
            f"Enchant {enchant} non supporte. Valides : {list(config.SUPPORTED_ENCHANTS)}."
        )

    # En mode focus, le focus est nécessairement activé.
    effective_focus = focus or mode is QuantityMode.FOCUS

    return OptimizerParams(
        tier=tier,
        mode=mode,
        station_rate=station_rate,
        focus=effective_focus,
        daily_bonus_pct=daily_bonus_pct,
        capital=capital,
        quantite=quantite,
        focus_available=focus_available,
        cost_per_focus=cost_per_focus,
        seuil_marge_min_pct=seuil_marge,
        excluded_buy_cities=list(config.DEFAULTS["excluded_buy_cities"]) + exclude_achat,
        excluded_sell_cities=list(config.DEFAULTS["excluded_sell_cities"]) + exclude_vente,
        recup_mode=recup_mode,
        resource=resource,
        enchant=enchant,
    )


@app.command()
def optimize(
    tier: Annotated[int, typer.Option("--tier", help="Tier du plank à produire (4-8).")],
    station_rate: Annotated[
        float,
        typer.Option("--station-rate", help="Rate de la station en silver / 100 nutrition."),
    ],
    mode: Annotated[
        QuantityMode, typer.Option("--mode", help="Mode de dimensionnement.")
    ] = QuantityMode.FIXED,
    capital: Annotated[
        float | None, typer.Option("--capital", help="Budget silver (mode capital).")
    ] = None,
    quantite: Annotated[
        int | None, typer.Option("--quantite", help="Quantité de bois (mode fixed).")
    ] = None,
    focus_available: Annotated[
        float | None,
        typer.Option("--focus-available", help="Budget focus disponible (mode focus)."),
    ] = None,
    focus: Annotated[
        bool, typer.Option("--focus/--no-focus", help="Active le focus (+59% RRR).")
    ] = False,
    daily_bonus: Annotated[
        DailyBonus, typer.Option("--daily-bonus", help="Bonus quotidien de production.")
    ] = DailyBonus.NONE,
    cost_per_focus: Annotated[
        float, typer.Option("--cost-per-focus", help="Coût silver d'un point de focus.")
    ] = 0.0,
    seuil_marge: Annotated[
        float,
        typer.Option(
            "--seuil-marge",
            help=(
                "ROI minimale sur capital dépensé en % (défaut 20). "
                "Ex. 20 = tu veux au moins +20% sur ton silver investi."
            ),
        ),
    ] = float(config.DEFAULTS["seuil_marge_min_pct"]),
    recup_mode: Annotated[
        RecupMode,
        typer.Option(
            "--recup-mode",
            help=(
                "Où vendre la récup RRR. "
                "'with-planks' (défaut) : dans la ville des raffinés (workflow réaliste). "
                "'local' : dans la ville spécialité (comportement V1, souvent défavorable)."
            ),
        ),
    ] = RecupMode.WITH_PLANKS,
    resource: Annotated[
        ResourceKind,
        typer.Option(
            "--resource",
            help=(
                "Filière raffinée. 'wood' (défaut) : bois → planks à Fort Sterling. "
                "'hide' : peau → cuir à Martlock. Même logique métier, seul l'item AODP "
                "et la ville spécialité changent."
            ),
        ),
    ] = ResourceKind.WOOD,
    enchant: Annotated[
        int,
        typer.Option(
            "--enchant",
            help=(
                "Niveau d'enchantement (0 = base, 1..4 = .1 -> .4). "
                "L'enchant modifie l'item AODP requeté (T7_WOOD_LEVEL1@1 par ex.) "
                "mais laisse la recette et la logique métier inchangées."
            ),
            min=0,
            max=4,
        ),
    ] = 0,
    exclude_vente: Annotated[
        list[str] | None, typer.Option("--exclude-vente", help="Ville à exclure de la vente.")
    ] = None,
    exclude_achat: Annotated[
        list[str] | None, typer.Option("--exclude-achat", help="Ville à exclure de l'achat.")
    ] = None,
    output_format: Annotated[
        OutputFormat, typer.Option("--format", help="Format de sortie.")
    ] = OutputFormat.TABLE,
    no_cache: Annotated[
        bool, typer.Option("--no-cache", help="Ignore le cache local et force le refresh.")
    ] = False,
    server: Annotated[str, typer.Option("--server", help="Serveur AODP.")] = "europe",
) -> None:
    """Calcule les meilleures routes de raffinage pour un tier donné."""
    _validate_tier(tier)

    params = _build_params(
        tier=tier,
        mode=mode,
        station_rate=float(station_rate),
        focus=focus,
        daily_bonus_pct=daily_bonus.as_pct(),
        capital=capital,
        quantite=quantite,
        focus_available=focus_available,
        cost_per_focus=cost_per_focus,
        seuil_marge=seuil_marge,
        exclude_vente=exclude_vente or [],
        exclude_achat=exclude_achat or [],
        recup_mode=recup_mode,
        resource=resource,
        enchant=enchant,
    )

    try:
        result = asyncio.run(run_optimization(params, server=server, use_cache=not no_cache))
    except AodpError as error:
        err_console.print(f"[bold red]Erreur AODP :[/] {error}")
        raise typer.Exit(code=2) from error

    if output_format is OutputFormat.JSON:
        console.print_json(formatters.format_json(result))
    else:
        formatters.render_report(result, console)


@app.command("check-item-ids")
def check_item_ids() -> None:
    """Vérifie que les item IDs codés en dur correspondent à ``items.json``."""
    data = config.load_items_data()
    ok = True
    # Filiere bois -> planks
    for tier, item_id in config.WOOD_ITEM_IDS.items():
        present = item_id in data.get("wood", {})
        console.print(f"bois    T{tier} : {item_id} {'✓' if present else '✗ ABSENT'}")
        ok = ok and present
    for tier, item_id in config.PLANK_ITEM_IDS.items():
        present = item_id in data.get("planks", {})
        console.print(f"plank   T{tier} : {item_id} {'✓' if present else '✗ ABSENT'}")
        ok = ok and present
    # Filiere peau -> cuir (ajoutee V2.2)
    for tier, item_id in config.HIDE_ITEM_IDS.items():
        present = item_id in data.get("hide", {})
        console.print(f"peau    T{tier} : {item_id} {'✓' if present else '✗ ABSENT'}")
        ok = ok and present
    for tier, item_id in config.LEATHER_ITEM_IDS.items():
        present = item_id in data.get("leather", {})
        console.print(f"cuir    T{tier} : {item_id} {'✓' if present else '✗ ABSENT'}")
        ok = ok and present
    if not ok:
        raise typer.Exit(code=1)
    console.print("[bold green]Tous les item IDs sont valides.[/]")


@app.command("test-api")
def test_api(server: Annotated[str, typer.Option("--server")] = "europe") -> None:
    """Ping l'AODP et vérifie qu'un prix connu revient."""

    async def _ping() -> int:
        async with AodpClient(server=server, use_cache=False) as client:
            quotes = await client.get_prices(["T4_PLANKS"], ["Martlock"])
        return len(quotes)

    try:
        count = asyncio.run(_ping())
    except AodpError as error:
        err_console.print(f"[bold red]AODP indisponible :[/] {error}")
        raise typer.Exit(code=2) from error
    console.print(f"[bold green]AODP OK[/] — {count} entrée(s) reçue(s).")


@app.command("clear-cache")
def clear_cache() -> None:
    """Vide le cache local des réponses AODP."""
    client = AodpClient(use_cache=True)
    client.clear_cache()
    client.close()
    console.print("[bold green]Cache vidé.[/]")


@app.command("dump-nutrition")
def dump_nutrition() -> None:
    """Affiche la table de nutrition par unité raffinée (silver / 100 nutrition)."""
    console.print("[bold]Nutrition par unité raffinée (= Item Value × 0.1125)[/]")
    for tier in config.SUPPORTED_TIERS:
        iv = config.REFINED_ITEM_VALUES[tier]
        nut = config.nutrition_per_unit(tier)
        console.print(f"T{tier} : IV {iv:>4} → {nut:>7.3f} nutrition/unité")


if __name__ == "__main__":  # pragma: no cover
    app()
