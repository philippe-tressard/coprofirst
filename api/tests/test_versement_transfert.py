"""Un transfert de courriel versé par erreur se défait d'un geste (#1482).

Demandé le 30/09/2026 : *« annuler ces ajouts (en une fois), et/ou réaffecter à
une autre affaire, et/ou créer une nouvelle affaire »*. Arbitré le même jour :
celui qui a transféré et l'administrateur ; aucun délai, mais plus dès qu'un
autre a écrit une Suite après le transfert. Resserré le 01/10/2026 : plus dès
qu'une Suite a été écrite, la sienne comprise, ni sous un transfert suivant.

Les scènes sont celles de `test_courriel_transfert.py`, écrites dans
`aides_courriel.py` : le fil du portillon (Jean le 26/09, Jean le 29/09, puis
le syndic), transféré par un membre du conseil.
"""

from __future__ import annotations

import uuid

import pytest
from fastapi import HTTPException
from sqlmodel import select

from app.auth.appartenance import exiger_auteur_du_versement
from app.models.core import StatutTicket, Ticket, TicketEvolution, Utilisateur
from app.models.courriel import FilCourriel, MessageVerse, VersementCourriel
from app.utils import versement_transfert as versements
from app.utils.courriel_ingestion import ACCEPTE
from tests.aides_base import compte
from tests.aides_courriel import (  # noqa: F401 — `monde` et `scene` sont des fixtures
    _affaires,
    _evolutions,
    _fil,
    _transferer,
    monde,
    scene,
)
from tests.aides_purge import purger_ligne


@pytest.fixture()
def lieu(monde):  # noqa: F811
    """La scène, et la purge de ce que ces tests ajoutent : les traces, les
    affaires détachées, les comptes de passage."""
    session, ticket, syndic, cs, objet = monde
    avant = set(session.exec(select(Ticket.id)).all())
    comptes: list[Utilisateur] = []
    yield session, ticket, syndic, cs, objet, comptes
    session.rollback()
    for v in session.exec(select(VersementCourriel).where(VersementCourriel.objet.contains(objet))):
        purger_ligne(session, VersementCourriel, v.id)
    for t in session.exec(select(Ticket)).all():
        if t.id not in avant and t.auteur_id != cs.id:
            for modele in (TicketEvolution, MessageVerse, FilCourriel):
                for ligne in session.exec(select(modele).where(modele.ticket_id == t.id)).all():
                    purger_ligne(session, modele, ligne.id)
            purger_ligne(session, Ticket, t.id)
    for u in comptes:
        purger_ligne(session, Utilisateur, u.id)
    session.commit()


def _dans_le_ticket(session, cs, ticket, syndic, objet):
    """Le fil versé dans l'affaire de la scène par son repère : trois Suites,
    dont la réponse du syndic, qui la fait passer « En cours »."""
    corps = f"{ticket.numero}\n\n" + _fil(syndic.email, objet)
    assert _transferer(session, cs, objet, corps) == ACCEPTE
    session.commit()
    (v,) = versements.versements_de(session, ticket.id)
    return v


def _autre_affaire(session, cs, *, statut=StatutTicket.ouvert) -> Ticket:
    t = Ticket(
        numero=f"TK-{uuid.uuid4().hex[:6]}",
        titre="Autre",
        description="…",
        categorie="panne",
        auteur_id=cs.id,
        statut=statut,
    )
    session.add(t)
    session.commit()
    session.refresh(t)
    return t


def _compte(session, comptes, roles: str) -> Utilisateur:
    u = compte(session, prefixe="u", prenom="U", nom="T", roles_json=roles)
    comptes.append(u)
    return u


# ── La trace ──────────────────────────────────────────────────────────────────


def test_chaque_suite_versee_connait_son_transfert(lieu):
    session, ticket, syndic, cs, objet, _ = lieu
    v = _dans_le_ticket(session, cs, ticket, syndic, objet)

    suites = versements.suites_du(session, v)
    assert len(suites) == 3 and all(s.versement_id == v.id for s in suites)
    assert v.statut_avant == StatutTicket.ouvert.value and v.transfere_par_id == cs.id
    assert (v.premier_nom, v.premier_adresse) == ("Jean Dupont", "jean.dupont@exemple.test")
    assert versements.motif_bloquant(session, v) is None


