"""Le suivi d'une actualité — optionnel, trois états, du conseil seul (10/10/2026).

Arbitrages : un REPÈRE (hors kanban, relances, compteurs), l'archivage d'une
affaire (« Annulé » aussitôt, « Résolu » à trente jours), une case au formulaire
puis l'état par une Suite. La règle vit dans `utils/suivi_actualite` ; ces tests
la prennent par les vraies routes.
"""

from __future__ import annotations

from datetime import datetime, timedelta

import pytest
from fastapi import HTTPException
from sqlmodel import select

from app.models.core import STATUTS_TICKET_ACTIFS, RoleUtilisateur, Ticket, TicketEvolution
from app.models.tickets import StatutTicket
from app.routers.tickets import evolutions
from app.schemas_tickets import TicketEvolutionUpdate
from app.utils.archivage import est_archivable
from app.utils.suivi_actualite import ETATS_SUIVI_ACTUALITE
from tests.aides_affaire import _compte, _corriger, _creer, _suite, session  # noqa: F401

CS = RoleUtilisateur.conseil_syndical


def _actualite(session, cs, **champs):
    return _creer(session, cs, categorie="actualite", **champs)


def _etat(session, user, ticket_id, etat):
    return _suite(session, user, ticket_id, type="etat", nouveau_statut=etat)


# ── La case : décochée par défaut, du conseil seul ─────────────────────────


def test_une_actualite_nait_sans_suivi(session):
    cs = _compte(session, role=CS)
    assert _actualite(session, cs).suivi_actualite is None


def test_cocher_la_case_ouvre_le_suivi(session):
    cs = _compte(session, role=CS)
    lu = _actualite(session, cs, suivre_actualite=True)
    assert lu.suivi_actualite == "ouvert"
    #  🔴 Un repère : l'actualité garde son état, et reste hors des circuits.
    assert lu.statut == StatutTicket.publie.value
    assert lu.statut not in STATUTS_TICKET_ACTIFS
    assert lu.suivi_kanban is False


def test_la_case_se_coche_et_se_decoche_en_correction(session):
    cs = _compte(session, role=CS)
    actu = _actualite(session, cs)
    assert _corriger(session, cs, actu.id, suivre_actualite=True).suivi_actualite == "ouvert"
    _etat(session, cs, actu.id, "résolu")
    #  Recocher une case cochée ne rouvre rien.
    assert _corriger(session, cs, actu.id, suivre_actualite=True).suivi_actualite == "résolu"
    lu = _corriger(session, cs, actu.id, suivre_actualite=False)
    assert lu.suivi_actualite is None
    assert session.get(Ticket, actu.id).ferme_le is None


def test_un_resident_ne_coche_pas_la_case(session):
    """L'auteur d'une affaire devenue actualité la corrige — il n'en active pas le suivi."""
    resident = _compte(session)
    admin = _compte(session, role=RoleUtilisateur.admin)  # le CS ne réécrit pas la demande
    affaire = _creer(session, resident, categorie="panne")
    _corriger(session, admin, affaire.id, categorie="actualite")
    _corriger(session, resident, affaire.id, suivre_actualite=True)
    assert session.get(Ticket, affaire.id).suivi_actualite is None


def test_une_affaire_suivie_n_a_pas_de_suivi_d_actualite(session):
    cs = _compte(session, role=CS)
    assert _creer(session, cs, categorie="panne", suivre_actualite=True).suivi_actualite is None
    actu = _actualite(session, cs, suivre_actualite=True)
    #  Devenue affaire suivie, elle perd le repère : son cycle prend le relais.
    lu = _corriger(session, cs, actu.id, categorie="panne")
    assert lu.suivi_actualite is None and lu.statut == "ouvert"


# ── L'état choisi au formulaire, dès l'ouverture (10/10/2026) ─────────────


def test_une_actualite_s_ouvre_directement_resolue(session):
    """« La résolution est parfois rapide et l'ouverture se fait directement en l'état résolu. »"""
    cs = _compte(session, role=CS)
    lu = _actualite(session, cs, suivre_actualite=True, suivi_actualite="résolu")
    assert lu.suivi_actualite == "résolu"
    assert session.get(Ticket, lu.id).ferme_le is not None
    #  Sans la case, un état ne pose rien : il n'y a pas de suivi à qualifier.
    assert _actualite(session, cs, suivi_actualite="résolu").suivi_actualite is None


def test_l_etat_se_corrige_en_modification_et_le_fil_le_dit(session):
    cs = _compte(session, role=CS)
    actu = _actualite(session, cs, suivre_actualite=True)
    lu = _corriger(session, cs, actu.id, suivi_actualite="annulé")
    assert lu.suivi_actualite == "annulé"
    trace = session.exec(select(TicketEvolution).where(TicketEvolution.ticket_id == actu.id)).one()
    #  Une CORRECTION, pas une transition : pas de jalon de suivi (#431).
    assert trace.type == "commentaire" and "Suivi : Ouvert → Annulé" in trace.contenu
    #  Rouvrir efface la clôture.
    _corriger(session, cs, actu.id, suivi_actualite="ouvert")
    assert session.get(Ticket, actu.id).ferme_le is None


def test_l_etat_saisi_hors_des_trois_est_refuse_et_le_resident_ignore(session):
    resident = _compte(session)
    admin = _compte(session, role=RoleUtilisateur.admin)
    cs = _compte(session, role=CS)
    with pytest.raises(HTTPException) as refus:
        _actualite(session, cs, suivre_actualite=True, suivi_actualite="en_cours")
    assert refus.value.status_code == 422
    affaire = _creer(session, resident, categorie="panne")
    _corriger(session, admin, affaire.id, categorie="actualite", suivre_actualite=True)
    _corriger(session, resident, affaire.id, suivi_actualite="résolu")
    assert session.get(Ticket, affaire.id).suivi_actualite == "ouvert"


