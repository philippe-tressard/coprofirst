"""La palette de la copropriété (#2379) : registre, choix, et les trois rendus.

- les valeurs claires de `front/src/styles/palettes.css` sont celles du registre
  (`utils/palettes`) — le front et l'API ne partagent aucun fichier ;
- seul l'administrateur choisit, et seulement une palette du registre (routeur
  `config_palette`) ;
- la clé est publique : le serveur du front pose la palette avant toute session ;
- un courriel, une affiche de hall et la fiche d'accueil servie (#2780) sortent
  aux couleurs choisies.
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


#: Les couleurs de la charte telles que les documents les écrivent (`utils/palettes`).
CHARTE = ("#1e3a5f", "#16304f", "#eef2f7", "#c9983a", "#f2efe9")


def test_la_fiche_d_accueil_servie_sort_aux_couleurs_de_la_palette(moteur):
    """#2780 : la route rendait la fiche en bleu et or quelle que soit la palette.

    Lu sur ce que la route SERT, pas sur une fonction : c'est la route qui oubliait
    la palette. Et la fiche Seine recolorée doit être exactement la fiche servie —
    rien d'autre ne change que les couleurs.
    """
    http, _ = client_http(moteur, RoleUtilisateur.conseil_syndical)
    seine = http.get("/admin/fiche-arrivant")
    assert seine.status_code == 200, seine.text
    assert "#1e3a5f" in seine.text.lower(), "la fiche ne porte plus la charte : contrôle inopérant"

    with Session(moteur) as s:
        ecrire_cle(s, CLE_PALETTE, "bordeaux")
        s.commit()
    bordeaux = http.get("/admin/fiche-arrivant").text

    restees = [c for c in CHARTE if c in bordeaux.lower()]
    assert not restees, f"la fiche servie garde des couleurs de la charte : {restees}"
    assert PALETTES["bordeaux"].primaire in bordeaux
    assert PALETTES["bordeaux"].accent in bordeaux
    assert bordeaux == recolorer(seine.text, "bordeaux")


# ── Les PDF qui embarquent la charte (#2819) ─────────────────────────────────

#: Les modules qui rendent un PDF SANS la palette de la copropriété, et pourquoi.
#: Le contrôle échoue si l'un cesse de rendre un PDF : l'exception ne sert plus.
PDF_SANS_PALETTE = {
    "app/utils/pdf_theme.py": "le moteur lui-même (`html_to_pdf`) : il rend ce qu'on lui donne",
    "app/demo/fichiers.py": "les documents FICTIFS de la démo, générés une fois avec elle — "
    "ni rapport ni manuel de la copropriété",
}

APP = RACINE / "api" / "app"


def _modules_qui_rendent_un_pdf() -> dict[str, str]:
    return {
        str(f.relative_to(RACINE / "api")): texte
        for f in APP.rglob("*.py")
        if "html_to_pdf(" in (texte := f.read_text(encoding="utf-8"))
    }


def test_tout_pdf_passe_par_la_palette_ou_se_declare():
    """Un document PDF neuf qui embarque la charte sortirait en bleu et or ailleurs
    qu'en Seine (#2819 : le suivi des affaires, le compte rendu et le manuel)."""
    modules = _modules_qui_rendent_un_pdf()
    assert len(modules) >= 5, "le balayage ne voit plus les rendus PDF : contrôle cassé"
    oublis = [m for m, t in modules.items() if "recolorer(" not in t and m not in PDF_SANS_PALETTE]
    assert not oublis, f"PDF rendus sans `palettes.recolorer` : {oublis}"
    perimees = [m for m in PDF_SANS_PALETTE if m not in modules]
    assert not perimees, (
        f"PDF_SANS_PALETTE nomme des modules qui ne rendent plus de PDF : {perimees}"
    )


@pytest.fixture
def html_rendu(monkeypatch):
    """Le moteur PDF remplacé par l'identité : on lit le HTML qui lui est donné."""
    from app.utils import manuel_pdf, points_conseil_pdf
    from app.utils.suivi_affaires import pdf as suivi_pdf

    for module in (suivi_pdf, points_conseil_pdf, manuel_pdf):
        monkeypatch.setattr(module, "html_to_pdf", lambda html: html.encode("utf-8"))
    return suivi_pdf, points_conseil_pdf, manuel_pdf


def _aux_couleurs_bordeaux(pdf: bytes) -> None:
    texte = pdf.decode("utf-8").lower()
    restees = [c for c in CHARTE if c in texte]
    assert not restees, f"le PDF garde des couleurs de la charte : {restees}"
    assert PALETTES["bordeaux"].primaire.lower() in texte


def test_le_rapport_et_le_compte_rendu_sortent_aux_couleurs_de_la_palette(html_rendu, monkeypatch):
    suivi_pdf, points_conseil_pdf, _ = html_rendu
    charte = "<style>" + " ".join(CHARTE) + "</style>"
    monkeypatch.setattr(suivi_pdf, "html_rapport", lambda *_a, **_k: charte)
    monkeypatch.setattr(points_conseil_pdf, "html_compte_rendu", lambda *_a, **_k: charte)

    _aux_couleurs_bordeaux(
        suivi_pdf.generer_pdf(None, site_nom="R", logo_png=None, palette="bordeaux")
    )
    _aux_couleurs_bordeaux(
        points_conseil_pdf.generer_pdf(None, site_nom="R", logo_png=None, palette="bordeaux")
    )
    assert suivi_pdf.generer_pdf(None, site_nom="R", logo_png=None).decode() == charte


def test_le_manuel_sort_aux_couleurs_de_la_palette_et_les_distingue_au_cache(
    html_rendu, monkeypatch, tmp_path
):
    *_, manuel_pdf = html_rendu
    monkeypatch.setattr(manuel_pdf, "composer_html", lambda *_a, **_k: " ".join(CHARTE))
    manuel_pdf._cache().clear()

    def rendre(palette):
        return manuel_pdf.generer_manuel_pdf(
            "R",
            "https://exemple.test",
            logo_png=None,
            html_manuel="m",
            dossier=tmp_path,
            palette=palette,
        )

    seine = rendre(None)
    _aux_couleurs_bordeaux(rendre("bordeaux"))
    #  Le cache ne rend pas le manuel d'une palette pour une autre.
    assert rendre(None) == seine and PALETTES["bordeaux"].primaire.encode() not in seine
