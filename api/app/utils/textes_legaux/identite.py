"""L'IDENTITÉ que nomment les textes légaux de la copropriété servie (#2065).

Une installation peut servir plusieurs syndicats de copropriétaires : chacun est
**responsable** du traitement de ses données, et l'opérateur de l'installation son
**sous-traitant** (RGPD art. 28). Les mentions légales et la politique de
confidentialité de chaque copropriété doivent donc nommer SON syndicat et SON
syndic, et l'opérateur commun à toutes.

| Ce qui est nommé | D'où il vient | À qui il appartient |
|---|---|---|
| le syndicat, son adresse | la fiche de la copropriété (`Copropriete`) | à la copropriété |
| le syndic, son adresse | `utils/syndic.nom_du_syndic`, `SyndicInfo.adresse` | à la copropriété |
| l'adresse où exercer ses droits | `ConfigSite.contact_donnees_personnelles` | à la copropriété |
| l'opérateur, l'hébergeur | les réglages de l'installation (`.env`) | à l'installation (D5) |

🔴 Une valeur absente vaut `None` — et les valeurs D'EXEMPLE que pose le seed
d'une base neuve aussi : « Ma Résidence, 1 rue Exemple » publiée comme éditeur
serait pire qu'un « À RENSEIGNER », qui au moins se voit.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from sqlmodel import Session, select

from app.config import get_settings
from app.models.copropriete import Copropriete
from app.models.gouvernance import SyndicInfo
from app.utils.config_site import config_site
from app.utils.liens import NOM_SITE_PAR_DEFAUT
from app.utils.syndic import nom_du_syndic

#: La clé de l'adresse où exercer ses droits : joignable SANS compte, au nom du
#: syndicat — un droit d'effacement s'exerce souvent après la suppression du compte.
CLE_CONTACT = "contact_donnees_personnelles"

#: La copropriété d'EXEMPLE que le seed pose sur une base vierge
#: (`seed._copropriete_par_defaut`, qui la lit ici) : reconnue comme non renseignée.
COPROPRIETE_EXEMPLE = {"nom": NOM_SITE_PAR_DEFAUT, "adresse": "1 rue Exemple, 75000 Paris"}


@dataclass(frozen=True)
class IdentiteLegale:
    copropriete: Optional[str] = None
    adresse_copropriete: Optional[str] = None
    syndic: Optional[str] = None
    adresse_syndic: Optional[str] = None
    contact: Optional[str] = None
    operateur: Optional[str] = None
    adresse_operateur: Optional[str] = None
    contact_operateur: Optional[str] = None
    hebergeur: Optional[str] = None
    pays_donnees: Optional[str] = None


def _renseigne(valeur: Optional[str], exemple: str = "") -> Optional[str]:
    """La valeur nettoyée, ou `None` si elle est vide ou vaut l'exemple du seed."""
    propre = (valeur or "").strip()
    return propre if propre and propre != exemple else None


def identite_legale(session: Session) -> IdentiteLegale:
    """L'identité de la copropriété servie par `session`, et celle de l'installation."""
    copro = session.exec(select(Copropriete)).first()
    syndic = session.exec(select(SyndicInfo)).first()
    s = get_settings()
    return IdentiteLegale(
        copropriete=_renseigne(copro and copro.nom, COPROPRIETE_EXEMPLE["nom"]),
        adresse_copropriete=_renseigne(copro and copro.adresse, COPROPRIETE_EXEMPLE["adresse"]),
        syndic=_renseigne(nom_du_syndic(session)),
        adresse_syndic=_renseigne(syndic and syndic.adresse),
        contact=_renseigne(config_site(session, CLE_CONTACT).get(CLE_CONTACT)),
        operateur=_renseigne(s.operateur_nom),
        adresse_operateur=_renseigne(s.operateur_adresse),
        contact_operateur=_renseigne(s.operateur_contact),
        hebergeur=_renseigne(s.hebergeur),
        pays_donnees=_renseigne(s.hebergeur_pays),
    )
