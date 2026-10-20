"""La validation du compte rendu d'un point CS / Syndic (#2042).

Ce qui est tenu :
- **l'envoi** : « Terminer » écrit aux présents joignables du CS et du syndic,
  chacun avec SON lien — jamais à un invité ;
- **le lien** (`standards/03` §5 bis) : l'ouvrir deux fois ne valide rien ; un
  jeton inconnu rend 404 ;
- **la validation** : tous les destinataires, ou 7 jours, ou le conseil ; un
  commentaire suspend les 7 jours, un nouvel envoi les refait courir ;
- **ce qu'elle rend lisible, et pas avant** : la rubrique de l'affaire (« CS et
  présents » aux lecteurs du conseil), une entrée au fil pour le CS et le syndic, le PDF ;
- **la correction** après « Terminer » : un CR saisi se corrige, aucun ne s'ajoute.
"""

from __future__ import annotations

from datetime import timedelta

import pytest
from sqlmodel import Session, select

from app.models.core import RoleUtilisateur, StatutUtilisateur
from app.models.points_conseil import CommentairePoint, CompteRenduAffaire, PointConseil
from app.utils import horloge
from app.utils.points_conseil_expedition import document
from app.utils.points_conseil_pdf import html_compte_rendu
from app.utils.points_conseil_validation import auto_valider
from tests.aides_http import base_http, client_http
from tests.aides_points_conseil import intercepter_envois, liens, point_termine


@pytest.fixture(name="moteur")
def moteur_fixture():
    with base_http() as moteur:
        yield moteur


@pytest.fixture(name="envois")
def envois_fixture(monkeypatch):
    return intercepter_envois(monkeypatch)


# ── L'envoi ─────────────────────────────────────────────────────────────────


def test_terminer_ecrit_aux_presents_joignables_jamais_a_l_invite(moteur, envois):
    cs, _ = client_http(moteur, RoleUtilisateur.conseil_syndical)
    point, _, adresse_cs = point_termine(moteur, cs)
    assert sorted(e["to"] for e in envois) == sorted([adresse_cs, "gestion@exemple.test"])
    assert {e["code"] for e in envois} == {"point_conseil_validation"}
    assert len(set(liens(envois))) == 2, "un lien PAR présent"
    #  Les textes partent échappés : le modèle ne l'est pas.
    assert envois[0]["affaires"][0]["texte"] == "Devis attendu"
    cr = cs.get("/points-conseil/courant?mode=affaires").json()["compte_rendu"]
    assert cr["validation"] == {
        "destinataires": 2,
        "valides": 0,
        "suspendue": False,
        "echeance": cr["validation"]["echeance"],
    }
    assert cr["validation"]["echeance"] is not None
    assert [p["destinataire"] for p in cr["presents"]] == [True, True, False]


# ── Le lien ─────────────────────────────────────────────────────────────────


def test_ouvrir_le_lien_deux_fois_ne_valide_rien(moteur, envois):
    cs, _ = client_http(moteur, RoleUtilisateur.conseil_syndical)
    point, _, _ = point_termine(moteur, cs)
    anonyme, _ = client_http(moteur, None)
    lien = f"/points-conseil/lien/{liens(envois)[0]}"
    premiere, seconde = anonyme.get(lien), anonyme.get(lien)
    assert premiere.status_code == seconde.status_code == 200
    assert premiere.json() == seconde.json()
    assert premiere.json()["deja_valide"] is False
    assert premiere.json()["etat"] == "a_valider"
    assert anonyme.get("/points-conseil/lien/inconnu").status_code == 404
    assert anonyme.post("/points-conseil/lien/inconnu/valider").status_code == 404


