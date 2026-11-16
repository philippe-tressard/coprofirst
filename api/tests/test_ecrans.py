"""L'écran de hall : appairage RFC 8628, ce qu'il montre, son retrait (#2770).

Les routes passent par la VRAIE authentification (`aides_http`) : le conseil confirme
par sa session, l'écran lit par `Authorization: Bearer`. Ce qui est servi à l'écran se
LIT — clés, valeurs, absences (`standards/04` §14) —, jamais le seul 200 : c'est un lieu
lu par tous (`standards/03` §2 bis).
"""

from __future__ import annotations

import json
from datetime import timedelta

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, select

from app.auth.appairage_ecran import DEMANDES_EN_COURS_MAX, INTERVALLE, purger_demandes
from app.auth.empreinte_jeton import est_empreinte
from app.auth.jetons_appareil import PORTEES
from app.main import app
from app.models.annonce_hall import AnnonceHall
from app.models.core import RoleUtilisateur
from app.models.ecrans import AppairageEcran, Ecran
from app.utils import horloge
from tests.aides_appareils import jeton_d_ecran
from tests.aides_base import compte
from tests.aides_http import base_http, client_http

CS = RoleUtilisateur.conseil_syndical
#: Ce qui ne doit JAMAIS paraître dans le hall : l'auteur, les destinataires, la trace.
AUTEUR = "Zorglubienne"
DESTINATAIRE = "destinataire@example.com"
#: La liste blanche de ce qu'un écran reçoit d'une affiche — exacte.
CHAMPS_ECRAN = {"id", "titre", "message", "format", "images", "envoyee_le", "creee_le"}


@pytest.fixture()
def moteur(batiments):
    with base_http() as m:
        yield m


@pytest.fixture()
def bat(batiments):
    """Les codes de périmètre des deux premiers bâtiments."""
    return f"bat:{batiments[0]}", f"bat:{batiments[1]}"


def _ecran(moteur, brut: str) -> TestClient:
    return TestClient(app, headers={"Authorization": f"Bearer {brut}"})


def _affiche(moteur, titre: str, perimetres: list[str] | str, **champs) -> int:
    with Session(moteur) as s:
        auteur = compte(s, prefixe="auteur", nom=AUTEUR, prenom="Test")
        a = AnnonceHall(
            titre=titre,
            message='<p>Coupure <b>d\'eau</b></p><script>alert(1)</script><img src=x onerror="alert(2)">',
            perimetre_cible=perimetres if isinstance(perimetres, str) else json.dumps(perimetres),
            destinataires=json.dumps([DESTINATAIRE]),
            auteur_id=auteur.id,
            envoye_le=horloge.maintenant(),
            **champs,
        )
        s.add(a)
        s.commit()
        return a.id


# ── L'appairage ─────────────────────────────────────────────────────────────


def test_l_appairage_rfc_8628_de_bout_en_bout(moteur, bat):
    ecran = TestClient(app)
    demande = ecran.post("/ecrans/appairage")
    assert demande.status_code == 200
    corps = demande.json()
    #  Rien sur l'installation : les deux codes, la durée, l'intervalle — et rien d'autre.
    assert set(corps) == {"code_appareil", "code_court", "expire_dans", "intervalle"}
    assert corps["intervalle"] == INTERVALLE and corps["expire_dans"] == 600
    interroger = {"code_appareil": corps["code_appareil"]}
    #  Avant le geste du conseil : en attente ; trop tôt ensuite : ralentir.
    r = ecran.post("/ecrans/appairage/jeton", json=interroger)
    assert (r.status_code, r.json()["detail"]) == (400, "en_attente")
    r = ecran.post("/ecrans/appairage/jeton", json=interroger)
    assert (r.status_code, r.json()["detail"]) == (400, "ralentir")
    #  Le conseil confirme — le code court se saisit sans tiret, en minuscules.
    conseil, _ = client_http(moteur, CS)
    saisi = corps["code_court"].replace("-", "").lower()
    r = conseil.post(
        "/ecrans", json={"code_court": saisi, "nom": "Hall bât. 2", "perimetre": bat[1]}
    )
    assert r.status_code == 201 and r.json()["nom"] == "Hall bât. 2"
    #  Une seconde confirmation du même code ne vaut rien.
    r = conseil.post("/ecrans", json={"code_court": saisi, "nom": "Autre", "perimetre": bat[0]})
    assert r.status_code == 404
    with Session(moteur) as s:
        d = s.exec(select(AppairageEcran)).one()
        d.interroge_le = horloge.maintenant() - timedelta(minutes=1)
        s.add(d)
        s.commit()
    r = ecran.post("/ecrans/appairage/jeton", json=interroger)
    assert r.status_code == 200, r.text
    jeton = r.json()["jeton"]
    assert _ecran(moteur, jeton).get("/ecrans/moi/affiches").status_code == 200
    #  Le jeton n'est rendu qu'une fois : la demande a disparu.
    r = ecran.post("/ecrans/appairage/jeton", json=interroger)
    assert (r.status_code, r.json()["detail"]) == (400, "inconnu")
    #  Rien en clair : les codes et le jeton ne vivent que par leur empreinte.
    with Session(moteur) as s:
        (e,) = s.exec(select(Ecran)).all()
        assert est_empreinte(e.empreinte) and e.empreinte != jeton
        assert s.exec(select(AppairageEcran)).all() == []


