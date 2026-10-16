"""Le rapport « Suivi des affaires » du Reporting CS (16/10/2026, maquette D2).

Ce qui est tenu :
- **qui entre** : toute affaire ni résolue ni annulée — plus seulement celles
  suivies au kanban —, jamais une actualité ;
- **la porte** : le conseil et l'administration, pas un résident ;
- **l'ancienneté** et ses deux seuils ;
- **la synthèse** : aucun nom de personne ne part au modèle, la réponse est du
  texte borné, et le PDF échappe tout ce qu'il reçoit.
"""

from __future__ import annotations

import json
from datetime import timedelta
from types import SimpleNamespace

import pytest
from sqlmodel import Session

from app.models.core import RoleUtilisateur
from app.models.tickets import Ticket
from app.utils import horloge
from app.utils.description_format import ReponseIllisible
from app.utils.suivi_affaires import synthese as module_synthese
from app.utils.suivi_affaires.format import construire_message, lire_reponse
from app.utils.suivi_affaires.pdf import html_rapport
from app.utils.suivi_affaires.releve import Releve, lire_affaire, tranche
from app.utils.suivi_affaires.synthese import Synthese, message_du_releve
from tests.aides_base import compte
from tests.aides_http import base_http, client_http
from tests.aides_pdf import besoin_weasyprint

_numero = [0]


@pytest.fixture(name="moteur")
def moteur_fixture():
    with base_http() as moteur:
        yield moteur


def _affaire(moteur, titre="Interphone muet", *, jours=0, **champs) -> int:
    _numero[0] += 1
    champs.setdefault("categorie", "panne")
    champs.setdefault("statut", "ouvert")
    champs.setdefault("perimetre_cible", json.dumps(["résidence"], ensure_ascii=False))
    with Session(moteur) as s:
        auteur = compte(s, prefixe="auteur", nom="Durand", prenom="Reine")
        t = Ticket(
            numero=f"S-{_numero[0]:04d}",
            titre=titre,
            description="<p>La platine ne sonne <strong>plus</strong>.</p>",
            auteur_id=auteur.id,
            cree_le=horloge.maintenant() - timedelta(days=jours),
            **champs,
        )
        s.add(t)
        s.commit()
        return t.id


# ── La porte ────────────────────────────────────────────────────────────────


@pytest.mark.parametrize("methode,route", [("get", ""), ("post", "/synthese"), ("post", "/pdf")])
def test_un_resident_est_refuse(moteur, methode, route):
    http, _ = client_http(moteur, RoleUtilisateur.propriétaire)
    reponse = getattr(http, methode)(
        f"/suivi-affaires{route}", **({"json": {}} if methode == "post" else {})
    )
    assert reponse.status_code == 403


def test_un_anonyme_est_refuse(moteur):
    http, _ = client_http(moteur, None)
    assert http.get("/suivi-affaires").status_code == 401


# ── Qui entre au rapport ────────────────────────────────────────────────────


def test_toutes_les_affaires_non_closes_et_elles_seules(moteur):
    ouverte = _affaire(moteur, "Ouverte", jours=5)
    suivie = _affaire(moteur, "Chez le prestataire", statut="chez_prestataire", suivi_kanban=True)
    non_suivie = _affaire(moteur, "À l'AG", statut="en_ag", categorie="etude_travaux", jours=200)
    _affaire(moteur, "Résolue", statut="résolu")
    _affaire(moteur, "Annulée", statut="annulé")
    _affaire(moteur, "Actualité", statut="publie", categorie="actualite")
    http, _ = client_http(moteur, RoleUtilisateur.conseil_syndical)

    corps = http.get("/suivi-affaires").json()

    assert corps["total"] == 3
    assert [a["id"] for a in corps["affaires"]] == [non_suivie, ouverte, suivie]
    assert corps["anciennes"] == 1
    assert corps["par_categorie"] == [
        {"categorie": "panne", "libelle": "Panne", "nombre": 2},
        {"categorie": "etude_travaux", "libelle": "Étude & travaux", "nombre": 1},
    ]
    premiere = corps["affaires"][0]
    assert premiere["anciennete"] == "ancienne"
    assert premiere["age_jours"] == 200
    #  Le descriptif est du TEXTE : l'écran ne fait aucun `{@html}`.
    assert premiere["descriptif"] == "La platine ne sonne plus ."
    assert "synthese_disponible" in corps


def test_aucune_affaire_ouverte(moteur):
    http, _ = client_http(moteur, RoleUtilisateur.admin)
    corps = http.get("/suivi-affaires").json()
    assert corps["total"] == 0 and corps["affaires"] == [] and corps["par_categorie"] == []


