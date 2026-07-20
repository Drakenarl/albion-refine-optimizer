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
    ``revenu_net × fill_proba`` en sell order.
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
    vente: SalesScenario
    recup_wood: float
    recup_plank: float
    recup_totale: float
    cout_total: float
    cout_net: float
    revenu_effectif: float
    benefice: float
    marge_pct: float
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
