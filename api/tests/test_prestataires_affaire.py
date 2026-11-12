"""Une affaire porte PLUSIEURS prestataires (#2704, contrat de coprofirst-ios#181).

Les dix arbitrages du ticket (12/11/2026) se jouent ici par les vraies routes :
création, correction, Suite, création en lot, lecture seule et en liste.

🔒 Le garde-fou qui compte pour le retour arrière : `ticket.prestataire_id` est le
PREMIER de la liste après chaque écriture (`test_la_colonne_est_le_premier_…`).
Une version antérieure du code ne lit que la colonne.
"""

from __future__ import annotations

import pytest
from fastapi import HTTPException
from sqlmodel import select

from app.models.core import RoleUtilisateur, Ticket, TicketEvolution
from app.models.tickets import TicketPrestataire
from app.routers.tickets import crud
from app.routers.tickets.lot import LotDeVisites, VisiteDuLot, creer_visites_en_lot
from app.schemas import TicketUpdate
from app.utils import horloge
from app.utils.prestataires_affaire import historique, liste_effective, prestataires_de
from tests.aides_affaire import (  # noqa: F401
    _compte,
    _contrat,
    _corriger,
    _creer,
    _prestataire,
    _suite,
    session,
)

CS = RoleUtilisateur.conseil_syndical


def _trois(session):
    return [_prestataire(session).id for _ in range(3)]


def _ids(lu) -> list[int]:
    return [p.id for p in lu.prestataires]


def _colonne_et_lignes(session, ticket_id) -> tuple:
    session.expire_all()
    t = session.get(Ticket, ticket_id)
    lignes = session.exec(
        select(TicketPrestataire.prestataire_id)
        .where(TicketPrestataire.ticket_id == ticket_id)
        .order_by(TicketPrestataire.rang)
    ).all()
    return t.prestataire_id, list(lignes)


# ── La règle pure : la colonne mène ─────────────────────────────────────────


def test_liste_effective_la_colonne_mene():
    assert liste_effective(None, [1, 2]) == []
    assert liste_effective(1, []) == [1]
    assert liste_effective(1, [1, 2, 3]) == [1, 2, 3]
    #  Une version antérieure a remplacé l'intervenant pendant un retour arrière :
    #  sa décision vaut celle d'un client ancien — le premier est remplacé (Q2).
    assert liste_effective(9, [1, 2, 3]) == [9, 2, 3]
    assert liste_effective(2, [1, 2, 3]) == [2, 3]


# ── Compatibilité ascendante, sur la route (critères a à e) ─────────────────


def test_a_un_client_qui_n_envoie_que_prestataire_id_cree_une_affaire_a_un_prestataire(session):
    cs = _compte(session, role=CS)
    p = _prestataire(session)
    lu = _creer(session, cs, categorie="panne", prestataire_id=p.id)
    assert _ids(lu) == [p.id]
    assert (lu.prestataire_id, lu.prestataire_nom) == (p.id, p.nom)


def test_b_corriger_le_titre_en_renvoyant_le_premier_ne_retire_personne(session):
    cs = _compte(session, role=CS)
    ids = _trois(session)
    t = _creer(session, cs, categorie="panne", prestataire_ids=ids)
    lu = _corriger(session, cs, t.id, titre="Titre corrigé", prestataire_id=ids[0])
    assert _ids(lu) == ids, "un client ancien a effacé les autres prestataires"


def test_b_bis_un_client_ancien_qui_change_l_intervenant_remplace_le_premier(session):
    cs = _compte(session, role=CS)
    ids = _trois(session)
    autre = _prestataire(session).id
    t = _creer(session, cs, categorie="panne", prestataire_ids=ids)
    lu = _corriger(session, cs, t.id, prestataire_id=autre)
    assert _ids(lu) == [autre, ids[1], ids[2]]


def test_c_prestataire_id_null_vide_la_liste(session):
    cs = _compte(session, role=CS)
    t = _creer(session, cs, categorie="panne", prestataire_ids=_trois(session))
    lu = _corriger(session, cs, t.id, prestataire_id=None)
    assert (_ids(lu), lu.prestataire_id, lu.prestataire_nom) == ([], None, None)
    assert _colonne_et_lignes(session, t.id) == (None, [])