# ── Annuler ───────────────────────────────────────────────────────────────────


def test_annuler_retire_les_suites_et_rend_le_statut_et_le_fil(lieu):
    session, ticket, syndic, cs, objet, _ = lieu
    v = _dans_le_ticket(session, cs, ticket, syndic, objet)
    session.refresh(ticket)
    assert ticket.statut == StatutTicket.en_cours, "la réponse du syndic l'avait avancée"

    versements.annuler(session, v)
    session.commit()

    session.refresh(ticket)
    assert _evolutions(session, ticket) == []
    assert ticket.statut == StatutTicket.ouvert
    assert session.exec(select(MessageVerse).where(MessageVerse.versement_id == v.id)).all() == []
    assert session.exec(select(FilCourriel).where(FilCourriel.ticket_id == ticket.id)).all() == []
    assert versements.versements_de(session, ticket.id) == []

    #  Plus d'empreinte : le même fil se verse de nouveau, là où on le désigne.
    assert _transferer(session, cs, objet, _fil(syndic.email, objet)) == ACCEPTE


def test_annuler_une_affaire_creee_l_archive_sans_la_supprimer(lieu):
    session, _ticket, syndic, cs, objet, _ = lieu
    _transferer(session, cs, objet, _fil(syndic.email, objet))
    session.commit()
    (affaire,) = _affaires(session, objet)
    (v,) = versements.versements_de(session, affaire.id)
    assert v.affaire_creee

    versements.annuler(session, v)
    session.commit()

    session.refresh(affaire)
    assert affaire.archive_manuel, "archivée — elle reste aux Archives"
    lien = session.exec(select(FilCourriel).where(FilCourriel.ticket_id == affaire.id)).first()
    assert lien is None, "le fil ne suit plus l'affaire annulée"
    assert _transferer(session, cs, objet, _fil(syndic.email, objet)) == ACCEPTE
    assert len(_affaires(session, objet)) == 2, "renvoyé, il ouvre une autre affaire"


# ── Réaffecter ────────────────────────────────────────────────────────────────


def test_reaffecter_deplace_les_suites_et_le_fil_vers_l_autre_affaire(lieu):
    session, ticket, syndic, cs, objet, _ = lieu
    v = _dans_le_ticket(session, cs, ticket, syndic, objet)
    cible = _autre_affaire(session, cs)

    versements.reaffecter(session, v, cible, cs)
    session.commit()

    session.refresh(ticket)
    session.refresh(cible)
    assert _evolutions(session, ticket) == []
    assert ticket.statut == StatutTicket.ouvert, "la source revient à son statut"
    assert len(_evolutions(session, cible)) == 3
    assert cible.statut == StatutTicket.en_cours, "le syndic fait avancer l'affaire qui le reçoit"
    lien = session.exec(select(FilCourriel).where(FilCourriel.cle.is_not(None))).all()
    assert any(f.ticket_id == cible.id for f in lien)
    assert v.ticket_id == cible.id and v.statut_avant == StatutTicket.ouvert.value


def test_reaffecter_ne_double_pas_ce_que_la_cible_a_deja(lieu):
    session, ticket, syndic, cs, objet, _ = lieu
    cible = _autre_affaire(session, cs)
    corps = f"{cible.numero}\n\n" + _fil(syndic.email, objet)
    assert _transferer(session, cs, objet, corps) == ACCEPTE
    session.commit()
    v = _dans_le_ticket(session, cs, ticket, syndic, objet)

    versements.reaffecter(session, v, cible, cs)
    session.commit()

    assert len(_evolutions(session, cible)) == 3, "les trois messages, une seule fois"
    assert _evolutions(session, ticket) == []


