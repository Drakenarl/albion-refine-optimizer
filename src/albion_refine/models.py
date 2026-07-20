"""Modèles de données typés du projet.

On utilise Pydantic pour la validation et la sérialisation JSON. Ces modèles
sont partagés par tous les modules : ``aodp_client`` produit des ``PriceQuote``
et ``VolumeData``, ``refining`` produit des ``RefiningResult``, ``market``
produit des ``SalesScenario``, et ``optimizer`` assemble le tout en ``Route``.

Aucune logique métier ici : uniquement des structures et de petits accesseurs
dérivés (âge d'un prix, absence de données).
"""

from __future__ import annotations

from datetime import datetime, timedelta
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

# ---------------------------------------------------------------------------
# Énumérations
# ---------------------------------------------------------------------------


class QuantityMode(StrEnum):
    """Mode de dimensionnement de la quantité à raffiner."""

    CAPITAL = "capital"
    FIXED = "fixed"
    FOCUS = "focus"


class SellStrategy(StrEnum):
    """Stratégie de vente évaluée pour une ville."""

    INSTANT_SELL = "instant_sell"
    SELL_ORDER = "sell_order"


class FreshnessLevel(StrEnum):
    """Niveau de fraîcheur d'un prix AODP."""

    FRESH = "fresh"  # ✓ vert
    WARNING = "warning"  # ⚠ jaune
    CRITICAL = "critical"  # ✗ rouge (exclu par défaut)
    UNKNOWN = "unknown"  # pas de timestamp exploitable


class WarningCode(StrEnum):
    """Codes d'avertissement attachables à une route."""

    ROUTE_ZONE_ROUGE = "ROUTE_ZONE_ROUGE"
    PROFONDEUR_INCERTAINE = "PROFONDEUR_INCERTAINE"
    DATA_JAUNE = "DATA_JAUNE"
    RECUP_PARTIELLE = "RECUP_PARTIELLE"


# Date sentinelle renvoyée par l'AODP quand aucune donnée n'existe.
AODP_SENTINEL_YEAR = 1


# ---------------------------------------------------------------------------
# Données brutes issues de l'AODP
# ---------------------------------------------------------------------------


class PriceQuote(BaseModel):
    """Prix courant d'un item dans une ville (endpoint ``/prices``).

    Les dates sentinelles de l'AODP (``0001-01-01``) sont converties en
    ``None`` en amont par le client. Un prix à ``0`` signifie « pas d'offre ».
    """

    model_config = ConfigDict(frozen=True)

    item_id: str
    city: str
    quality: int = 1
    sell_price_min: int = 0
    sell_price_min_date: datetime | None = None
    sell_price_max: int = 0
    sell_price_max_date: datetime | None = None
    buy_price_min: int = 0
    buy_price_min_date: datetime | None = None
    buy_price_max: int = 0
    buy_price_max_date: datetime | None = None

    @property
    def has_sell_offer(self) -> bool:
        """Vrai si un ordre de vente exploitable existe (prix > 0 et daté)."""
        return self.sell_price_min > 0 and self.sell_price_min_date is not None

    @property
    def has_buy_offer(self) -> bool:
        """Vrai si un ordre d'achat exploitable existe (prix > 0 et daté)."""
        return self.buy_price_max > 0 and self.buy_price_max_date is not None

    def sell_min_age(self, now: datetime) -> timedelta | None:
        """Âge du prix ``sell_price_min`` par rapport à ``now`` (ou ``None``)."""
        if self.sell_price_min_date is None:
            return None
        return now - self.sell_price_min_date

    def buy_max_age(self, now: datetime) -> timedelta | None:
        """Âge du prix ``buy_price_max`` par rapport à ``now`` (ou ``None``)."""
        if self.buy_price_max_date is None:
            return None
        return now - self.buy_price_max_date


class VolumeData(BaseModel):
    """Volume échangé sur 24h pour un item dans une ville (endpoint ``/history``)."""

    model_config = ConfigDict(frozen=True)

    item_id: str
    city: str
    total_volume_24h: float = 0.0
    latest_timestamp: datetime | None = None
    num_points: int = 0


# ---------------------------------------------------------------------------
# Résultats métier
# ---------------------------------------------------------------------------


class RefiningResult(BaseModel):
    """Résultat d'un raffinage (formules SPEC sections 7.1, 7.2, 3.4)."""

    planks_produits: int
    wood_utilise: int
    plank_moins_1_utilise: int
    wood_retour: float
    plank_moins_1_retour: float
    cout_station: float
    rrr_effectif: float
    focus_utilise: float