def test_d_une_lecture_garde_prestataire_id_et_nom_egaux_au_premier(session):
    cs = _compte(session, role=CS)
    ids = _trois(session)
    t = _creer(session, cs, categorie="panne", prestataire_ids=ids)
    for lu in (
        crud.get_ticket(t.id, session=session, user=cs),
        next(x for x in crud.list_tickets(session=session, user=cs) if x.id == t.id),
    ):
        assert _ids(lu) == ids, "l'ordre de saisie n'est pas rendu"
        assert lu.prestataire_id == ids[0]
        assert lu.prestataire_nom == lu.prestataires[0].nom


@pytest.mark.parametrize("cas", ["second_annonce_premier", "liste_vide_et_un_premier"])
def test_e_prestataire_ids_et_prestataire_id_incoherents_sont_refuses(session, cas):
    cs = _compte(session, role=CS)
    ids = _trois(session)
    corps = (
        {"prestataire_ids": ids, "prestataire_id": ids[1]}
        if cas == "second_annonce_premier"
        else {"prestataire_ids": [], "prestataire_id": ids[0]}
    )
    with pytest.raises(HTTPException) as refus:
        _creer(session, cs, categorie="panne", **corps)
    assert refus.value.status_code == 422


def test_e_bis_les_deux_coherents_passent(session):
    cs = _compte(session, role=CS)
    ids = _trois(session)
    lu = _creer(session, cs, categorie="panne", prestataire_ids=ids, prestataire_id=ids[0])
    assert _ids(lu) == ids


# ── 🔒 La colonne est le premier, après chaque écriture ─────────────────────


def test_la_colonne_est_le_premier_apres_chaque_chemin_d_ecriture(session):
    """Création, correction, Suite du conseil, création en lot : la colonne que lit
    la version précédente du code dit toujours le premier de la liste (#1757)."""
    cs = _compte(session, role=CS)
    a, b, c = _trois(session)
    ecarts = []

    t = _creer(session, cs, categorie="panne", prestataire_ids=[b, a])
    if _colonne_et_lignes(session, t.id) != (b, [b, a]):
        ecarts.append(f"création : {_colonne_et_lignes(session, t.id)}")
    _corriger(session, cs, t.id, prestataire_ids=[c, b])
    if _colonne_et_lignes(session, t.id) != (c, [c, b]):
        ecarts.append(f"correction : {_colonne_et_lignes(session, t.id)}")
    _suite(session, cs, t.id, prestataire_ids=[a, c, b])
    if _colonne_et_lignes(session, t.id) != (a, [a, c, b]):
        ecarts.append(f"Suite : {_colonne_et_lignes(session, t.id)}")

    creer_visites_en_lot(
        LotDeVisites(
            affaires=[
                VisiteDuLot(titre="Visite", debut=horloge.maintenant(), prestataire_ids=[c, a])
            ]
        ),
        session=session,
        user=cs,
    )
    visite = session.exec(select(Ticket).order_by(Ticket.id.desc())).first()
    if _colonne_et_lignes(session, visite.id) != (c, [c, a]):
        ecarts.append(f"lot : {_colonne_et_lignes(session, visite.id)}")
    assert not ecarts, "La colonne n'est plus le premier :\n" + "\n".join(ecarts)


def test_le_lot_accepte_encore_un_seul_prestataire_id(session):
    cs = _compte(session, role=CS)
    p = _prestataire(session)
    creer_visites_en_lot(
        LotDeVisites(
            affaires=[VisiteDuLot(titre="Visite", debut=horloge.maintenant(), prestataire_id=p.id)]
        ),
        session=session,
        user=cs,
    )
    visite = session.exec(select(Ticket).order_by(Ticket.id.desc())).first()
    assert _colonne_et_lignes(session, visite.id) == (p.id, [p.id])


# ── Les règles d'écriture, étendues à la liste ──────────────────────────────


def test_un_resident_ne_designe_pas_de_prestataires(session):
    resident = _compte(session)
    lu = _creer(session, resident, categorie="panne", prestataire_ids=_trois(session))
    assert _ids(lu) == []


