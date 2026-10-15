"""Une affaire ARCHIVÉE quitte le fil, comme elle quitte la liste (15/10/2026).

Signalé à l'écran : la réponse d'un copropriétaire avait ouvert une seconde
affaire (TK-973074) au lieu de rejoindre la sienne (TK-749553) — « Rép. : »
n'était pas lu comme un préfixe de réponse (`test_courriel_fil.py`). Le conseil
l'a archivée, et elle est RESTÉE au fil : la rubrique des affaires n'appliquait
pas la règle d'archivage, que celle des actualités applique depuis toujours.

La règle est écrite au fil même (`flux/__init__.py`) : « ce qui s'archive se
retire du fil en s'archivant ». Elle est celle de `utils/archivage`, la seule —
un archivage manuel retire aussitôt, une affaire résolue reste trente jours.
"""

from __future__ import annotations

from datetime import timedelta

from app.models.core import RoleUtilisateur, Ticket
from app.routers.flux import tickets as flux_tickets
from app.routers.flux.commun import ContexteFlux
from app.utils import horloge
from tests.aides_affaire import _compte, _creer, _suite, session  # noqa: F401 — fixture


def _affaire(session, user, titre: str) -> Ticket:
    """Une affaire créée par la vraie route, puis nommée (l'aide impose son titre)."""
    ticket = session.get(Ticket, _creer(session, user, categorie="etude_travaux").id)
    ticket.titre = titre
    session.add(ticket)
    session.commit()
    return ticket


def _titres_du_fil(session, user) -> set[str]:
    maintenant = horloge.maintenant()
    ctx = ContexteFlux(
        session=session, user=user, now=maintenant, since=maintenant - timedelta(days=14)
    )
    return {carte.titre for carte in flux_tickets.collecter(ctx)}


def test_une_affaire_archivee_quitte_le_fil(session):  # noqa: F811
    cs = _compte(session, role=RoleUtilisateur.conseil_syndical)
    gardee = _affaire(session, cs, "Rendez-vous avec Conseil Syndical")
    archivee = _affaire(session, cs, "Rép. : Rendez-vous avec Conseil Syndical")
    for affaire in (gardee, archivee):
        _suite(session, cs, affaire.id)
    assert {gardee.titre, archivee.titre} <= _titres_du_fil(session, cs), (
        "cas zéro : les deux affaires actives doivent être au fil"
    )

    ticket = session.get(Ticket, archivee.id)
    ticket.archive_manuel = True
    session.add(ticket)
    session.commit()

    titres = _titres_du_fil(session, cs)
    assert archivee.titre not in titres, "une affaire archivée par le conseil reste au fil"
    assert gardee.titre in titres


def test_une_affaire_resolue_recemment_reste_au_fil(session):  # noqa: F811
    """La règle n'est pas « fermée = retirée » : « Résolu » s'archive trente jours plus tard."""
    cs = _compte(session, role=RoleUtilisateur.conseil_syndical)
    resolue = _affaire(session, cs, "Porte du hall réparée")
    _suite(session, cs, resolue.id, type="etat", nouveau_statut="résolu")
    assert resolue.titre in _titres_du_fil(session, cs)
