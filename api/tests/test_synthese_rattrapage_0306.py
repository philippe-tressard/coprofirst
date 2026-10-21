"""La 0306 inscrit la synthèse des affaires closes par un point validé, et rien d'autre.

À retirer après la MEP qui applique la 0306 (`feedback_tests_migrations_appliquees`) :
les garde-fous génériques des migrations restent.
"""

from __future__ import annotations

from datetime import datetime
from types import SimpleNamespace

from sqlmodel import Session, select

from app.models.points_conseil import VALIDE, CompteRenduAffaire, PointConseil
from app.models.synthese import A_PRODUIRE, VALIDEE, SyntheseAffaire
from app.models.tickets import Ticket
from tests.aides_migrations import charger_migration

MIGRATION = charger_migration("0306")
CLOTURE = datetime(2026, 10, 21, 4, 4, 55)


def _jouer(session: Session) -> None:
    MIGRATION.op = SimpleNamespace(execute=session.connection().execute)
    MIGRATION.upgrade()
    session.commit()


def _affaire(session: Session, numero: str, *, statut="résolu", categorie="question") -> Ticket:
    t = Ticket(
        numero=numero,
        titre=numero,
        description="<p>x</p>",
        categorie=categorie,
        statut=statut,
        ferme_le=CLOTURE if statut in ("résolu", "annulé") else None,
    )
    session.add(t)
    session.commit()
    return t


def _point(session: Session, etat: str, abordees: list[tuple[Ticket, str | None]]) -> None:
    p = PointConseil(debut=datetime(2026, 10, 19, 17), etat=etat)
    session.add(p)
    session.commit()
    for t, cible in abordees:
        session.add(CompteRenduAffaire(point_id=p.id, ticket_id=t.id, etat_cible=cible))
    session.commit()


def _demandes(session: Session) -> dict[str, str]:
    lignes = session.exec(select(SyntheseAffaire, Ticket).join(Ticket)).all()
    return {t.numero: s.statut for s, t in lignes}


def test_seules_les_closes_d_un_point_valide_sans_synthese_sont_inscrites(session: Session):
    question = _affaire(session, "Q")
    nuisance = _affaire(session, "N", categorie="nuisance")
    deja = _affaire(session, "D", categorie="panne")
    session.add(SyntheseAffaire(ticket_id=deja.id, statut=VALIDEE, cloture_le=CLOTURE))
    ouverte = _affaire(session, "O", statut="en_cours")
    rouverte = _affaire(session, "R", statut="en_cours")  # close au point, rouverte depuis
    _point(
        session,
        VALIDE,
        [(question, "résolu"), (nuisance, "résolu"), (deja, "résolu"), (ouverte, None)]
        + [(rouverte, "résolu")],
    )
    hors_point = _affaire(session, "H")
    _point(session, "a_valider", [(hors_point, "résolu")])

    _jouer(session)
    assert _demandes(session) == {"Q": A_PRODUIRE, "N": A_PRODUIRE, "D": VALIDEE}
    (q,) = session.exec(select(SyntheseAffaire).where(SyntheseAffaire.ticket_id == question.id))
    assert q.cloture_le == CLOTURE

    _jouer(session)  # rejouée : rien de plus
    assert len(session.exec(select(SyntheseAffaire)).all()) == 3