def test_hors_du_bati_la_liste_est_videe_et_l_historique_le_dit(session):
    from app.utils.intervenant import appliquer_intervenant

    cs = _compte(session, role=CS)
    t = _creer(session, cs, categorie="panne", prestataire_ids=_trois(session))
    lu = _corriger(session, cs, t.id, categorie="question")
    assert _ids(lu) == [] and _colonne_et_lignes(session, t.id) == (None, [])
    #  La phrase, au pluriel : celle que la Suite et la notification écrivent.
    t = _creer(session, cs, categorie="panne", prestataire_ids=_trois(session))
    ligne = session.get(Ticket, t.id)
    ligne.categorie = "question"
    lignes = appliquer_intervenant(ligne, TicketUpdate(), session, est_cs=True)
    assert "Intervenants effacés" in lignes


def test_un_identifiant_inconnu_est_404_un_doublon_422(session):
    cs = _compte(session, role=CS)
    p = _prestataire(session)
    with pytest.raises(HTTPException) as inconnu:
        _creer(session, cs, categorie="panne", prestataire_ids=[p.id, 999_999])
    assert inconnu.value.status_code == 404
    with pytest.raises(HTTPException) as doublon:
        _creer(session, cs, categorie="panne", prestataire_ids=[p.id, p.id])
    assert doublon.value.status_code == 422


def test_un_archive_ne_s_ajoute_pas_mais_reste_s_il_y_etait(session):
    cs = _compte(session, role=CS)
    a, b = _prestataire(session), _prestataire(session)
    t = _creer(session, cs, categorie="panne", prestataire_ids=[a.id])
    a.actif = False
    b.actif = False
    session.add_all([a, b])
    session.commit()
    #  Déjà présent : il reste, et la liste se réordonne autour de lui.
    c = _prestataire(session)
    assert _ids(_corriger(session, cs, t.id, prestataire_ids=[c.id, a.id])) == [c.id, a.id]
    with pytest.raises(HTTPException) as refus:
        _corriger(session, cs, t.id, prestataire_ids=[c.id, a.id, b.id])
    assert refus.value.status_code == 422


def test_le_contrat_d_un_second_prestataire_cadre_l_intervention(session):
    cs = _compte(session, role=CS)
    a, b = _prestataire(session), _prestataire(session)
    contrat = _contrat(session, b)
    lu = _creer(
        session, cs, categorie="entretien", prestataire_ids=[a.id, b.id], contrat_id=contrat.id
    )
    assert lu.contrat_id == contrat.id
    #  Son prestataire quitte la liste : le contrat ne cadre plus rien (Q4).
    lu = _corriger(session, cs, lu.id, prestataire_ids=[a.id])
    assert lu.contrat_id is None


def test_supprimer_l_affaire_retire_ses_lignes(session):
    admin = _compte(session, role=RoleUtilisateur.admin)
    t = _creer(session, admin, categorie="panne", prestataire_ids=_trois(session))
    crud.delete_ticket(t.id, session=session, _=admin)
    assert not session.exec(
        select(TicketPrestataire).where(TicketPrestataire.ticket_id == t.id)
    ).all()


# ── L'historique (Q5) ───────────────────────────────────────────────────────


def test_historique_ajout_retrait_remplacement_ordre(session):
    a, b, c = (_prestataire(session) for _ in range(3))
    assert historique(session, [], [a.id]) == [f"Prestataire ajouté : {a.nom}"]
    assert historique(session, [a.id, b.id], [a.id]) == [f"Prestataire retiré : {b.nom}"]
    assert historique(session, [a.id], [c.id]) == [
        f"Prestataire ajouté : {c.nom}",
        f"Prestataire retiré : {a.nom}",
    ]
    assert historique(session, [a.id, b.id], [b.id, a.id]) == ["Nouvel ordre des prestataires"]
    assert historique(session, [], [a.id, b.id]) == [f"Prestataires ajoutés : {a.nom}, {b.nom}"]


def test_la_suite_du_conseil_ecrit_l_historique_au_fil(session):
    cs = _compte(session, role=CS)
    a, b = _prestataire(session), _prestataire(session)
    t = _creer(session, cs, categorie="panne", prestataire_ids=[a.id])
    _suite(session, cs, t.id, prestataire_ids=[b.id, a.id])
    contenus = " ".join(
        c or ""
        for c in session.exec(
            select(TicketEvolution.contenu).where(TicketEvolution.ticket_id == t.id)
        ).all()
    )
    assert f"Prestataire ajouté : {b.nom}" in contenus