def test_une_reponse_du_syndic_deplacee_vers_une_affaire_deja_avancee_reste_un_commentaire(lieu):
    session, ticket, syndic, cs, objet, _ = lieu
    v = _dans_le_ticket(session, cs, ticket, syndic, objet)
    cible = _autre_affaire(session, cs, statut=StatutTicket.en_cours)

    versements.reaffecter(session, v, cible, cs)
    session.commit()

    assert all(s.type == "commentaire" for s in _evolutions(session, cible))


def test_reaffecter_une_affaire_creee_y_verse_aussi_sa_description(lieu):
    session, _ticket, syndic, cs, objet, _ = lieu
    _transferer(session, cs, objet, _fil(syndic.email, objet))
    session.commit()
    (affaire,) = _affaires(session, objet)
    (v,) = versements.versements_de(session, affaire.id)
    cible = _autre_affaire(session, cs)

    versements.reaffecter(session, v, cible, cs)
    session.commit()

    session.refresh(affaire)
    suites = _evolutions(session, cible)
    assert len(suites) == 3, "la description devient la première Suite"
    assert affaire.description in [s.contenu for s in suites]
    assert affaire.archive_manuel


def test_on_ne_reaffecte_ni_vers_une_affaire_close_ni_vers_soi(lieu):
    session, ticket, syndic, cs, objet, _ = lieu
    v = _dans_le_ticket(session, cs, ticket, syndic, objet)
    close = _autre_affaire(session, cs, statut=StatutTicket.résolu)

    for cible in (close, ticket):
        with pytest.raises(HTTPException) as e:
            versements.reaffecter(session, v, cible, cs)
        assert e.value.status_code == 422


# ── Détacher ──────────────────────────────────────────────────────────────────


def test_detacher_cree_une_affaire_decrite_par_le_premier_message(lieu):
    session, ticket, syndic, cs, objet, _ = lieu
    v = _dans_le_ticket(session, cs, ticket, syndic, objet)

    nouvelle = versements.detacher(session, v, cs)
    session.commit()

    session.refresh(ticket)
    assert nouvelle.titre == objet
    assert "portillon" in nouvelle.description.lower()
    assert (nouvelle.saisi_pour_nom, nouvelle.saisi_pour_email) == (
        "Jean Dupont",
        "jean.dupont@exemple.test",
    )
    assert len(_evolutions(session, nouvelle)) == 2, "les deux autres messages"
    assert nouvelle.statut == StatutTicket.en_cours, "le syndic a répondu"
    assert _evolutions(session, ticket) == [] and ticket.statut == StatutTicket.ouvert
    assert v.affaire_creee and v.ticket_id == nouvelle.id


# ── Quand le geste s'éteint ───────────────────────────────────────────────────


def test_une_suite_d_un_AUTRE_apres_le_transfert_eteint_le_geste(lieu):
    session, ticket, syndic, cs, objet, comptes = lieu
    v = _dans_le_ticket(session, cs, ticket, syndic, objet)
    autre = _compte(session, comptes, "conseil_syndical")
    session.add(
        TicketEvolution(ticket_id=ticket.id, type="commentaire", contenu="Vu", auteur_id=autre.id)
    )
    session.commit()

    assert "depuis ce transfert" in versements.motif_bloquant(session, v)
    with pytest.raises(HTTPException) as e:
        versements.annuler(session, v)
    assert e.value.status_code == 409


def test_une_suite_de_celui_qui_a_transfere_l_eteint_aussi(lieu):
    """Arbitré le 01/10/2026 : sa réponse s'appuie sur ce qui a été versé.
    L'annulation restait offerte après elle — c'est le défaut signalé."""
    session, ticket, syndic, cs, objet, _ = lieu
    v = _dans_le_ticket(session, cs, ticket, syndic, objet)
    session.add(
        TicketEvolution(ticket_id=ticket.id, type="commentaire", contenu="Noté", auteur_id=cs.id)
    )
    session.commit()

    assert "depuis ce transfert" in versements.motif_bloquant(session, v)