@pytest.mark.parametrize(
    "age,attendue",
    [(0, "recente"), (30, "recente"), (31, "moyenne"), (90, "moyenne"), (91, "ancienne")],
)
def test_les_seuils_d_anciennete(age, attendue):
    assert tranche(age) == attendue


# ── La synthèse ─────────────────────────────────────────────────────────────


def _releve() -> Releve:
    jour = horloge.aujourd_hui()
    t = Ticket(
        id=7,
        numero="S-7",
        titre="Fuite colonne B",
        description="<p>Plombier mandaté.</p>",
        categorie="panne",
        statut="en_cours",
        cree_le=horloge.maintenant() - timedelta(days=40),
    )
    return Releve(jour=jour, affaires=[lire_affaire(t, jour, {"en_cours": "Chez le syndic"})])


def test_le_message_porte_dates_et_etat_jamais_un_nom(moteur, monkeypatch):
    _affaire(moteur, "Interphone muet", jours=12)
    http, _ = client_http(moteur, RoleUtilisateur.conseil_syndical)
    envoye: dict = {}

    async def faux_demander(session, *, usage, consigne, message, demandeur):
        envoye.update(usage=usage, consigne=consigne, message=message)
        return SimpleNamespace(
            texte='{"resume": "Une panne ouverte.", "points": ["Relancer le syndic", 3, ""]}'
        )

    monkeypatch.setattr(module_synthese, "demander", faux_demander)
    reponse = http.post("/suivi-affaires/synthese")

    assert reponse.status_code == 200, reponse.text
    assert reponse.json() == {"resume": "Une panne ouverte.", "points": ["Relancer le syndic"]}
    assert envoye["usage"] == "synthese_affaires_en_cours"
    assert "Interphone muet" in envoye["message"] and "(12 jours)" in envoye["message"]
    assert "Durand" not in envoye["message"] and "Reine" not in envoye["message"]
    assert "JSON" in envoye["consigne"]


def test_sans_affaire_la_synthese_le_dit(moteur):
    http, _ = client_http(moteur, RoleUtilisateur.conseil_syndical)
    reponse = http.post("/suivi-affaires/synthese")
    assert reponse.status_code == 400
    assert "Aucune affaire" in reponse.json()["detail"]


def test_le_message_du_releve():
    message = message_du_releve(_releve())
    assert "[Panne] « Fuite colonne B »" in message
    assert "(40 jours), état : Chez le syndic." in message
    assert "Descriptif : Plombier mandaté." in message


def test_le_message_se_borne_aux_plus_anciennes():
    affaires = [
        {
            "libelle_categorie": "Panne",
            "titre": f"A{i}",
            "ouverte_le": "01/01/2026",
            "age_jours": 1,
            "libelle_statut": "Ouvert",
            "descriptif": "",
        }
        for i in range(160)
    ]
    message = construire_message("16/10/2026", affaires)
    assert "Affaires ouvertes : 160." in message
    assert "« A149 »" in message and "« A150 »" not in message


def test_une_reponse_sans_resume_est_illisible():
    with pytest.raises(ReponseIllisible):
        lire_reponse('{"points": ["x"]}')


# ── Le PDF ──────────────────────────────────────────────────────────────────


def test_le_pdf_echappe_tout_ce_qu_il_recoit():
    r = _releve()
    html = html_rapport(
        r,
        Synthese(resume="<script>alert(1)</script>", points=["<b>gras</b>"]),
        site_nom="Résidence <Test>",
        logo_png=None,
    )
    assert "<script>" not in html and "&lt;script&gt;" in html
    assert "&lt;b&gt;gras&lt;/b&gt;" in html
    assert "Résidence &lt;Test&gt;" in html
    assert "Fuite colonne B" in html and "Par catégorie" in html
    assert "line-clamp: 10" in html


def test_le_pdf_sans_synthese_n_en_porte_pas():
    html = html_rapport(_releve(), None, site_nom="Résidence", logo_png=None)
    assert "Synthèse de l'assistant" not in html


@besoin_weasyprint
def test_l_export_rend_un_pdf(moteur):
    _affaire(moteur, "Interphone muet", jours=3)
    http, _ = client_http(moteur, RoleUtilisateur.conseil_syndical)
    reponse = http.post(
        "/suivi-affaires/pdf", json={"synthese": {"resume": "Une panne.", "points": ["Relancer"]}}
    )
    assert reponse.status_code == 200
    assert reponse.headers["content-type"] == "application/pdf"
    assert reponse.content.startswith(b"%PDF")
    assert "suivi-des-affaires-" in reponse.headers["content-disposition"]