class SalesScenario(BaseModel):
    """Évaluation d'un scénario de vente pour une ville donnée.

    ``expected_revenu`` vaut ``revenu_net`` en instant sell et
    ``revenu_net × fill_proba`` en sell order. ``marge_pct`` est renseignée par
    l'optimiseur une fois le coût net de la route connu.
    """

    strategy: SellStrategy
    city: str
    planks: int
    prix_unitaire_ref: float
    revenu_brut: float
    revenu_net: float
    fill_proba: float
    expected_revenu: float
    stack_suffisant: bool
    data_age_hours: float | None = None
    # Certitude qualitative : « haute » en instant sell (revenu immédiat),
    # « moyenne » en sell order (conditionnel au remplissage de l'ordre).
    certitude: str = "haute"
    marge_pct: float | None = None
    benefice: float | None = None
    # Scénario B uniquement : écart d'espérance de revenu face au scénario A.
    gain_marginal_vs_a: float | None = None
    gain_marginal_pct: float | None = None


class VenteBlock(BaseModel):
    """Les deux scénarios de vente d'une ville, présentés côte à côte.

    La V1.0 ne retenait que le meilleur des deux, ce qui masquait le scénario A
    (instant sell) alors que c'est l'option « safe ». On expose désormais
    toujours les deux et on laisse l'utilisateur arbitrer (SPEC_FIX section 3).
    """

    ville: str
    scenario_a_instant_sell: SalesScenario | None = None
    scenario_b_sell_order: SalesScenario | None = None
    recommandation: str = "instant_sell"


class SourcingLeg(BaseModel):
    """Coût d'approvisionnement d'un input (bois ou plank T-1) dans une ville."""

    kind: str  # "wood" ou "plank"
    item_id: str
    tier: int
    city: str
    prix_unitaire: float
    quantite: int
    cout_total: float
    data_age_hours: float | None = None
    freshness: FreshnessLevel = FreshnessLevel.UNKNOWN


class Route(BaseModel):
    """Route complète d'achat → raffinage → vente, avec sa marge nette."""

    rank: int = 0
    tier: int
    quantite: int
    achat_wood: SourcingLeg
    # ``None`` quand la recette ne consomme pas de plank T-1 (cas du T2).
    achat_plank: SourcingLeg | None = None
    raffinage: RefiningResult
    vente: VenteBlock
    recup_wood: float
    recup_plank: float
    # Quantités réellement absorbées par les buy orders de la ville de raffinage
    # face aux quantités retournées par le RRR (walk du carnet, SPEC_FIX 5).
    recup_wood_absorbe: int = 0
    recup_wood_demande: int = 0
    recup_plank_absorbe: int = 0
    recup_plank_demande: int = 0
    recup_totale: float
    cout_total: float
    cout_net: float
    # Toutes les valeurs « safe » ci-dessous proviennent du scénario A
    # (instant sell) : c'est sur elles que portent le tri et le seuil de marge.
    revenu_effectif: float
    benefice: float
    marge_pct: float
    # Potentiel du scénario B (sell order), pondéré par la fill probability.
    benefice_b: float | None = None
    marge_pct_b: float | None = None
    silver_par_focus: float | None = None
    warnings: list[WarningCode] = Field(default_factory=list)


class RefreshChecklistItem(BaseModel):
    """Une entrée de la check-list des pages marché à rafraîchir en jeu."""

    city: str
    item_id: str
    age_hours: float | None
    freshness: FreshnessLevel


class DiscardedRoute(BaseModel):
    """Meilleur candidat écarté, affiché quand aucune route ne passe le seuil."""

    description: str
    marge_pct: float | None
    raison: str
    suggestions: list[str] = Field(default_factory=list)


class RunMetadata(BaseModel):
    """Métadonnées d'un run d'optimisation."""

    timestamp: datetime
    tier: int
    mode: QuantityMode
    params: dict[str, Any] = Field(default_factory=dict)


class OptimizationResult(BaseModel):
    """Résultat complet d'un run : routes triées + check-list + candidat écarté."""

    run_metadata: RunMetadata
    routes: list[Route] = Field(default_factory=list)
    refresh_checklist: list[RefreshChecklistItem] = Field(default_factory=list)
    discarded_best: DiscardedRoute | None = None
