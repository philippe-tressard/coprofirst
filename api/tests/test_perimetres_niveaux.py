"""L'arborescence s'arrête au niveau 3 (10/11/2026).

Demandé à l'écran : *« interdire de niveau 4 ou plus »* — Bâtiment 1 (niveau 1),
Logement (2), Terrasses Balcons (3). Le regroupement « Bâtiments » ne compte pas.
La règle (`utils/perimetres/niveaux.py`) se juge sur des lignes en mémoire ; chaque
geste qui POSE un nœud, sur l'arbre semé de la fixture `batiments`.
"""

import pytest
from fastapi import HTTPException
from sqlmodel import Session, select

from app.database import engine
from app.models.perimetre import Perimetre
from app.routers.patrimoine import creer_perimetre, lister_perimetres, modifier_perimetre
from app.routers.patrimoine_schemas import PerimetreCreate, PerimetreUpdate
from app.routers.patrimoine_branche import (
    PerimetreCopie,
    PerimetreDeplacement,
    copier_perimetre,
    deplacer_perimetre,
)
from app.utils.perimetres.deplacement import sens_admis
from app.utils.perimetres.niveaux import (
    NIVEAU_MAX,
    hauteur,
    niveau,
    nouveaux_trop_profonds,
    refus_niveau,
    trop_profonds,
)
from tests.aides_base import compte


def _arbre() -> dict[str, Perimetre]:
    """batiments (regroupement) ─ bat ─ logement ─ terrasses
    parking ─ places
    """
    noeuds = [
        Perimetre(id=1, code="batiments", libelle="Bâtiments", selectionnable=False, ordre=1),
        Perimetre(id=2, code="bat", libelle="Bâtiment 1", parent_id=1, ordre=0),
        Perimetre(id=3, code="logement", libelle="Logement", parent_id=2, ordre=0),
        Perimetre(id=4, code="terrasses", libelle="Terrasses", parent_id=3, ordre=0),
        Perimetre(id=5, code="parking", libelle="Parking", ordre=2),
        Perimetre(id=6, code="places", libelle="Places", parent_id=5, ordre=0),
        Perimetre(id=7, code="jardin", libelle="Jardin", parent_id=3, ordre=1),
    ]
    return {n.code: n for n in noeuds}


def test_le_regroupement_ne_compte_pas():
    a = _arbre()
    par_id = {n.id: n for n in a.values()}
    assert [niveau(a[c], par_id) for c in ("batiments", "bat", "logement", "terrasses")] == [
        0,
        1,
        2,
        3,
    ]
    assert niveau(a["parking"], par_id) == 1
    assert NIVEAU_MAX == 3


def test_rien_ne_se_pose_au_niveau_4():
    a = _arbre()
    tous = list(a.values())
    assert refus_niveau(None, True, a["terrasses"].id, tous) is not None
    assert refus_niveau(None, True, a["logement"].id, tous) is None
    #  Une branche compte sa hauteur : « Parking › Places » sous « Logement »
    #  poserait Places au niveau 4.
    assert hauteur(a["parking"], tous) == 1
    assert refus_niveau(a["parking"], True, a["logement"].id, tous) is not None
    assert refus_niveau(a["parking"], True, a["bat"].id, tous) is None


def test_la_fleche_droite_se_grise_avant_le_niveau_4():
    """Jardin, après Terrasses sous Logement, n'entre pas dans Terrasses."""
    a = _arbre()
    tous = list(a.values())
    assert "droite" not in sens_admis(a["jardin"], tous, None)
    assert "gauche" in sens_admis(a["jardin"], tous, None)


def test_un_noeud_deja_trop_profond_ne_bloque_pas_le_reste():
    """Écrit avant la règle, il reste ; seul un nœud de PLUS est refusé."""
    a = _arbre()
    a["vieux"] = Perimetre(id=8, code="vieux", libelle="Vieux", parent_id=4, ordre=0)
    tous = list(a.values())
    avant = trop_profonds(tous)
    assert avant == {8}
    assert nouveaux_trop_profonds(avant, tous) is None
    #  « Bâtiments » devenu une cible fait descendre toute sa branche d'un niveau.
    a["batiments"].selectionnable = True
    assert nouveaux_trop_profonds(avant, tous) is not None


def _noeud(session: Session, code: str) -> Perimetre:
    return session.exec(select(Perimetre).where(Perimetre.code == code)).one()


def test_les_gestes_refusent_le_niveau_4(batiments):
    with Session(engine) as session:
        admin = compte(session, prefixe="admin")
        hall = _noeud(session, f"bat:{batiments[0]}/hall")
        n3 = creer_perimetre(
            PerimetreCreate(code="niveau-3", libelle="Niveau 3", parent=hall.code),
            session,
            admin,
        )
        assert (n3.niveau, n3.niveaux_libres) == (3, 0)
        lus = {n.code: n for n in lister_perimetres(session, admin)}
        assert (lus[hall.code].niveau, lus[hall.code].hauteur) == (2, 1)
        assert lus["batiments"].niveau == 0

        #  Création sous un niveau 3.
        with pytest.raises(HTTPException) as refus:
            creer_perimetre(
                PerimetreCreate(code="niveau-4", libelle="Niveau 4", parent="niveau-3"),
                session,
                admin,
            )
        assert refus.value.status_code == 422 and "niveau 3" in refus.value.detail

        #  Changement de parent, puis « Bâtiments » rendu sélectionnable.
        for corps in (PerimetreUpdate(parent="niveau-3"), PerimetreUpdate(selectionnable=True)):
            cible = _noeud(session, "batiments" if corps.selectionnable else hall.code)
            with pytest.raises(HTTPException) as refus:
                modifier_perimetre(cible.id, corps, session, admin)
            assert refus.value.status_code == 422
        session.expire_all()
        assert _noeud(session, hall.code).parent_id != _noeud(session, "niveau-3").id
        assert _noeud(session, "batiments").selectionnable is False

        #  Copie d'une branche à deux niveaux sous un niveau 2.
        hall2 = _noeud(session, f"bat:{batiments[1]}/hall")
        with pytest.raises(HTTPException) as refus:
            copier_perimetre(hall.id, PerimetreCopie(parents=[hall2.code]), session, admin)
        assert refus.value.status_code == 422 and "niveau 3" in refus.value.detail

        #  La flèche droite : « second » entrerait dans « niveau-3 », au niveau 4.
        creer_perimetre(
            PerimetreCreate(code="second", libelle="Second", parent=hall.code, ordre=1),
            session,
            admin,
        )
        lus = {n.code: n for n in lister_perimetres(session, admin)}
        assert "droite" not in lus["second"].deplacements
        with pytest.raises(HTTPException) as refus:
            deplacer_perimetre(
                _noeud(session, "second").id, PerimetreDeplacement(sens="droite"), session, admin
            )
        assert "niveau 3" in refus.value.detail
