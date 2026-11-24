"""Un jeton se stocke par son EMPREINTE, jamais en clair (#1389, 27/09/2026).

Les trois familles — rafraîchissement, mot de passe oublié, vérification
d'adresse — étaient écrites telles quelles et cherchées par égalité : une copie
de la base (sauvegarde, export hors site) donnait des jetons utilisables.

Ce fichier tient trois choses :

1. **Aucune écriture ni recherche en clair** dans `app/` : tout `Modele(token=…)`,
   tout `x.token = …` et tout `Modele.token == …` passe par `empreinte(…)`. Lu dans
   l'arbre syntaxique, pas par motif textuel — un nom de variable ne prouve rien.
   La table des colonnes à jeton se DÉRIVE du schéma (#2940) : chaque colonne
   `token`, et chaque colonne dont le nom contient `empreinte`, sauf celles déclarées
   ci-dessous avec leur raison. Une table figée à six modèles avait laissé
   `PresentPoint.jeton_empreinte` hors de portée.
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
from pathlib import Path
from urllib.parse import parse_qs, urlparse

import pytest
from fastapi import BackgroundTasks, Response
from sqlmodel import Session, select
from sqlmodel.main import default_registry

from app.auth import session_ouverte
from app.auth.empreinte_jeton import empreinte, est_empreinte
from app.database import engine
from app.models.core import EmailVerificationToken, PasswordResetToken, RefreshToken
from app.registre.modeles import registre_plateforme
from app.routers import auth, auth_mot_de_passe
from app.utils import verification_adresse
from app.routers.auth_schemas import LoginRequest
from tests.aides_sources import Module, modules_app
from tests.conftest import requete_de_test

#: Les colonnes d'« empreinte » qui ne gardent PAS un jeton : rien ne s'y présente pour
#: ouvrir un accès. Vérifiée dans les deux sens — une entrée sortie du schéma échoue.
EMPREINTES_NON_JETONS = {
    ("AcceptationConditions", "empreinte"): "le texte des conditions accepté (registre) — "
    "la preuve de ce qui a été lu",
    ("ArchiveAffaires", "empreinte"): "le SHA-256 du zip d'archive — l'intégrité d'un fichier",
    ("FichierRecu", "empreinte"): "le contenu d'une pièce jointe — elle ne se verse pas deux "
    "fois dans une affaire",
    ("Installation", "empreinte_cle"): "la clé PUBLIQUE d'une installation (registre) — "
    "publique par nature",
    ("JetonMontre", "empreinte_compte"): "l'état du COMPTE à l'émission (mot de passe haché, "
    "génération des sessions) — recalculé et comparé, jamais présenté",
    ("MessageVerse", "empreinte"): "un message versé (auteur, texte normalisé) — un doublon "
    "ne se reverse pas",
    ("TexteReglement", "empreinte"): "le texte du règlement — recharger le même fichier ne "
    "crée pas de version",
}

#: Les affectations `x.<colonne> = …` hors `empreinte(…)` qui visent une colonne
#: HOMONYME d'une colonne à jeton, sans en être une. L'affectation se lit par le nom de
#: l'attribut — le type du receveur n'est pas dans l'arbre. Vérifiée dans les deux sens.
AFFECTATIONS_DECLAREES = {
    ("utils/courriel_pieces_jointes.py", "empreinte"): "la trace d'un fichier reçu "
    "(`FichierRecu.empreinte`, son contenu), homonyme de l'empreinte d'un écran ou d'une montre",
}


def _colonnes_candidates() -> dict[str, set[str]]:
    """{Modèle: colonnes} — `token`, et tout nom qui contient `empreinte` —, lues dans les
    deux registres : celui des copropriétés et celui de la plateforme."""
    candidates: dict[str, set[str]] = {}
    for registre in (default_registry, registre_plateforme):
        for mapper in registre.mappers:
            for colonne in mapper.column_attrs:
                if colonne.key == "token" or "empreinte" in colonne.key:
                    candidates.setdefault(mapper.class_.__name__, set()).add(colonne.key)
    return candidates


def _modeles_a_jeton() -> dict[str, tuple[str, ...]]:
    modeles = {}
    for modele, colonnes in _colonnes_candidates().items():
        jetons = tuple(sorted(c for c in colonnes if (modele, c) not in EMPREINTES_NON_JETONS))
        if jetons:
            modeles[modele] = jetons
    return modeles


#: Chaque modèle qui garde un jeton, et la colonne qui le porte — dérivé du schéma.
MODELES = _modeles_a_jeton()
#: Les noms de colonne à jeton, tous modèles confondus : ce qu'une affectation vise.
COLONNES_JETON = {c for colonnes in MODELES.values() for c in colonnes}


def _sans_jeton_brut(noeud: ast.AST) -> bool:
    """`empreinte(…)`, ou `None` — tout le reste est un jeton en clair."""
    if isinstance(noeud, ast.Constant) and noeud.value is None:
        return True
    return (
        isinstance(noeud, ast.Call)
        and isinstance(noeud.func, ast.Name)
        and noeud.func.id == "empreinte"
    )


def _colonne_a_jeton(noeud: ast.AST) -> bool:
    """`Modele.colonne`, la colonne d'un modèle à jeton."""
    return (
        isinstance(noeud, ast.Attribute)
        and isinstance(noeud.value, ast.Name)
        and noeud.attr in MODELES.get(noeud.value.id, ())
    )