def test_cs_et_presents_se_lit_des_presents(moteur, envois):
    """« CS et présents » (#2082, ex-« Conseil seul ») : le lien et le courriel le
    montrent aux présents — ils l'ont entendu ; seuls le fil et l'affaire le taisent."""
    cs, _ = client_http(moteur, RoleUtilisateur.conseil_syndical)
    point_termine(moteur, cs, conseil_seul=True)
    anonyme, _ = client_http(moteur, None)
    (lu,) = anonyme.get(f"/points-conseil/lien/{liens(envois)[0]}").json()["abordees"]
    assert lu["conseil_seul"] is True and lu["contenu"]
    assert envois[0]["affaires"][0]["texte"] == "Devis attendu"


# ── La validation ───────────────────────────────────────────────────────────


def test_valide_quand_tous_les_destinataires_ont_valide(moteur, envois):
    cs, _ = client_http(moteur, RoleUtilisateur.conseil_syndical)
    point, _, _ = point_termine(moteur, cs)
    anonyme, _ = client_http(moteur, None)
    premier, second = liens(envois)
    assert anonyme.post(f"/points-conseil/lien/{premier}/valider").json()["deja_valide"]
    #  Idempotent : un second clic ne change rien.
    assert anonyme.post(f"/points-conseil/lien/{premier}/valider").status_code == 200
    assert anonyme.get(f"/points-conseil/lien/{second}").json()["etat"] == "a_valider"
    assert anonyme.post(f"/points-conseil/lien/{second}/valider").json()["etat"] == "valide"


def test_un_commentaire_suspend_les_sept_jours_un_envoi_les_refait_courir(moteur, envois):
    cs, _ = client_http(moteur, RoleUtilisateur.conseil_syndical)
    point, _, _ = point_termine(moteur, cs)
    anonyme, _ = client_http(moteur, None)
    r = anonyme.post(
        f"/points-conseil/lien/{liens(envois)[1]}/commentaire",
        json={"contenu": "Le devis est attendu sous 10 jours, pas 15."},
    )
    assert r.status_code == 200
    cr = cs.get("/points-conseil/courant?mode=affaires").json()["compte_rendu"]
    assert cr["validation"]["suspendue"] and cr["validation"]["echeance"] is None
    assert cr["commentaires"][0]["auteur"] == "Paul BERNARD"  # nom_affiche : le nom en capitales

    _vieillir(moteur, point, jours=8)
    with Session(moteur) as s:
        assert auto_valider(s) == 0, "suspendue : pas de validation d'office"

    assert cs.post(f"/points-conseil/{point}/renvoyer").json() == {"envoyes": 2}
    anciens = liens(envois)[:2]
    assert anonyme.get(f"/points-conseil/lien/{anciens[0]}").status_code == 404
    #  Le nouvel envoi passe APRÈS le commentaire : on recule les deux d'autant.
    with Session(moteur) as s:
        for c in s.exec(select(CommentairePoint)).all():
            c.cree_le = horloge.maintenant() - timedelta(days=9)
            s.add(c)
        s.commit()
    _vieillir(moteur, point, jours=8)
    with Session(moteur) as s:
        assert auto_valider(s) == 1


def _vieillir(moteur, point_id: int, *, jours: int) -> None:
    with Session(moteur) as s:
        p = s.get(PointConseil, point_id)
        p.envoye_le = horloge.maintenant() - timedelta(days=jours)
        s.add(p)
        s.commit()


def test_sept_jours_sans_reponse_valident_d_office(moteur, envois):
    cs, _ = client_http(moteur, RoleUtilisateur.conseil_syndical)
    point, _, _ = point_termine(moteur, cs)
    _vieillir(moteur, point, jours=6)
    with Session(moteur) as s:
        assert auto_valider(s) == 0
    _vieillir(moteur, point, jours=7)
    with Session(moteur) as s:
        assert auto_valider(s) == 1
        assert s.get(PointConseil, point).etat == "valide"


def test_le_conseil_valide_en_l_etat_le_resident_ne_le_peut_pas(moteur, envois):
    cs, _ = client_http(moteur, RoleUtilisateur.conseil_syndical)
    point, _, _ = point_termine(moteur, cs)
    resident, _ = client_http(moteur, RoleUtilisateur.propriétaire)
    assert resident.post(f"/points-conseil/{point}/valider").status_code == 403
    assert cs.post(f"/points-conseil/{point}/valider").status_code == 204
    assert cs.post(f"/points-conseil/{point}/valider").status_code == 409


