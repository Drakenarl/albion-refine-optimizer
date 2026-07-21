"""Constantes et paramètres de référence du projet.

Ce module ne contient **aucune** logique métier ni I/O réseau : uniquement des
constantes (item IDs, villes, taxes, valeurs par défaut) et un petit utilitaire
de chargement du fichier ``items.json`` embarqué, utilisé par la commande
``check-item-ids`` pour vérifier que les IDs codés en dur correspondent bien à
la source de vérité.

Toutes les valeurs proviennent de ``SPEC.md`` (sections 3, 6 et 7) après
application des corrections urgentes (nutrition en silver/100 nutrition).
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Final

from albion_refine.models import ResourceKind as ResourceKind  # re-export explicite

# ---------------------------------------------------------------------------
# Tiers de raffinage supportés en V1
# ---------------------------------------------------------------------------

MIN_TIER: Final = 4
MAX_TIER: Final = 8
SUPPORTED_TIERS: Final = tuple(range(MIN_TIER, MAX_TIER + 1))

# ---------------------------------------------------------------------------
# Ressources supportees (voir SPEC section 6.1 + extension V2.2 pour la peau)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Resource:
    """Filiere de raffinage : IDs AODP, ville specialite, libelles FR.

    Sert de source de verite unique pour paramerer l'optimiseur, la CLI, la
    checklist et le rendu. Ajouter une filiere (fibre, minerai, pierre) =
    ajouter une entree dans ``RESOURCES`` et zero changement dans la logique.
    """

    kind: ResourceKind
    raw_prefix: str  # ex "WOOD" -> item id "T5_WOOD"
    refined_prefix: str  # ex "PLANKS" -> item id "T5_PLANKS"
    refining_city: str  # ville qui accorde +40% specialite
    display_raw: str  # libelle FR de la matiere premiere (ex "bois")
    display_refined: str  # libelle FR du raffine (ex "plank")

    def raw_item_id(self, tier: int) -> str:
        """Item ID AODP de la matiere premiere pour ``tier`` (ex ``T5_WOOD``)."""
        return f"T{tier}_{self.raw_prefix}"

    def refined_item_id(self, tier: int) -> str:
        """Item ID AODP du raffine pour ``tier`` (ex ``T5_PLANKS``)."""
        return f"T{tier}_{self.refined_prefix}"


RESOURCES: Final[dict[ResourceKind, Resource]] = {
    ResourceKind.WOOD: Resource(
        kind=ResourceKind.WOOD,
        raw_prefix="WOOD",
        refined_prefix="PLANKS",
        refining_city="Fort Sterling",
        display_raw="bois",
        display_refined="plank",
    ),
    ResourceKind.HIDE: Resource(
        kind=ResourceKind.HIDE,
        raw_prefix="HIDE",
        refined_prefix="LEATHER",
        refining_city="Martlock",
        display_raw="peau",
        display_refined="cuir",
    ),
}


def resource(kind: ResourceKind | str) -> Resource:
    """Retourne la ``Resource`` correspondant a un ``ResourceKind`` ou son slug."""
    return RESOURCES[ResourceKind(kind)]


# Alias historiques (bois par defaut) : conserves pour la retrocompatibilite
# des tests V1/V2.0. Nouveaux appels : passer par ``resource(kind).raw_item_id``.
WOOD_ITEM_IDS: Final[dict[int, str]] = {tier: f"T{tier}_WOOD" for tier in range(4, 9)}
PLANK_ITEM_IDS: Final[dict[int, str]] = {tier: f"T{tier}_PLANKS" for tier in range(3, 9)}
HIDE_ITEM_IDS: Final[dict[int, str]] = {tier: f"T{tier}_HIDE" for tier in range(4, 9)}
LEATHER_ITEM_IDS: Final[dict[int, str]] = {tier: f"T{tier}_LEATHER" for tier in range(3, 9)}


def wood_item_id(tier: int) -> str:
    """[compat] Item ID du bois brut d'un tier. Prefer ``resource('wood').raw_item_id``."""
    return WOOD_ITEM_IDS[tier]


def plank_item_id(tier: int) -> str:
    """[compat] Item ID du plank d'un tier. Prefer ``resource('wood').refined_item_id``."""
    return PLANK_ITEM_IDS[tier]


# ---------------------------------------------------------------------------
# Recettes de raffinage (SPEC_FIX section 1.2, confirmées in-game le 20/07/2026)
# ---------------------------------------------------------------------------

