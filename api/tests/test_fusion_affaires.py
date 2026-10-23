"""La FUSION d'affaires à la clôture (#1704) — arbitrée le 05/10/2026.

Ce que ce fichier éprouve, dans l'ordre de ce qui coûterait le plus cher :

1. 🔒 aucune fuite : une affaire lue par moins de monde que celle qu'on clôt
   est proposée DÉSACTIVÉE, et l'absorber est refusé ;
2. le conseil fusionne, et lui seul ;
3. l'absorption : Suites marquées et versées à leur date, transitions racontées
   en commentaire, Suite d'ouverture, messages et liens rattachés, absorbée
   close au même état et renvoyant vers la principale — par la Suite comme par
   la correction ;
4. l'absorbée ne reçoit plus de Suite, sort du carnet et des moyennes, et la
   durée de la principale court depuis la plus ancienne ouverture.
"""

from __future__ import annotations

import ast
from datetime import timedelta

import pytest
from fastapi import BackgroundTasks, HTTPException
from sqlmodel import select

from app.models.affaires_liees import AffaireLiee
from app.models.core import RoleUtilisateur, Ticket, TicketEvolution
from app.models.tickets import MessageTicket
from app.routers.tickets import evolutions, messages
from app.routers.tickets.messages_schemas import MessageCreate
from app.routers.tickets.commun import ticket_read
from app.schemas_tickets import TicketEvolutionCreate, TicketEvolutionUpdate
from app.utils.synthese_affaire.production import peut_etre_produite
from app.utils.affaire_absorbee import ouverture_effective
from app.utils.affaires_liees import ajouter_liens, ids_lies
from app.utils.fusion_affaires import MOTIF_LECTEURS, candidates
from app.utils.visibility import ticket_visible
from tests.aides_affaire import _compte, _corriger, _creer, _suite, session  # noqa: F401
from tests.aides_sources import module_app


def _clore(session, user, ticket_id, fusionner=None, statut="résolu"):
    corps = TicketEvolutionCreate(
        type="etat", nouveau_statut=statut, notifier=False, fusionner=fusionner
    )
    return evolutions.add_evolution(ticket_id, corps, BackgroundTasks(), session=session, user=user)


@pytest.fixture()
def trois(session):
    """A (qu'on clôt), B et C liées à A ; un résident auteur de B, le conseil."""
    resident = _compte(session)
    cs = _compte(session, role=RoleUtilisateur.conseil_syndical)
    a = _creer(session, cs, categorie="panne")
    b = _creer(session, resident, categorie="panne")
    c = _creer(session, cs, categorie="panne")
    ajouter_liens(session, session.get(Ticket, a.id), [b.id, c.id], cs)
    session.commit()
    return session, resident, cs, a.id, b.id, c.id


def _fil(session, ticket_id):
    return session.exec(
        select(TicketEvolution)
        .where(TicketEvolution.ticket_id == ticket_id)
        .order_by(TicketEvolution.cree_le)
    ).all()


# ── 1. Aucune fuite ─────────────────────────────────────────────────────────


def test_une_absorbee_lue_par_moins_de_monde_est_desactivee_et_refusee(trois):
    session, _resident, cs, a, b, _c = trois
    secrete = session.get(Ticket, b)
    secrete.confidentiel = True  # son auteur et le conseil seulement
    session.add(secrete)
    session.commit()
    #  Précondition — sans un lecteur de A qui ne lit pas B, rien ne fuirait.
    voisin = _compte(session)
    assert ticket_visible(session.get(Ticket, a), voisin)
    assert not ticket_visible(secrete, voisin)
    verdicts = {x["id"]: x for x in candidates(session, session.get(Ticket, a), cs)}
    assert verdicts[b]["fusionnable"] is False
    assert verdicts[b]["motif"] == MOTIF_LECTEURS
    with pytest.raises(HTTPException) as exc:
        _clore(session, cs, a, fusionner=[b])
    assert exc.value.status_code == 422
    session.rollback()
    assert session.get(Ticket, b).fusionnee_dans_id is None


def test_l_inverse_est_admis_une_principale_plus_fermee_absorbe(trois):
    """Personne ne lit la principale sans lire l'absorbée : rien ne fuit."""
    session, _resident, cs, a, b, _c = trois
    principale = session.get(Ticket, a)
    principale.confidentiel = True
    session.add(principale)
    session.commit()
    _clore(session, cs, a, fusionner=[b])
    assert session.get(Ticket, b).fusionnee_dans_id == a