# ── Ce que la validation rend lisible ───────────────────────────────────────


def test_la_rubrique_de_l_affaire_ne_parait_qu_a_la_validation(moteur, envois):
    cs, _ = client_http(moteur, RoleUtilisateur.conseil_syndical)
    point, t, _ = point_termine(moteur, cs)
    resident, _ = client_http(moteur, RoleUtilisateur.propriétaire)
    assert resident.get(f"/points-conseil/affaires/{t}").json() == []
    cs.post(f"/points-conseil/{point}/valider")
    (cr,) = resident.get(f"/points-conseil/affaires/{t}").json()
    assert cr["contenu"] == "<p>Devis <b>attendu</b></p>"
    #  Rendu privé par le conseil : le résident ne le lit plus, le conseil si.
    assert (
        cs.patch(
            f"/points-conseil/comptes-rendus/{cr['cr_id']}", json={"conseil_seul": True}
        ).status_code
        == 204
    )
    assert resident.get(f"/points-conseil/affaires/{t}").json() == []
    assert len(cs.get(f"/points-conseil/affaires/{t}").json()) == 1


def test_une_seule_entree_au_fil_pour_le_cs_et_le_syndic(moteur, envois):
    cs, _ = client_http(moteur, RoleUtilisateur.conseil_syndical)
    point, _, _ = point_termine(moteur, cs)
    cs.post(f"/points-conseil/{point}/valider")

    def entrees(http):
        return [i for i in http.get("/flux").json()["items"] if i["type"] == "point_conseil"]

    (entree,) = entrees(cs)
    assert entree["lien"] == f"/espace-cs/reporting#point-cs-{point}"
    syndic, _ = client_http(moteur, RoleUtilisateur.externe, statut=StatutUtilisateur.syndic)
    (vue_syndic,) = entrees(syndic)
    assert vue_syndic["lien"] is None, "le Reporting est au conseil seul"
    resident, _ = client_http(moteur, RoleUtilisateur.propriétaire)
    assert entrees(resident) == []


def test_le_pdf_n_existe_qu_une_fois_valide_et_echappe_tout(moteur, envois):
    cs, _ = client_http(moteur, RoleUtilisateur.conseil_syndical)
    point, _, _ = point_termine(moteur, cs, contenu="<p>&lt;script&gt;x&lt;/script&gt;</p>")
    assert cs.post(f"/points-conseil/{point}/pdf").status_code == 409
    with Session(moteur) as s:
        p = s.get(PointConseil, point)
        html = html_compte_rendu(document(s, p, None), site_nom="<Résidence>", logo_png=None)
    assert "<script>" not in html and "&lt;Résidence&gt;" in html


# ── La correction après « Terminer » ────────────────────────────────────────


def test_apres_terminer_un_cr_se_corrige_aucun_ne_s_ajoute(moteur, envois):
    cs, _ = client_http(moteur, RoleUtilisateur.conseil_syndical)
    point, t, _ = point_termine(moteur, cs)
    r = cs.put(f"/points-conseil/{point}/affaires/{t}", json={"contenu": "<p>Corrigé</p>"})
    assert r.status_code == 200, r.text
    assert cs.put(f"/points-conseil/{point}/affaires/{t}", json={"contenu": " "}).status_code == 409
    with Session(moteur) as s:
        autre = s.exec(select(CompteRenduAffaire)).all()
        assert [c.contenu for c in autre] == ["<p>Corrigé</p>"]
    oubliee = cs.get("/points-conseil/courant?mode=affaires").json()["compte_rendu"]
    (nt,) = oubliee["non_traitees"]
    assert (
        cs.put(f"/points-conseil/{point}/affaires/{nt['id']}", json={"contenu": "<p>x</p>"})
    ).status_code == 409