def test_seul_le_conseil_confirme_un_code_et_un_code_faux_ne_dit_rien(moteur, bat):
    code = TestClient(app).post("/ecrans/appairage").json()["code_court"]
    resident, _ = client_http(moteur, RoleUtilisateur.propriétaire)
    corps = {"code_court": code, "nom": "Hall", "perimetre": bat[0]}
    assert resident.post("/ecrans", json=corps).status_code == 403
    assert TestClient(app).post("/ecrans", json=corps).status_code == 401
    conseil, _ = client_http(moteur, CS)
    assert conseil.post("/ecrans", json={**corps, "code_court": "BBBB-BBBB"}).status_code == 404
    assert conseil.post("/ecrans", json={**corps, "perimetre": "nulle-part"}).status_code == 422


def test_une_demande_echue_ne_se_confirme_plus_et_se_purge(moteur, bat):
    code = TestClient(app).post("/ecrans/appairage").json()["code_court"]
    with Session(moteur) as s:
        d = s.exec(select(AppairageEcran)).one()
        d.expire_le = horloge.maintenant() - timedelta(seconds=1)
        s.add(d)
        s.commit()
    conseil, _ = client_http(moteur, CS)
    corps = {"code_court": code, "nom": "Hall", "perimetre": bat[0]}
    assert conseil.post("/ecrans", json=corps).status_code == 404
    with Session(moteur) as s:
        assert purger_demandes(s, horloge.maintenant()) == 1


def test_les_demandes_anonymes_sont_plafonnees(moteur):
    with Session(moteur) as s:
        for i in range(DEMANDES_EN_COURS_MAX):
            s.add(
                AppairageEcran(
                    empreinte_code_appareil=f"a{i}",
                    empreinte_code_court=f"c{i}",
                    expire_le=horloge.maintenant() + timedelta(minutes=5),
                )
            )
        s.commit()
    assert TestClient(app).post("/ecrans/appairage").status_code == 429


# ── Ce que l'écran montre — lu, pas supposé ─────────────────────────────────


def test_l_ecran_ne_recoit_que_les_affiches_de_son_perimetre_et_rien_de_personnel(moteur, bat):
    pour_tous = _affiche(moteur, "Coupure d'eau", ["résidence"])
    pour_son_bat = _affiche(moteur, "Ascenseur", [bat[1]])
    _affiche(moteur, "Autre bâtiment", [bat[0]])
    _affiche(moteur, "Sous son bâtiment", [f"{bat[1]}/toit"])
    _affiche(moteur, "Archivée", ["résidence"], archivee=True)
    _affiche(moteur, "Illisible", "pas du json")
    ecran = _ecran(moteur, jeton_d_ecran(moteur, perimetre=bat[1]))
    r = ecran.get("/ecrans/moi/affiches")
    assert r.status_code == 200
    recues = r.json()
    assert sorted(a["id"] for a in recues) == sorted([pour_tous, pour_son_bat]), recues
    for a in recues:
        assert set(a) == CHAMPS_ECRAN, a
        #  Le message est assaini par le serveur ; le texte reste.
        assert "<script" not in a["message"] and "onerror" not in a["message"]
        assert "Coupure" in a["message"] and "<b>" in a["message"]
    brut = r.text
    for interdit in (AUTEUR, DESTINATAIRE, "destinataires", "auteur", "peut_"):
        assert interdit not in brut, f"« {interdit} » servi à l'écran du hall"


