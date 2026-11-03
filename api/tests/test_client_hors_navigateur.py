"""Un client HORS navigateur passe la même porte d'authentification (#2457).

## Pourquoi ce test

L'app iOS (dépôt distinct) s'authentifiera par la porte du navigateur : les deux
cookies `httponly`/`secure`/`samesite=strict` que pose `auth/session_ouverte`,
relus par `auth/deps`. Arbitré le 01/11/2026 : **pas de second mode** (Bearer),
une seule porte à auditer. Or tous les tests de la porte appelaient les routes en
fonctions (`test_jeton_rejoue.py`) ou posaient le jeton à la main
(`aides_http.client_http`) : rien ne prouvait qu'un client HTTP ordinaire — un jar
de cookies, ni `Origin`, ni `Sec-Fetch-*`, ni `Referer` — fasse le tour complet.

Le client est celui de `TestClient` (httpx) sous `https://` : un cookie `Secure`
n'est rendu que sur HTTPS, comme le fera `URLSession`. Le parcours : connexion →
requête authentifiée → rafraîchissement → rotation, puis le **rejeu** d'un ancien
jeton, qui ferme toutes les sessions du compte.

## Ce que ce fichier ne refait pas

- Le jeton n'est valable que sous l'hôte qui l'a émis (secret par copropriété) :
  `test_etancheite_coproprietes.py` ; un hôte inconnu reçoit 421 :
  `test_resolution_par_hote.py`.
- Les règles fines du rejeu (délai de grâce, déconnexion, mot de passe posé) :
  `test_jeton_rejoue.py`. Ici, le parcours par HTTP seulement.
"""

from __future__ import annotations

import ast
import re
from datetime import timedelta

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session

from app.auth.empreinte_jeton import empreinte
from app.auth.jetons_rafraichissement import DELAI_GRACE_ROTATION
from app.auth.jwt import hash_password
from app.main import app
from app.utils.limiter import LIMITE_SESSION
from tests.aides_base import compte
from tests.aides_http import base_http
from tests.aides_rafraichissement import sessions_ouvertes, vieillir_l_echange
from tests.aides_sources import chaines_du_code, modules_app

MOT_DE_PASSE = "Appli-Mobile-1"

#: Ce que l'app enverra, et rien d'un navigateur. L'hôte est celui que le registre
#: de l'essai déclare (`HOTES_COPROPRIETE`, conftest).
ADRESSE = "https://testserver"
AGENT = "CoproFirst-iOS/essai"

#: Les en-têtes que seul un navigateur pose — ou dont la valeur n'appartient qu'à lui.
#: Une route qui en dépendrait refuserait l'app, ou la traiterait autrement.
EN_TETES_DE_NAVIGATEUR = re.compile(
    r"^(origin|referer|user-agent|sec-fetch-[\w-]+|sec-ch-[\w-]+|upgrade-insecure-requests)$",
    re.IGNORECASE,
)


@pytest.fixture()
def moteur():
    with base_http() as m:
        yield m


def _app_mobile() -> TestClient:
    """Un client HTTP nu : son jar de cookies, son agent, aucun en-tête de navigateur."""
    return TestClient(app, base_url=ADRESSE, headers={"user-agent": AGENT})


def _compte(moteur) -> tuple[int, str]:
    with Session(moteur) as s:
        u = compte(
            s,
            prefixe="mobile",
            hashed_password=hash_password(MOT_DE_PASSE),
            email_verifie=True,
        )
        return u.id, u.email


def _connecter(email: str) -> TestClient:
    http = _app_mobile()
    r = http.post("/auth/login", json={"email": email, "password": MOT_DE_PASSE})
    assert r.status_code == 200, r.text
    envoyes = {k.lower() for k in r.request.headers}
    assert not {k for k in envoyes if EN_TETES_DE_NAVIGATEUR.match(k) and k != "user-agent"}, (
        f"le client d'essai pose un en-tête de navigateur : {sorted(envoyes)}"
    )
    return http


def test_les_cookies_de_session_sont_ceux_du_navigateur(moteur):
    """Les mêmes drapeaux pour l'app : rien n'est relâché pour un client hors navigateur."""
    _, email = _compte(moteur)
    r = _app_mobile().post("/auth/login", json={"email": email, "password": MOT_DE_PASSE})
    assert r.status_code == 200, r.text
    poses = {c.split("=", 1)[0]: c.lower() for c in r.headers.get_list("set-cookie")}
    assert set(poses) == {"access_token", "refresh_token"}
    for nom, cookie in poses.items():
        for drapeau in ("httponly", "secure", "samesite=strict", "path=/"):
            assert drapeau in cookie, f"{nom} sans « {drapeau} » : {cookie}"


