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

from albion_refine import config
from albion_refine.models import (
    FreshnessLevel,
    OptimizationResult,
    Route,
    SalesScenario,
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

_RECO_LABEL: dict[str, str] = {
    "instant_sell": "INSTANT SELL (gain marginal du sell order insuffisant)",
    "sell_order": "SELL ORDER (gain marginal significatif)",
    "au_choix": "AU CHOIX (les deux scénarios se valent)",
}


_CONSEILS_TRADING: tuple[str, ...] = (
    "Ouvrir en jeu les pages listées ci-dessus pour rafraîchir la data",
    "Relancer l'outil 30-60 secondes après pour obtenir les vrais prix",
    "Confirmer le top buy order en jeu avant de committer sur instant sell",
    "Ne jamais placer un sell order sans vérifier la profondeur du carnet",
)


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


def classify_age(age_hours_value: float | None) -> FreshnessLevel:
    """Classe un âge en heures selon les seuils par défaut (3h / 6h).

    Args:
        age_hours_value: Âge de la donnée en heures, ou ``None``.

    Returns:
        Le niveau de fraîcheur à afficher.
    """
    if age_hours_value is None:
        return FreshnessLevel.UNKNOWN
    if age_hours_value >= float(config.DEFAULTS["freshness_critical_hours"]):
        return FreshnessLevel.CRITICAL
    if age_hours_value >= float(config.DEFAULTS["freshness_warning_hours"]):
        return FreshnessLevel.WARNING
    return FreshnessLevel.FRESH


def _marge_color(marge_pct: float) -> str:
    """Retourne la couleur associée à une ROI capital safe.

    Recalibré pour la V2 : les seuils s'appliquent désormais à la ROI capital
    (bénéfice / coût total), pas à l'ancienne marge d'efficacité qui gonflait
    artificiellement les %. Un vert < 30% ROI est déjà excellent en Albion.
    """
    if marge_pct > 30:
        return "green"
    if marge_pct >= 15:
        return "yellow"
    return "red"


def _confiance_line(scenario: SalesScenario) -> Text:
    """Rend la ligne « confiance fraîcheur » d'un scénario de vente."""
    niveau = classify_age(scenario.data_age_hours)
    icon, color = _FRESHNESS_ICON[niveau]
    return Text(
        f"      × confiance      : {scenario.freshness_factor:.2f} "
        f"(data {fmt_age(scenario.data_age_hours)} {icon})\n",
        style=color,
    )


def _append_scenario_a(body: Text, scenario: SalesScenario | None) -> None:
    """Ajoute le bloc du scénario A (instant sell) au corps du panneau."""
    body.append("► INSTANT SELL (safe)\n", style="bold")
    if scenario is None:  # pragma: no cover - une route sans A n'est pas construite
        body.append("      indisponible (aucun buy order exploitable)\n", style="dim")
        return
    body.append(f"      top buy {scenario.prix_unitaire_ref:.0f} s × {scenario.planks} unités\n")
    body.append(f"      revenu net brut  : {fmt_silver(scenario.revenu_net)}\n")
    body.append(_confiance_line(scenario))
    body.append(f"      revenu pondéré   : {fmt_silver(scenario.revenu_net_pondere)}\n")
    if scenario.marge_pct is not None:
        body.append(f"      ROI capital      : {scenario.marge_pct:.1f}%\n")
    if scenario.marge_efficacite_pct is not None:
        body.append(
            f"      marge efficacité : {scenario.marge_efficacite_pct:.1f}% "
            "(après récup, indicateur secondaire)\n",
            style="dim",
        )


def _append_scenario_b(body: Text, scenario: SalesScenario | None) -> None:
    """Ajoute le bloc du scénario B (sell order) au corps du panneau."""
    style = "dim" if scenario is not None and scenario.fill_proba < 0.4 else ""
    body.append("► SELL ORDER (attente)\n", style="bold")
    if scenario is None:
        body.append("      indisponible (aucun sell order exploitable)\n", style="dim")
        return
    body.append(
        f"      undercut à {scenario.prix_unitaire_ref:.0f} s | "
        f"fill proba {scenario.fill_proba * 100:.0f}%\n",
        style=style,
    )
    body.append(
        f"      revenu si rempli : {fmt_silver(scenario.revenu_net)}\n",
        style=style,
    )
    body.append(_confiance_line(scenario))
    body.append(
        f"      espérance pondérée : {fmt_silver(scenario.expected_revenu)} "
        f"({scenario.fill_proba:.2f} × {fmt_silver(scenario.revenu_net_pondere)})\n",
        style=style,
    )
    if scenario.marge_pct is not None:
        body.append(
            f"      ROI capital esp. : {scenario.marge_pct:.1f}%\n", style=style
        )
    if scenario.marge_efficacite_pct is not None:
        body.append(
            f"      marge efficacité : {scenario.marge_efficacite_pct:.1f}% "
            "(secondaire)\n",
            style="dim",
        )
    if scenario.gain_marginal_vs_a is not None:
        signe = "+" if scenario.gain_marginal_vs_a >= 0 else ""
        detail = ""
        if scenario.gain_marginal_pct is not None:
            detail = f" ({signe}{scenario.gain_marginal_pct:.1f}%)"
        body.append(
            f"      gain vs instant  : {signe}{fmt_silver(scenario.gain_marginal_vs_a)}{detail}\n",
            style=style,
        )


def _route_panel(route: Route) -> Panel:
    """Construit un panneau ``rich`` détaillant une route."""
    body = Text()
    res = config.resource(route.resource_kind)
    raw_upper = res.display_raw.upper()
    refined_upper = res.display_refined.upper()
    refining_city_short = res.refining_city.split()[0].upper()  # FORT ou MARTLOCK

    # Achats.
    wood = route.achat_wood
    plank = route.achat_plank
    body.append(
        f"ACHAT {raw_upper} T{wood.tier}   {wood.city:<14} "
        f"{wood.prix_unitaire:.0f} s × {wood.quantite} = {fmt_silver(wood.cout_total)}\n"
    )
    icon, color = _FRESHNESS_ICON[wood.freshness]
    body.append(
        f"                 fraîcheur : {fmt_age(wood.data_age_hours)} {icon}\n", style=color
    )
    if plank is not None:
        body.append(
            f"ACHAT {refined_upper} T{plank.tier}  {plank.city:<14} "
            f"{plank.prix_unitaire:.0f} s × {plank.quantite} = {fmt_silver(plank.cout_total)}\n"
        )
        icon, color = _FRESHNESS_ICON[plank.freshness]
        body.append(
            f"                 fraîcheur : {fmt_age(plank.data_age_hours)} {icon}\n", style=color
        )

    # Raffinage.
    refined = route.raffinage
    body.append(
        f"RAFFINAGE {refining_city_short:<6} coût station = {fmt_silver(refined.cout_station)}\n"
    )
    body.append(
        f"RRR effectif : {refined.rrr_effectif * 100:.1f}% | "
        f"Output : {refined.planks_produits} {res.display_refined}s "
        f"+ {refined.wood_retour:.0f} {res.display_raw} "
        f"+ {refined.plank_moins_1_retour:.0f} {res.display_refined} T-1 retour\n"
    )
    if refined.focus_utilise > 0:
        body.append(f"FOCUS : {refined.focus_utilise:.0f}\n")

    # Vente — les deux scénarios sont toujours affichés côte à côte.
    body.append("\n")
    body.append(f"VENTE @ {route.vente.ville}\n", style="bold cyan")
    _append_scenario_a(body, route.vente.scenario_a_instant_sell)
    _append_scenario_b(body, route.vente.scenario_b_sell_order)

    if WarningCode.ROUTE_ZONE_ROUGE in route.warnings:
        body.append("        ⚠ ROUTE PAR ZONE ROUGE\n", style="bold red")
    if WarningCode.PROFONDEUR_INCERTAINE in route.warnings:
        body.append(
            "        ⚠ profondeur de marché incertaine (volume < quantité)\n", style="yellow"
        )

    # Synthèse.
    body.append("\n")
    if route.recup_totale > 0 or route.recup_wood_demande > 0:
        ville = route.recup_city or res.refining_city
        detail = (
            f"{route.recup_wood_absorbe}/{route.recup_wood_demande} "
            f"{res.display_raw} absorbés, "
            f"{route.recup_plank_absorbe}/{route.recup_plank_demande} "
            f"{res.display_refined} T-1 absorbés"
        )
        body.append(
            f"RÉCUP @ {ville:<11}: {fmt_silver(route.recup_totale)} ({detail})\n",
            style="green",
        )
    if WarningCode.RECUP_PARTIELLE in route.warnings:
        reste_bois = route.recup_wood_demande - route.recup_wood_absorbe
        reste_plank = route.recup_plank_demande - route.recup_plank_absorbe
        body.append(
            f"        ⚠ {reste_bois} {res.display_raw} et {reste_plank} "
            f"{res.display_refined} T-1 restent en "
            "inventaire, non valorisés (carnet d'achat insuffisant)\n",
            style="yellow",
        )
    if WarningCode.RECUP_SATURATION in route.warnings:
        body.append(
            "        ⚠ récup > 50% du volume 24h de la ville : "
            "risque d'écraser le carnet en dumpant tout d'un coup\n",
            style="yellow",
        )
    body.append(f"CAPITAL DÉPENSÉ  : {fmt_silver(route.cout_total)}\n")
    body.append(
        f"COÛT NET (après récup) : {fmt_silver(route.cout_net)}\n",
        style="dim",
    )
    benefice_style = "bold green" if route.benefice >= 0 else "bold red"
    sign = "+" if route.benefice >= 0 else ""
    body.append(f"BÉNÉFICE SAFE    : {sign}{fmt_silver(route.benefice)}\n", style=benefice_style)
    body.append(
        f"ROI CAPITAL      : {sign}{route.marge_pct:.1f}% "
        "(bénéfice / capital dépensé, la vraie ROI trader)\n",
        style=benefice_style,
    )
    body.append(
        f"marge efficacité : {route.marge_efficacite_pct:.1f}% "
        "(ancien indicateur V1, bénéfice / coût net)\n",
        style="dim",
    )
    if route.benefice_b is not None:
        signe_b = "+" if route.benefice_b >= 0 else ""
        body.append(
            f"POTENTIEL SO     : {signe_b}{fmt_silver(route.benefice_b)} (espérance sell order)\n",
            style="dim",
        )
    if route.silver_par_focus is not None:
        body.append(f"SILVER / FOCUS   : {route.silver_par_focus:.2f} s\n")
    body.append(
        f"RECOMMANDATION   : {_RECO_LABEL.get(route.vente.recommandation, '?')}\n",
        style="bold",
    )

    signe = "+" if route.benefice >= 0 else ""
    title = (
        f"TOP {route.rank} — Capital {fmt_silver(route.cout_total)} → "
        f"Bénéfice {signe}{fmt_silver(route.benefice)} (ROI {signe}{route.marge_pct:.1f}%)"
    )
    if route.marge_pct_b is not None:
        title += f" | potentiel SO {route.marge_pct_b:+.1f}%"
    subtitle = f"TIER {route.tier} {refined_upper} — {route.quantite} unités"
    return Panel(body, title=title, subtitle=subtitle, border_style=_marge_color(route.marge_pct))


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
        if entry.role:
            line += f" — {entry.role}"
        console.print(line, style=color)

    console.print()
    console.print("━━━ CONSEILS TRADING ━━━", style="bold")
    for conseil in _CONSEILS_TRADING:
        console.print(f"  - {conseil}")


def _render_no_routes(result: OptimizationResult, console: Console) -> None:
    """Affiche les alternatives écartées quand aucune route ne passe le seuil.

    Depuis V2.1, on liste jusqu'à ``top_n`` candidats (via ``discarded_top``)
    au lieu du seul « meilleur » : l'utilisateur voit l'éventail réel du
    marché et peut arbitrer manuellement (baisser le seuil, changer de tier).
    """
    seuil = result.run_metadata.params.get("seuil_marge_min_pct", "?")
    alternatives = result.discarded_top or (
        [result.discarded_best] if result.discarded_best is not None else []
    )
    if not alternatives:
        console.print(
            "Aucun candidat exploitable trouvé (données absentes ou trop vieilles).",
            style="bold yellow",
        )
        return

    console.print(
        f"Aucune route ne passe le seuil de {seuil}% de ROI capital. "
        f"Voici les {len(alternatives)} meilleures alternatives :",
        style="bold yellow",
    )
    console.print()
    for rank, discarded in enumerate(alternatives, start=1):
        console.print(f"[{rank}] {discarded.description}", style="bold")
        if discarded.marge_pct is not None:
            console.print(
                f"    ROI capital (instant sell) : {discarded.marge_pct:.1f}%"
            )
        if discarded.marge_pct_b is not None:
            console.print(
                f"    ROI capital (sell order)   : {discarded.marge_pct_b:.1f}%"
            )
        if discarded.marge_efficacite_pct is not None:
            console.print(
                f"    Marge efficacité (secondaire, V1) : "
                f"{discarded.marge_efficacite_pct:.1f}%",
                style="dim",
            )
        console.print()

    console.print("Suggestions :", style="bold")
    for suggestion in alternatives[0].suggestions:
        console.print(f"  - {suggestion}")


def format_json(result: OptimizationResult) -> str:
    """Sérialise le résultat en JSON indenté (structure SPEC section 9.4).

    Args:
        result: Résultat d'optimisation.

    Returns:
        Une chaîne JSON UTF-8 lisible.
    """
    return json.dumps(result.model_dump(mode="json"), indent=2, ensure_ascii=False)