# ── 2. Le conseil seul ──────────────────────────────────────────────────────


def test_un_resident_qui_clot_ne_fusionne_pas(trois):
    session, resident, _cs, _a, b, c = trois
    ajouter_liens(session, session.get(Ticket, b), [c], _cs)
    session.commit()
    with pytest.raises(HTTPException) as exc:
        _clore(session, resident, b, fusionner=[c])
    assert exc.value.status_code == 403


def test_cas_zero_une_cloture_sans_fusion_ne_touche_a_rien(trois):
    session, _resident, cs, a, b, c = trois
    _clore(session, cs, a)
    assert session.get(Ticket, b).fusionnee_dans_id is None
    assert ids_lies(session, a) == {b, c}


def test_seules_les_liees_ouvertes_sont_proposees(trois):
    session, _resident, cs, a, b, c = trois
    _clore(session, cs, c)
    assert [x["id"] for x in candidates(session, session.get(Ticket, a), cs)] == [b]


def test_une_candidate_porte_la_forme_d_une_affaire_nommee(trois):
    """La fusion depuis la correction (#2173) range le groupe par ancienneté — la
    plus ancienne absorbe : la candidate porte sa date de création, comme toute
    affaire liée (`affaires_liees._lue`), plus son verdict."""
    session, _resident, cs, a, b, _c = trois
    c = candidates(session, session.get(Ticket, a), cs)[0]
    t = session.get(Ticket, c["id"])
    assert c["cree_le"] == t.cree_le
    #  `fusionnee` (#2186) : toujours faux ici — une absorbée n'est jamais candidate.
    assert set(c) == {
        "id",
        "numero",
        "titre",
        "statut",
        "cree_le",
        "fusionnee",
        "fusionnable",
        "motif",
    }


# ── 3. L'absorption ─────────────────────────────────────────────────────────


def test_la_suite_qui_clot_absorbe_les_liees(trois):
    session, resident, cs, a, b, c = trois
    _suite(session, resident, b)  # « Point d'étape. »
    _clore(session, cs, b, statut="en_cours")  # une transition de B, à raconter
    session.add(MessageTicket(ticket_id=b, auteur_id=resident.id, contenu="Photo jointe"))
    autre = _creer(session, cs, categorie="panne")
    ajouter_liens(session, session.get(Ticket, b), [autre.id], cs)
    session.commit()

    _clore(session, cs, a, fusionner=[b, c])

    for x in (b, c):
        absorbee = session.get(Ticket, x)
        assert absorbee.fusionnee_dans_id == a
        assert absorbee.statut == "résolu"
        assert absorbee.ferme_le == session.get(Ticket, a).ferme_le
        #  Il ne lui reste que sa Suite de fusion, qui dit où le suivi se poursuit.
        (reste,) = _fil(session, x)
        assert reste.nouveau_statut == "résolu" and "Fusionnée dans" in reste.contenu
    fil = _fil(session, a)
    contenus = [e.contenu or "" for e in fil]
    b_ = session.get(Ticket, b)
    ouverture = next(e for e in fil if f"Ouverture de {b_.numero}" in (e.contenu or ""))
    assert (ouverture.auteur_id, ouverture.cree_le) == (resident.id, b_.cree_le)
    assert any("Venue de" in t and "Point d'étape." in t for t in contenus)
    #  La transition de B y est RACONTÉE, jamais rejouée comme celle de A.
    racontee = next(e for e in fil if "État : Ouvert →" in (e.contenu or ""))
    assert (racontee.type, racontee.nouveau_statut) == ("commentaire", None)
    assert [e.cree_le for e in fil] == sorted(e.cree_le for e in fil)
    assert "Fusion :" in contenus[-1] or any("🔀 Fusion" in t for t in contenus)
    assert session.exec(select(MessageTicket).where(MessageTicket.ticket_id == a)).all()
    #  Le lien de B vers une tierce affaire passe à A ; celui vers A reste.
    assert autre.id in ids_lies(session, a)
    assert ids_lies(session, b) == {a}
    lue = ticket_read(session.get(Ticket, b), session, cs)
    assert (lue.fusionnee_dans.id, lue.fusionnee) == (a, True)
    assert ticket_read(session.get(Ticket, a), session, cs).fusionnee is False


