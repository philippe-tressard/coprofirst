"""Ce que vaut l'inscription de CETTE installation — la décision PURE (R2 #1878, §4.11).

Aucune entrée-sortie : l'état rangé, l'instant, la clé de l'installation, son rôle
et les clés de la référence entrent ; un `Constat` sort. C'est ce qui se teste
sans réseau ni disque, cas par cas (`tests/test_inscription_constat.py`).

## Les règles

1. **La référence ne passe jamais en mode limité** (règle 7), et une installation
   d'**essai** n'est jamais limitée (règle 9).
2. **Un bail illisible vaut « limitée », jamais un arrêt** (règle 3) — et chaque
   raison de ne pas le croire se NOMME : signature, clé inconnue ou révoquée,
   époque inférieure (règle 11), bail d'une autre clé, échéance passée.
3. **L'état vient du bail, et seulement de lui** : « active » et « suspendue » ne
   se croient que signés.
4. **Mode constat** : ce verdict s'AFFICHE ; rien ne l'applique encore (R6 #1882) —
   sauf les SERVICES, avancés le 13/10/2026 : une réplique n'allume que ceux que
   son bail cru autorise (`services`, lu par `utils/services.service_actif`).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Optional

from pydantic import ValidationError

from app.inscription.depot import EtatLocal
from app.registre import signature
from app.registre.contrat import BailSigne, octets_du_bail
from app.utils import horloge
from app.utils.dates_fr import datetime_longue

#: Sans renouvellement depuis ce délai, l'administrateur d'installation est alerté (D19).
RETARD_RENOUVELLEMENT = timedelta(days=3)

REFERENCE = "reference"
ESSAI = "essai"
LIMITEE = "limitee"
ACTIVE = "active"
SUSPENDUE = "suspendue"


@dataclass(frozen=True)
class Constat:
    etat: str  #: reference · essai · limitee · active · suspendue
    raison: str
    identifiant: Optional[str] = None
    canal: Optional[str] = None
    version_cible: Optional[str] = None
    epoque: Optional[int] = None
    echeance: Optional[datetime] = None
    renouvellement_en_retard: bool = False
    #: Les services que la référence autorise : `None` = aucune restriction (la
    #: référence, une installation d'essai) ; sinon ceux du bail cru, et AUCUN
    #: sans bail cru, échu, en attente, suspendu ou résilié.
    services: Optional[frozenset[str]] = frozenset()


def bail_valide(
    etat: EtatLocal,
    cle_installation: Optional[str],
    cles: dict[int, str],
    revoquees: frozenset[str],
) -> tuple[Optional[BailSigne], str]:
    """Le bail rangé, s'il se croit — sinon None et la raison de ne pas le croire."""
    if not etat.bail:
        if etat.etat_inscription == "en_attente":
            return None, "inscription en attente de validation par la référence"
        return None, "aucun bail reçu de la référence"
    try:
        signe = BailSigne.model_validate(etat.bail)
    except ValidationError:
        return None, "bail illisible"
    bail = signe.bail
    cle = cles.get(bail.epoque)
    if cle is None:
        return None, f"clé de la référence inconnue pour l'époque {bail.epoque}"
    if cle in revoquees:
        return None, "bail signé par une clé révoquée"
    if not signature.verifier(cle, octets_du_bail(bail), signe.signature):
        return None, "signature du bail invalide"
    if bail.epoque < etat.plus_haute_epoque:
        return None, f"bail d'une ancienne référence (époque {bail.epoque})"
    if (
        bail.identifiant != etat.identifiant
        or not cle_installation
        or bail.empreinte_cle != signature.empreinte(cle_installation)
    ):
        return None, "bail d'une autre installation"
    return signe, ""


def _utc_naif(instant: datetime) -> datetime:
    """L'instant en UTC NAÏF, comme `horloge.maintenant()` — le bail les porte conscients."""
    if instant.tzinfo is None:
        return instant
    return instant.astimezone(timezone.utc).replace(tzinfo=None)


def _en_retard(etat: EtatLocal, maintenant: datetime) -> bool:
    if not etat.dernier_renouvellement_le:
        return etat.identifiant is not None
    try:
        dernier = datetime.fromisoformat(etat.dernier_renouvellement_le)
    except ValueError:
        return True
    return maintenant - dernier > RETARD_RENOUVELLEMENT


def constater(
    etat: EtatLocal,
    *,
    maintenant: datetime,
    cle_installation: Optional[str],
    reference: bool,
    essai: bool,
    cles: dict[int, str],
    revoquees: frozenset[str] = frozenset(),
) -> Constat:
    """Le verdict, et sa raison en clair."""
    if reference:
        return Constat(REFERENCE, "la référence n'est jamais limitée", services=None)
    if essai:
        return Constat(
            ESSAI, "installation d'essai : la référence n'est pas appelée", services=None
        )
    if etat.illisible:
        return Constat(LIMITEE, "état d'inscription illisible")
    if not etat.identifiant:
        return Constat(LIMITEE, "installation non inscrite au registre")
    retard = _en_retard(etat, maintenant)
    signe, raison = bail_valide(etat, cle_installation, cles, revoquees)
    if signe is None:
        return Constat(LIMITEE, raison, etat.identifiant, renouvellement_en_retard=retard)
    bail = signe.bail
    echeance = _utc_naif(bail.echeance)
    commun = dict(
        identifiant=bail.identifiant,
        canal=bail.canal,
        version_cible=bail.version_cible,
        epoque=bail.epoque,
        echeance=echeance,
        renouvellement_en_retard=retard,
    )
    if maintenant >= echeance:
        return Constat(
            LIMITEE, f"bail échu le {datetime_longue(horloge.a_paris(echeance))}", **commun
        )
    if bail.etat == SUSPENDUE:
        return Constat(SUSPENDUE, "suspendue par la référence", **commun)
    if bail.etat == ACTIVE:
        return Constat(ACTIVE, "bail valide", services=frozenset(bail.services_autorises), **commun)
    if bail.etat == "en_attente":
        return Constat(LIMITEE, "inscription en attente de validation par la référence", **commun)
    if bail.etat == "resiliee":
        return Constat(LIMITEE, "inscription résiliée par la référence", **commun)
    return Constat(LIMITEE, f"état de bail inconnu : {bail.etat}", **commun)
