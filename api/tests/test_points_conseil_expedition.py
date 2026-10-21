"""Le point CS / Syndic, ce que #2082 y ajoute côté document — par les routes des
deux routeurs et leurs schémas (`points_conseil_schemas`).

Ce qui est tenu :
- **les révisions** : « Terminer » envoie la révision 1 ; un CR corrigé ensuite
  est « Modifié en révision 2 » — à l'écran, au courriel, sur la page de relecture ;
- **la dérogation** : l'administrateur seul valide POUR un présent, avec son
  accord écrit ; cet accord ne suspend pas les 7 jours ; le dernier accord valide ;
- **l'expédition** : validé, le PDF est RANGÉ (dossier privé) et part en pièce
  jointe aux présents joignables — jamais à l'invité ; le PDF servi est le rangé ;
- **l'aperçu** : à tout instant, pour le conseil seul ;
- **l'historique** : les points validés du mode ;
- **le document** : dans l'ordre arbitré — graphiques, le point et ses
  validations, la liste à traiter, puis le CR —, tout texte échappé.
"""

from __future__ import annotations

import pytest
from sqlmodel import Session, select

from app.models.core import RoleUtilisateur, Utilisateur
from app.models.points_conseil import PointConseil, PresentPoint
from app.utils.points_conseil_expedition import destinataires_du_pdf, document
from app.utils.points_conseil_pdf import html_compte_rendu
from app.utils.points_conseil_validation import auto_valider, etat_validation
from app.utils.stockage import DOSSIER_PRIVE, stockage
from tests.aides_http import base_http, client_http
from tests.aides_points_conseil import intercepter_envois, liens, point_termine


@pytest.fixture(name="moteur")
def moteur_fixture():
    with base_http() as moteur:
        yield moteur


@pytest.fixture(name="envois")
def envois_fixture(monkeypatch, disque_jetable):
    return intercepter_envois(monkeypatch)


def _cr(cs) -> dict:
    return cs.get("/points-conseil/courant?mode=affaires").json()["compte_rendu"]


def _destinataires(moteur, point: int) -> list[PresentPoint]:
    with Session(moteur) as s:
        presents = s.exec(select(PresentPoint).where(PresentPoint.point_id == point)).all()
        return [p for p in presents if p.jeton_empreinte]


# ── Les révisions ───────────────────────────────────────────────────────────


def test_un_cr_corrige_apres_l_envoi_est_modifie_en_revision_2(moteur, envois):
    cs, _ = client_http(moteur, RoleUtilisateur.conseil_syndical)
    point, t, _ = point_termine(moteur, cs)
    assert _cr(cs)["revision"] == 1
    assert [a["marque"] for a in _cr(cs)["abordees"]] == [None]
    cs.put(f"/points-conseil/{point}/affaires/{t}", json={"contenu": "<p>Corrigé</p>"})
    assert _cr(cs)["revision"] == 2, "la prochaine révision, déjà marquée"
    assert [a["marque"] for a in _cr(cs)["abordees"]] == ["Modifié en révision 2"]
    envois.clear()
    assert cs.post(f"/points-conseil/{point}/renvoyer").status_code == 200
    assert envois[0]["affaires"][0]["marque"] == " — Modifié en révision 2"
    anonyme, _ = client_http(moteur, None)
    lu = anonyme.get(f"/points-conseil/lien/{liens(envois)[0]}").json()
    assert lu["revision"] == 2 and lu["abordees"][0]["marque"] == "Modifié en révision 2"


# ── La dérogation ───────────────────────────────────────────────────────────


def test_la_derogation_est_reservee_a_l_administrateur(moteur, envois):
    cs, _ = client_http(moteur, RoleUtilisateur.conseil_syndical)
    point, _, _ = point_termine(moteur, cs)
    present = _destinataires(moteur, point)[0].id
    chemin = f"/points-conseil/{point}/presents/{present}/derogation"
    assert cs.post(chemin, json={}).status_code == 403


def test_l_accord_ecrit_valide_sans_suspendre_et_le_dernier_valide_le_cr(moteur, envois):
    cs, _ = client_http(moteur, RoleUtilisateur.conseil_syndical)
    admin, _ = client_http(moteur, RoleUtilisateur.admin)
    point, _, _ = point_termine(moteur, cs)
    premier, second = (p.id for p in _destinataires(moteur, point))
    r = admin.post(
        f"/points-conseil/{point}/presents/{premier}/derogation",
        json={"commentaire": "Accord donné par téléphone."},
    )
    assert r.status_code == 204, r.text
    cr = _cr(cs)
    assert cr["validation"]["suspendue"] is False, "un accord n'est pas une objection"
    assert cr["commentaires"][0]["par_derogation"] is True
    assert [p["par_derogation"] for p in cr["presents"] if p["destinataire"]] == [True, False]
    assert (
        admin.post(f"/points-conseil/{point}/presents/{premier}/derogation", json={}).status_code
        == 409
    )
    envois.clear()
    admin.post(f"/points-conseil/{point}/presents/{second}/derogation", json={})
    with Session(moteur) as s:
        assert s.get(PointConseil, point).etat == "valide"
    assert {e["code"] for e in envois} == {"point_conseil_valide"}