# Format : tier du plank produit -> (quantité de bois T{N}, quantité de plank T{N-1})
# pour UNE unité de plank produite. La V1.0 supposait à tort (1, 1) partout, ce
# qui sous-estimait massivement le coût en bois brut aux tiers 5 à 8.
PLANK_RECIPES: Final[dict[int, tuple[int, int]]] = {
    2: (1, 0),
    3: (2, 1),
    4: (2, 1),
    5: (3, 1),
    6: (4, 1),
    7: (5, 1),
    8: (5, 1),
}


def plank_recipe(tier: int) -> tuple[int, int]:
    """Retourne la recette d'un plank : ``(bois requis, plank T-1 requis)``.

    Args:
        tier: Tier du plank produit (2 à 8).

    Returns:
        Un tuple ``(wood_qty, lower_plank_qty)`` par unité produite. Le T2 vaut
        ``(1, 0)`` : il n'a pas d'input plank.

    Raises:
        KeyError: Si le tier n'a pas de recette connue.
    """
    return PLANK_RECIPES[tier]


def wood_qty_per_plank(tier: int) -> int:
    """Retourne la quantité de bois brut nécessaire pour un plank de ce tier."""
    return plank_recipe(tier)[0]


def lower_plank_qty_per_plank(tier: int) -> int:
    """Retourne la quantité de plank T-1 nécessaire pour un plank de ce tier (0 en T2)."""
    return plank_recipe(tier)[1]


# ---------------------------------------------------------------------------
# Villes Royal du continent (voir SPEC section 6.2)
# ---------------------------------------------------------------------------

CITIES: Final[dict[str, dict[str, Any]]] = {
    "Caerleon": {"safe": False, "warning": "zone rouge autour"},
    "Fort Sterling": {"safe": True, "wood_refining_bonus": True},
    "Lymhurst": {"safe": True},
    "Bridgewatch": {"safe": True},
    "Martlock": {"safe": True},
    "Thetford": {"safe": True},
    "Brecilien": {"safe": True, "excluded_default": True},
}

# [compat] Ville de raffinage historique (bois). Depuis V2.2, chaque
# ``Resource`` porte sa propre ``refining_city`` : bois -> Fort Sterling,
# peau -> Martlock. A n'utiliser que dans les chemins de code non parametres.
REFINING_CITY: Final = "Fort Sterling"

# Ville dont une route déclenche le flag « zone rouge ».
RED_ZONE_CITY: Final = "Caerleon"


def all_cities() -> list[str]:
    """Retourne la liste de toutes les villes connues, dans l'ordre de config."""
    return list(CITIES.keys())


def safe_cities() -> list[str]:
    """Retourne les villes marquées comme sûres (``safe=True``)."""
    return [name for name, meta in CITIES.items() if meta.get("safe", False)]


# ---------------------------------------------------------------------------
# Bonus de Resource Return Rate à Fort Sterling (voir SPEC section 3.2 / 7.1)
# ---------------------------------------------------------------------------

CITY_BONUS_PCT: Final = 18  # bonus general de la ville de raffinage
# Le bonus specialite +40% est le meme pour toutes les filieres (bois a Fort
# Sterling, peau a Martlock, fibre a Lymhurst, etc.), a condition de raffiner
# dans la ville dediee. Le nom garde "WOOD" pour compat mais s'applique a toutes.
SPECIALTY_BONUS_PCT: Final = 40
WOOD_SPECIALTY_BONUS_PCT: Final = SPECIALTY_BONUS_PCT  # [compat]
BASE_REFINING_BONUS_PCT: Final = CITY_BONUS_PCT + SPECIALTY_BONUS_PCT  # 58
FOCUS_BONUS_PCT: Final = 59  # bonus apporte par le focus

# Daily bonus autorisés (affichés en jeu dans le menu Activités).
ALLOWED_DAILY_BONUS_PCT: Final = (0, 10, 20)

# Focus consommé par action de raffinage. La SPEC (section 8.3) indique
# « ~1 par action, à vérifier » : on retient 1.0 par défaut en V1.
FOCUS_PER_REFINE: Final = 1.0

# ---------------------------------------------------------------------------
# Coût station : valeurs de nutrition par unité raffinée (items.json corrigé)
# ---------------------------------------------------------------------------