def test_seul_le_transfert_le_plus_recent_se_defait(lieu):
    """Deux transferts du même fil dans une affaire proposaient chacun
    « Annuler » (01/10/2026) : on défait du plus récent au plus ancien."""
    session, ticket, syndic, cs, objet, _ = lieu
    premier = _dans_le_ticket(session, cs, ticket, syndic, objet)
    avant = versements.etat_avant(session, ticket, premier.cle_fil)
    second = versements.ouvrir_versement(session, cs, ticket, avant, objet, creee=False)
    session.add(
        TicketEvolution(
            ticket_id=ticket.id,
            type="commentaire",
            contenu="J'approuve également.",
            auteur_id=cs.id,
            versement_id=second.id,
        )
    )
    session.commit()

    assert "annulez-le d'abord" in versements.motif_bloquant(session, premier)
    assert versements.motif_bloquant(session, second) is None
    versements.annuler(session, second)
    session.commit()
    assert versements.motif_bloquant(session, premier) is None


# ── Valider (13/10/2026) ──────────────────────────────────────────────────────


def test_valider_retire_le_transfert_de_la_liste_et_eteint_les_gestes(lieu):
    """« Il manque Valider ce transfert (si c'est ok et pour faire disparaître
    ces boutons) » : validé, il reste versé, quitte la liste et ne se défait plus."""
    session, ticket, syndic, cs, objet, _ = lieu
    v = _dans_le_ticket(session, cs, ticket, syndic, objet)

    versements.valider(session, v, cs)
    session.commit()

    assert (v.valide_par_id, v.valide_le is not None) == (cs.id, True)
    assert len(_evolutions(session, ticket)) == 3, "les Suites restent versées"
    assert versements.a_proposer(session, ticket.id) == []
    assert versements.motif_bloquant(session, v) == "ce transfert a été validé"
    with pytest.raises(HTTPException) as e:
        versements.annuler(session, v)
    assert e.value.status_code == 409


def test_valider_le_plus_recent_ne_rouvre_pas_le_precedent(lieu):
    """Validé, le transfert suivant reste EN PLACE : le précédent reste bloqué
    sous lui — l'annuler rendrait le lien du fil sous un transfert maintenu."""
    session, ticket, syndic, cs, objet, _ = lieu
    premier = _dans_le_ticket(session, cs, ticket, syndic, objet)
    avant = versements.etat_avant(session, ticket, premier.cle_fil)
    second = versements.ouvrir_versement(session, cs, ticket, avant, objet, creee=False)
    session.add(
        TicketEvolution(
            ticket_id=ticket.id,
            type="commentaire",
            contenu="J'approuve également.",
            auteur_id=cs.id,
            versement_id=second.id,
        )
    )
    session.commit()

    versements.valider(session, second, cs)
    session.commit()

    assert "annulez-le d'abord" in versements.motif_bloquant(session, premier)
    assert [v.id for v in versements.a_proposer(session, ticket.id)] == [premier.id]
    #  Un transfert éteint se valide aussi : c'est ce qui vide la liste.
    versements.valider(session, premier, cs)
    session.commit()
    assert versements.a_proposer(session, ticket.id) == []


def test_un_transfert_annule_ne_se_valide_pas(lieu):
    session, ticket, syndic, cs, objet, _ = lieu
    v = _dans_le_ticket(session, cs, ticket, syndic, objet)
    versements.annuler(session, v)
    session.commit()
    with pytest.raises(HTTPException) as e:
        versements.valider(session, v, cs)
    assert e.value.status_code == 409


def test_la_route_valider_prend_le_droit_d_annuler(lieu):
    """Celui qui a transféré valide ; un autre membre du conseil reçoit 403."""
    from app.routers.tickets.transferts import valider_transfert

    session, ticket, syndic, cs, objet, comptes = lieu
    v = _dans_le_ticket(session, cs, ticket, syndic, objet)
    autre_cs = _compte(session, comptes, "conseil_syndical")

    with pytest.raises(HTTPException) as e:
        valider_transfert(ticket.id, v.id, session=session, user=autre_cs)
    assert e.value.status_code == 403
    assert valider_transfert(ticket.id, v.id, session=session, user=cs).ticket_id == ticket.id
    session.refresh(v)
    assert v.valide_par_id == cs.id


