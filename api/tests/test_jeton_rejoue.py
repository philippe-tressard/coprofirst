"""Un jeton de rafraîchissement déjà échangé qui revient ferme toutes les sessions.

## Le défaut (audit de sécurité du 27/09/2026)

`/auth/refresh` échangeait bien le jeton présenté et révoquait l'ancien, mais un
ancien jeton qui revenait était simplement refusé. Or c'est le seul signal
qu'on ait d'un vol de session : le porteur légitime et le voleur tiennent le
même jeton, et celui qui arrive le second présente un jeton déjà échangé.

🔴 Une régression ici est **invisible** : sans la détection, le refus reste un
401, exactement comme avec elle. Aucun écran ne change, aucun autre test ne
casse. D'où ces tests, qui éprouvent les **trois** révocations : un échange
signale un vol, une déconnexion ou un mot de passe posé n'en signale aucun.
Traiter ces deux dernières en vol fermerait la session que la personne vient
d'ouvrir sur son autre appareil.

La règle vit dans `app/auth/jetons_rafraichissement.py`.
"""

from __future__ import annotations

import ast
import pathlib
import uuid
from datetime import timedelta

import pytest
from fastapi import HTTPException, Response
from sqlmodel import Session, select

from app.auth.empreinte_jeton import empreinte
from app.auth.jetons_rafraichissement import DELAI_GRACE_ROTATION, purger
from app.auth.jwt import create_refresh_token
from app.database import engine
from app.models.core import RefreshToken, Utilisateur
from app.routers.auth import logout, refresh
from app.utils import horloge
from app.utils.mots_de_passe import poser_mot_de_passe
from tests.aides_rafraichissement import sessions_ouvertes, vieillir_l_echange
from tests.aides_sources import modules_app
from tests.conftest import requete_de_test

RACINE = pathlib.Path(__file__).resolve().parents[1] / "app"
MODULE = RACINE / "auth" / "jetons_rafraichissement.py"


def _ouvrir(session: Session, user_id: int) -> str:
    """Une session ouverte : un jeton signé, enregistré, valable sept jours."""
    jeton = create_refresh_token({"sub": str(user_id)})
    session.add(
        RefreshToken(
            user_id=user_id,
            token=empreinte(jeton),
            expires_at=horloge.maintenant() + timedelta(days=7),
        )
    )
    session.commit()
    return jeton


def _rafraichir(session: Session, jeton: str) -> None:
    refresh(
        requete_de_test("/auth/refresh"), response=Response(), refresh_token=jeton, session=session
    )


def _refuse(session: Session, jeton: str) -> None:
    with pytest.raises(HTTPException) as refus:
        _rafraichir(session, jeton)
    assert refus.value.status_code == 401


def test_un_jeton_echange_qui_revient_ferme_TOUTES_les_sessions(utilisateur):
    """Le cas du vol : l'ancien jeton revient bien après son échange."""
    with Session(engine) as session:
        vole = _ouvrir(session, utilisateur.id)
        _ouvrir(session, utilisateur.id)  # un autre appareil
        _rafraichir(session, vole)
        assert len(sessions_ouvertes(session, utilisateur.id)) == 2  # le neuf, et l'autre appareil

        vieillir_l_echange(session, vole, DELAI_GRACE_ROTATION + timedelta(minutes=1))
        _refuse(session, vole)

        assert sessions_ouvertes(session, utilisateur.id) == set(), (
            "Un jeton déjà échangé est revenu, et des sessions restent ouvertes : "
            "celle du voleur en fait peut-être partie."
        )


def test_dans_le_delai_de_grace_rien_ne_ferme(utilisateur):
    """Les appels concurrents d'une page qui charge ne sont pas un vol."""
    with Session(engine) as session:
        jeton = _ouvrir(session, utilisateur.id)
        _rafraichir(session, jeton)
        neufs = sessions_ouvertes(session, utilisateur.id)
        assert len(neufs) == 1

        _refuse(session, jeton)

        assert sessions_ouvertes(session, utilisateur.id) == neufs, (
            "Un appel concurrent a fermé la session : chaque chargement de page "
            "déconnecterait son visiteur."
        )


def test_un_jeton_ferme_par_deconnexion_ne_ferme_rien_d_autre(utilisateur):
    with Session(engine) as session:
        deconnecte = _ouvrir(session, utilisateur.id)
        autre_appareil = _ouvrir(session, utilisateur.id)
        logout(
            requete_de_test("/auth/logout"), Response(), refresh_token=deconnecte, session=session
        )

        _refuse(session, deconnecte)

        assert sessions_ouvertes(session, utilisateur.id) == {empreinte(autre_appareil)}


