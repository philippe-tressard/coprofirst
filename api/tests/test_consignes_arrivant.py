"""Les consignes de la fiche arrivant : en base, éditables, rendues échappées (#1727).

Ce que ce fichier tient :

1. 🔴 le garde-fou du ticket — plus aucun nom de rue ni de syndic dans `api/app` :
   ce sont des données de l'instance (migration 0269), pas du produit ;
2. le texte saisi est ÉCHAPPÉ : la fiche est une page HTML servie à tout
   utilisateur connecté, et un HTML libre y serait injecté tel quel ;
3. le nom du syndic se lit dans le contrat, au rendu (`{syndic}`) ;
4. sans saisie, c'est le gabarit générique ; une saisie illisible n'efface pas la fiche ;
5. la porte : le conseil et l'administration lisent et écrivent, le résident non ;
6. la migration recopie le texte de la résidence sous la nouvelle forme ;
7. la phrase d'accueil, sous « Bonjour et bienvenue ! », est éditable elle aussi
   (09/11/2026) : écrite en dur dans la fiche, le conseil ne pouvait pas la corriger.
"""

from __future__ import annotations

import re

import pytest

from app.models.core import ConfigSite, RoleUtilisateur
from app.seed.consignes_arrivant import ACCUEIL_GABARIT, GABARIT
from app.utils.consignes_arrivant import (
    CLE,
    CLE_ACCUEIL,
    MARQUEUR_SITE,
    MARQUEUR_SYNDIC,
    Consigne,
    consignes_en_html,
    enregistrer_consignes,
    lire_accueil,
    lire_consignes,
    texte_en_html,
)
from app.utils.fiche_arrivant import generer_fiche_arrivant
from tests.aides_http import base_http, client_http
from tests.aides_sources import modules_app


#: Les rues de CETTE résidence : des données de l'instance, pas du produit.
RUES_INSTANCE = ("Boulevard Hostachy", "Maurice Berteaux")

#: Le syndic ne se nomme pas — même ici : le dépôt est public, et un nom en dur
#: est exactement ce que le ticket retire. La règle se lit sur la PHRASE :
#: « Demander au syndic » est toujours suivi du marqueur, jamais d'un nom.
_SYNDIC_EN_DUR = re.compile(r"au syndic (?!\{syndic\})[A-Z]")


@pytest.fixture(name="moteur")
def moteur_fixture():
    with base_http() as moteur:
        yield moteur


# ── 1. Le garde-fou ─────────────────────────────────────────────────────────


def _fautes(sources: dict[str, str]) -> list[str]:
    fautes = []
    for nom, texte in sources.items():
        fautes += [f"{nom} : {r}" for r in RUES_INSTANCE if r in texte]
        fautes += [f"{nom} : syndic nommé" for _ in _SYNDIC_EN_DUR.finditer(texte)]
    return fautes


def test_aucun_nom_de_rue_ni_de_syndic_dans_le_code():
    #  `modules_app` lève si la portée est vide : le cas zéro est le sien.
    assert _fautes({m.rel: m.source for m in modules_app(minimum=100)}) == []


def test_temoin_le_balayage_voit_ce_qu_il_refuse():
    #  Si le motif ne trouvait rien ici, le test précédent serait vert sans rien mesurer.
    assert len(_fautes({"témoin": "Demander au syndic Cabinet Témoin. Rue Maurice Berteaux"})) == 2
    assert _fautes({"témoin": "Demander au syndic {syndic} de changer les noms."}) == []


# ── 2 et 3. Le rendu ────────────────────────────────────────────────────────


def test_le_texte_saisi_est_echappe():
    html = texte_en_html('<img src=x onerror="alert(1)"> **gras**', "Syndic")
    assert "<img" not in html
    assert "&lt;img" in html
    assert "<strong>gras</strong>" in html


def test_le_nom_du_syndic_vient_du_contrat_et_s_echappe_aussi():
    html = texte_en_html(f"Demander au syndic {MARQUEUR_SYNDIC}.", "A & <B>")
    assert html == "Demander au syndic A &amp; &lt;B&gt;."
    #  Sans syndic connu, la phrase reste lisible — jamais « None » ni un vide.
    assert "{syndic}" not in texte_en_html(MARQUEUR_SYNDIC, "")


def test_la_fiche_imprime_les_consignes_saisies(session):
    enregistrer_consignes(
        session, [Consigne(titre="Vélos <local>", contenu="Au **sous-sol**, syndic {syndic}.")]
    )
    fiche = generer_fiche_arrivant(
        cs_data={"membres": []},
        syndic_data={"nom_syndic": "", "adresse": "", "membres": []},
        site_nom="Résidence Témoin",
        site_url="https://exemple.fr",
        logo_png=None,
        whatsapp_url=None,
        consignes=consignes_en_html(lire_consignes(session), "Syndic Témoin"),
        annee=2026,
    )
    assert "Vélos &lt;local&gt;" in fiche
    assert "Au <strong>sous-sol</strong>, syndic Syndic Témoin." in fiche