# ── Le droit servi (Q1) ─────────────────────────────────────────────────────


@pytest.mark.parametrize(
    "role, categorie, statut, attendu",
    [
        ("auteur", "panne", None, False),
        ("conseil", "panne", None, True),
        ("admin", "panne", None, True),
        ("conseil", "panne", "résolu", False),
        ("conseil", "question", None, False),
    ],
)
def test_peut_changer_prestataires(session, role, categorie, statut, attendu):
    auteur = _compte(session)
    lecteur = {
        "auteur": auteur,
        "conseil": _compte(session, role=CS),
        "admin": _compte(session, role=RoleUtilisateur.admin),
    }[role]
    t = _creer(session, auteur, categorie=categorie)
    if statut:
        _corriger(session, _compte(session, role=CS), t.id, statut=statut)
    lu = crud.get_ticket(t.id, session=session, user=lecteur)
    assert lu.peut_changer_prestataires is attendu
    if attendu:
        #  Servi, le geste passe par la route : la liste change vraiment.
        p = _prestataire(session)
        assert _ids(_corriger(session, lecteur, t.id, prestataire_ids=[p.id])) == [p.id]


def test_un_resident_qui_envoie_la_liste_ne_change_rien(session):
    """Non servi au résident : la route l'ignore, comme l'intervenant d'avant."""
    auteur = _compte(session)
    t = _creer(session, auteur, categorie="panne")
    lu = _corriger(session, auteur, t.id, prestataire_ids=[_prestataire(session).id])
    assert _ids(lu) == [] and lu.peut_changer_prestataires is False


# ── Une lecture après un retour arrière ─────────────────────────────────────


def test_une_version_anterieure_qui_change_la_colonne_remplace_le_premier(session):
    """Le code d'avant n'écrit que la colonne : à la lecture, il a remplacé le premier."""
    cs = _compte(session, role=CS)
    a, b, c, d = (_prestataire(session).id for _ in range(4))
    t = _creer(session, cs, categorie="panne", prestataire_ids=[a, b, c])
    ligne = session.get(Ticket, t.id)
    ligne.prestataire_id = d  # ce qu'écrirait la v3.89.0
    session.add(ligne)
    session.commit()
    assert prestataires_de(session, ligne) == [d, b, c]
    assert _ids(crud.get_ticket(t.id, session=session, user=cs)) == [d, b, c]


def test_aucune_requete_par_affaire_dans_la_liste(session):
    """La liste lit les lignes de toutes ses affaires en une requête (lecture groupée)."""
    from sqlalchemy import event

    cs = _compte(session, role=CS)
    for _ in range(4):
        _creer(session, cs, categorie="panne", prestataire_ids=_trois(session))
    session.expire_all()
    vues: list[str] = []
    moteur = session.get_bind()

    def compter(conn, curseur, requete, *args):
        if "ticket_prestataire" in requete:
            vues.append(requete)

    event.listen(moteur, "before_cursor_execute", compter)
    try:
        crud.list_tickets(session=session, user=cs)
    finally:
        event.remove(moteur, "before_cursor_execute", compter)
    assert len(vues) == 1, f"{len(vues)} requêtes sur ticket_prestataire pour une liste"


def test_cas_zero_une_affaire_sans_prestataire_n_ecrit_aucune_ligne(session):
    cs = _compte(session, role=CS)
    lu = _creer(session, cs, categorie="panne")
    assert _ids(lu) == [] and _colonne_et_lignes(session, lu.id) == (None, [])


def test_le_carnet_nomme_tous_les_prestataires_en_une_entree(session):
    """Q7 : une entrée par affaire ; l'équipement de repli est la spécialité du PREMIER."""
    from app.utils.carnet_entretien import _entrees_interventions

    cs = _compte(session, role=CS)
    a, b = _prestataire(session), _prestataire(session)
    b.specialite = "plomberie"
    session.add(b)
    session.commit()
    t = _creer(
        session,
        cs,
        categorie="entretien",
        prestataire_ids=[a.id, b.id],
        debut=horloge.maintenant(),
    )
    _corriger(session, cs, t.id, statut="résolu")
    [entree] = [e for e in _entrees_interventions(session, None, cs) if e.ticket_id == t.id]
    assert entree.detail == f"{a.nom}, {b.nom} · hors contrat"
    assert entree.equipement == a.specialite
