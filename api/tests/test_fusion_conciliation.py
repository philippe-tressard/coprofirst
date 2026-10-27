"""La CONCILIATION d'une fusion refusée pour fuite de lecture (27/10/2026).

La fusion reste refusée quand elle ferait lire à quelqu'un ce qu'il ne lisait pas
(#1704). La conciliation n'ôte pas ce refus : elle le transforme en décision du
conseil, avec le NOM de ceux qu'elle touche. Ce que ce fichier éprouve, dans
l'ordre de ce qui coûterait le plus cher :

1. 🔒 l'invariant tient : sans conciliation le refus demeure ; avec elle, chaque
   personne qui lirait sans avoir lu est confirmée par son nom, ou rien ne part ;
2. `elargir` : l'union des deux, confirmation nominative exacte (409 sinon) ;
3. `restreindre` : ce que les deux affaires avaient en commun ;
4. `inverser` : l'autre affaire absorbe — hors clôture seulement ;
5. une affaire confidentielle ne s'ouvre jamais par conciliation ;
6. la mesure n'écrit rien, et le geste laisse sa trace (Suite + journal).
"""

from __future__ import annotations

import json
import logging

import pytest
from fastapi import BackgroundTasks, HTTPException
from sqlmodel import select

from app.models.core import RoleUtilisateur, StatutUtilisateur, Ticket, TicketEvolution
from app.routers.tickets.fusion import CandidateFusion
from app.schemas_communs import ChoixConciliation
from app.schemas_tickets import TicketEvolutionCreate
from app.routers import suivi_affaires_fusions as suivi_fusions
from app.routers.tickets import evolutions
from app.utils import fusion_en_cours
from app.utils.affaires_liees import ajouter_liens
from app.utils.fusion_affaires import candidates
from app.utils.fusion_conciliation import options
from app.utils.visibility import ticket_visible
from tests.aides_affaire import _compte, _creer, session  # noqa: F401
from tests.aides_base import compte


def _resident(session, batiment_id):
    return compte(
        session,
        prefixe="res",
        statut=StatutUtilisateur.copropriétaire_résident,
        roles_json="résident",
        batiment_id=batiment_id,
    )


def _affaire(session, auteur, perimetre, *, reserve=True, confidentiel=False):
    """Une panne ciblée sur ce périmètre, lue par le seul périmètre si `reserve`."""
    t = _creer(session, auteur, categorie="panne")
    t = session.get(Ticket, t.id)
    t.perimetre_cible = json.dumps(perimetre)
    t.reserve_perimetre = reserve
    t.confidentiel = confidentiel
    session.add(t)
    session.commit()
    return t.id


@pytest.fixture()
def deux_batiments(session, batiments):
    """P (la plus ancienne) sur le bât. 1, A sur le bât. 2 ; un résident par bâtiment."""
    b1, b2 = batiments[0], batiments[1]
    cs = _compte(session, role=RoleUtilisateur.conseil_syndical)
    r1, r2 = _resident(session, b1), _resident(session, b2)
    p = _affaire(session, cs, [f"bat:{b1}"])
    a = _affaire(session, cs, [f"bat:{b2}"])
    ajouter_liens(session, session.get(Ticket, p), [a], cs)
    session.commit()
    return session, cs, r1, r2, p, a, b1, b2


@pytest.fixture()
def residence_et_batiment(session, batiments):
    """P sur toute la résidence (réservée), A sur le bât. 1 seul : A est plus étroite."""
    b1 = batiments[0]
    cs = _compte(session, role=RoleUtilisateur.conseil_syndical)
    r1, r2 = _resident(session, b1), _resident(session, batiments[1])
    p = _affaire(session, cs, ["résidence"])
    a = _affaire(session, cs, [f"bat:{b1}"])
    ajouter_liens(session, session.get(Ticket, p), [a], cs)
    session.commit()
    return session, cs, r1, r2, p, a, b1


def _clore(session, user, ticket_id, fusionner, conciliations=None):
    corps = TicketEvolutionCreate(
        type="etat",
        nouveau_statut="résolu",
        notifier=False,
        fusionner=fusionner,
        conciliations=conciliations,
    )
    return evolutions.add_evolution(ticket_id, corps, BackgroundTasks(), session=session, user=user)


def _option(session, p, a, code, *, inversion=False):
    return next(
        o
        for o in options(
            session, session.get(Ticket, p), session.get(Ticket, a), inversion=inversion
        )
        if o["code"] == code
    )


# ── 1. L'invariant tient ────────────────────────────────────────────────────


def test_sans_conciliation_le_refus_demeure(deux_batiments):
    session, cs, _r1, _r2, p, a, *_ = deux_batiments
    with pytest.raises(HTTPException) as exc:
        _clore(session, cs, p, [a])
    assert exc.value.status_code == 422
    session.rollback()
    assert session.get(Ticket, a).fusionnee_dans_id is None


