"""Les quatre flèches d'un périmètre — d'un rang ou d'un niveau (01/11/2026).

La règle (`utils/perimetres/deplacement.py`) se juge sur des lignes posées en
mémoire ; la route, sur l'arbre semé de la fixture `batiments`.
"""

import pytest
from fastapi import HTTPException
from sqlmodel import Session, select

from app.database import engine
from app.models.perimetre import Perimetre
from app.routers.patrimoine import lister_perimetres
from app.routers.patrimoine_branche import PerimetreDeplacement, deplacer_perimetre
from app.utils.perimetres.deplacement import deplacement, refus_deplacement, sens_admis
from tests.aides_base import compte


def _arbre() -> dict[str, Perimetre]:
    """racine ─ a ─ a1
    └ b
    └ c   (c porte un bâtiment)"""
    noeuds = [
        Perimetre(id=1, code="racine", libelle="Racine", portee_globale=True, ordre=0),
        Perimetre(id=2, code="a", libelle="A", parent_id=1, ordre=0),
        Perimetre(id=3, code="b", libelle="B", parent_id=1, ordre=0),
        Perimetre(id=4, code="c", libelle="C", parent_id=1, ordre=5, batiment_id=9),
        Perimetre(id=5, code="a1", libelle="A1", parent_id=2, ordre=0),
    ]
    return {n.code: n for n in noeuds}


def _codes(d) -> tuple:
    return d.parent_id, [n.code for n in d.fratrie]


def test_haut_et_bas_echangent_avec_le_frere_voisin():
    a = _arbre()
    tous = list(a.values())
    assert _codes(deplacement(a["b"], tous, "haut", "racine")) == (1, ["b", "a", "c"])
    assert _codes(deplacement(a["b"], tous, "bas", "racine")) == (1, ["a", "c", "b"])
    assert deplacement(a["a"], tous, "haut", "racine") is None
    assert "premier" in refus_deplacement(a["a"], tous, "haut", "racine")
    assert deplacement(a["c"], tous, "bas", "racine") is None


def test_droite_entre_dans_le_frere_qui_precede_en_dernier():
    a = _arbre()
    tous = list(a.values())
    assert _codes(deplacement(a["b"], tous, "droite", "racine")) == (2, ["a1", "b"])
    assert deplacement(a["a"], tous, "droite", "racine") is None, "aucun frère avant lui"


def test_gauche_sort_du_parent_et_se_range_juste_apres_lui():
    a = _arbre()
    tous = list(a.values())
    assert _codes(deplacement(a["a1"], tous, "gauche", "racine")) == (1, ["a", "a1", "b", "c"])


def test_la_racine_ne_change_pas_de_niveau():
    """🔴 Elle est le périmètre par défaut de tout contenu sans périmètre."""
    a = _arbre()
    a["racine2"] = Perimetre(id=6, code="racine2", libelle="R2", ordre=1)
    tous = list(a.values())
    assert sens_admis(a["racine2"], tous, "racine") == ["haut", "droite"]
    assert sens_admis(a["racine"], tous, "racine") == ["bas"]
    assert "racine" in refus_deplacement(a["racine"], tous, "droite", "racine")


def test_un_batiment_ne_se_range_pas_dans_un_autre():
    a = _arbre()
    a["d"] = Perimetre(id=7, code="d", libelle="D", parent_id=1, ordre=9, batiment_id=8)
    tous = list(a.values())
    assert deplacement(a["d"], tous, "droite", "racine") is None
    assert "bâtiment" in refus_deplacement(a["d"], tous, "droite", "racine")
    #  …mais un bâtiment entre dans un nœud qui n'en est pas un, ou en sort.
    assert sens_admis(a["c"], tous, "racine") == ["haut", "bas", "gauche", "droite"]


def test_un_sens_inconnu_est_refuse():
    a = _arbre()
    assert "inconnu" in refus_deplacement(a["b"], list(a.values()), "travers", "racine")


def test_la_route_renumerote_la_fratrie_et_l_ecran_lit_la_meme_regle(batiments):
    """Deux frères à rang égal s'échangent vraiment : la fratrie est renumérotée."""
    with Session(engine) as session:
        admin = compte(session, prefixe="admin")
        hall = session.exec(
            select(Perimetre).where(Perimetre.code == f"bat:{batiments[0]}/hall")
        ).one()
        lus = {n.code: n for n in lister_perimetres(session, admin)}
        assert "haut" not in lus[hall.code].deplacements
        assert "gauche" in lus[hall.code].deplacements

        lu = deplacer_perimetre(hall.id, PerimetreDeplacement(sens="bas"), session, admin)
        assert lu.ordre == 1
        freres = session.exec(
            select(Perimetre).where(Perimetre.parent_id == hall.parent_id).order_by(Perimetre.ordre)
        ).all()
        assert [f.ordre for f in freres] == list(range(len(freres)))
        assert freres[1].id == hall.id

        lu = deplacer_perimetre(hall.id, PerimetreDeplacement(sens="gauche"), session, admin)
        assert lu.parent == "batiments" and lu.profondeur == 1

        with pytest.raises(HTTPException) as refus:
            deplacer_perimetre(hall.id, PerimetreDeplacement(sens="travers"), session, admin)
        assert refus.value.status_code == 422