def test_un_mot_de_passe_pose_ne_fait_pas_passer_l_autre_appareil_pour_un_voleur(utilisateur):
    """L'autre appareil présente son ancien jeton : c'est une session fermée, pas un vol."""
    with Session(engine) as session:
        ancien = _ouvrir(session, utilisateur.id)
        courant = _ouvrir(session, utilisateur.id)
        compte = session.get(Utilisateur, utilisateur.id)
        poser_mot_de_passe(session, compte, "Nouveau-Mdp1", jeton_courant=courant)
        session.commit()

        _refuse(session, ancien)

        assert sessions_ouvertes(session, utilisateur.id) == {empreinte(courant)}, (
            "Changer son mot de passe puis rouvrir l'autre appareil a fermé la "
            "session qu'on venait de garder."
        )


def test_la_purge_garde_les_jetons_echanges_jusqu_a_leur_expiration(utilisateur):
    """Sans eux, un jeton rejoué devient « inconnu », et la détection se tait."""
    maintenant = horloge.maintenant()
    demain, hier = maintenant + timedelta(days=1), maintenant - timedelta(days=1)
    lignes = {
        "echange": dict(expires_at=demain, revoked=True, remplace_le=hier),
        "actif": dict(expires_at=demain),
        "echange_expire": dict(expires_at=hier, revoked=True, remplace_le=hier),
        "deconnecte": dict(expires_at=demain, revoked=True),
        "expire": dict(expires_at=hier),
    }
    with Session(engine) as session:
        noms = {}
        for nom, champs in lignes.items():
            jeton = f"{nom}-{uuid.uuid4().hex}"
            noms[jeton] = nom
            session.add(RefreshToken(user_id=utilisateur.id, token=jeton, **champs))
        session.commit()

        purger(session, maintenant)
        session.commit()

        restants = {
            noms[t.token]
            for t in session.exec(
                select(RefreshToken).where(RefreshToken.user_id == utilisateur.id)
            ).all()
        }
    assert restants == {"echange", "actif"}


# ── La règle s'écrit une fois ────────────────────────────────────────────────
#
#  Deux purges supprimaient les jetons révoqués — le démarrage de l'API (ORM) et
#  la maintenance (SQL brut) —, chacune à sa façon. Une troisième écrite demain
#  sans le cas des jetons échangés éteindrait la détection, et aucun test de
#  comportement ne regarde les purges qu'il ne connaît pas.


def _ecarts(source: str) -> list[str]:
    """Une suppression de jetons, ou un échange marqué, hors du module de la règle."""
    ecarts = []
    for n in ast.walk(ast.parse(source)):
        if (
            isinstance(n, ast.Call)
            and getattr(n.func, "id", getattr(n.func, "attr", None)) == "delete"
            and any(isinstance(a, ast.Name) and a.id == "RefreshToken" for a in n.args)
        ):
            ecarts.append(f"ligne {n.lineno} : delete(RefreshToken)")
        if (
            isinstance(n, ast.Constant)
            and isinstance(n.value, str)
            and "delete from refresh_token" in " ".join(n.value.lower().split())
        ):
            ecarts.append(f"ligne {n.lineno} : DELETE FROM refresh_token")
        if isinstance(n, (ast.Assign, ast.AugAssign)):
            cibles = n.targets if isinstance(n, ast.Assign) else [n.target]
            if any(isinstance(c, ast.Attribute) and c.attr == "remplace_le" for c in cibles):
                ecarts.append(f"ligne {n.lineno} : remplace_le écrit")
    return ecarts


def test_le_controle_voit_ce_qu_il_doit_refuser():
    """Un contrôle qui ne peut pas échouer ne prouve rien (`standards/04`)."""
    assert len(_ecarts("s.exec(delete(RefreshToken).where(x))")) == 1
    assert len(_ecarts('_supprimer("DELETE FROM  refresh_token WHERE revoked = 1")')) == 1
    assert len(_ecarts("jeton.remplace_le = maintenant")) == 1
    assert _ecarts("session.delete(jeton)\njeton.revoked = True") == []


def test_purge_et_echange_ne_s_ecrivent_que_dans_le_module_de_la_regle():
    fichiers = modules_app()
    assert len(fichiers) > 100, "le contrôle ne voit presque rien : sa portée a changé"
    ecarts = [
        f"app/{m.rel} — {e}" for m in fichiers if m.chemin != MODULE for e in _ecarts(m.source)
    ]
    assert not ecarts, (
        "Les jetons de rafraîchissement se purgent et s'échangent par "
        "`app/auth/jetons_rafraichissement.py`, pas ailleurs :\n"
        + "\n".join(f"  • {e}" for e in ecarts)
    )
