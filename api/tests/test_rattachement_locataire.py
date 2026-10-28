"""Le locataire dit lui-même ce qu'il loue, d'après le fichier des lots (04/10/2026).

Son propriétaire n'a pas de compte : seul le fichier du syndic connaît ses lots.
Trois questions — appartement, cave, parking —, chaque « oui » rattache tout
de suite et remet tous les badges du lot. Bornes : les seuls lots du
propriétaire nommé, le bâtiment du profil, et rien pour qui est déjà rattaché.
"""

from __future__ import annotations

from datetime import date

import pytest
from fastapi import HTTPException
from sqlmodel import Session, select

from app.auth.appartenance import exiger_lots_proposes_au_locataire
from app.models.copropriete import Lot, TypeLot
from app.models.core import (
    LocationBail,
    LotImport,
    RoleUtilisateur,
    StatutAcces,
    StatutLotImport,
    StatutUtilisateur,
    Telecommande,
    TypeLien,
    UserLot,
    Vigik,
)
from app.utils.acces_bail import adopter_declares, rendre_au_bailleur
from app.utils.rattachement_locataire import (
    lots_proposes,
    rattacher_lots_declares,
    rendre_acces_declares,
)
from tests.aides_base import compte
from tests.aides_http import base_http, client_http


def _lot_au_fichier(session, numero, nature, *, copro="DURANDAL Paul", no="408001", batiment_id=4):
    """Un lot ET sa ligne du fichier des lots, résolue sur lui."""
    lot = Lot(numero=numero, type=nature, batiment_id=batiment_id)
    session.add(lot)
    session.commit()
    session.refresh(lot)
    session.add(
        LotImport(
            batiment_id=batiment_id,
            numero=numero,
            type_raw="ST",
            no_coproprietaire=no,
            nom_coproprietaire=copro,
            lot_id=lot.id,
            statut=StatutLotImport.lot_lie,
        )
    )
    session.commit()
    return lot


@pytest.fixture
def parc(session):
    """Un copropriétaire sans compte : un appartement au bât. 4, un au bât. 2, une cave, un parking."""
    lots = {
        "appart": _lot_au_fichier(session, "13", TypeLot.appartement),
        "autre_bat": _lot_au_fichier(session, "27", TypeLot.appartement, batiment_id=2),
        "cave": _lot_au_fichier(session, "408", TypeLot.cave),
        "parking": _lot_au_fichier(session, "462", TypeLot.parking, batiment_id=None),
        "voisin": _lot_au_fichier(
            session, "14", TypeLot.appartement, copro="BAILLEUR Alice", no="408002"
        ),
    }
    badges = {
        "vigik": Vigik(code="V1", lot_id=lots["appart"].id),
        "vigik_perdu": Vigik(code="V2", lot_id=lots["appart"].id, statut=StatutAcces.perdu),
        "tc": Telecommande(code="T1", lot_id=lots["parking"].id),
    }
    for b in badges.values():
        session.add(b)
    session.commit()
    return lots, badges


def _locataire(session, nom_proprietaire="DURANDAL", statut=StatutUtilisateur.locataire):
    return compte(
        session, nom="LOC", statut=statut, nom_proprietaire=nom_proprietaire, batiment_id=4
    )


def _numeros(proposes):
    return {nature: [lot.numero for lot in lots] for nature, lots in proposes.items()}


def test_les_lots_du_proprietaire_nomme_sont_proposes_par_nature(session, parc):
    assert _numeros(lots_proposes(_locataire(session), session)) == {
        "appartement": ["13"],  # le bât. 2 est écarté par le profil
        "cave": ["408"],
        "parking": ["462"],
    }


def test_un_batiment_qui_ne_laisse_aucun_appartement_ne_cache_rien(session, parc):
    loc = _locataire(session)
    loc.batiment_id = 9
    assert _numeros(lots_proposes(loc, session))["appartement"] == ["13", "27"]


@pytest.mark.parametrize(
    "cas",
    ["proprietaire_inconnu", "pas_locataire", "deja_rattache"],
)
def test_rien_n_est_propose(session, parc, cas):
    lots, _ = parc
    if cas == "proprietaire_inconnu":
        loc = _locataire(session, nom_proprietaire="INCONNU")
    elif cas == "pas_locataire":
        loc = _locataire(session, statut=StatutUtilisateur.copropriétaire_résident)
    else:
        loc = _locataire(session)
        session.add(UserLot(user_id=loc.id, lot_id=lots["voisin"].id, type_lien=TypeLien.locataire))
        session.commit()
    assert not any(lots_proposes(loc, session).values())


