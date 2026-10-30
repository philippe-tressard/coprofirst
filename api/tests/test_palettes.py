"""La palette de la copropriété (#2379) : registre, choix, et les trois rendus.

- les valeurs claires de `front/src/styles/palettes.css` sont celles du registre
  (`utils/palettes`) — le front et l'API ne partagent aucun fichier ;
- seul l'administrateur choisit, et seulement une palette du registre (routeur
  `config_palette`) ;
- la clé est publique : le serveur du front pose la palette avant toute session ;
- un courriel et une affiche de hall sortent aux couleurs choisies.
"""

from __future__ import annotations

import re

import pytest
from sqlmodel import Session

from app.models.core import ModeleEmail, RoleUtilisateur
from app.utils.annonce_hall import construire_html
from app.utils.config_site import ecrire_cle
from app.utils.email import _contexte_rendu, composer_email
from app.utils.palettes import CLE_PALETTE, PALETTE_PAR_DEFAUT, PALETTES, recolorer
from tests.aides_compose import RACINE
from tests.aides_http import base_http, client_http

FEUILLE = RACINE / "front" / "src" / "styles" / "palettes.css"

#: Les jetons de la feuille et le champ du registre qui porte la même couleur.
JETONS = {
    "--color-primary": "primaire",
    "--color-primary-dark": "primaire_fonce",
    "--color-primary-light": "primaire_clair",
    "--color-accent": "accent",
    "--color-bg": "fond",
}


def _regles_claires() -> dict[str, dict[str, str]]:
    css = re.sub(r"/\*.*?\*/", "", FEUILLE.read_text(encoding="utf-8"), flags=re.S)
    regles = {}
    for code, corps in re.findall(
        r":root\[data-palette='([a-z]+)'\],\s*:root\[data-palette='\1'\] \.ilot-clair\s*\{([^}]*)\}",
        css,
    ):
        regles[code] = dict(re.findall(r"(--[a-z-]+)\s*:\s*([^;]+);", corps))
    return regles


@pytest.fixture
def moteur():
    with base_http() as m:
        yield m


# ── Le registre et la feuille ────────────────────────────────────────────────


def test_la_feuille_porte_exactement_les_palettes_du_registre():
    regles = _regles_claires()
    assert regles, "aucune règle lue dans palettes.css : contrôle inopérant"
    assert set(regles) == set(PALETTES) - {PALETTE_PAR_DEFAUT}, (
        "la charte n'a pas de règle ; toute autre palette du registre en a une, et "
        "la feuille n'en a pas d'autre"
    )


def test_les_couleurs_claires_de_la_feuille_sont_celles_du_registre():
    for code, jetons in _regles_claires().items():
        palette = PALETTES[code]
        for jeton, champ in JETONS.items():
            assert jetons[jeton].strip().lower() == getattr(palette, champ), (code, jeton)


def test_recolorer_laisse_la_charte_et_l_inconnu_tels_quels():
    html = '<p style="color:#1E3A5F;background:#C9983A">'
    assert recolorer(html, PALETTE_PAR_DEFAUT) == html
    assert recolorer(html, "inconnue") == html
    assert recolorer(html, None) == html


def test_recolorer_remplace_chaque_couleur_de_la_charte_quelle_que_soit_sa_casse():
    p = PALETTES["bordeaux"]
    html = recolorer("#1E3A5F #16304f #EEF2F7 #c9983a #F2EFE9 #3D6B4F", "bordeaux")
    assert html.split() == [
        p.primaire,
        p.primaire_fonce,
        p.primaire_clair,
        p.accent,
        p.fond,
        "#3D6B4F",
    ]


# ── Le choix ─────────────────────────────────────────────────────────────────


def test_l_administrateur_choisit_et_la_palette_devient_publique(moteur):
    admin, _ = client_http(moteur, RoleUtilisateur.admin)
    offertes = admin.get("/config/palettes").json()
    assert [p["code"] for p in offertes] == list(PALETTES)
    assert admin.put("/config/palette", json={"palette": "prune"}).status_code == 200
    anonyme, _ = client_http(moteur, None)
    assert anonyme.get("/config").json()[CLE_PALETTE] == "prune"


def test_une_palette_hors_du_registre_est_refusee(moteur):
    admin, _ = client_http(moteur, RoleUtilisateur.admin)
    assert admin.put("/config/palette", json={"palette": "fuchsia"}).status_code == 422
    assert admin.put("/config", json={CLE_PALETTE: "fuchsia"}).status_code == 422


@pytest.mark.parametrize("role", [None, RoleUtilisateur.conseil_syndical])
def test_seul_l_administrateur_choisit_la_palette(moteur, role):
    http, _ = client_http(moteur, role)
    assert http.put("/config/palette", json={"palette": "prune"}).status_code in (401, 403)
    assert http.get("/config/palettes").status_code in (401, 403)


# ── Les rendus ───────────────────────────────────────────────────────────────


def test_un_courriel_part_aux_couleurs_de_la_palette(moteur):
    modele = ModeleEmail(
        code="essai_palette",
        sujet="Essai",
        corps_html='<p style="color:#1E3A5F">Bonjour</p>',
    )
    with Session(moteur) as s:
        ecrire_cle(s, CLE_PALETTE, "roi")
        s.commit()
        ctx, nom, url, pied = _contexte_rendu(s, {})
    _, html = composer_email(modele, ctx, site_nom=nom, site_url=url, email_footer=pied)
    assert PALETTES["roi"].primaire in html
    assert "#1E3A5F" not in html.upper(), "le gabarit garde une couleur de la charte"


def test_l_affiche_de_hall_sort_aux_couleurs_de_la_palette():
    def affiche(palette):
        return construire_html(
            titre="Coupure d'eau",
            message_html="<p>Mardi matin.</p>",
            perimetre_label="Bâtiment B",
            format_effectif="a5",
            site_nom="Résidence du Parc",
            site_url="https://exemple.test",
            logo_png=None,
            palette=palette,
        ).lower()

    assert "#1e3a5f" in affiche(None)
    assert "#1e3a5f" not in affiche("bouteille")
    assert PALETTES["bouteille"].primaire in affiche("bouteille")
