"""L'ÉDITION d'une Suite corrige toutes ses sections — et d'abord son Suivi.

## La demande (01/10/2026, à l'écran)

> « l'édition d'une suite doit permettre de modifier tous les sections
>   éditables et surtout le suivi »

Arbitré : **corriger l'entrée** — même date, même auteur ; l'affaire suit
seulement si c'est sa dernière transition (`app/utils/suivi_fil.py`). La
Diffusion reste absente : une correction ne renvoie rien.

🔴 Le risque couvert est double, et symétrique : qu'une correction ancienne
défasse un état récent, et qu'une correction de TEXTE touche au Suivi. Les deux
se vérifient en relisant la BASE (`standards/04` §14).
"""

from __future__ import annotations

import inspect
import json
import uuid
from datetime import datetime, timedelta

import pytest
from fastapi import BackgroundTasks, HTTPException
from sqlmodel import Session, select

from app.database import engine
from app.models.core import Ticket, TicketEvolution
from app.routers.tickets.evolutions import get_evolutions, update_evolution
from app.routers.tickets.lot import LotDeVisites, creer_visites_en_lot
from app.routers.tickets.mise_a_jour import update_ticket
from app.schemas import TicketEvolutionUpdate, TicketUpdate
from tests.aides_fil import cs, nettoyer_affaires  # noqa: F401

T0 = datetime(2026, 9, 1, 9, 0)


def _affaire(session: Session, auteur_id: int, statut: str, categorie: str = "panne") -> Ticket:
    t = Ticket(
        numero=f"TK-S{uuid.uuid4().hex[:6]}",
        titre="Porte du hall bloquée",
        description="<p>Elle ne se ferme plus.</p>",
        categorie=categorie,
        statut=statut,
        auteur_id=auteur_id,
        perimetre_cible=json.dumps(["résidence"], ensure_ascii=False),
    )
    session.add(t)
    session.commit()
    session.refresh(t)
    return t


def _entree(session, ticket, auteur_id, rang, ancien=None, nouveau=None) -> TicketEvolution:
    """Une entrée datée à la main : deux `maintenant()` peuvent coïncider."""
    e = TicketEvolution(
        ticket_id=ticket.id,
        type="etat" if nouveau else "commentaire",
        contenu=f"<p>Entrée {rang}</p>",
        ancien_statut=ancien,
        nouveau_statut=nouveau,
        auteur_id=auteur_id,
        cree_le=T0 + timedelta(hours=rang),
    )
    session.add(e)
    session.commit()
    session.refresh(e)
    return e


def _corriger(session, cs, ticket, evol, **champs):
    lu = update_evolution(
        ticket.id, evol.id, TicketEvolutionUpdate(**champs), session=session, user=cs
    )
    session.expire_all()
    return lu


def _crayon_du_titre(session, cs, ticket, statut: str) -> None:
    """L'état posé HORS du fil : le `PATCH` de l'affaire écrit une correction, pas
    une transition (`test_correction_pas_transition.py`)."""
    update_ticket(
        ticket.id, TicketUpdate(statut=statut), BackgroundTasks(), session=session, user=cs
    )
    session.expire_all()


def _nb(session, ticket) -> int:
    return len(
        session.exec(select(TicketEvolution).where(TicketEvolution.ticket_id == ticket.id)).all()
    )


def test_corriger_la_derniere_transition_change_l_affaire_sans_ajouter_d_etape(cs):
    with Session(engine) as session:
        t = _affaire(session, cs.id, "en_cours")
        try:
            e = _entree(session, t, cs.id, 1, "ouvert", "en_cours")
            _corriger(session, cs, t, e, type="etat", nouveau_statut="résolu")
            e, t = session.get(TicketEvolution, e.id), session.get(Ticket, t.id)
            assert (e.type, e.ancien_statut, e.nouveau_statut) == ("etat", "ouvert", "résolu")
            assert t.statut == "résolu"
            #  La clôture est datée de la Suite, pas de la correction.
            assert t.ferme_le == e.cree_le
            assert _nb(session, t) == 1, "Une correction ne doit ajouter aucune étape au fil."
        finally:
            nettoyer_affaires(session, t.id)


def test_revenir_a_l_etat_d_avant_ramene_la_suite_a_un_commentaire(cs):
    with Session(engine) as session:
        t = _affaire(session, cs.id, "en_cours")
        try:
            e = _entree(session, t, cs.id, 1, "ouvert", "en_cours")
            _corriger(session, cs, t, e, type="etat", nouveau_statut="ouvert")
            e, t = session.get(TicketEvolution, e.id), session.get(Ticket, t.id)
            assert (e.type, e.ancien_statut, e.nouveau_statut) == ("commentaire", None, None)
            assert t.statut == "ouvert"
        finally:
            nettoyer_affaires(session, t.id)