# ── L'état : par une Suite, trois valeurs, le conseil seul ────────────────


def test_les_trois_etats():
    assert ETATS_SUIVI_ACTUALITE == ("ouvert", "résolu", "annulé")


def test_une_suite_fait_avancer_le_suivi_et_le_trace_au_fil(session):
    cs = _compte(session, role=CS)
    actu = _actualite(session, cs, suivre_actualite=True)
    _etat(session, cs, actu.id, "résolu")
    t = session.get(Ticket, actu.id)
    assert t.suivi_actualite == "résolu" and t.ferme_le is not None
    assert t.statut == StatutTicket.publie.value  # toujours hors circuit
    trace = session.exec(select(TicketEvolution).where(TicketEvolution.ticket_id == actu.id)).one()
    assert (trace.type, trace.ancien_statut, trace.nouveau_statut) == ("etat", "ouvert", "résolu")
    #  Rouvrir efface la clôture, comme pour une affaire.
    _etat(session, cs, actu.id, "ouvert")
    assert session.get(Ticket, actu.id).ferme_le is None


@pytest.mark.parametrize("etat", ["en_cours", "en_ag", "chez_prestataire", "publie"])
def test_seuls_trois_etats_se_posent(session, etat):
    cs = _compte(session, role=CS)
    actu = _actualite(session, cs, suivre_actualite=True)
    with pytest.raises(HTTPException) as refus:
        _etat(session, cs, actu.id, etat)
    assert refus.value.status_code == 422


def test_sans_suivi_une_suite_ne_pose_aucun_etat(session):
    cs = _compte(session, role=CS)
    actu = _actualite(session, cs)
    with pytest.raises(HTTPException) as refus:
        _etat(session, cs, actu.id, "résolu")
    assert refus.value.status_code == 422


def test_seul_le_conseil_fait_avancer_le_suivi(session):
    resident = _compte(session)
    admin = _compte(session, role=RoleUtilisateur.admin)
    affaire = _creer(session, resident, categorie="panne")
    _corriger(session, admin, affaire.id, categorie="actualite", suivre_actualite=True)
    with pytest.raises(HTTPException) as refus:
        _etat(session, resident, affaire.id, "résolu")
    assert refus.value.status_code == 403


def test_corriger_la_suite_corrige_le_suivi(session):
    cs = _compte(session, role=CS)
    actu = _actualite(session, cs, suivre_actualite=True)
    evol = _etat(session, cs, actu.id, "résolu")
    evolutions.update_evolution(
        actu.id,
        evol.id,
        TicketEvolutionUpdate(type="etat", nouveau_statut="annulé"),
        session=session,
        user=cs,
    )
    assert session.get(Ticket, actu.id).suivi_actualite == "annulé"
    #  Revenir à l'état d'avant en refait un commentaire, et l'actualité suit.
    lu = evolutions.update_evolution(
        actu.id,
        evol.id,
        TicketEvolutionUpdate(type="etat", nouveau_statut="ouvert"),
        session=session,
        user=cs,
    )
    assert lu.type == "commentaire"
    assert session.get(Ticket, actu.id).suivi_actualite == "ouvert"


# ── L'archivage : comme une affaire ────────────────────────────────────────

MAINTENANT = datetime(2026, 10, 10, 12, 0)


def _objet(**champs):
    defauts = {
        "categorie": "actualite",
        "statut": "publie",
        "cree_le": MAINTENANT - timedelta(days=2),
        "mis_a_jour_le": MAINTENANT - timedelta(days=2),
        "ferme_le": None,
        "archive_manuel": False,
        "epingle": False,
        "debut": None,
        "fin": None,
    }
    return type("Objet", (), {**defauts, **champs})()


def _archivee(**champs):
    return est_archivable("ticket", _objet(**champs), maintenant=MAINTENANT)


def test_annule_archive_aussitot():
    assert _archivee(suivi_actualite="annulé")


def test_resolu_archive_trente_jours_apres_la_cloture():
    assert not _archivee(suivi_actualite="résolu", ferme_le=MAINTENANT - timedelta(days=29))
    assert _archivee(suivi_actualite="résolu", ferme_le=MAINTENANT - timedelta(days=30))


def test_ouvert_suit_la_regle_de_l_actualite():
    vieux = MAINTENANT - timedelta(days=31)
    for suivi in (None, "ouvert"):
        assert not _archivee(suivi_actualite=suivi)
        assert _archivee(suivi_actualite=suivi, mis_a_jour_le=vieux, cree_le=vieux)
        #  Et la date d'événement passée la fait sortir, suivie ou non.
        assert _archivee(suivi_actualite=suivi, debut=MAINTENANT - timedelta(days=2))


def test_l_ecran_propose_les_memes_trois_etats():
    """Le miroir d'écran (`#lib/tickets`) ne diverge pas du serveur."""
    import pathlib
    import re

    source = (
        pathlib.Path(__file__).resolve().parents[2] / "front" / "src" / "lib" / "tickets.ts"
    ).read_text(encoding="utf-8")
    trouve = re.search(r"ETATS_SUIVI_ACTUALITE[^=]*=\s*\[([^\]]*)\]", source)
    assert trouve, "`ETATS_SUIVI_ACTUALITE` a quitté `#lib/tickets` : ce contrôle ne lit plus rien"
    assert tuple(re.findall(r"'([^']+)'", trouve.group(1))) == ETATS_SUIVI_ACTUALITE