def test_un_homonyme_ne_propose_rien(session, parc):
    _lot_au_fichier(session, "50", TypeLot.appartement, copro="DURANDAL Alice", no="408003")
    assert not any(lots_proposes(_locataire(session), session).values())


def test_oui_rattache_et_remet_tous_les_badges(session, parc):
    lots, badges = parc
    loc = _locataire(session)
    remis = rattacher_lots_declares(loc, [lots["appart"], lots["cave"], lots["parking"]], session)
    session.commit()
    assert remis == {"lots": 3, "vigik": 1, "telecommande": 1}
    liens = session.exec(select(UserLot).where(UserLot.user_id == loc.id)).all()
    assert {(ul.lot_id, ul.type_lien) for ul in liens} == {
        (lots[n].id, TypeLien.locataire) for n in ("appart", "cave", "parking")
    }
    for cle in ("vigik", "tc"):
        session.refresh(badges[cle])
        assert (badges[cle].chez_locataire, badges[cle].user_id) == (True, loc.id)
    session.refresh(badges["vigik_perdu"])
    assert badges["vigik_perdu"].chez_locataire is False  # un badge perdu n'est chez personne
    #  Une fois rattaché, plus de questions.
    assert not any(lots_proposes(loc, session).values())


def test_un_lot_non_propose_est_refuse_et_rien_n_est_ecrit(session, parc):
    lots, _ = parc
    loc = _locataire(session)
    with pytest.raises(HTTPException) as refus:
        exiger_lots_proposes_au_locataire(session, [lots["appart"].id, lots["voisin"].id], loc)
    assert refus.value.status_code == 403
    with pytest.raises(HTTPException):
        exiger_lots_proposes_au_locataire(session, [], loc)
    assert session.exec(select(UserLot).where(UserLot.user_id == loc.id)).all() == []


def test_defaire_rend_les_badges_que_le_locataire_s_etait_remis(session, parc):
    lots, badges = parc
    loc = _locataire(session)
    rattacher_lots_declares(loc, [lots["appart"]], session)
    session.commit()
    rendre_acces_declares(session, loc.id, lots["appart"].id)
    session.commit()
    session.refresh(badges["vigik"])
    assert (badges["vigik"].chez_locataire, badges["vigik"].user_id) == (False, None)


def test_le_bail_pose_ensuite_adopte_les_badges_et_les_rend_a_sa_fin(session, parc):
    lots, badges = parc
    loc = _locataire(session)
    rattacher_lots_declares(loc, [lots["appart"]], session)
    proprio = compte(session, nom="DURANDAL", statut=StatutUtilisateur.copropriétaire_bailleur)
    bail = LocationBail(
        lot_id=lots["appart"].id,
        bailleur_id=proprio.id,
        locataire_id=loc.id,
        date_entree=date(2026, 10, 1),
    )
    session.add(bail)
    session.flush()
    adopter_declares(session, bail)
    session.commit()
    session.refresh(badges["vigik"])
    assert badges["vigik"].bail_id == bail.id
    assert [o.code for _, o in rendre_au_bailleur(session, bail)] == ["V1"]


#  ── Les routes, authentification comprise ─────────────────────────────────


def test_les_routes_proposent_puis_rattachent():
    with base_http() as moteur:
        with Session(moteur) as s:
            _lot_au_fichier(s, "13", TypeLot.appartement)
            _lot_au_fichier(s, "462", TypeLot.parking, batiment_id=None)
        http, ident = client_http(
            moteur,
            RoleUtilisateur.résident,
            statut=StatutUtilisateur.locataire,
            nom_proprietaire="DURANDAL",
            batiment_id=4,
        )
        propositions = http.get("/lots/ma-location/propositions").json()
        assert propositions["proprietaire"] == "DURANDAL"
        assert [lot["numero"] for lot in propositions["appartement"]] == ["13"]
        assert propositions["parking"][0]["acces"] == {"vigik": 0, "telecommande": 0}

        lot_id = propositions["appartement"][0]["id"]
        assert http.post("/lots/ma-location", json={"lot_ids": [lot_id]}).status_code == 200
        mes_lots = http.get("/lots/mes-lots").json()
        assert [(lot["id"], lot["type_lien"]) for lot in mes_lots] == [(lot_id, "locataire")]
        #  Déjà rattaché : une seconde déclaration ne passe plus.
        assert http.post("/lots/ma-location", json={"lot_ids": [lot_id]}).status_code == 403

        anonyme, _ = client_http(moteur, None)
        assert anonyme.get("/lots/ma-location/propositions").status_code == 401