def test_l_ecran_lit_les_images_de_ses_affiches_et_aucune_autre(moteur, bat, disque_jetable):
    (disque_jetable / "annonces").mkdir()
    (disque_jetable / "annonces" / "photo.jpg").write_bytes(b"\xff\xd8\xff\xe0jpeg")
    (disque_jetable / "annonces" / "note.txt").write_text("secret")
    images = json.dumps(["/uploads/annonces/photo.jpg", "/uploads/annonces/note.txt"])
    visible = _affiche(moteur, "Visible", [bat[1]], images_json=images)
    cachee = _affiche(moteur, "Ailleurs", [bat[0]], images_json=images)
    ecran = _ecran(moteur, jeton_d_ecran(moteur, perimetre=bat[1]))
    (lue,) = ecran.get("/ecrans/moi/affiches").json()
    assert lue["images"] == [
        f"/ecrans/moi/affiches/{visible}/images/0",
        f"/ecrans/moi/affiches/{visible}/images/1",
    ]
    r = ecran.get(lue["images"][0])
    assert r.status_code == 200 and r.content == b"\xff\xd8\xff\xe0jpeg"
    assert r.headers["content-type"].startswith("image/")
    #  Un fichier qui n'est pas une image, une affiche d'ailleurs, un rang hors liste : 404.
    assert ecran.get(lue["images"][1]).status_code == 404
    assert ecran.get(f"/ecrans/moi/affiches/{cachee}/images/0").status_code == 404
    assert ecran.get(f"/ecrans/moi/affiches/{visible}/images/7").status_code == 404


# ── Le conseil voit, retire ; le jeton suit ─────────────────────────────────


def test_le_conseil_voit_la_derniere_lecture_et_retire_l_ecran(moteur, bat):
    brut = jeton_d_ecran(moteur, perimetre=bat[1], nom="Hall B")
    conseil, _ = client_http(moteur, CS)
    (avant,) = conseil.get("/ecrans").json()
    assert avant["vu_le"] is None and avant["nom"] == "Hall B" and "jeton" not in avant
    assert "empreinte" not in avant and avant["echu"] is False
    assert _ecran(moteur, brut).get("/ecrans/moi/affiches").status_code == 200
    (apres,) = conseil.get("/ecrans").json()
    assert apres["vu_le"] is not None
    resident, _ = client_http(moteur, RoleUtilisateur.propriétaire)
    assert resident.get("/ecrans").status_code == 403
    assert resident.delete(f"/ecrans/{apres['id']}").status_code == 403
    assert conseil.delete(f"/ecrans/{apres['id']}").status_code == 204
    assert _ecran(moteur, brut).get("/ecrans/moi/affiches").status_code == 401
    assert conseil.get("/ecrans").json() == []


def test_l_echeance_est_glissante_et_un_ecran_echu_ne_lit_plus(moteur, bat):
    brut = jeton_d_ecran(moteur, perimetre=bat[1])
    with Session(moteur) as s:
        e = s.exec(select(Ecran)).one()
        e.expire_le = horloge.maintenant() + timedelta(days=1)
        s.add(e)
        s.commit()
    assert _ecran(moteur, brut).get("/ecrans/moi/affiches").status_code == 200
    duree = PORTEES["ecran"].duree
    with Session(moteur) as s:
        e = s.exec(select(Ecran)).one()
        assert duree - timedelta(minutes=1) < e.expire_le - horloge.maintenant() <= duree
        e.expire_le = horloge.maintenant() - timedelta(seconds=1)
        s.add(e)
        s.commit()
    assert _ecran(moteur, brut).get("/ecrans/moi/affiches").status_code == 401
    conseil, _ = client_http(moteur, CS)
    (lu,) = conseil.get("/ecrans").json()
    assert lu["echu"] is True