# ── L'expédition ────────────────────────────────────────────────────────────


def test_valide_le_pdf_est_range_et_part_aux_presents_copie_au_conseil(moteur, envois):
    """« Le CR une fois validé doit être envoyé aux présents, copie tout le CS »
    (21/10/2026) : UN courriel, jamais à l'invité, le conseil en copie."""
    cs, ident_cs = client_http(moteur, RoleUtilisateur.conseil_syndical)
    point, _, adresse_cs = point_termine(moteur, cs)
    envois.clear()
    assert cs.post(f"/points-conseil/{point}/valider").status_code == 204
    with Session(moteur) as s:
        p = s.get(PointConseil, point)
        assert p.pdf_cle and p.pdf_cle.startswith(f"{DOSSIER_PRIVE}/")
        assert stockage().lire(p.pdf_cle) == b"%PDF-1.4 essai"
    (envoi,) = envois
    assert sorted(envoi["to"]) == sorted([adresse_cs, "gestion@exemple.test"])
    with Session(moteur) as s:
        adresse_conseil = s.get(Utilisateur, ident_cs).email
    assert adresse_conseil in envoi["cc"] and adresse_cs not in envoi["cc"]
    assert envoi["pieces"] and envoi["pieces"][0].endswith(".pdf")
    servi = cs.post(f"/points-conseil/{point}/pdf")
    assert servi.status_code == 200 and servi.content == b"%PDF-1.4 essai"


def test_valide_d_office_le_pdf_part_aussi(moteur, envois):
    cs, _ = client_http(moteur, RoleUtilisateur.conseil_syndical)
    point, _, _ = point_termine(moteur, cs)
    with Session(moteur) as s:
        p = s.get(PointConseil, point)
        p.envoye_le = p.envoye_le.replace(year=p.envoye_le.year - 1)
        s.add(p)
        s.commit()
    envois.clear()
    with Session(moteur) as s:
        assert auto_valider(s) == 1
        assert s.get(PointConseil, point).pdf_cle
    assert {e["code"] for e in envois} == {"point_conseil_valide"}


# ── L'aperçu et l'historique ────────────────────────────────────────────────


def test_l_apercu_a_tout_instant_pour_le_conseil_seul(moteur, envois):
    cs, _ = client_http(moteur, RoleUtilisateur.conseil_syndical)
    point = cs.post(
        "/points-conseil", json={"mode": "affaires", "debut": "2026-10-19T17:00:00"}
    ).json()["point"]["id"]
    assert cs.post(f"/points-conseil/{point}/apercu").status_code == 200
    resident, _ = client_http(moteur, RoleUtilisateur.résident)
    assert resident.post(f"/points-conseil/{point}/apercu").status_code == 403


def test_l_historique_liste_les_points_valides_du_mode(moteur, envois):
    cs, _ = client_http(moteur, RoleUtilisateur.conseil_syndical)
    point, _, _ = point_termine(moteur, cs)
    assert cs.get("/points-conseil/historique?mode=affaires").json() == []
    cs.post(f"/points-conseil/{point}/valider")
    (h,) = cs.get("/points-conseil/historique?mode=affaires").json()
    assert (h["id"], h["abordees"], h["pdf_range"]) == (point, 1, True)
    assert cs.get("/points-conseil/historique?mode=entretien").json() == []


# ── Le document ─────────────────────────────────────────────────────────────


def test_le_document_suit_l_ordre_arbitre_et_marque_le_projet(moteur, envois):
    cs, _ = client_http(moteur, RoleUtilisateur.conseil_syndical)
    point, _, _ = point_termine(moteur, cs, etat_cible="résolu", conseil_seul=True)
    with Session(moteur) as s:
        p = s.get(PointConseil, point)
        html = html_compte_rendu(document(s, p, None, projet=True), site_nom="R", logo_png=None)
        assert etat_validation(p, [], []).echeance is not None
    #  La maquette B (#2089) : le point et ses validations, la tête du rapport,
    #  puis chaque affaire abordée — son résumé d'origine, puis son CR.
    reperes = [
        html.index("Le point"),
        html.index("Validations"),
        html.index("Par catégorie"),
        html.index("Les affaires · "),
        html.index("La platine ne sonne"),
        html.index("Devis attendu"),
        html.index("Non abordées"),
    ]
    assert reperes == sorted(reperes)
    assert "Projet — révision 1" in html
    assert "(CS et présents)" in html
    assert "État à la validation : Ouvert → Résolu" in html
    assert "Oubliée" in html, "les non abordées se citent à la fin"
    assert "Chez le syndic" in html or "Ouvert" in html, "l'état de suivi en vignette"


def test_la_copie_au_conseil_ne_double_pas_un_present():
    a, copie = destinataires_du_pdf(
        ["Reine@exemple.test", None, "syndic@exemple.test"],
        [(1, "reine@exemple.test"), (2, "jean@exemple.test")],
    )
    assert [e for _, e in a] == ["Reine@exemple.test", "syndic@exemple.test"]
    assert copie == [(2, "jean@exemple.test")]