def _ecarts(modules) -> list[tuple[str, int, str, str]]:
    """(module, ligne, forme, colonne) pour chaque jeton écrit, affecté ou cherché en clair."""
    ecarts = []
    for module in modules:
        for n in ast.walk(module.arbre):
            #  Modele(token=…)
            if isinstance(n, ast.Call) and isinstance(n.func, ast.Name) and n.func.id in MODELES:
                for kw in n.keywords:
                    if kw.arg in MODELES[n.func.id] and not _sans_jeton_brut(kw.value):
                        ecarts.append((module.rel, n.lineno, f"{n.func.id}({kw.arg}=…)", kw.arg))
            #  x.token = …
            if isinstance(n, (ast.Assign, ast.AnnAssign)) and n.value is not None:
                cibles = n.targets if isinstance(n, ast.Assign) else [n.target]
                for cible in cibles:
                    if (
                        isinstance(cible, ast.Attribute)
                        and cible.attr in COLONNES_JETON
                        and not _sans_jeton_brut(n.value)
                    ):
                        ecarts.append((module.rel, n.lineno, f"x.{cible.attr} = …", cible.attr))
            #  Modele.token == …, dans un sens ou dans l'autre
            if isinstance(n, ast.Compare):
                termes = [n.left, *n.comparators]
                for t in termes:
                    if _colonne_a_jeton(t) and not all(
                        _sans_jeton_brut(autre) for autre in termes if autre is not t
                    ):
                        forme = f"{t.value.id}.{t.attr} == …"
                        ecarts.append((module.rel, n.lineno, forme, t.attr))
    return ecarts


def test_aucun_jeton_ecrit_ni_cherche_en_clair():
    ecarts = [
        f"app/{rel}:{ligne} {forme} en clair"
        for rel, ligne, forme, colonne in _ecarts(modules_app())
        if not (forme.startswith("x.") and (rel, colonne) in AFFECTATIONS_DECLAREES)
    ]
    assert not ecarts, "jetons hors de `empreinte` :\n" + "\n".join(ecarts)


def test_chaque_affectation_declaree_sert_encore():
    vues = {
        (rel, colonne)
        for rel, _, forme, colonne in _ecarts(modules_app())
        if forme.startswith("x.")
    }
    perimees = sorted(set(AFFECTATIONS_DECLAREES) - vues)
    assert not perimees, f"`AFFECTATIONS_DECLAREES` déclare des affectations disparues : {perimees}"


def test_la_table_des_jetons_se_derive_du_schema():
    """Cas zéro et autre sens : la dérivation voit les jetons connus, et chaque colonne
    déclarée « non-jeton » existe encore — sinon la déclaration ne couvre plus rien."""
    attendus = {
        "RefreshToken": "token",
        "PasswordResetToken": "token",
        "EmailVerificationToken": "token",
        "JetonMontre": "empreinte",
        "Ecran": "empreinte",
        "AppairageEcran": "empreinte_code_appareil",
        "PresentPoint": "jeton_empreinte",
    }
    manquants = {m: c for m, c in attendus.items() if c not in MODELES.get(m, ())}
    assert not manquants, f"la table dérivée a perdu {manquants} : {MODELES}"
    candidates = _colonnes_candidates()
    perimees = sorted((m, c) for m, c in EMPREINTES_NON_JETONS if c not in candidates.get(m, set()))
    assert not perimees, f"`EMPREINTES_NON_JETONS` déclare des colonnes disparues : {perimees}"


def test_le_detecteur_voit_CHAQUE_forme_en_clair():
    """Un extrait forgé par forme à refuser, et quatre écritures qui passent (#2940)."""
    source = "\n".join(
        (
            "RefreshToken(token=brut)",  # 1
            "RefreshToken(token=empreinte(brut))",  # passe
            "ligne.token = brut",  # 3 — affectation d'attribut
            "ligne.token = empreinte(brut)",  # passe
            "present.jeton_empreinte = None",  # passe : on efface
            "select(PresentPoint).where(PresentPoint.jeton_empreinte == jeton)",  # 6
            "select(Ecran).where(jeton == Ecran.empreinte)",  # 7 — dans l'autre sens
            "PresentPoint(jeton_empreinte=jeton)",  # 8
            "trace.empreinte: str = brut",  # 9 — annotée
            "FichierRecu(empreinte=somme)",  # passe : pas un jeton
        )
    )
    forge = Module(chemin=Path("forge.py"), rel="utils/forge.py", source=source)
    vues = sorted(ligne for _, ligne, _, _ in _ecarts([forge]))
    assert vues == [1, 3, 6, 7, 8, 9], (
        f"le détecteur a vu les lignes {vues} : une forme d'écriture ou de recherche en "
        "clair lui échappe, ou une écriture sûre passe pour un jeton"
    )


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