def test_une_correction_ancienne_ne_defait_pas_un_etat_recent(cs):
    with Session(engine) as session:
        t = _affaire(session, cs.id, "résolu")
        try:
            vieille = _entree(session, t, cs.id, 1, "ouvert", "en_cours")
            _entree(session, t, cs.id, 2, "en_cours", "résolu")
            _corriger(session, cs, t, vieille, type="etat", nouveau_statut="annulé")
            assert session.get(TicketEvolution, vieille.id).nouveau_statut == "annulé"
            assert session.get(Ticket, t.id).statut == "résolu"
        finally:
            nettoyer_affaires(session, t.id)


def test_un_commentaire_peut_devenir_la_transition_qu_il_aurait_du_etre(cs):
    with Session(engine) as session:
        t = _affaire(session, cs.id, "ouvert")
        try:
            e = _entree(session, t, cs.id, 1)
            _corriger(session, cs, t, e, type="etat", nouveau_statut="en_cours")
            e = session.get(TicketEvolution, e.id)
            assert (e.type, e.ancien_statut, e.nouveau_statut) == ("etat", "ouvert", "en_cours")
            assert session.get(Ticket, t.id).statut == "en_cours"
        finally:
            nettoyer_affaires(session, t.id)


def test_corriger_le_texte_seul_ne_touche_pas_au_suivi(cs):
    """Sans `type`, la Suite garde le sien — le cas de l'actualité, sans Suivi."""
    with Session(engine) as session:
        t = _affaire(session, cs.id, "en_cours")
        try:
            e = _entree(session, t, cs.id, 1, "ouvert", "en_cours")
            _corriger(session, cs, t, e, contenu="<p>Corrigé</p>")
            e = session.get(TicketEvolution, e.id)
            assert (e.type, e.nouveau_statut, e.contenu) == ("etat", "en_cours", "<p>Corrigé</p>")
            assert session.get(Ticket, t.id).statut == "en_cours"
        finally:
            nettoyer_affaires(session, t.id)


def test_une_actualite_n_a_pas_de_suivi_a_corriger(cs):
    with Session(engine) as session:
        t = _affaire(session, cs.id, "publie", categorie="actualite")
        try:
            e = _entree(session, t, cs.id, 1)
            with pytest.raises(HTTPException) as refus:
                _corriger(session, cs, t, e, type="etat", nouveau_statut="résolu")
            assert refus.value.status_code == 422
        finally:
            nettoyer_affaires(session, t.id)


def test_les_sections_de_la_suite_se_corrigent_aussi(cs):
    """Mise en avant et Destinataires : la correction les pose comme l'ajout."""
    with Session(engine) as session:
        t = _affaire(session, cs.id, "ouvert")
        try:
            e = _entree(session, t, cs.id, 1)
            _corriger(session, cs, t, e, urgente=True, public_cible=["locataires"])
            t, e = session.get(Ticket, t.id), session.get(TicketEvolution, e.id)
            assert str(t.priorite).endswith("haute")
            assert json.loads(t.public_cible) == ["locataires"]
            #  Les droits valent pour tout le fil, et la Suite le dit.
            assert "<em>" in (e.contenu or "")
        finally:
            nettoyer_affaires(session, t.id)


def test_le_fil_livre_l_etat_d_avant_chaque_entree(cs):
    """L'écran n'en a pas de copie : c'est le serveur qui le calcule."""
    with Session(engine) as session:
        t = _affaire(session, cs.id, "résolu")
        try:
            c = _entree(session, t, cs.id, 1)
            e = _entree(session, t, cs.id, 2, "ouvert", "résolu")
            lus = {x.id: x.statut_avant for x in get_evolutions(t.id, session=session, user=cs)}
            assert lus == {c.id: "ouvert", e.id: "ouvert"}
        finally:
            nettoyer_affaires(session, t.id)


def test_la_correction_ne_diffuse_rien():
    """La Diffusion est absente en correction : le schéma n'en porte aucun canal."""
    champs = set(TicketEvolutionUpdate.model_fields)
    assert not champs & {"partager_whatsapp", "envoyer_syndic", "envoyer_cs", "email_externe"}
    #  …et la route ne reçoit pas de tâches de fond : rien ne peut partir après elle.
    assert "background_tasks" not in inspect.signature(update_evolution).parameters


def test_la_regle_pure_du_suivi_corrige():
    """Les trois règles de `suivi_fil` — leurs cas contre-intuitifs y sont écrits."""
    from app.utils.suivi_fil import _selftest

    _selftest()


# ── #2715 : l'état posé hors du fil, et ce que l'affaire fait de la correction ──