def test_connexion_requete_rafraichissement_et_rotation_sans_navigateur(moteur):
    ident, email = _compte(moteur)
    http = _connecter(email)

    moi = http.get("/auth/me")
    assert moi.status_code == 200, moi.text
    assert moi.json()["id"] == ident

    ancien = http.cookies["refresh_token"]
    r = http.post("/auth/refresh")
    assert r.status_code == 200, r.text
    neuf = http.cookies["refresh_token"]
    assert neuf != ancien, "le rafraîchissement n'a pas fait tourner le jeton"

    with Session(moteur) as s:
        assert sessions_ouvertes(s, ident) == {empreinte(neuf)}, (
            "Après l'échange, seul le jeton neuf doit rester ouvert."
        )
    assert http.get("/auth/me").status_code == 200, "le jeton d'accès neuf n'ouvre pas la porte"


def test_le_rejeu_d_un_ancien_jeton_ferme_toutes_les_sessions(moteur):
    """Le vol : un ancien jeton, déjà échangé, revient après le délai de grâce."""
    ident, email = _compte(moteur)
    telephone = _connecter(email)
    tablette = _connecter(email)  # un second appareil du même compte

    vole = telephone.cookies["refresh_token"]
    assert telephone.post("/auth/refresh").status_code == 200
    with Session(moteur) as s:
        assert len(sessions_ouvertes(s, ident)) == 2  # le jeton neuf, et la tablette
        vieillir_l_echange(s, vole, DELAI_GRACE_ROTATION + timedelta(minutes=1))

    voleur = _app_mobile()
    voleur.cookies.set("refresh_token", vole)
    assert voleur.post("/auth/refresh").status_code == 401

    with Session(moteur) as s:
        assert sessions_ouvertes(s, ident) == set(), (
            "Un jeton déjà échangé est revenu, et des sessions restent ouvertes : "
            "celle du voleur en fait peut-être partie."
        )
    for appareil in (telephone, tablette):
        assert appareil.post("/auth/refresh").status_code == 401, (
            "un appareil du compte rafraîchit encore après le rejeu"
        )


def test_le_rejeu_refuse_aussi_les_jetons_d_acces_deja_emis(moteur):
    """#2481 : fermer les sessions ne suffit pas — le voleur tient la PAIRE.

    Son jeton d'accès, émis avant le rejeu, valait encore jusqu'à 120 minutes :
    la porte refusait ses rafraîchissements, pas ses requêtes. Le rejeu change
    l'empreinte du compte (`generation_sessions`), comme un mot de passe changé
    (#1063) : tous les jetons d'accès du compte tombent au geste suivant.
    """
    ident, email = _compte(moteur)
    telephone = _connecter(email)
    tablette = _connecter(email)

    vole = telephone.cookies["refresh_token"]
    voleur = _app_mobile()
    voleur.cookies.set("access_token", telephone.cookies["access_token"])
    assert voleur.get("/auth/me").status_code == 200, "la paire volée n'ouvre pas la porte"

    assert telephone.post("/auth/refresh").status_code == 200
    with Session(moteur) as s:
        vieillir_l_echange(s, vole, DELAI_GRACE_ROTATION + timedelta(minutes=1))
    rejoueur = _app_mobile()
    rejoueur.cookies.set("refresh_token", vole)
    assert rejoueur.post("/auth/refresh").status_code == 401

    for nom, appareil in (("voleur", voleur), ("téléphone", telephone), ("tablette", tablette)):
        assert appareil.get("/auth/me").status_code == 401, (
            f"le jeton d'accès du {nom}, émis avant le rejeu, ouvre encore la porte"
        )

    #  Le porteur légitime se reconnecte : son jeton neuf porte la nouvelle empreinte.
    revenu = _connecter(email)
    assert revenu.get("/auth/me").status_code == 200, "la reconnexion après un rejeu est refusée"
    assert revenu.post("/auth/refresh").status_code == 200
    assert revenu.get("/auth/me").status_code == 200, "le rafraîchissement perd l'empreinte"


def test_la_limite_de_debit_vaut_pour_le_client_hors_navigateur(moteur):
    """La limite se compte par visiteur, pas par navigateur : l'app la reçoit aussi."""
    plafond = int(LIMITE_SESSION.split("/")[0])
    http = _app_mobile()
    codes = [http.post("/auth/refresh").status_code for _ in range(plafond + 1)]
    assert codes[:plafond] == [401] * plafond
    assert codes[plafond] == 429


