"""Une correction écrite dans le suivi se comprend seule (05/10/2026, signalé à l'écran).

> *« Correction : Description => ça veut dire quoi ? Correction : Date de fin =>
>   y en avait pas, ou elle a été modifiée ? Correction : Documents => le doc X a
>   été ajouté aurait été plus clair ! Correction : Saisi pour => pour qui ? »*

Le suivi nommait le champ touché, jamais le geste ni la valeur. Ces tests lisent
**le fil en base** après un vrai `PATCH` — pas le texte d'une fonction isolée —
et exigent, pour chaque champ, le geste (ajout, modification, suppression) et
la valeur. Le texte exact des phrases est vérifié par `corrections_texte.py
--selftest` ; ici on vérifie qu'ils sont BRANCHÉS.
"""

from __future__ import annotations

from datetime import datetime

import pytest
from sqlmodel import func, select

from app.models.core import RoleUtilisateur, Ticket, TicketEvolution
from app.routers.tickets.commun import evol_read
from app.utils.corrections import est_correction
from app.utils.corrections_texte import NON_CONSERVE
from tests.aides_affaire import _compte, _corriger, _creer, session  # noqa: F401
from tests.aides_purge import purger_ligne


@pytest.fixture(autouse=True)
def _sans_trace(session):
    """Les affaires créées ici repartent : les numéros suivants restent ceux que
    les autres tests attendent (les versements de courriel s'y rattachent par
    l'identifiant du ticket, et ne se nettoient pas)."""
    dernier = session.exec(select(func.max(Ticket.id))).one() or 0
    yield
    for t in session.exec(select(Ticket).where(Ticket.id > dernier)).all():
        for e in session.exec(
            select(TicketEvolution).where(TicketEvolution.ticket_id == t.id)
        ).all():
            session.delete(e)
        purger_ligne(session, Ticket, t.id)
    session.commit()


def _suivi(session, ticket_id) -> str:
    """Le contenu de LA correction écrite — relu en base."""
    evols = session.exec(
        select(TicketEvolution).where(TicketEvolution.ticket_id == ticket_id)
    ).all()
    corrections = [
        e for e in evols if est_correction(e) or (e.contenu or "").startswith("Correction")
    ]
    assert len(corrections) == 1, [e.contenu for e in evols]
    return corrections[0].contenu


def test_la_correction_dit_le_geste_et_la_valeur(session):
    #  L'administrateur : le conseil ne réécrit pas le texte d'une demande déjà
    #  engagée (`update_ticket`), et l'état change dans la même édition.
    cs = _compte(session, role=RoleUtilisateur.admin)
    ticket = _creer(session, cs, categorie="panne")

    # Un changement d'ÉTAT est ce qui inscrit une correction (18/08/2026) ; le
    # reste de l'édition s'y raconte.
    _corriger(
        session,
        cs,
        ticket.id,
        statut="en_cours",
        titre="Rénovation de l'ascenseur",
        description="<p>Travaux du 28 septembre au 16 octobre.</p>",
        #  Dans le dossier des pièces jointes : la racine est écartée depuis #2157.
        fichiers_urls=["/uploads/fichiers/0123456789abcdef0123456789abcdef_annonce-renovation.pdf"],
        fin=datetime(2026, 10, 16),
    )
    contenu = _suivi(session, ticket.id)

    assert "Modification du titre : Visite ascenseur → Rénovation de l'ascenseur" in contenu
    assert "Modification de la description (elle commence désormais par « Travaux du 28" in contenu
    assert "Ajout du document : annonce-renovation.pdf" in contenu
    assert "Ajout de la date de fin : 16/10/2026" in contenu
    for nu in ("Description modifiée", "Pièces jointes modifiées", "Quand modifié"):
        assert nu not in contenu, f"un libellé nu est revenu : « {nu} »"


def test_une_date_modifiee_dit_d_ou_l_on_vient(session):
    cs = _compte(session, role=RoleUtilisateur.conseil_syndical)
    ticket = _creer(session, cs, categorie="panne")
    _corriger(session, cs, ticket.id, fin=datetime(2026, 10, 15))

    _corriger(session, cs, ticket.id, statut="en_cours", fin=datetime(2026, 10, 16))

    assert "Modification de la date de fin : 15/10/2026 → 16/10/2026" in _suivi(session, ticket.id)


def test_saisi_pour_nomme_la_personne(session):
    cs = _compte(session, role=RoleUtilisateur.conseil_syndical)
    pour = _compte(session)
    pour.prenom, pour.nom = "Alix", "Fontaine"
    session.add(pour)
    session.commit()
    ticket = _creer(session, cs, categorie="panne")

    _corriger(session, cs, ticket.id, statut="en_cours", saisi_pour_user_id=pour.id)

    assert "Saisi pour : Alix FONTAINE (auparavant : son auteur)" in _suivi(session, ticket.id)


def test_une_ancienne_correction_ne_pretend_pas_en_dire_plus(session):
    """Le calendrier écrivait « Correction : Date de fin » (avant v2.23.0) : le
    détail n'a jamais été conservé. La lecture le DIT, et ne touche pas la base."""
    cs = _compte(session, role=RoleUtilisateur.conseil_syndical)
    ticket = _creer(session, cs, categorie="panne")
    ancienne = TicketEvolution(
        ticket_id=ticket.id, type="commentaire", contenu="Correction : Date de fin", auteur_id=cs.id
    )
    session.add(ancienne)
    session.commit()
    session.refresh(ancienne)

    lue = evol_read(ancienne, session)

    assert lue.contenu == "Correction : Date de fin" + NON_CONSERVE
    assert session.get(TicketEvolution, ancienne.id).contenu == "Correction : Date de fin"
