"""Rendu des résultats : tableaux ``rich`` pour le terminal et export JSON.

Ce module ne fait que de la présentation : il transforme un
``OptimizationResult`` en sortie lisible (panneaux colorés + check-list) ou en
JSON exploitable par un futur frontend (SPEC section 9.4).
"""

from __future__ import annotations

import json

from rich.console import Console
from rich.panel import Panel
from rich.text import Text

from albion_refine.models import (
    FreshnessLevel,
    OptimizationResult,
    Route,
    SellStrategy,
    WarningCode,
)

_FRESHNESS_ICON: dict[FreshnessLevel, tuple[str, str]] = {
    FreshnessLevel.FRESH: ("✓", "green"),
    FreshnessLevel.WARNING: ("⚠", "yellow"),
    FreshnessLevel.CRITICAL: ("✗", "red"),
    FreshnessLevel.UNKNOWN: ("?", "dim"),
}

_STRATEGY_LABEL: dict[SellStrategy, str] = {
    SellStrategy.INSTANT_SELL: "INSTANT SELL",
    SellStrategy.SELL_ORDER: "SELL ORDER",
}


def fmt_silver(value: float) -> str:
    """Formate un montant en silver avec séparateur d'espace (ex. ``31 360 s``)."""
    return f"{value:,.0f}".replace(",", " ") + " s"


def fmt_age(age_hours: float | None) -> str:
    """Formate un âge en heures/minutes lisible (ex. ``12 min``, ``4h``)."""
    if age_hours is None:
        return "n/a"
    if age_hours < 1:
        return f"{age_hours * 60:.0f} min"
    return f"{age_hours:.1f}h"


def freshness_icon(level: FreshnessLevel) -> str:
    """Retourne l'icône associée à un niveau de fraîcheur."""
    return _FRESHNESS_ICON[level][0]


def _route_panel(route: Route) -> Panel:
    """Construit un panneau ``rich`` détaillant une route."""
    body = Text()

    # Achats.
    wood = route.achat_wood
    plank = route.achat_plank
    body.append(
        f"ACHAT BOIS T{wood.tier}   {wood.city:<14} "
        f"{wood.prix_unitaire:.0f} s × {wood.quantite} = {fmt_silver(wood.cout_total)}\n"
    )
    icon, color = _FRESHNESS_ICON[wood.freshness]
    body.append(
        f"                 fraîcheur : {fmt_age(wood.data_age_hours)} {icon}\n", style=color
    )
    body.append(
        f"ACHAT PLANK T{plank.tier}  {plank.city:<14} "
        f"{plank.prix_unitaire:.0f} s × {plank.quantite} = {fmt_silver(plank.cout_total)}\n"
    )
    icon, color = _FRESHNESS_ICON[plank.freshness]
    body.append(
        f"                 fraîcheur : {fmt_age(plank.data_age_hours)} {icon}\n", style=color
    )

    # Raffinage.
    refined = route.raffinage
    body.append(f"RAFFINAGE FS     coût station = {fmt_silver(refined.cout_station)}\n")
    body.append(
        f"RRR effectif : {refined.rrr_effectif * 100:.1f}% | "
        f"Output : {refined.planks_produits} planks "
        f"+ {refined.wood_retour:.0f} bois + {refined.plank_moins_1_retour:.0f} plank T-1 retour\n"
    )
    if refined.focus_utilise > 0:
        body.append(f"FOCUS : {refined.focus_utilise:.0f}\n")

    # Vente.
    vente = route.vente
    body.append("\n")
    body.append(
        f"VENTE ► {_STRATEGY_LABEL[vente.strategy]} @ {vente.city}\n",
        style="bold cyan",
    )
    body.append(f"        prix réf {vente.prix_unitaire_ref:.0f} s")
    if vente.strategy == SellStrategy.SELL_ORDER:
        body.append(f" | fill proba {vente.fill_proba * 100:.0f}%")
    body.append(f"\n        revenu net : {fmt_silver(vente.revenu_net)}\n")

    if WarningCode.ROUTE_ZONE_ROUGE in route.warnings:
        body.append("        ⚠ ROUTE PAR ZONE ROUGE\n", style="bold red")
    if WarningCode.PROFONDEUR_INCERTAINE in route.warnings:
        body.append(
            "        ⚠ profondeur de marché incertaine (volume < quantité)\n", style="yellow"
        )

    # Synthèse.
    body.append("\n")
    if route.recup_totale > 0:
        body.append(f"RÉCUP (retours)  : {fmt_silver(route.recup_totale)}\n", style="green")
    body.append(f"COÛT NET         : {fmt_silver(route.cout_net)}\n")
    body.append(f"REVENU EFFECTIF  : {fmt_silver(route.revenu_effectif)}\n")
    benefice_style = "bold green" if route.benefice >= 0 else "bold red"
    sign = "+" if route.benefice >= 0 else ""
    body.append(f"BÉNÉFICE         : {sign}{fmt_silver(route.benefice)}\n", style=benefice_style)
    if route.silver_par_focus is not None:
        body.append(f"SILVER / FOCUS   : {route.silver_par_focus:.2f} s\n")

    title = f"TOP {route.rank} — Marge nette : {route.marge_pct:.1f}%"
    subtitle = f"TIER {route.tier} PLANKS — {route.quantite} unités"
    return Panel(body, title=title, subtitle=subtitle, border_style="cyan")


def render_report(result: OptimizationResult, console: Console | None = None) -> None:
    """Affiche le rapport complet (routes + check-list) dans le terminal.

    Args:
        result: Résultat d'optimisation à afficher.
        console: Console ``rich`` cible (une nouvelle est créée par défaut).
    """
    console = console or Console()

    if not result.routes:
        _render_no_routes(result, console)
        return

    for route in result.routes:
        console.print(_route_panel(route))

    console.print()
    console.print("━━━ CHECK-LIST FRAÎCHEUR — Pages marché à ouvrir en jeu ━━━", style="bold")
    for entry in result.refresh_checklist:
        icon, color = _FRESHNESS_ICON[entry.freshness]
        line = f"[ ] {entry.city} : {entry.item_id} (data {fmt_age(entry.age_hours)} {icon})"
        console.print(line, style=color)


def _render_no_routes(result: OptimizationResult, console: Console) -> None:
    """Affiche le rapport du meilleur candidat écarté quand aucune route ne passe."""
    seuil = result.run_metadata.params.get("seuil_marge_min_pct", "?")
    console.print(f"Aucune route ne passe le seuil de {seuil}%.", style="bold yellow")
    discarded = result.discarded_best
    if discarded is None:
        console.print("Aucun candidat exploitable trouvé (données absentes ou trop vieilles).")
        return
    console.print("Meilleure route trouvée :", style="bold")
    console.print(f"  {discarded.description}")
    if discarded.marge_pct is not None:
        console.print(f"  Marge : {discarded.marge_pct:.1f}%")
    console.print(f"  Écartée car : {discarded.raison}")
    console.print("Suggestions :", style="bold")
    for suggestion in discarded.suggestions:
        console.print(f"  - {suggestion}")


def format_json(result: OptimizationResult) -> str:
    """Sérialise le résultat en JSON indenté (structure SPEC section 9.4).

    Args:
        result: Résultat d'optimisation.

    Returns:
        Une chaîne JSON UTF-8 lisible.
    """
    return json.dumps(result.model_dump(mode="json"), indent=2, ensure_ascii=False)
