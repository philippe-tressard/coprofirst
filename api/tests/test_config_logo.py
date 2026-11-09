"""Le logo de la résidence : le téléverser, le servir, le retirer (#1728).

Les règles arbitrées le 08/10/2026 : PNG ou JPEG seulement ; sans logo, le
logo NEUTRE ; la route qui le sert est publique, à tailles fermées ; le nom du
fichier ne s'écrit que par le téléversement. Le vrai client HTTP, la vraie
authentification ; seuls la base et le dossier des téléversements sont
détournés.
"""

from __future__ import annotations

import io

import pytest
from PIL import Image
from sqlmodel import Session

from app.models.core import ConfigSite, RoleUtilisateur
from app.utils import logo
from app.utils.images import carre_png
from app.utils.pdf_theme import logo_html, logo_svg
from tests.aides_http import base_http, client_http
from tests.aides_sources import modules_app


def _png(couleur=(200, 30, 30, 255), taille=(40, 20)) -> bytes:
    sortie = io.BytesIO()
    Image.new("RGBA", taille, couleur).save(sortie, format="PNG")
    return sortie.getvalue()


def _pixel_central(png: bytes) -> tuple:
    img = Image.open(io.BytesIO(png)).convert("RGBA")
    return img.getpixel((img.width // 2, img.height // 2))


@pytest.fixture
def moteur(disque_jetable):
    with base_http() as m:
        yield m


def _televerser(
    http, octets: bytes, type_mime: str = "image/png", nom: str = "logo.png", variante: str = ""
):
    params = {"variante": variante} if variante else None
    return http.post("/config/logo", params=params, files={"file": (nom, octets, type_mime)})


# ── La route publique ────────────────────────────────────────────────────────


def test_sans_logo_la_route_publique_sert_le_logo_NEUTRE(moteur):
    anonyme, _ = client_http(moteur, None)
    r = anonyme.get("/config/logo.png", params={"taille": 64})
    assert r.status_code == 200, "le logo doit se lire sans session (connexion, courriels)"
    assert r.headers["content-type"] == "image/png"
    assert Image.open(io.BytesIO(r.content)).size == (64, 64)
    assert r.content == carre_png(logo.NEUTRE_PNG.read_bytes(), 64)


def test_une_taille_hors_bornes_est_refusee(moteur):
    """Une route publique ne redimensionne pas n'importe quoi à la demande."""
    anonyme, _ = client_http(moteur, None)
    assert anonyme.get("/config/logo.png", params={"taille": 5000}).status_code == 422
    assert anonyme.get("/config/logo.png", params={"taille": 1}).status_code == 422


# ── Téléverser ───────────────────────────────────────────────────────────────


def test_l_administrateur_televerse_et_le_logo_est_servi(moteur, tmp_path):
    admin, _ = client_http(moteur, RoleUtilisateur.admin)
    r = _televerser(admin, _png())
    assert r.status_code == 200, r.text
    nom = r.json()[logo.CLE_LOGO]
    assert (tmp_path / logo.DOSSIER / nom).is_file()

    servi = client_http(moteur, None)[0].get("/config/logo.png", params={"taille": 128}).content
    assert _pixel_central(servi) == (200, 30, 30, 255), "la route sert encore le neutre"
    #  Une image non carrée est CENTRÉE sur du transparent, jamais rognée.
    assert Image.open(io.BytesIO(servi)).convert("RGBA").getpixel((64, 2))[3] == 0

    publique = client_http(moteur, None)[0].get("/config").json()
    assert publique.get(logo.CLE_LOGO) == nom, "le front ne saurait pas qu'un logo existe"


def test_remplacer_le_logo_efface_l_ancien_fichier(moteur, tmp_path):
    admin, _ = client_http(moteur, RoleUtilisateur.admin)
    premier = _televerser(admin, _png()).json()[logo.CLE_LOGO]
    second = _televerser(admin, _png((0, 0, 200, 255))).json()[logo.CLE_LOGO]
    assert premier != second
    assert not (tmp_path / logo.DOSSIER / premier).exists(), "l'ancien logo reste sur disque"


@pytest.mark.parametrize(
    "octets,type_mime,nom",
    [
        #  🔴 Le SVG est refusé, arbitré : il peut porter du script, et le logo
        #  est servi publiquement.
        (
            b'<svg xmlns="http://www.w3.org/2000/svg"><script>alert(1)</script></svg>',
            "image/svg+xml",
            "l.svg",
        ),
        (b"GIF89a....", "image/gif", "l.gif"),
        #  Un « PNG » dont le contenu n'en est pas un : la signature tranche.
        (b"<html>pas une image</html>", "image/png", "l.png"),
    ],
)
def test_ce_qui_n_est_ni_png_ni_jpeg_est_refuse(moteur, tmp_path, octets, type_mime, nom):
    admin, _ = client_http(moteur, RoleUtilisateur.admin)
    assert _televerser(admin, octets, type_mime, nom).status_code == 400
    assert (
        not list((tmp_path / logo.DOSSIER).glob("*"))
        if (tmp_path / logo.DOSSIER).exists()
        else True
    )


def test_un_png_tronque_est_refuse_et_ne_reste_pas_sur_disque(moteur, tmp_path):
    """La signature est bonne, l'image illisible : Pillow tranche."""
    admin, _ = client_http(moteur, RoleUtilisateur.admin)
    assert _televerser(admin, _png()[:40]).status_code == 400
    assert not list((tmp_path / logo.DOSSIER).glob("*"))


@pytest.mark.parametrize("role", [None, RoleUtilisateur.conseil_syndical])
def test_seul_l_administrateur_change_le_logo(moteur, role):
    http, _ = client_http(moteur, role)
    assert _televerser(http, _png()).status_code in (401, 403)
    assert http.delete("/config/logo").status_code in (401, 403)


def test_le_nom_du_logo_ne_s_ecrit_pas_par_la_configuration(moteur):
    """Seul le téléversement, qui contrôle le fichier, pose `site_logo`."""
    admin, _ = client_http(moteur, RoleUtilisateur.admin)
    assert admin.put("/config", json={logo.CLE_LOGO: "../../etc/passwd"}).status_code == 422


# ── Retirer ──────────────────────────────────────────────────────────────────


def test_retirer_le_logo_revient_au_neutre(moteur, tmp_path):
    admin, _ = client_http(moteur, RoleUtilisateur.admin)
    nom = _televerser(admin, _png()).json()[logo.CLE_LOGO]
    assert admin.delete("/config/logo").status_code == 200
    assert not (tmp_path / logo.DOSSIER / nom).exists()
    servi = client_http(moteur, None)[0].get("/config/logo.png", params={"taille": 64}).content
    assert servi == carre_png(logo.NEUTRE_PNG.read_bytes(), 64)


# ── Ce que les documents et les courriels reçoivent ──────────────────────────


def test_un_nom_force_ne_sort_pas_du_dossier_du_logo(moteur, tmp_path):
    (tmp_path / "secret.png").write_bytes(_png())
    with Session(moteur) as s:
        s.add(ConfigSite(cle=logo.CLE_LOGO, valeur="../secret.png"))
        s.commit()
        assert logo.fichier_logo(s) is None
        assert logo.logo_televerse_png(s) is None


def test_un_document_porte_le_neutre_ou_le_logo_televerse():
    #  Sans logo : le dessin neutre, celui de la marque du logiciel (09/10/2026). La
    #  règle du 08/10 — « sans la touche dorée, qui évoquait cette résidence » —
    #  ne tient plus : l'or de la fenêtre allumée appartient à la marque.
    assert logo_html(None, 40) == logo_svg(40), "sans logo : le dessin neutre"
    avec = logo_html(_png(), 40)
    assert avec.startswith('<img src="data:image/png;base64,') and 'width="40"' in avec
    #  WeasyPrint ignore l'attribut : sans le style, le PNG sort à sa taille native.
    assert 'style="width:40px;height:40px"' in avec, "le logo téléversé déborde du document"


def test_le_courriel_charge_le_logo_par_son_adresse_publique():
    assert (
        logo.adresse_logo("https://residence.example/", 96)
        == "https://residence.example/api/config/logo.png?taille=96"
    )
    assert logo.TAILLE_MIN <= 96 <= logo.TAILLE_MAX, "le courriel demande une taille refusée"


# ── La variante du thème sombre (09/11/2026) ─────────────────────────────────
#
#  Un logo composé sur fond blanc porte ce fond : au sombre, on voyait un cadre
#  blanc. L'administration téléverse un second dessin, servi à l'écran seulement.

IVOIRE = (232, 230, 225, 255)


def _servi(moteur, variante: str) -> tuple:
    anonyme, _ = client_http(moteur, None)
    r = anonyme.get("/config/logo.png", params={"taille": 128, "variante": variante})
    assert r.status_code == 200, r.text
    return _pixel_central(r.content)


def test_la_variante_sombre_se_televerse_et_se_sert_a_part(moteur, tmp_path):
    admin, _ = client_http(moteur, RoleUtilisateur.admin)
    clair = _televerser(admin, _png()).json()[logo.CLE_LOGO]
    r = _televerser(admin, _png(IVOIRE), variante="sombre")
    assert r.status_code == 200, r.text
    sombre = r.json()[logo.CLE_LOGO_SOMBRE]
    assert (tmp_path / logo.DOSSIER / sombre).is_file()
    assert (tmp_path / logo.DOSSIER / clair).is_file(), "la variante a écrasé le logo"

    assert _servi(moteur, "sombre") == IVOIRE
    assert _servi(moteur, "clair") == (200, 30, 30, 255)
    publique = client_http(moteur, None)[0].get("/config").json()
    assert publique.get(logo.CLE_LOGO_SOMBRE) == sombre, "le front ne saurait pas qu'elle existe"
    #  Un document sur fond blanc garde le logo ; sur fond sombre, il reçoit la variante.
    with Session(moteur) as s:
        assert _pixel_central(logo.logo_televerse_png(s)) == (200, 30, 30, 255)
        assert _pixel_central(logo.logo_televerse_png(s, "sombre")) == IVOIRE


def test_sans_variante_sombre_la_demande_rend_le_logo(moteur):
    """Une adresse qui la demande ne casse jamais.

    Sans aucun logo : le neutre du fond sombre (sans tuile blanche). Avec un logo
    sans sa variante : le logo lui-même — on ne devine pas le dessin d'une résidence.
    """
    anonyme, _ = client_http(moteur, None)
    r = anonyme.get("/config/logo.png", params={"taille": 64, "variante": "sombre"})
    assert r.content == carre_png(logo.NEUTRE_SOMBRE_PNG.read_bytes(), 64)
    assert r.content != anonyme.get("/config/logo.png", params={"taille": 64}).content
    admin, _ = client_http(moteur, RoleUtilisateur.admin)
    _televerser(admin, _png())
    assert _servi(moteur, "sombre") == (200, 30, 30, 255)


def test_la_variante_sombre_accompagne_le_logo(moteur, tmp_path):
    admin, _ = client_http(moteur, RoleUtilisateur.admin)
    #  Seule, aucun écran ne la montrerait : refusée, et rien ne reste sur disque.
    assert _televerser(admin, _png(IVOIRE), variante="sombre").status_code == 409
    assert not list((tmp_path / logo.DOSSIER).glob("*"))

    _televerser(admin, _png())
    sombre = _televerser(admin, _png(IVOIRE), variante="sombre").json()[logo.CLE_LOGO_SOMBRE]
    #  La retirer seule laisse le logo…
    assert admin.delete("/config/logo", params={"variante": "sombre"}).status_code == 200
    assert not (tmp_path / logo.DOSSIER / sombre).exists()
    assert _servi(moteur, "clair") == (200, 30, 30, 255)
    #  … et retirer le logo l'emporte avec lui.
    sombre = _televerser(admin, _png(IVOIRE), variante="sombre").json()[logo.CLE_LOGO_SOMBRE]
    assert admin.delete("/config/logo").status_code == 200
    assert not list((tmp_path / logo.DOSSIER).glob("*")), "un fichier de logo reste sur disque"
    publique = client_http(moteur, None)[0].get("/config").json()
    assert logo.CLE_LOGO not in publique and logo.CLE_LOGO_SOMBRE not in publique


@pytest.mark.parametrize("role", [None, RoleUtilisateur.conseil_syndical])
def test_seul_l_administrateur_change_la_variante_sombre(moteur, role):
    http, _ = client_http(moteur, role)
    assert _televerser(http, _png(), variante="sombre").status_code in (401, 403)
    assert http.delete("/config/logo", params={"variante": "sombre"}).status_code in (401, 403)


# ── Partout où le fond est sombre, sans exception ────────────────────────────

#: Le trait ivoire du dessin neutre du fond sombre, et la tuile blanche de l'autre.
_TRAIT_IVOIRE, _TUILE_BLANCHE = 'stroke="#E8E6E1"', 'fill="#FFFFFF"'

#: Qui pose le logo sur un fond SOMBRE : (le module qui DEMANDE le PNG, celui qui
#: le REND). Les deux gestes vont ensemble — `"sombre"` à la demande, `sombre=True`
#: au rendu ; un lieu de plus sur fond sombre s'ajoute ici.
SUR_FOND_SOMBRE = (
    ("routers/admin/arrivants.py", "utils/fiche_arrivant.py"),
    ("routers/annonces_hall.py", "utils/annonce_hall.py"),
    ("utils/manuel_pdf.py", "utils/manuel_pdf_pages.py"),
)
#: Qui le pose sur un fond BLANC : le logo, jamais la variante.
SUR_FOND_BLANC = ("routers/suivi_affaires.py", "utils/points_conseil_expedition.py")


def _source(rel: str) -> str:
    return next(m.source for m in modules_app(minimum=100) if m.rel == rel)


def test_le_dessin_neutre_du_fond_sombre_n_a_pas_de_tuile_blanche():
    sombre = logo_html(None, 40, sombre=True)
    assert sombre == logo_svg(40, sombre=True)
    assert _TRAIT_IVOIRE in sombre and _TUILE_BLANCHE not in sombre
    assert _TUILE_BLANCHE in logo_svg(40), "témoin : le dessin du fond clair garde sa tuile"


@pytest.mark.parametrize("demande, rendu", SUR_FOND_SOMBRE)
def test_chaque_document_sur_fond_sombre_demande_et_rend_la_variante(demande, rendu):
    assert 'logo_televerse_png(session, "sombre")' in _source(demande), demande
    assert "sombre=True" in _source(rendu) and "logo_html(" in _source(rendu), rendu


@pytest.mark.parametrize("rel", SUR_FOND_BLANC)
def test_un_document_sur_fond_blanc_garde_le_logo(rel):
    assert "logo_televerse_png(session)" in _source(rel), rel


def test_aucun_appel_au_logo_n_echappe_a_la_declaration():
    """Un lieu neuf qui montre le logo se range dans l'une des deux listes."""
    appelants = {
        m.rel
        for m in modules_app(minimum=100)
        if "logo_televerse_png(" in m.source
        #  `logo.py` la définit, `pdf_theme.py` la cite dans une docstring.
    } - {"utils/logo.py", "utils/pdf_theme.py"}
    assert appelants, "cas zéro : aucun appelant trouvé"
    assert appelants == {d for d, _ in SUR_FOND_SOMBRE} | set(SUR_FOND_BLANC)


def test_la_fiche_arrivant_servie_porte_la_variante_sombre(moteur):
    import base64

    admin, _ = client_http(moteur, RoleUtilisateur.admin)
    #  Sans logo : le dessin neutre du fond sombre, dans l'en-tête bleu marine.
    fiche = admin.get("/admin/fiche-arrivant").text
    assert _TRAIT_IVOIRE in fiche and _TUILE_BLANCHE not in fiche
    _televerser(admin, _png())
    _televerser(admin, _png(IVOIRE), variante="sombre")
    with Session(moteur) as s:
        attendu = base64.b64encode(logo.logo_png(s, 512, "sombre")).decode()
    assert attendu in admin.get("/admin/fiche-arrivant").text


def test_le_courriel_charge_la_variante_sombre_dans_son_en_tete_bleu():
    from app.utils.email import gabarit

    assert (
        logo.adresse_logo("https://residence.example/", 96, "sombre")
        == "https://residence.example/api/config/logo.png?taille=96&variante=sombre"
    )
    assert 'adresse_logo(site_url, TAILLE_LOGO_COURRIEL * 2, "sombre")' in _source(
        "utils/email/gabarit.py"
    )
    assert gabarit.TAILLE_LOGO_COURRIEL * 2 <= logo.TAILLE_MAX


def test_une_variante_inconnue_est_refusee(moteur):
    anonyme, _ = client_http(moteur, None)
    assert anonyme.get("/config/logo.png", params={"variante": "rose"}).status_code == 422
    admin, _ = client_http(moteur, RoleUtilisateur.admin)
    assert admin.put("/config", json={logo.CLE_LOGO_SOMBRE: "x.png"}).status_code == 422