# ── 4. Le repli ─────────────────────────────────────────────────────────────


def test_sans_saisie_c_est_le_gabarit(session):
    lues = lire_consignes(session)
    assert lues.personnalisees is False
    assert [c.model_dump() for c in lues.consignes] == GABARIT


def test_une_saisie_illisible_rend_le_gabarit(session):
    session.add(ConfigSite(cle=CLE, valeur="{pas du json"))
    session.commit()
    assert lire_consignes(session).personnalisees is False


def test_le_gabarit_nomme_le_syndic_par_le_marqueur():
    assert any(MARQUEUR_SYNDIC in c["contenu"] for c in GABARIT)


# ── 5. La porte ─────────────────────────────────────────────────────────────

ROUTE = "/admin/consignes-arrivant"
SAISIE = {"consignes": [{"titre": "Tri", "contenu": "Le **mardi**."}]}


def test_un_resident_ne_lit_ni_n_ecrit(moteur):
    http, _ = client_http(moteur, RoleUtilisateur.résident)
    assert http.get(ROUTE).status_code == 403
    assert http.put(ROUTE, json=SAISIE).status_code == 403


@pytest.mark.parametrize("role", [RoleUtilisateur.conseil_syndical, RoleUtilisateur.admin])
def test_le_conseil_et_l_administration_enregistrent(moteur, role):
    http, _ = client_http(moteur, role)
    assert http.get(ROUTE).json()["personnalisees"] is False
    r = http.put(ROUTE, json=SAISIE)
    assert r.status_code == 200, r.text
    assert http.get(ROUTE).json() == {**SAISIE, "personnalisees": True, "accueil": ACCUEIL_GABARIT}


@pytest.mark.parametrize(
    "corps",
    [
        {"consignes": []},
        {"consignes": [{"titre": "", "contenu": "x"}]},
        {"consignes": [{"titre": "x" * 121, "contenu": "x"}]},
        {"consignes": [{"titre": "x", "contenu": "x"}] * 13},
    ],
)
def test_une_saisie_hors_des_bornes_est_refusee(moteur, corps):
    http, _ = client_http(moteur, RoleUtilisateur.conseil_syndical)
    assert http.put(ROUTE, json=corps).status_code == 422


# ── 7. La phrase d'accueil ──────────────────────────────────────────────────


def _fiche(accueil: str | None) -> str:
    return generer_fiche_arrivant(
        cs_data={"membres": []},
        syndic_data={"nom_syndic": "", "adresse": "", "membres": []},
        site_nom="Résidence Témoin",
        site_url="https://exemple.fr",
        logo_png=None,
        whatsapp_url=None,
        consignes=[],
        accueil=accueil,
        annee=2026,
    )


def test_sans_saisie_la_fiche_imprime_l_accueil_du_gabarit(session):
    assert lire_accueil(session) == ACCUEIL_GABARIT
    assert lire_consignes(session).accueil == ACCUEIL_GABARIT
    #  Le gabarit nomme le site par le marqueur, jamais par une adresse en dur.
    assert MARQUEUR_SITE in ACCUEIL_GABARIT
    fiche = _fiche(None)
    assert "sur le site exemple.fr de la copropriété" in fiche
    assert MARQUEUR_SITE not in fiche


def test_l_accueil_saisi_s_imprime_echappe(session):
    enregistrer_consignes(
        session,
        [Consigne(titre="Tri", contenu="Le mardi.")],
        "  <b>Bienvenue</b> chez **nous**, voyez {site}.  ",
    )
    assert (
        session.get(ConfigSite, CLE_ACCUEIL).valeur
        == "<b>Bienvenue</b> chez **nous**, voyez {site}."
    )
    fiche = _fiche(lire_accueil(session))
    assert "&lt;b&gt;Bienvenue&lt;/b&gt; chez <strong>nous</strong>, voyez exemple.fr." in fiche
    assert "<b>Bienvenue" not in fiche


def test_enregistrer_sans_accueil_le_laisse_tel_quel(moteur):
    http, _ = client_http(moteur, RoleUtilisateur.conseil_syndical)
    assert (
        http.put(ROUTE, json={**SAISIE, "accueil": "Bienvenue."}).json()["accueil"] == "Bienvenue."
    )
    #  Un client d'avant n'envoie pas la phrase : elle n'est ni vidée ni remise au gabarit.
    assert http.put(ROUTE, json=SAISIE).json()["accueil"] == "Bienvenue."
    assert http.get(ROUTE).json()["accueil"] == "Bienvenue."


@pytest.mark.parametrize("accueil", ["", "x" * 1001])
def test_un_accueil_hors_des_bornes_est_refuse(moteur, accueil):
    http, _ = client_http(moteur, RoleUtilisateur.conseil_syndical)
    assert http.put(ROUTE, json={**SAISIE, "accueil": accueil}).status_code == 422


# ── 6. La migration ─────────────────────────────────────────────────────────
