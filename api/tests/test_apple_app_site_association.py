"""Garde-fou : `/.well-known/apple-app-site-association` ouvre l'app iOS sur les bons liens (#2459).

POURQUOI : l'app iOS s'ouvre depuis un lien de courriel ou le QR de la fiche arrivant
(liens universels d'Apple). Chaque installation doit donc servir ce fichier, en JSON,
sans redirection. Deux défauts guettent, et aucun ne fait d'erreur :

  * un chemin que NOS courriels ouvrent et que le fichier ne couvre pas — le lien
    s'ouvre dans Safari, l'app n'est jamais proposée ;
  * un chemin couvert que l'app ne sait pas afficher — elle s'ouvre sur un écran
    qui n'existe pas.

Le premier se mesure : les chemins sont LUS dans les modèles de courriel et dans les
deux liens à jeton de l'API, jamais devinés. Le second est une décision : les chemins que
l'app n'ouvre pas encore sont DÉCLARÉS ci-dessous, avec leur raison, et le test échoue
quand l'un d'eux cesse d'être écrit ailleurs (une exception qui ne sert plus se retire).

Ne sont pas lus ici : les liens bâtis à l'exécution (`{{ objet.lien }}`, `{{ lien }}`),
dont la forme est `/tickets/<id>` ou un chemin de menu ; `/tickets/*` les couvre.

Le test lit `front/` depuis `api/tests/` comme `test_security_txt.py` : la CI n'exécute
pytest qu'ici, et un contrôle sans exécution est un contrôle absent.
"""

import json
import pathlib
import re

from tests.aides_caddy import bloc_handle, caddyfile

_RACINE = pathlib.Path(__file__).resolve().parents[2]
_FICHIER = _RACINE / "front" / "static" / ".well-known" / "apple-app-site-association"

#: Identifiant d'équipe Apple (public : il figure dans chaque app signée) et
#: identifiant d'app (`PRODUCT_BUNDLE_IDENTIFIER` de coprofirst-ios/project.yml).
APP_ID = "GUX8KASNTG.fr.coprofirst.app"

#: Où un chemin de lien se lit : les modèles de courriel, et les deux liens à jeton.
_SOURCES_COURRIELS = sorted((_RACINE / "api" / "app" / "seed" / "emails").glob("*.py"))
_SOURCES_JETONS = [
    _RACINE / "api" / "app" / "utils" / "verification_adresse.py",
    _RACINE / "api" / "app" / "routers" / "auth_mot_de_passe.py",
]

#: Chemins que nos courriels ouvrent et que l'app n'ouvre PAS (v1) : le lien reste
#: dans le navigateur. Une entrée ne vit que tant qu'un courriel écrit encore ce chemin.
NON_OUVERTS_PAR_L_APP = {
    "/admin": "l'administration est le dernier lot de l'app (#2460)",
    "/calendrier": "pas d'écran Calendrier dans l'app v1",
    "/point-cs/x": "validation d'une synthèse par jeton, dans le navigateur",
}

#: Un `{{ app.url }}` suivi d'un chemin littéral. Un chemin qui finit par « / » est
#: suivi d'un identifiant : on lui en pose un pour l'essai (`/tickets/x`).
_CHEMIN_COURRIEL = re.compile(r"\{\{ app\.url \}\}(?=[\"/?])((?:/[a-z0-9\-]+)*/?)")
_CHEMIN_JETON = re.compile(r"\{site_url\}((?:/[a-z0-9\-]+)+)")


def _document() -> dict:
    return json.loads(_FICHIER.read_text(encoding="utf-8"))


def _composants() -> list[dict]:
    (detail,) = _document()["applinks"]["details"]
    return detail["components"]


def _correspond(motif: str, chemin: str) -> bool:
    """Le jeu de caractères d'Apple : `*` = zéro ou plusieurs caractères, `?` = un seul."""
    expr = "".join(".*" if c == "*" else "." if c == "?" else re.escape(c) for c in motif)
    return re.fullmatch(expr, chemin) is not None


def _couvert(chemin: str) -> bool:
    return any(
        _correspond(c["/"], chemin) for c in _composants() if "/" in c and "exclude" not in c
    )


def _chemins_lus() -> set[str]:
    trouves: set[str] = set()
    for fichier in _SOURCES_COURRIELS:
        for brut in _CHEMIN_COURRIEL.findall(fichier.read_text(encoding="utf-8")):
            trouves.add("/" if brut == "" else brut + "x" if brut.endswith("/") else brut)
    for fichier in _SOURCES_JETONS:
        trouves.update(_CHEMIN_JETON.findall(fichier.read_text(encoding="utf-8")))
    return trouves


def test_cas_zero_les_chemins_sont_bien_lus():
    """Une lecture qui ne trouve rien ne prouve rien : les chemins connus doivent sortir."""
    lus = _chemins_lus()
    assert {"/", "/tickets/x", "/auth/connexion", "/auth/verifier-email"} <= lus, sorted(lus)
    assert "/auth/reinitialisation-mdp" in lus, sorted(lus)


def test_le_fichier_est_en_json_utf8_sans_bom_ni_crlf():
    octets = _FICHIER.read_bytes()
    assert not octets.startswith(b"\xef\xbb\xbf"), "BOM en tête"
    assert b"\r" not in octets, "fins de ligne CRLF"
    _document()


def test_l_app_est_celle_de_l_equipe_apple_du_projet():
    (detail,) = _document()["applinks"]["details"]
    assert detail["appIDs"] == [APP_ID]


def test_le_fichier_ne_nomme_pas_la_residence():
    """Il part chez toutes les installations (`lint:nom-residence` le garde aussi)."""
    texte = _FICHIER.read_text(encoding="utf-8").lower()
    for mot in ("hostachy", "résidence", "residence"):
        assert mot not in texte


def test_chaque_chemin_de_courriel_est_couvert_ou_declare_non_ouvert():
    manquants = sorted(
        c for c in _chemins_lus() if not _couvert(c) and c not in NON_OUVERTS_PAR_L_APP
    )
    assert not manquants, (
        f"chemins de courriel hors du fichier : {manquants}. Les couvrir dans "
        "front/static/.well-known/apple-app-site-association, ou les déclarer dans "
        "NON_OUVERTS_PAR_L_APP avec leur raison."
    )


def test_un_chemin_declare_non_ouvert_n_est_pas_couvert_et_sert_encore():
    lus = _chemins_lus()
    for chemin, raison in NON_OUVERTS_PAR_L_APP.items():
        assert chemin in lus, f"{chemin} n'est plus écrit dans un courriel : retirer l'exception"
        assert not _couvert(chemin), f"{chemin} est couvert : retirer l'exception ({raison})"


def test_la_racine_est_couverte_seule_pour_le_qr_de_la_fiche_arrivant():
    """Le QR encode l'adresse du site : `/` ouvre l'app, `/mentions-legales` reste web."""
    assert _couvert("/")
    assert not _couvert("/mentions-legales")
    assert not _couvert("/politique-de-confidentialite")


def test_caddy_le_sert_en_json_sans_redirection():
    """Le serveur du front pose un type par l'extension : celui-ci n'en a pas. Apple exige
    `application/json` et refuse toute redirection."""
    bloc = bloc_handle(caddyfile(), "/.well-known/apple-app-site-association")
    assert bloc is not None, (
        "aucun `handle /.well-known/apple-app-site-association` dans le Caddyfile"
    )
    assert 'header >Content-Type "application/json"' in bloc
    assert "reverse_proxy front:3000" in bloc
    assert "redir" not in bloc