# ── Qui ───────────────────────────────────────────────────────────────────────


def test_seuls_celui_qui_a_transfere_et_l_administrateur_le_defont(lieu):
    session, ticket, syndic, cs, objet, comptes = lieu
    v = _dans_le_ticket(session, cs, ticket, syndic, objet)
    autre_cs = _compte(session, comptes, "conseil_syndical")
    admin = _compte(session, comptes, "admin")

    assert exiger_auteur_du_versement(session, ticket.id, v.id, cs, deplacer=True).id == v.id
    assert exiger_auteur_du_versement(session, ticket.id, v.id, admin, deplacer=True).id == v.id
    with pytest.raises(HTTPException) as e:
        exiger_auteur_du_versement(session, ticket.id, v.id, autre_cs, deplacer=False)
    assert e.value.status_code == 403
    with pytest.raises(HTTPException) as e:
        exiger_auteur_du_versement(session, ticket.id + 10**6, v.id, cs, deplacer=False)
    assert e.value.status_code == 404


def test_un_correspondant_qui_ne_modere_pas_annule_mais_ne_deplace_pas(lieu):
    session, ticket, syndic, cs, objet, _ = lieu
    v = _dans_le_ticket(session, cs, ticket, syndic, objet)
    v.transfere_par_id = syndic.id  # le syndic a transféré dans l'affaire désignée
    session.add(v)
    session.commit()

    assert exiger_auteur_du_versement(session, ticket.id, v.id, syndic, deplacer=False)
    with pytest.raises(HTTPException) as e:
        exiger_auteur_du_versement(session, ticket.id, v.id, syndic, deplacer=True)
    assert e.value.status_code == 403


def _admis(session, ticket, v, user) -> tuple[bool, bool]:
    """(annuler est admis, déplacer est admis) — ce que les gestes répondent."""
    reponses = []
    for deplacer in (False, True):
        try:
            exiger_auteur_du_versement(session, ticket.id, v.id, user, deplacer=deplacer)
        except HTTPException as e:
            assert e.status_code == 403
            reponses.append(False)
        else:
            reponses.append(True)
    return reponses[0], reponses[1]


def _propose(session, ticket, v, user) -> tuple[bool, bool]:
    """(la ligne est proposée, le déplacement est proposé) — ce que l'écran reçoit."""
    from app.routers.tickets.transferts import lister_transferts

    lignes = {t.id: t for t in lister_transferts(ticket.id, session=session, user=user)}
    return v.id in lignes, v.id in lignes and lignes[v.id].peut_deplacer


def test_la_liste_propose_exactement_ce_que_le_geste_admet(lieu):
    """#1551 : la liste filtrait sur sa propre copie de la règle du geste.

    Lecteur par lecteur, ce que `GET …/transferts` propose (la ligne, et
    `peut_deplacer`) est ce que les gestes admettent — y compris le cas limite
    du correspondant qui a transféré sans modérer : il voit la ligne, il peut
    annuler, il ne peut pas déplacer.
    """
    session, ticket, syndic, cs, objet, comptes = lieu
    v = _dans_le_ticket(session, cs, ticket, syndic, objet)
    lecteurs = {
        "celui qui a transféré": cs,
        "administrateur": _compte(session, comptes, "admin"),
        "autre membre du conseil": _compte(session, comptes, "conseil_syndical"),
    }
    attendu = {
        "celui qui a transféré": (True, True),
        "administrateur": (True, True),
        "autre membre du conseil": (False, False),
    }
    for nom, user in lecteurs.items():
        assert _propose(session, ticket, v, user) == _admis(session, ticket, v, user), nom
        assert _admis(session, ticket, v, user) == attendu[nom], nom

    v.transfere_par_id = syndic.id  # un correspondant qui ne modère pas
    session.add(v)
    session.commit()
    assert _propose(session, ticket, v, syndic) == _admis(session, ticket, v, syndic)
    assert _admis(session, ticket, v, syndic) == (True, False)