# ── Aucune route ne dépend d'un en-tête de navigateur ───────────────────────
#
#  `lint:en-tetes-lus` garde l'autre bord : un en-tête que le FRONT pose et
#  qu'aucune route ne lit. Ici : un en-tête que seul un navigateur pose, LU par
#  l'API — `Origin` pour un contrôle CSRF, `Sec-Fetch-Site`, `User-Agent` pour
#  trier les clients. L'app iOS n'en pose aucun (ou pas la même valeur).


def _lectures_d_en_tetes(arbre: ast.AST) -> list[str]:
    """Les en-têtes de REQUÊTE lus : `headers.get("x")`, `headers["x"]`, `Header(alias="x")`,
    et un paramètre `x_y: … = Header(…)` sans alias (FastAPI lit alors `x-y`)."""
    lus = []
    for n in ast.walk(arbre):
        if (
            isinstance(n, ast.Call)
            and isinstance(n.func, ast.Attribute)
            and n.func.attr == "get"
            and isinstance(n.func.value, ast.Attribute)
            and n.func.value.attr == "headers"
            and n.args
            and isinstance(n.args[0], ast.Constant)
        ):
            lus.append(str(n.args[0].value))
        elif (
            isinstance(n, ast.Subscript)
            and isinstance(n.value, ast.Attribute)
            and n.value.attr == "headers"
            and isinstance(n.slice, ast.Constant)
            and isinstance(n.ctx, ast.Load)
        ):
            lus.append(str(n.slice.value))
        elif isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)):
            args = n.args.args + n.args.kwonlyargs
            defauts = [None] * (len(n.args.args) - len(n.args.defaults)) + list(n.args.defaults)
            defauts += list(n.args.kw_defaults)
            for arg, defaut in zip(args, defauts):
                if (
                    isinstance(defaut, ast.Call)
                    and isinstance(defaut.func, ast.Name)
                    and defaut.func.id == "Header"
                ):
                    alias = next(
                        (k.value.value for k in defaut.keywords if k.arg == "alias"),
                        arg.arg.replace("_", "-"),
                    )
                    lus.append(str(alias))
    return lus


def test_aucune_route_ne_lit_un_en_tete_que_seul_un_navigateur_pose():
    lus = {
        (m.rel, nom.lower())
        for m in modules_app(minimum=100)
        for nom in _lectures_d_en_tetes(m.arbre)
    }
    #  Cas zéro (`standards/04` §2) : le lecteur doit voir les lectures connues —
    #  l'adresse que Caddy transmet au `forward_auth`, la clé des scripts.
    noms = {nom for _, nom in lus}
    assert {"x-forwarded-uri", "x-maintenance-key", "host"} <= noms, (
        f"lecteur d'en-têtes cassé : il ne voit que {sorted(noms)}"
    )
    fautifs = sorted(f"{rel} : {nom}" for rel, nom in lus if EN_TETES_DE_NAVIGATEUR.match(nom))
    assert not fautifs, (
        "Une route lit un en-tête que seul un navigateur pose : l'app iOS, qui passe "
        "par la même porte (#2457), en serait refusée ou traitée autrement.\n  "
        + "\n  ".join(fautifs)
    )


def test_le_lecteur_voit_les_trois_formes():
    source = (
        "def f(request, a: str = Header(default=None, alias='Origin'),"
        " sec_fetch_site: str = Header(None)):\n"
        "    request.headers.get('Referer'); request.headers['user-agent']\n"
    )
    assert sorted(_lectures_d_en_tetes(ast.parse(source))) == [
        "Origin",
        "Referer",
        "sec-fetch-site",
        "user-agent",
    ]


def test_aucune_chaine_d_en_tete_de_navigateur_n_est_comparee_dans_l_api():
    """Le filet de l'AST : un `Sec-Fetch-*` ou `Sec-CH-*` écrit en chaîne n'a rien à faire
    dans `app/` — l'API n'en émet aucun, elle ne pourrait que le lire."""
    trouves = sorted(
        f"{m.rel} : {c.value}"
        for m in modules_app(minimum=100)
        for c in chaines_du_code(m.arbre)
        if isinstance(c.value, str) and re.match(r"(?i)^sec-(fetch|ch)-", c.value)
    )
    assert not trouves, "\n".join(trouves)