# Nutrition consommée par unité raffinée = Item Value(tier) × 0.1125.
# Valeurs approximatives, à reconfirmer en jeu (voir CORRECTIONS_URGENTES).
NUTRITION_PER_REFINED_UNIT: Final[dict[int, float]] = {
    4: 1.575,
    5: 3.375,
    6: 6.975,
    7: 14.175,
    8: 28.575,
}

# Item Value des planks raffinés par tier (référence, non utilisé directement
# dans les formules mais conservé pour la commande dump-nutrition).
REFINED_ITEM_VALUES: Final[dict[int, int]] = {
    4: 14,
    5: 30,
    6: 62,
    7: 126,
    8: 254,
}


def nutrition_per_unit(tier: int) -> float:
    """Retourne la nutrition consommée par unité raffinée pour un tier.

    Args:
        tier: Tier du plank raffiné (4 à 8).

    Returns:
        La nutrition par unité, par exemple ``14.175`` pour le T7.

    Raises:
        KeyError: Si le tier n'est pas supporté.
    """
    return NUTRITION_PER_REFINED_UNIT[tier]


# ---------------------------------------------------------------------------
# Taxes de marché (joueur sans premium — voir SPEC section 6.5)
# ---------------------------------------------------------------------------

TAX_INSTANT_SELL: Final = 0.08
TAX_SELL_ORDER_SETUP: Final = 0.05
TAX_SELL_ORDER_SALE: Final = 0.08
TAX_SELL_ORDER_TOTAL: Final = TAX_SELL_ORDER_SETUP + TAX_SELL_ORDER_SALE  # 0.13

# ---------------------------------------------------------------------------
# Endpoints AODP (voir SPEC section 6.3)
# ---------------------------------------------------------------------------

AODP_BASE_URLS: Final[dict[str, str]] = {
    "europe": "https://europe.albion-online-data.com",
    "west": "https://west.albion-online-data.com",
    "east": "https://east.albion-online-data.com",
}

PRICES_PATH: Final = "/api/v2/stats/prices/{items}.json"
HISTORY_PATH: Final = "/api/v2/stats/history/{items}.json"

# Qualité forcée à 1 (Normal) pour le bois et les planks (SPEC section 3.6).
FORCED_QUALITY: Final = 1

# Timeouts et retries réseau (SPEC section 11.1).
HTTP_TIMEOUT_SECONDS: Final = 10.0
HTTP_MAX_RETRIES: Final = 3

# ---------------------------------------------------------------------------
# Paramètres par défaut (voir SPEC section 6.4)
# ---------------------------------------------------------------------------

DEFAULTS: Final[dict[str, Any]] = {
    # Depuis V2, le seuil s'applique à la ROI capital (bénéfice / dépense
    # brute), pas à l'ancienne marge d'efficacité (bénéfice / coût net après
    # récup). Le défaut à 0 laisse remonter toute route rentable ; l'utilisateur
    # serre la vis avec ``--seuil-marge N`` s'il veut filtrer plus haut.
    "seuil_marge_min_pct": 0,
    "seuil_fill_probability_pct": 20,
    "freshness_warning_hours": 3,  # jaune
    "freshness_critical_hours": 6,  # rouge, exclu par défaut
    "cache_ttl_minutes": 15,
    "sell_order_undercut_pct": 1,  # sous-cote 1% pour scénario B
    "premium": False,
    "server": "europe",
    "refining_city": REFINING_CITY,
    "excluded_sell_cities": ["Brecilien"],
    "excluded_buy_cities": ["Brecilien"],
}

# Le rate de station (silver / 100 nutrition) n'a PAS de valeur par défaut :
# l'utilisateur DOIT le fournir via --station-rate (SPEC section 6.4 corrigée).

# ---------------------------------------------------------------------------
# Chargement du fichier items.json embarqué
# ---------------------------------------------------------------------------

DATA_DIR: Final = Path(__file__).parent / "data"
ITEMS_JSON_PATH: Final = DATA_DIR / "items.json"


def load_items_data() -> dict[str, Any]:
    """Charge et retourne le contenu du ``items.json`` embarqué.

    Returns:
        Le dictionnaire désérialisé du fichier ``items.json``.

    Raises:
        FileNotFoundError: Si le fichier embarqué est absent.
    """
    with ITEMS_JSON_PATH.open(encoding="utf-8") as handle:
        data: dict[str, Any] = json.load(handle)
    return data
