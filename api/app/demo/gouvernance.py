"""Ce que l'annuaire lit : le conseil syndical, le syndic, la prochaine AG (spec §6.2)."""

from __future__ import annotations

from sqlmodel import Session

from app.demo.dates import jour
from app.models.core import Utilisateur
from app.models.gouvernance import AgCsInfo, GenreCivilite, MembreCS, MembreSyndic, SyndicInfo
from app.utils import horloge

#: Dans trois semaines : l'AG que le calendrier et l'annuaire annoncent.
JOURS_AVANT_AG = 21


def _membre(user: Utilisateur, genre: GenreCivilite, ordre: int, **champs) -> MembreCS:
    return MembreCS(
        genre=genre,
        prenom=user.prenom,
        nom=user.nom,
        batiment_id=user.batiment_id,
        etage=user.etage,
        ordre=ordre,
        user_id=user.id,
        **champs,
    )


def poser(session: Session, comptes: dict[str, Utilisateur]) -> None:
    session.add(_membre(comptes["Jean Dupont"], GenreCivilite.mr, 1, est_president=True))
    session.add(_membre(comptes["conseil-syndical"], GenreCivilite.mme, 2))
    session.add(_membre(comptes["Catherine Blondel"], GenreCivilite.mme, 3))
    session.add(
        MembreSyndic(
            genre=GenreCivilite.mme,
            prenom="Sylvie",
            nom="Martineau",
            fonction="Gestionnaire de la copropriété",
            email="gestion@syndic.demo.coprofirst.invalid",
            telephone="01 99 00 10 05",
            est_principal=True,
        )
    )
    session.add(SyndicInfo(adresse="3 rue de l'Exemple, 99000 Ville-Exemple"))
    session.add(AgCsInfo(ag_annee=horloge.aujourd_hui().year, ag_date=jour(JOURS_AVANT_AG)))