def test_la_derniere_suite_corrigee_l_emporte_sur_l_etat_pose_au_crayon(cs):
    """Le cas du ticket (TK-E00066) : « Chez le prestataire » posé par le crayon du
    titre, la dernière Suite corrigée en « Résolu » — l'affaire suit, et le dit."""
    with Session(engine) as session:
        t = _affaire(session, cs.id, "en_cours")
        try:
            e = _entree(session, t, cs.id, 1, "ouvert", "en_cours")
            _crayon_du_titre(session, cs, t, "chez_prestataire")
            lu = _corriger(session, cs, t, e, type="etat", nouveau_statut="résolu")
            e, t = session.get(TicketEvolution, e.id), session.get(Ticket, t.id)
            assert (e.ancien_statut, e.nouveau_statut) == ("ouvert", "résolu")
            assert t.statut == "résolu" and t.ferme_le == e.cree_le
            assert (lu.affaire_suivie, lu.affaire_suivie_libelle, lu.etat_propose) == (
                True,
                "",
                None,
            )
        finally:
            nettoyer_affaires(session, t.id)


def test_une_suite_qui_n_est_pas_la_derniere_n_ecrase_rien_et_le_dit(cs):
    """🔴 Ne pas écraser un état plus récent reste garanti — mais plus en silence."""
    with Session(engine) as session:
        t = _affaire(session, cs.id, "résolu")
        try:
            vieille = _entree(session, t, cs.id, 1, "ouvert", "en_cours")
            _entree(session, t, cs.id, 2, "en_cours", "résolu")
            lu = _corriger(session, cs, t, vieille, type="etat", nouveau_statut="annulé")
            assert session.get(Ticket, t.id).statut == "résolu"
            assert lu.affaire_suivie is False
            assert lu.etat_propose == "annulé" and lu.etat_propose_libelle
            assert "« Résolu »" in lu.affaire_suivie_libelle
            assert "Suite plus récente" in lu.affaire_suivie_libelle
        finally:
            nettoyer_affaires(session, t.id)


def test_ramenee_a_un_commentaire_la_derniere_suite_ne_restaure_pas_l_etat_ancien(cs):
    """L'état réel posé au crayon est le plus récent : l'état d'avant du fil ne
    l'écrase pas, et l'écran propose de l'appliquer."""
    with Session(engine) as session:
        t = _affaire(session, cs.id, "en_cours")
        try:
            e = _entree(session, t, cs.id, 1, "ouvert", "en_cours")
            _crayon_du_titre(session, cs, t, "chez_prestataire")
            lu = _corriger(session, cs, t, e, type="etat", nouveau_statut="ouvert")
            assert session.get(TicketEvolution, e.id).type == "commentaire"
            assert session.get(Ticket, t.id).statut == "chez_prestataire"
            assert (lu.affaire_suivie, lu.etat_propose) == (False, "ouvert")
            assert "hors de l'Historique" in lu.affaire_suivie_libelle
        finally:
            nettoyer_affaires(session, t.id)


def test_une_visite_creee_en_lot_suit_la_correction_de_sa_suite(cs):
    """La création en lot pose « Chez le prestataire » sans Suite (`lot.py`)."""
    with Session(engine) as session:
        creer_visites_en_lot(
            LotDeVisites(
                affaires=[
                    {
                        "titre": f"Visite {uuid.uuid4().hex[:6]}",
                        "debut": datetime(2027, 1, 15, 9, 0),
                        "perimetre_cible": ["résidence"],
                    }
                ]
            ),
            session=session,
            user=cs,
        )
        t = session.exec(
            select(Ticket).where(Ticket.auteur_id == cs.id).order_by(Ticket.id.desc())
        ).first()
        try:
            assert t.statut == "chez_prestataire"
            e = _entree(session, t, cs.id, 1)
            lu = _corriger(session, cs, t, e, type="etat", nouveau_statut="résolu")
            e = session.get(TicketEvolution, e.id)
            assert (e.ancien_statut, e.nouveau_statut) == ("chez_prestataire", "résolu")
            assert session.get(Ticket, t.id).statut == "résolu"
            assert lu.affaire_suivie is True
        finally:
            nettoyer_affaires(session, t.id)


def test_le_fil_ne_sert_pas_d_issue_hors_de_la_correction(cs):
    """`affaire_suivie` ne parle que de la correction du Suivi : `None` ailleurs."""
    with Session(engine) as session:
        t = _affaire(session, cs.id, "en_cours")
        try:
            e = _entree(session, t, cs.id, 1, "ouvert", "en_cours")
            assert _corriger(session, cs, t, e, contenu="<p>Texte</p>").affaire_suivie is None
            lus = get_evolutions(t.id, session=session, user=cs)
            assert [x.affaire_suivie for x in lus] == [None]
        finally:
            nettoyer_affaires(session, t.id)
