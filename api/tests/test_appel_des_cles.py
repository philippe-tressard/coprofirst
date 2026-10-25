"""Une clé appelée ou non par le syndic, et son libellé sur l'appel de fonds (#2252).

Le conseil les règle dans Admin › Copropriété › Lots ; « Mes lots » les lit. Tout est
FICTIF : clé « Ascenseur X », lot 9xx.
"""

from __future__ import annotations

from fastapi.testclient import TestClient
from sqlmodel import Session

from app.auth.deps import require_cs_or_admin
from app.database import engine
from app.main import app
from app.models.charges import CleDeCharges, QuotePartLot
from app.models.copropriete import Lot, TypeLot
from app.utils.lecture_lots import designations


def _une_cle_et_sa_part(session: Session, batiment_id: int) -> tuple[int, int]:
    cle = CleDeCharges(code="ascenseur-x", libelle="Ascenseur X", denominateur=10)
    lot = Lot(numero="961", batiment_id=batiment_id, type=TypeLot.appartement)
    session.add_all([cle, lot])
    session.flush()
    session.add(QuotePartLot(lot_id=lot.id, cle_id=cle.id, numerateur=10))
    session.commit()
    return cle.id, lot.id


def test_le_conseil_regle_l_appel_et_le_libelle_et_mes_lots_le_lit(batiments, lots_jetables):
    with Session(engine) as session:
        cle_id, lot_id = _une_cle_et_sa_part(session, batiments[0])
    app.dependency_overrides[require_cs_or_admin] = lambda: None
    try:
        client = TestClient(app)
        (lue,) = [c for c in client.get("/lots/admin/cles").json() if c["id"] == cle_id]
        assert (lue["appelee"], lue["libelle_syndic"]) == (True, None), "défaut : rien ne change"

        corps = {"appelee": False, "libelle_syndic": "  ASCENSEUR BAT X  "}
        reglee = client.patch(f"/lots/admin/cles/{cle_id}", json=corps).json()
        assert (reglee["appelee"], reglee["libelle_syndic"]) == (False, "ASCENSEUR BAT X")
        #  Un champ absent ne touche à rien ; un libellé vide s'efface au lieu d'un blanc.
        assert client.patch(f"/lots/admin/cles/{cle_id}", json={}).json()["appelee"] is False
        vide = client.patch(f"/lots/admin/cles/{cle_id}", json={"libelle_syndic": " "}).json()
        assert vide["libelle_syndic"] is None
        assert client.patch("/lots/admin/cles/999999", json={}).status_code == 404
    finally:
        app.dependency_overrides.pop(require_cs_or_admin, None)

    with Session(engine) as session:
        lot = session.get(Lot, lot_id)
        (part,) = designations(session, [lot], lambda _lot: True)[lot_id].quotes_parts
        assert part.appelee is False and part.libelle_syndic is None


def test_le_reglage_ne_touche_ni_au_libelle_ni_au_denominateur_de_l_acte():
    from app.routers.lots_admin import CleUpdate

    assert set(CleUpdate.model_fields) == {"appelee", "libelle_syndic"}
