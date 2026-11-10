"""La forme de `GET /telemetry/dashboard` — le tableau de bord de l'administrateur.

## Pourquoi (#2618, 10/11/2026)

La route rendait le dict de `utils/telemetrie_tableau.tableau`, que le contrat
annonçait `{}` : l'app iOS, qui se génère depuis `openapi.json`, le relisait « en
miroir ». Ces schémas décrivent ce que le serveur sert DÉJÀ, clé pour clé, toutes
portées comprises — rien n'est ajouté ni renommé.

⚠️ Un `response_model` FILTRE : une clé que la lecture ajouterait sans la déclarer
ici disparaîtrait de la réponse sans un mot. 🔒 `test_reponses_typees_parametrage.py`
compare, pour chaque portée, la réponse au dict produit par la lecture.

Les indicateurs (`kpi`) varient selon la portée : tous facultatifs, `null` quand la
portée ne les calcule pas — le site les lit par `!= null` / `??`.
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field, model_serializer


class Record(BaseModel):
    """Le jour (`jour`, « AAAA-MM-JJ ») ou le mois (`mois`, « AAAA-MM ») record."""

    jour: Optional[str] = None
    mois: Optional[str] = None
    uniques: int

    @model_serializer(mode="wrap")
    def _sans_la_cle_absente(self, suite):
        """Sert `{"jour": …, "uniques": n}` OU `{"mois": …}` — la forme d'avant le
        typage, que le site compare telle quelle : jamais la clé de l'autre portée."""
        return {k: v for k, v in suite(self).items() if v is not None or k == "uniques"}


class IndicateursTelemetrie(BaseModel):
    """`kpi` — la partie qui dépend de la portée (jour, mois, année, total)."""

    vues: int
    pages: int
    utilisateurs: Optional[int] = None
    heure_pointe: Optional[str] = None
    moy_vues_utilisateur: Optional[float] = None
    moy_vues_jour: Optional[float] = None
    moy_utilisateurs_jour: Optional[float] = None
    jour_pointe: Optional[Record] = None
    vues_non_attribuees: Optional[int] = None
    record_jour: Optional[Record] = None
    record_mois: Optional[Record] = None
    mois_actifs: Optional[int] = None
    moy_vues_mois: Optional[float] = None
    annees_actives: Optional[int] = None
    moy_vues_an: Optional[float] = None


class Baton(BaseModel):
    """Un bâton du graphique ; `uniques` est absent du graphique par année."""

    label: str
    total: int
    uniques: Optional[int] = None


class PageTop(BaseModel):
    page: str
    total: int
    uniques: int


class UtilisateurTop(BaseModel):
    nom: str
    derniere_connexion: Optional[datetime] = None
    statut: Optional[str] = None
    batiment_id: Optional[int] = None
    total: int
    pages: int


class ErreurDuTableau(BaseModel):
    page: str
    code: str
    total: int
    premiere_le: datetime
    derniere_le: datetime


class IndicateurDuree(BaseModel):
    indicateur: str
    mesures: int
    mediane: int
    p75: int


class DureePage(IndicateurDuree):
    page: str


class Durees(BaseModel):
    indicateurs: list[IndicateurDuree]
    pages: list[DureePage]


class Geste(BaseModel):
    geste: str
    ouvertures: int
    envois: int
    taux: Optional[int] = None


class Arrivee(BaseModel):
    canal: str
    modele: Optional[str] = None
    libelle: Optional[str] = None
    arrivees: int
    comptes: int
    envois: Optional[int] = None


class LigneAdoption(BaseModel):
    libelle: str
    actifs: int
    comptes: int
    taux: Optional[int] = None


class Adoption(BaseModel):
    """`global` est un mot réservé de Python : le champ s'appelle `ensemble`, et
    sort sous son nom servi par l'alias."""

    model_config = ConfigDict(populate_by_name=True, serialize_by_alias=True)

    periode: str
    ensemble: LigneAdoption = Field(alias="global")
    refus: int
    par_profil: list[LigneAdoption]
    par_type: list[LigneAdoption]
    par_batiment: list[LigneAdoption]


class SeuilDormants(BaseModel):
    seuil: int
    nombre: int


class CompteDormant(BaseModel):
    user_id: int
    nom: str
    type: str
    derniere_visite: Optional[str] = None
    jours: int


class RetourArrivants(BaseModel):
    periode: str
    fenetre_jours: int
    valides: int
    revenus: int
    jamais_revenus: int
    en_attente: int
    taux: Optional[int] = None


class Retour(BaseModel):
    comptes_mesures: int
    refus: int
    dormants: list[SeuilDormants]
    liste_dormants: list[CompteDormant]
    arrivants: RetourArrivants


class FiltreGestionnaire(BaseModel):
    propose: bool
    gestionnaire_designe: bool
    applique: str
    non_distingue_jusqu_au: Optional[str] = None


class TableauTelemetrie(BaseModel):
    """`GET /telemetry/dashboard` — le pendant serveur de `TableauTelemetrie` (front)."""

    scope: str
    kpi: IndicateursTelemetrie
    chart: list[Baton]
    chart_label: str
    top_pages: list[PageTop]
    top_users: list[UtilisateurTop]
    erreurs: list[ErreurDuTableau]
    performance: Durees
    gestes: list[Geste]
    arrivees: list[Arrivee]
    adoption: Optional[Adoption] = None
    retour: Retour
    filtre_gestionnaire: FiltreGestionnaire
