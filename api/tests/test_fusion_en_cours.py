"""Les affaires liées du Suivi des affaires : rassemblées, fusionnées, ou écartées (#2083)
— par les routes de `suivi_affaires_fusions`.

Ce qui est tenu :
- **rassembler** : un groupe prend la place de sa plus ancienne, les autres la
  suivent ; une chaîne A–B–C forme UN groupe ; un lien écarté ne rassemble plus ;
- **fusionner** : la plus ancienne absorbe, reste ouverte, prend le titre et la
  description relus ; une Suite le dit ; l'absorbée quitte le relevé et se cite
  sous la principale ; une chaîne se fusionne d'un geste ;
- **écarter** : le tri par ancienneté reprend, une Suite dans chaque affaire, et
  la clôture ne propose plus la fusion ;
- **la proposition** : sans assistant prêt, elle se compose sans lui ;
- **les droits** : le conseil seul.
"""

from __future__ import annotations

import pytest
from sqlmodel import Session, select

from app.models.affaires_liees import AffaireLiee
from app.models.core import RoleUtilisateur
from app.models.tickets import Ticket, TicketEvolution
from app.utils.fusion_affaires import candidates
from app.utils.fusion_en_cours import composantes, ordonner
from app.utils.fusion_en_cours_ia import en_paragraphes
from tests.aides_http import base_http, client_http
from tests.aides_suivi import affaire_ouverte


@pytest.fixture(name="moteur")
def moteur_fixture():
    with base_http() as moteur:
        yield moteur


def _lier(moteur, a: int, b: int) -> None:
    with Session(moteur) as s:
        x, y = sorted((a, b))
        s.add(AffaireLiee(affaire_id=x, liee_id=y))
        s.commit()


def _titres(cs) -> list[str]:
    return [a["titre"] for a in cs.get("/suivi-affaires").json()["affaires"]]


class _A:
    def __init__(self, i):
        self.id = i


# ── Rassembler ──────────────────────────────────────────────────────────────


def test_une_chaine_forme_un_seul_groupe_et_suit_sa_plus_ancienne():
    ids = [1, 2, 3, 4, 5]
    groupe = composantes([(1, 4), (4, 5)], ids)
    assert groupe == {1: 1, 4: 1, 5: 1}
    assert [a.id for a in ordonner([_A(i) for i in ids], groupe)] == [1, 4, 5, 2, 3]


def test_le_suivi_rassemble_les_affaires_liees(moteur):
    cs, _ = client_http(moteur, RoleUtilisateur.conseil_syndical)
    vieille = affaire_ouverte(moteur, "Fuite toiture", jours=60)
    affaire_ouverte(moteur, "Interphone", jours=40)
    recente = affaire_ouverte(moteur, "Tache plafond 5e", jours=5)
    _lier(moteur, vieille, recente)
    assert _titres(cs) == ["Fuite toiture", "Tache plafond 5e", "Interphone"]
    groupes = {a["titre"]: a["groupe"] for a in cs.get("/suivi-affaires").json()["affaires"]}
    assert groupes == {"Fuite toiture": vieille, "Tache plafond 5e": vieille, "Interphone": None}


# ── Fusionner ───────────────────────────────────────────────────────────────


def test_la_plus_ancienne_absorbe_et_reste_ouverte(moteur):
    cs, _ = client_http(moteur, RoleUtilisateur.conseil_syndical)
    vieille = affaire_ouverte(moteur, "Fuite toiture", jours=60, statut="en_cours")
    recente = affaire_ouverte(moteur, "Tache plafond 5e", jours=5)
    _lier(moteur, vieille, recente)
    r = cs.post(
        "/suivi-affaires/fusions",
        json={
            "ids": [recente, vieille],
            "titre": "Infiltrations toiture et 5e",
            "description": "<p>Une seule cause.</p>",
        },
    )
    assert r.status_code == 200, r.text
    assert r.json() == {"principale_id": vieille, "absorbees": [recente]}
    with Session(moteur) as s:
        p, a = s.get(Ticket, vieille), s.get(Ticket, recente)
        assert (p.titre, p.description, p.statut) == (
            "Infiltrations toiture et 5e",
            "<p>Une seule cause.</p>",
            "en_cours",
        )
        assert a.fusionnee_dans_id == vieille
        suites = s.exec(select(TicketEvolution).where(TicketEvolution.ticket_id == vieille)).all()
        assert any(
            "🔀 Fusion" in (e.contenu or "") and "Fuite toiture" in e.contenu for e in suites
        )
    (seule,) = cs.get("/suivi-affaires").json()["affaires"]
    assert seule["id"] == vieille and seule["fusionnees"][0].endswith("Tache plafond 5e")


