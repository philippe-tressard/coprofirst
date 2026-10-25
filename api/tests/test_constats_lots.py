"""Les constats du patrimoine des lots, et les routes de l'onglet Lots (#2216).

`constater` est pure : les cas se rejouent sur des relevés FICTIFS. Les routes se
vérifient sur leurs droits (`routers/lots_admin`) et sur la re-dérivation, qui
garde une ligne posée à la main.
"""

from __future__ import annotations

from sqlmodel import Session, select

from app.database import engine
from app.models.copropriete import Lot, TypeLot
from app.models.perimetre import LotPerimetre, Perimetre
from app.utils import constats as C
from app.utils.constats_lots import Releve, constater


def _codes(r: Releve) -> dict[str, C.Constat]:
    return {c.code: c for c in constater(r)}


def test_un_patrimoine_vide_rend_inconnu_jamais_aucun_constat():
    (seul,) = constater(Releve(lots=[]))
    assert seul.gravite == C.INCONNU


def test_chaque_constat_se_declenche_sur_son_cas():
    trouves = _codes(
        Releve(
            lots=[("901", False, True), ("902", True, False), ("903", True, True)],
            lots_avec_proprietaire={"901", "903"},
            comptes_proprietaires_sans_lot=2,
            cles=[("Générales", 100, 99), ("Ascenseur X", 10, 10)],
            batiments_sans_lettre=["Bât. 2"],
            etat_descriptif={"901", "902"},
            nb_lots_fiche=4,
        )
    )
    assert trouves["sans_proprietaire"].lots == ["902"]
    assert "2 comptes copropriétaires n'ont aucun lot" in trouves["proprietaire_sans_lot"].message
    assert trouves["annexe_sans_circulation"].lots == ["902"]
    assert trouves["annexe_sans_circulation"].gravite == C.INFORMATION, (
        "état appliqué : accès direct"
    )
    assert "Générales" in trouves["somme_cle"].message
    assert "Bât. 2" in trouves["batiment_sans_lettre"].message
    assert trouves["hors_etat_descriptif"].lots == ["903"]
    assert "4 sur la fiche" in trouves["total_fiche"].message


def test_un_seul_compte_sans_lot_se_dit_au_singulier():
    (seul,) = [
        c
        for c in constater(
            Releve(
                lots=[("901", False, True)],
                lots_avec_proprietaire={"901"},
                comptes_proprietaires_sans_lot=1,
            )
        )
        if c.code == "proprietaire_sans_lot"
    ]
    assert seul.message.startswith("1 compte copropriétaire n'a aucun lot actif")


def test_un_patrimoine_juste_ne_dit_rien():
    assert (
        constater(
            Releve(
                lots=[("901", False, True)],
                lots_avec_proprietaire={"901"},
                cles=[("Générales", 100, 100)],
                etat_descriptif={"901"},
                nb_lots_fiche=1,
            )
        )
        == []
    )


def test_sans_etat_descriptif_une_annexe_sans_circulation_avertit():
    trouves = _codes(Releve(lots=[("902", True, False)], lots_avec_proprietaire={"902"}))
    assert trouves["annexe_sans_circulation"].gravite == C.AVERTISSEMENT
    assert "hors_etat_descriptif" not in trouves


def test_chaque_route_de_l_onglet_exige_le_conseil_ou_l_administration():
    from fastapi.routing import APIRoute

    from app.auth.deps import require_cs_or_admin
    from app.routers.lots_admin import router

    routes = [r for r in router.routes if isinstance(r, APIRoute)]
    assert len(routes) == 6, "une route ajoutée ou retirée : relire ce test"
    for route in routes:
        assert require_cs_or_admin in {d.call for d in route.dependant.dependencies}, route.path


def test_un_perimetre_pose_a_la_main_survit_a_la_rederivation(batiments, lots_jetables):
    from fastapi.testclient import TestClient

    from app.auth.deps import require_cs_or_admin
    from app.main import app

    with Session(engine) as session:
        lot = Lot(numero="981", batiment_id=batiments[0], type=TypeLot.appartement)
        session.add(lot)
        session.commit()
        toit = session.exec(
            select(Perimetre).where(Perimetre.code == f"bat:{batiments[1]}/toit")
        ).one()
        lot_id, toit_id = lot.id, toit.id
    app.dependency_overrides[require_cs_or_admin] = lambda: None
    try:
        client = TestClient(app)
        corps = {"perimetre_id": toit_id, "relation": "desservi_par"}
        assert client.post(f"/lots/admin/{lot_id}/perimetres", json=corps).status_code == 201
        assert client.post("/lots/admin/rederiver").json()["modifies"] >= 1
        with Session(engine) as session:
            lignes = session.exec(select(LotPerimetre).where(LotPerimetre.lot_id == lot_id)).all()
            assert any(lp.perimetre_id == toit_id and not lp.derive for lp in lignes)
            derivee = next(lp for lp in lignes if lp.derive)
        #  Une ligne dérivée ne se retire pas à la main ; la manuelle, si.
        url = f"/lots/admin/{lot_id}/perimetres/{derivee.perimetre_id}/{derivee.relation.value}"
        assert client.delete(url).status_code == 409
        url = f"/lots/admin/{lot_id}/perimetres/{toit_id}/desservi_par"
        assert client.delete(url).status_code == 204
        assert client.get("/lots/admin/constats").status_code == 200
    finally:
        app.dependency_overrides.pop(require_cs_or_admin, None)