def test_la_correction_qui_clot_absorbe_aussi(trois):
    session, _resident, cs, a, b, _c = trois
    _corriger(session, cs, a, statut="annulé", fusionner=[b])
    absorbee = session.get(Ticket, b)
    assert (absorbee.fusionnee_dans_id, absorbee.statut) == (a, "annulé")


def test_une_absorbee_ne_recoit_plus_de_suite(trois):
    session, _resident, cs, a, b, _c = trois
    _clore(session, cs, a, fusionner=[b])
    with pytest.raises(HTTPException) as exc:
        _suite(session, cs, b)
    assert exc.value.status_code == 422


def test_une_absorbee_ne_recoit_ni_message_ni_correction_ni_synthese(trois):
    session, _resident, cs, a, b, _c = trois
    _clore(session, cs, a, fusionner=[b])
    absorbee = session.get(Ticket, b)
    assert not peut_etre_produite(absorbee)  # sa principale la couvre
    assert peut_etre_produite(session.get(Ticket, a))
    with pytest.raises(HTTPException) as exc:
        messages.add_message(
            b, MessageCreate(contenu="Encore ?"), BackgroundTasks(), session=session, user=cs
        )
    assert exc.value.status_code == 422
    (fusion,) = _fil(session, b)
    with pytest.raises(HTTPException) as exc:
        evolutions.update_evolution(
            b,
            fusion.id,
            TicketEvolutionUpdate(type="etat", nouveau_statut="ouvert"),
            session=session,
            user=cs,
        )
    assert exc.value.status_code == 422


def test_la_principale_court_depuis_la_plus_ancienne_ouverture(trois):
    session, _resident, cs, a, b, _c = trois
    plus_ancienne = session.get(Ticket, b)
    plus_ancienne.cree_le = plus_ancienne.cree_le - timedelta(days=30)
    session.add(plus_ancienne)
    session.commit()
    _clore(session, cs, a, fusionner=[b])
    assert ouverture_effective(session, session.get(Ticket, a)) == plus_ancienne.cree_le


def test_la_liste_des_liens_ne_garde_pas_de_doublon(trois):
    session, _resident, cs, a, b, c = trois
    ajouter_liens(session, session.get(Ticket, b), [c], cs)
    session.commit()
    _clore(session, cs, a, fusionner=[b])
    paires = session.exec(select(AffaireLiee).where(AffaireLiee.liee_id == c)).all()
    assert len([p for p in paires if p.affaire_id == a]) == 1


# ── 4. 🔒 Chaque lecteur d'affaires closes écarte les absorbées ─────────────

#: Les modules qui COMPTENT des affaires closes — carnet, moyennes, récidive.
#: Une absorbée y compterait deux fois : elle l'est dans sa principale.
LECTEURS_DE_CLOTURES = (
    "utils/carnet_entretien.py",
    "utils/synthese_affaire/agregats.py",
    "utils/synthese_affaire/rassemblement.py",
    "utils/synthese_affaire/recidive.py",
)


def _requetes_de_clotures(source: str):
    """Les `select(Ticket)…` dont le texte vise un état clos."""
    arbre = ast.parse(source)
    for noeud in ast.walk(arbre):
        if isinstance(noeud, ast.Call) and isinstance(noeud.func, ast.Attribute):
            if noeud.func.attr != "where":
                continue
            texte = ast.get_source_segment(source, noeud) or ""
            if "select(Ticket)" in texte and ("résolu" in texte or "STATUTS_TICKET_CLOS" in texte):
                yield texte


def test_chaque_lecteur_de_clotures_ecarte_les_absorbees():
    vues = 0
    for chemin in LECTEURS_DE_CLOTURES:
        source = module_app(chemin).source
        requetes = list(_requetes_de_clotures(source))
        #  Témoin : un module listé qui ne lit plus de clôtures sort de la liste.
        assert requetes, f"{chemin} ne lit plus d'affaires closes : retirez-le de la liste"
        for texte in requetes:
            vues += 1
            assert "pas_absorbee()" in texte, f"{chemin} compte les absorbées :\n{texte}"
    assert vues >= len(LECTEURS_DE_CLOTURES)
