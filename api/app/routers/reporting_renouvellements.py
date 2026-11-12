"""Reporting CS › Renouvellements — le RELEVÉ servi (#2525).

## Pourquoi il existe

La vue se calculait dans le front (`#lib/reporting.ts`) : l'échéance et l'urgence
d'un diagnostic, l'ordre des contrats (la pire note d'abord), les trois compteurs
du bandeau et l'année de référence — celle du navigateur. L'app iOS ne recopie
aucune règle du site (`standards/09` §8) : elle laissait la vue au site. Le Suivi
des affaires montrait la voie (`GET /suivi-affaires` porte la règle) ; ce relevé
la suit, et le site le lit tel quel.

Ce qu'il sert, et d'où chaque règle vient :

- un contrat : sa lecture entière (`prestataires_lecture.lire_contrats`, échéance
  comprise — `utils/echeance_contrat`), le nom et la note de son prestataire, et
  si son terme ou son préavis tombe dans l'année ;
- un diagnostic APPLICABLE : sa lecture (`diagnostics.lire_type_diagnostic`) et
  son échéance (`utils/echeance_diagnostic`) — un non applicable est une décision
  de la copropriété, il sort ; un permanent reste, sans échéance ;
- les compteurs du bandeau, comptés sur ces deux listes.
"""

from __future__ import annotations

from datetime import date
from typing import Literal, Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlmodel import Session, select

from app.auth.deps import require_cs_or_admin
from app.database import get_session
from app.models.core import DiagnosticType, Prestataire, Utilisateur
from app.routers.diagnostics import DiagnosticTypeRead, lire_type_diagnostic
from app.routers.prestataires_lecture import lister_contrats
from app.routers.prestataires_schemas import ContratRead
from app.utils import horloge
from app.utils.echeance_contrat import PREAVIS_MOIS
from app.utils.echeance_diagnostic import est_permanent, prochaine_echeance, urgence_diagnostic
from app.utils.notes_prestataires import SANS_AVIS, notes_des_prestataires
from app.utils.recuperer import precharger

router = APIRouter(prefix="/reporting", tags=["reporting"])

#: Une note absente se range APRÈS la pire note réelle (sur 5) : jamais devant un
#: prestataire réellement mal noté.
NOTE_ABSENTE = 6


class ContratARenouveler(ContratRead):
    prestataire_nom: str
    note_moyenne: Optional[float] = None
    nb_notations: int = 0
    #: Le terme OU le début du préavis tombe dans l'année du relevé.
    echeance_dans_l_annee: bool


class DiagnosticAEcheance(DiagnosticTypeRead):
    permanent: bool
    dernier_rapport_le: Optional[date] = None
    prochaine_echeance: Optional[date] = None
    urgence_echeance: Optional[Literal["depasse", "annee", "futur"]] = None


class CompteursRenouvellements(BaseModel):
    #: Préavis en cours, ou terme qui ne se déduit pas.
    contrats_en_preavis: int
    echeances_contrats_annee: int
    #: Dépassés, à faire dans l'année, ou sans échéance connue.
    audits_a_planifier: int


class ReleveRenouvellements(BaseModel):
    #: L'année de référence : celle du jour de Paris.
    annee: int
    preavis_mois: int
    compteurs: CompteursRenouvellements
    #: La pire note d'abord, puis le terme le plus proche.
    contrats: list[ContratARenouveler]
    #: L'échéance la plus proche d'abord ; sans échéance, à la fin.
    diagnostics: list[DiagnosticAEcheance]


def _contrats(session: Session, annee: int) -> list[ContratARenouveler]:
    #  Un contrat REMPLACÉ est déjà renouvelé : son successeur porte désormais la
    #  question, et le relancer ferait deux lignes pour une seule décision
    #  (`utils/remplacement_contrat`). Résilié SANS suite, il reste : il manque un contrat.
    lus = [c for c in lister_contrats(session, archivees=False) if c.remplace_par_id is None]
    ids = [c.prestataire_id for c in lus]
    notes = notes_des_prestataires(session, ids)
    noms = {p.id: p.nom for p in precharger(session, Prestataire, ids)}
    contrats = []
    for c in lus:
        moyenne, nombre = notes.get(c.prestataire_id, SANS_AVIS)
        contrats.append(
            ContratARenouveler(
                **c.model_dump(),
                prestataire_nom=noms.get(c.prestataire_id, f"#{c.prestataire_id}"),
                note_moyenne=moyenne,
                nb_notations=nombre,
                echeance_dans_l_annee=c.date_fin is not None
                and annee in {c.date_fin.year, c.date_preavis and c.date_preavis.year},
            )
        )
    return sorted(
        contrats,
        key=lambda c: (
            NOTE_ABSENTE if c.note_moyenne is None else c.note_moyenne,
            c.date_fin is None,
            c.date_fin or date.max,
        ),
    )


def _diagnostics(session: Session) -> list[DiagnosticAEcheance]:
    types = session.exec(
        select(DiagnosticType)
        .where(DiagnosticType.actif == True)  # noqa: E712
        .where(DiagnosticType.non_applicable == False)  # noqa: E712
        .order_by(DiagnosticType.ordre)
    ).all()
    diagnostics = []
    for t in types:
        lu = lire_type_diagnostic(session, t)
        #  Les rapports viennent le plus récent d'abord : le premier daté fait foi.
        dernier = next((r.date_rapport for r in lu.rapports if r.date_rapport), None)
        echeance = prochaine_echeance(lu.frequence, dernier)
        diagnostics.append(
            DiagnosticAEcheance(
                **lu.model_dump(),
                permanent=est_permanent(lu.frequence),
                dernier_rapport_le=dernier,
                prochaine_echeance=echeance,
                urgence_echeance=urgence_diagnostic(echeance),
            )
        )
    return sorted(
        diagnostics,
        key=lambda d: (d.prochaine_echeance is None, d.prochaine_echeance or date.max),
    )


@router.get("/renouvellements", response_model=ReleveRenouvellements)
def releve_renouvellements(
    session: Session = Depends(get_session),
    _: Utilisateur = Depends(require_cs_or_admin),
) -> ReleveRenouvellements:
    """Les contrats et les diagnostics à renouveler, rangés et comptés (Reporting CS)."""
    annee = horloge.aujourd_hui().year
    contrats = _contrats(session, annee)
    diagnostics = _diagnostics(session)
    return ReleveRenouvellements(
        annee=annee,
        preavis_mois=PREAVIS_MOIS,
        compteurs=CompteursRenouvellements(
            contrats_en_preavis=sum(c.urgence_echeance in (None, "preavis") for c in contrats),
            echeances_contrats_annee=sum(c.echeance_dans_l_annee for c in contrats),
            audits_a_planifier=sum(d.urgence_echeance != "futur" for d in diagnostics),
        ),
        contrats=contrats,
        diagnostics=diagnostics,
    )