def test_une_refusee_porte_son_ecart_et_ses_trois_options(deux_batiments):
    session, cs, _r1, _r2, p, a, *_ = deux_batiments
    c = candidates(session, session.get(Ticket, p), cs)[0]
    assert c["fusionnable"] is False
    #  La forme sérialisée est celle du schéma de réponse.
    lue = CandidateFusion.model_validate(c)
    assert [e.champ for e in lue.conciliation.ecarts] == ["perimetre"]
    assert [o.code for o in lue.conciliation.options] == ["inverser", "restreindre", "elargir"]


def test_une_fusionnable_n_a_pas_de_conciliation(session, batiments):
    cs = _compte(session, role=RoleUtilisateur.conseil_syndical)
    p = _affaire(session, cs, ["résidence"], reserve=False)
    a = _affaire(session, cs, ["résidence"], reserve=False)
    ajouter_liens(session, session.get(Ticket, p), [a], cs)
    session.commit()
    c = candidates(session, session.get(Ticket, p), cs)[0]
    assert c["fusionnable"] is True and c["conciliation"] is None


# ── 2. Élargir ──────────────────────────────────────────────────────────────


def test_elargir_exige_la_liste_nominative_exacte(deux_batiments):
    session, cs, r1, r2, p, a, *_ = deux_batiments
    o = _option(session, p, a, "elargir")
    assert o["disponible"] and o["consentement"]
    assert {x["id"] for x in o["exposes"]} >= {r1.id, r2.id}
    for fausse in ([], [r1.id]):
        with pytest.raises(HTTPException) as exc:
            _clore(
                session,
                cs,
                p,
                [a],
                [ChoixConciliation(affaire_id=a, option="elargir", confirmes=fausse)],
            )
        assert exc.value.status_code == 409
        session.rollback()
    assert session.get(Ticket, a).fusionnee_dans_id is None


def test_elargir_confirme_fusionne_et_ouvre_la_principale_aux_deux(deux_batiments):
    session, cs, r1, r2, p, a, b1, b2 = deux_batiments
    assert not ticket_visible(session.get(Ticket, p), r2)
    attendus = [x["id"] for x in _option(session, p, a, "elargir")["exposes"]]
    _clore(
        session, cs, p, [a], [ChoixConciliation(affaire_id=a, option="elargir", confirmes=attendus)]
    )
    principale = session.get(Ticket, p)
    assert session.get(Ticket, a).fusionnee_dans_id == p
    assert set(json.loads(principale.perimetre_cible)) == {f"bat:{b1}", f"bat:{b2}"}
    #  Ceux de l'absorbée ne perdent rien : ils lisent maintenant la principale.
    assert ticket_visible(principale, r1) and ticket_visible(principale, r2)


def test_elargir_laisse_une_suite_qui_nomme_les_personnes(deux_batiments):
    session, cs, _r1, _r2, p, a, *_ = deux_batiments
    attendus = [x["id"] for x in _option(session, p, a, "elargir")["exposes"]]
    _clore(
        session, cs, p, [a], [ChoixConciliation(affaire_id=a, option="elargir", confirmes=attendus)]
    )
    suites = [
        e.contenu
        for e in session.exec(select(TicketEvolution).where(TicketEvolution.ticket_id == p)).all()
        if "Conciliation de la fusion" in (e.contenu or "")
    ]
    assert len(suites) == 1
    assert "Périmètre" in suites[0] and "Prénom NOM" in suites[0]


def test_la_conciliation_laisse_une_ligne_de_journal(deux_batiments, caplog):
    session, cs, _r1, _r2, p, a, *_ = deux_batiments
    attendus = [x["id"] for x in _option(session, p, a, "elargir")["exposes"]]
    with caplog.at_level(logging.INFO, logger="securite"):
        _clore(
            session,
            cs,
            p,
            [a],
            [ChoixConciliation(affaire_id=a, option="elargir", confirmes=attendus)],
        )
    lignes = [r.getMessage() for r in caplog.records if "fusion_conciliation" in r.getMessage()]
    assert len(lignes) == 1 and f"acteur={cs.id}" in lignes[0] and f"cible={p}" in lignes[0]
    #  Un identifiant, jamais une adresse.
    assert "@" not in lignes[0]


# ── 3. Restreindre ──────────────────────────────────────────────────────────