# ── D'office, à la validation du compte (#2267, 27/10/2026) ─────────────────
#  Les quatre derniers locataires n'avaient pas répondu aux questions : sans
#  lot ni badge, ils ont été rattachés à la main — aux lots que la règle des
#  noms désignait déjà.


def test_la_validation_rattache_d_office_tout_le_lot_et_ses_badges(session, parc):
    from app.utils.auto_match_service import auto_match_pour_utilisateur

    lots, badges = parc
    loc = _locataire(session)
    resultat = auto_match_pour_utilisateur(loc, session)
    session.commit()
    assert resultat["lots_d_office"] == 3
    liens = session.exec(select(UserLot).where(UserLot.user_id == loc.id)).all()
    assert {ul.lot_id for ul in liens} == {lots[n].id for n in ("appart", "cave", "parking")}
    for cle in ("vigik", "tc"):
        session.refresh(badges[cle])
        assert (badges[cle].chez_locataire, badges[cle].user_id) == (True, loc.id)


def test_deux_appartements_restent_aux_questions(session, parc):
    from app.utils.rattachement_locataire import rattacher_d_office

    loc = compte(
        session, nom="LOC", statut=StatutUtilisateur.locataire, nom_proprietaire="DURANDAL"
    )
    assert rattacher_d_office(loc, session) == 0
    assert session.exec(select(UserLot).where(UserLot.user_id == loc.id)).all() == []
    assert len(lots_proposes(loc, session)["appartement"]) == 2


def test_un_lot_deja_loue_a_un_autre_n_est_pas_pris(session, parc):
    from app.utils.rattachement_locataire import rattacher_d_office

    lots, badges = parc
    autre = _locataire(session)
    session.add(UserLot(user_id=autre.id, lot_id=lots["parking"].id, type_lien=TypeLien.locataire))
    session.commit()
    loc = _locataire(session)
    assert rattacher_d_office(loc, session) == 0
    session.refresh(badges["tc"])
    assert badges["tc"].user_id is None


def test_la_resolution_d_un_import_remet_les_badges_au_locataire(session, parc):
    from app.routers.lots_imports import _lier_utilisateurs

    lots, badges = parc
    loc = _locataire(session)
    _lier_utilisateurs(session, [{"user_id": loc.id, "type_lien": "locataire"}], lots["appart"].id)
    session.commit()
    session.refresh(badges["vigik"])
    assert (badges["vigik"].chez_locataire, badges["vigik"].user_id) == (True, loc.id)
    #  Rejouée, elle ne duplique rien.
    _lier_utilisateurs(session, [{"user_id": loc.id, "type_lien": "locataire"}], lots["appart"].id)
    session.commit()
    assert len(session.exec(select(UserLot).where(UserLot.user_id == loc.id)).all()) == 1


def test_relancer_l_appariement_remet_les_badges_d_un_lien_pose_a_la_main(session, parc):
    """Le rattrapage des locataires liés avant la porte unique (#2267)."""
    from app.utils.auto_match_service import auto_match_pour_utilisateur

    lots, badges = parc
    loc = _locataire(session)
    session.add(UserLot(user_id=loc.id, lot_id=lots["appart"].id, type_lien=TypeLien.locataire))
    session.commit()
    resultat = auto_match_pour_utilisateur(loc, session)
    session.commit()
    assert (resultat["lots_d_office"], resultat["badges_remis"]) == (0, 1)
    session.refresh(badges["vigik"])
    assert (badges["vigik"].chez_locataire, badges["vigik"].user_id) == (True, loc.id)
    #  Rejoué, rien de plus.
    assert auto_match_pour_utilisateur(loc, session)["badges_remis"] == 0
