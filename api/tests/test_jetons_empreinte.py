"""Un jeton se stocke par son EMPREINTE, jamais en clair (#1389, 27/09/2026).

Les trois familles — rafraîchissement, mot de passe oublié, vérification
d'adresse — étaient écrites telles quelles et cherchées par égalité : une copie
de la base (sauvegarde, export hors site) donnait des jetons utilisables.

Ce fichier tient trois choses :

1. **Aucune écriture ni recherche en clair** dans `app/` : tout `Modele(token=…)`
   et tout `Modele.token == …` passe par `empreinte(…)`. Lu dans l'arbre
   syntaxique, pas par motif textuel — un nom de variable ne prouve rien.
2. **L'empreinte est stable, liée à la clé, et reconnaissable** — un jeton brut
   n'en a jamais la forme.
3. **Aucun jeton brut en base après un parcours réel** — exécuté, en bas de ce
   fichier : lien de vérification d'adresse (émis puis servi), connexion, mot de
   passe oublié, par les routes de l'application. Le brut est pris où son
   porteur le reçoit — le cookie, le lien du courriel intercepté —, puis les
   trois tables sont relues. Ce point était promis ici sans qu'aucun test ne
   l'exécute, jusqu'au 30/09/2026 (#1496).
"""

from __future__ import annotations

import ast
import asyncio
from urllib.parse import parse_qs, urlparse

import pytest
from fastapi import BackgroundTasks, Response
from sqlmodel import Session, select

from app.auth import session_ouverte
from app.auth.empreinte_jeton import empreinte, est_empreinte
from app.database import engine
from app.models.core import EmailVerificationToken, PasswordResetToken, RefreshToken
from app.routers import auth, auth_mot_de_passe
from app.utils import verification_adresse
from app.routers.auth_schemas import LoginRequest
from tests.aides_sources import modules_app
from tests.conftest import requete_de_test

MODELES = {"RefreshToken", "PasswordResetToken", "EmailVerificationToken"}


def _appel_empreinte(noeud: ast.AST) -> bool:
    return (
        isinstance(noeud, ast.Call)
        and isinstance(noeud.func, ast.Name)
        and noeud.func.id == "empreinte"
    )


def _ecarts() -> list[str]:
    ecarts = []
    for module in modules_app():
        rel = f"app/{module.rel}"
        for n in ast.walk(module.arbre):
            #  Modele(token=…)
            if isinstance(n, ast.Call) and isinstance(n.func, ast.Name) and n.func.id in MODELES:
                for kw in n.keywords:
                    if kw.arg == "token" and not _appel_empreinte(kw.value):
                        ecarts.append(f"{rel}:{n.lineno} {n.func.id}(token=…) en clair")
            #  Modele.token == …
            if isinstance(n, ast.Compare) and isinstance(n.left, ast.Attribute):
                gauche = n.left
                if (
                    gauche.attr == "token"
                    and isinstance(gauche.value, ast.Name)
                    and gauche.value.id in MODELES
                    and not all(_appel_empreinte(c) for c in n.comparators)
                ):
                    ecarts.append(f"{rel}:{n.lineno} {gauche.value.id}.token == … en clair")
    return ecarts


def test_aucun_jeton_ecrit_ni_cherche_en_clair():
    ecarts = _ecarts()
    assert not ecarts, "jetons hors de `empreinte` :\n" + "\n".join(ecarts)


def test_le_controle_voit_bien_les_trois_familles():
    """Cas zéro : un contrôle qui ne trouverait aucun point d'usage serait vert à vide."""
    sources = "\n".join(m.source for m in modules_app())
    for modele in MODELES:
        assert f"{modele}(" in sources, f"{modele} n'est plus construit nulle part"


def test_l_empreinte_est_stable_a_cle_et_reconnaissable():
    assert empreinte("abc", "k" * 32) == empreinte("abc", "k" * 32)
    assert empreinte("abc", "k" * 32) != empreinte("abc", "z" * 32), "sans clé, pas un HMAC"
    assert est_empreinte(empreinte("abc", "k" * 32))
    #  Aucun jeton brut n'a la forme d'une empreinte : c'est ce qui rend 0231 rejouable.
    assert not est_empreinte("eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiIxIn0.sig")
    assert not est_empreinte("Qx3_kz8-" * 5 + "abc")


# ── 3. Les parcours réels : ce que la base garde, jeton émis ─────────────────


def _lien(envois: list, code: str) -> str:
    """Le jeton brut que porte le lien du dernier courriel `code` intercepté."""
    contextes = [ctx for c, ctx in envois if c == code]
    assert contextes, f"aucun courriel « {code} » intercepté"
    return parse_qs(urlparse(contextes[-1]["lien"]).query)["token"][0]