def test_l_absorbee_quitte_la_liste_et_se_dit_fusionnee_la_principale_reste(moteur):
    """🔀 L'absorbée hérite de « Chez le syndic » : sans cela, deux cartes se
    lisaient comme deux affaires, et la correction de la principale offrait
    « Fusionner » sur une liée déjà absorbée (#2186, arbitré le 23/10/2026)."""
    cs, _ = client_http(moteur, RoleUtilisateur.conseil_syndical)
    vieille = affaire_ouverte(moteur, "Contrat incendie", jours=60, statut="en_cours")
    recente = affaire_ouverte(moteur, "Dénonciation du contrat", jours=5)
    _lier(moteur, vieille, recente)
    r = cs.post("/suivi-affaires/fusions", json={"ids": [vieille, recente], "titre": "Incendie"})
    assert r.status_code == 200, r.text
    lues = {t["id"]: t for t in cs.get("/tickets").json()}
    assert lues[recente]["archivee"] and lues[recente]["fusionnee"]
    assert not lues[vieille]["archivee"]
    (liee,) = lues[vieille]["affaires_liees"]
    assert (liee["id"], liee["fusionnee"]) == (recente, True)
    #  Plus rien à fusionner : la candidate absorbée n'est plus proposée.
    assert cs.get(f"/tickets/{vieille}/fusion").json() == []


def test_une_chaine_se_fusionne_d_un_geste(moteur):
    cs, _ = client_http(moteur, RoleUtilisateur.conseil_syndical)
    a = affaire_ouverte(moteur, "A", jours=30)
    b = affaire_ouverte(moteur, "B", jours=20)
    c = affaire_ouverte(moteur, "C", jours=10)
    _lier(moteur, a, b)
    _lier(moteur, b, c)
    r = cs.post("/suivi-affaires/fusions", json={"ids": [a, b, c], "titre": "ABC"})
    assert r.status_code == 200, r.text
    assert sorted(r.json()["absorbees"]) == [b, c]


def test_des_affaires_sans_lien_ne_se_fusionnent_pas(moteur):
    cs, _ = client_http(moteur, RoleUtilisateur.conseil_syndical)
    a = affaire_ouverte(moteur, "A", jours=30)
    b = affaire_ouverte(moteur, "B", jours=20)
    assert cs.post("/suivi-affaires/fusions", json={"ids": [a, b], "titre": "x"}).status_code == 422


def test_le_conseil_seul_fusionne(moteur):
    a = affaire_ouverte(moteur, "A", jours=30)
    b = affaire_ouverte(moteur, "B", jours=20)
    _lier(moteur, a, b)
    resident, _ = client_http(moteur, RoleUtilisateur.résident)
    for chemin in ("/suivi-affaires/fusions", "/suivi-affaires/fusions/ecarter"):
        assert resident.post(chemin, json={"ids": [a, b], "titre": "x"}).status_code == 403


# ── Écarter ─────────────────────────────────────────────────────────────────


def test_ecarter_rend_le_tri_et_tait_la_fusion_a_la_cloture(moteur):
    cs, ident = client_http(moteur, RoleUtilisateur.conseil_syndical)
    vieille = affaire_ouverte(moteur, "Fuite toiture", jours=60)
    affaire_ouverte(moteur, "Interphone", jours=40)
    recente = affaire_ouverte(moteur, "Tache plafond 5e", jours=5)
    _lier(moteur, vieille, recente)
    assert (
        cs.post("/suivi-affaires/fusions/ecarter", json={"ids": [vieille, recente]}).status_code
        == 204
    )
    assert _titres(cs) == ["Fuite toiture", "Interphone", "Tache plafond 5e"]
    with Session(moteur) as s:
        for t in (vieille, recente):
            suites = s.exec(select(TicketEvolution).where(TicketEvolution.ticket_id == t)).all()
            assert any("Fusion écartée" in (e.contenu or "") for e in suites)
        from app.models.core import Utilisateur

        assert candidates(s, s.get(Ticket, vieille), s.get(Utilisateur, ident)) == []


# ── La proposition ──────────────────────────────────────────────────────────


def test_sans_assistant_la_proposition_se_compose_sans_lui(moteur):
    cs, _ = client_http(moteur, RoleUtilisateur.conseil_syndical)
    a = affaire_ouverte(moteur, "Fuite toiture", jours=30)
    b = affaire_ouverte(moteur, "Tache plafond", jours=20)
    _lier(moteur, a, b)
    r = cs.post("/suivi-affaires/fusions/proposition", json={"ids": [a, b]})
    assert r.status_code == 200, r.text
    assert r.json()["assiste_ia"] is False
    assert r.json()["titre"] == "Fuite toiture / Tache plafond"


def test_une_reponse_de_l_assistant_est_echappee_en_paragraphes():
    assert en_paragraphes("Un <b>\n\nDeux") == "<p>Un &lt;b&gt;</p><p>Deux</p>"