def test_restreindre_prend_ce_que_les_deux_ont_en_commun(residence_et_batiment):
    session, cs, r1, r2, p, a, b1 = residence_et_batiment
    #  Précondition : sans conciliation la fusion est refusée (P est lue de la
    #  résidence entière, A du seul bât. 1).
    assert candidates(session, session.get(Ticket, p), cs)[0]["fusionnable"] is False
    assert ticket_visible(session.get(Ticket, p), r2)
    o = _option(session, p, a, "restreindre")
    assert o["disponible"]
    assert o["consentement"] is False and o["exposes"] == []
    _clore(session, cs, p, [a], [ChoixConciliation(affaire_id=a, option="restreindre")])
    principale = session.get(Ticket, p)
    assert session.get(Ticket, a).fusionnee_dans_id == p
    assert json.loads(principale.perimetre_cible) == [f"bat:{b1}"]
    assert ticket_visible(principale, r1)
    assert not ticket_visible(principale, r2)


def test_restreindre_est_indisponible_sans_perimetre_commun(deux_batiments):
    session, _cs, _r1, _r2, p, a, *_ = deux_batiments
    o = _option(session, p, a, "restreindre")
    assert o["disponible"] is False and "rien en commun" in o["pourquoi"]
    with pytest.raises(HTTPException) as exc:
        _clore(
            session,
            _cs,
            p,
            [a],
            [ChoixConciliation(affaire_id=a, option="restreindre")],
        )
    assert exc.value.status_code == 422


# ── 4. Inverser ─────────────────────────────────────────────────────────────


def test_inverser_n_existe_pas_a_la_cloture(residence_et_batiment):
    session, _cs, _r1, _r2, p, a, _b1 = residence_et_batiment
    o = _option(session, p, a, "inverser", inversion=False)
    assert o["disponible"] is False and "clôture" in o["pourquoi"]


def test_inverser_est_offert_quand_l_autre_est_plus_etroite(residence_et_batiment):
    session, _cs, *_resto, p, a, _b1 = residence_et_batiment
    assert _option(session, p, a, "inverser", inversion=True)["disponible"] is True


def test_inverser_est_refuse_quand_l_autre_serait_lue_par_de_nouveaux(deux_batiments):
    session, _cs, _r1, _r2, p, a, *_ = deux_batiments
    o = _option(session, p, a, "inverser", inversion=True)
    assert o["disponible"] is False


def test_hors_cloture_la_principale_choisie_absorbe(residence_et_batiment):
    session, cs, _r1, _r2, p, a, _b1 = residence_et_batiment
    #  La plus ancienne (P, la résidence) absorberait une affaire qu'elle fait fuir.
    with pytest.raises(HTTPException) as exc:
        fusion_en_cours.fusionner(session, [p, a], cs, "Titre", "")
    assert exc.value.status_code == 422
    session.rollback()
    principale, absorbees = fusion_en_cours.fusionner(
        session, [p, a], cs, "Titre", "", principale_id=a
    )
    assert principale.id == a
    assert [x.id for x, _ in absorbees] == [p]


def test_le_suivi_offre_la_conciliation_de_son_groupe(residence_et_batiment):
    session, cs, _r1, _r2, p, a, _b1 = residence_et_batiment
    rendu = suivi_fusions.conciliation(
        suivi_fusions.GroupeEntree(ids=[p, a]), session=session, user=cs
    )
    assert [c["id"] for c in rendu] == [a]
    inverser = next(o for o in rendu[0]["conciliation"]["options"] if o["code"] == "inverser")
    assert inverser["disponible"] is True


def test_une_principale_hors_du_groupe_est_refusee(residence_et_batiment):
    session, cs, _r1, _r2, p, a, _b1 = residence_et_batiment
    with pytest.raises(HTTPException) as exc:
        fusion_en_cours.affaires_du_groupe(session, [p, a], principale_id=999999)
    assert exc.value.status_code == 422


# ── 5. Le confidentiel ne s'ouvre jamais ────────────────────────────────────


def test_une_confidentielle_ne_s_elargit_pas(session, batiments):
    cs = _compte(session, role=RoleUtilisateur.conseil_syndical)
    auteur = _resident(session, batiments[0])
    p = _affaire(session, auteur, ["résidence"], reserve=False)
    a = _affaire(session, cs, ["résidence"], reserve=False, confidentiel=True)
    ajouter_liens(session, session.get(Ticket, p), [a], cs)
    session.commit()
    o = _option(session, p, a, "elargir")
    assert o["disponible"] is False and "confidentielle" in o["pourquoi"]
    with pytest.raises(HTTPException) as exc:
        _clore(session, cs, p, [a], [ChoixConciliation(affaire_id=a, option="elargir")])
    assert exc.value.status_code == 422


# ── 6. La mesure n'écrit rien ───────────────────────────────────────────────


def test_le_diagnostic_n_ecrit_rien(deux_batiments):
    session, cs, _r1, _r2, p, _a, *_ = deux_batiments
    avant = session.get(Ticket, p).perimetre_cible
    candidates(session, session.get(Ticket, p), cs, inversion=True)
    principale = session.get(Ticket, p)
    assert principale.perimetre_cible == avant
    assert not session.is_modified(principale)