def _cookie(reponse: Response, nom: str) -> str:
    for cle, valeur in reponse.raw_headers:
        if cle == b"set-cookie" and valeur.startswith(f"{nom}=".encode()):
            return valeur.decode().split(";", 1)[0].split("=", 1)[1]
    raise AssertionError(f"aucun cookie « {nom} » posé")


def _parcourir(session: Session, user, monkeypatch) -> dict:
    """Les trois parcours qui émettent un jeton, par les routes — rend {modèle: brut}."""
    envois: list = []

    async def _intercepter(code, to, context, *args, **kwargs):  # noqa: ARG001
        envois.append((code, context))

    #  Lue à l'appel par les routes (`from app.utils.email import send_email`) :
    #  la tâche de fond reçoit la doublure, rien ne part.
    monkeypatch.setattr("app.utils.email.send_email", _intercepter)

    def _executer(taches: BackgroundTasks) -> None:
        asyncio.run(taches())

    #  Vérification d'adresse : le lien émis, puis SERVI — le brut du courriel
    #  est bien celui que la base reconnaît.
    taches = BackgroundTasks()
    auth.resend_verification(
        requete_de_test("/auth/renvoyer-verification"),
        body=auth.RenvoiVerificationRequest(email=user.email),
        background_tasks=taches,
        session=session,
    )
    _executer(taches)
    brut_verification = _lien(envois, "verification_email")
    auth.verify_email(
        requete_de_test("/auth/verifier-email", "GET"), token=brut_verification, session=session
    )

    #  Connexion : le jeton de rafraîchissement est dans le cookie.
    reponse = Response()
    auth.login(
        requete_de_test("/auth/login"),
        body=LoginRequest(email=user.email, password="Ancien-Mdp1"),
        response=reponse,
        session=session,
    )
    brut_rafraichissement = _cookie(reponse, "refresh_token")

    #  Mot de passe oublié : le lien du courriel.
    taches = BackgroundTasks()
    auth_mot_de_passe.request_password_reset(
        requete_de_test("/auth/mot-de-passe-oublie"),
        body=auth_mot_de_passe.PasswordResetRequest(email=user.email),
        background_tasks=taches,
        session=session,
    )
    _executer(taches)
    return {
        EmailVerificationToken: brut_verification,
        RefreshToken: brut_rafraichissement,
        PasswordResetToken: _lien(envois, "reinitialisation_mdp"),
    }


def _ecarts_en_base(session: Session, bruts: dict) -> list[str]:
    ecarts = []
    for modele, brut in bruts.items():
        stockes = session.exec(select(modele.token)).all()
        if any(brut in s for s in stockes):
            ecarts.append(f"{modele.__name__} : jeton BRUT en base")
        if empreinte(brut) not in stockes:
            ecarts.append(f"{modele.__name__} : empreinte du jeton émis introuvable")
    return ecarts


@pytest.fixture()
def jetons_emis(utilisateur, monkeypatch):
    """Les parcours joués sur le compte de test, puis ses jetons de vérification purgés.

    La fixture `utilisateur` purge ceux de rafraîchissement et de réinitialisation.
    """

    def jouer():
        with Session(engine) as session:
            bruts = _parcourir(session, utilisateur, monkeypatch)
            return bruts, _ecarts_en_base(session, bruts)

    yield jouer
    with Session(engine) as session:
        for evt in session.exec(
            select(EmailVerificationToken).where(EmailVerificationToken.user_id == utilisateur.id)
        ).all():
            session.delete(evt)
        session.commit()


def test_aucun_jeton_brut_en_base_apres_les_parcours_reels(jetons_emis):
    bruts, ecarts = jetons_emis()
    #  Cas zéro : trois familles, trois jetons réellement émis et captés.
    assert len(bruts) == 3 and all(len(b) > 20 for b in bruts.values()), bruts
    assert not ecarts, "\n".join(ecarts)


def test_le_parcours_VOIT_un_jeton_stocke_en_clair(jetons_emis, monkeypatch):
    """Garde-fou : une écriture qui stockerait le brut est refusée, dans les trois familles."""
    #  Le lien de vérification s'émet dans `utils/verification_adresse` (#1549), le
    #  jeton de rafraîchissement s'écrit dans `auth/session_ouverte` (#1903).
    for module in (auth, auth_mot_de_passe, verification_adresse, session_ouverte):
        monkeypatch.setattr(module, "empreinte", lambda brut: brut)
    _, ecarts = jetons_emis()
    for modele in ("EmailVerificationToken", "RefreshToken", "PasswordResetToken"):
        assert f"{modele} : jeton BRUT en base" in ecarts, (modele, ecarts)
