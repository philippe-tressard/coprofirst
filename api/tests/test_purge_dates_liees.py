"""Une purge compare des DATES, jamais des chaînes au mauvais format (#1298).

## Le défaut (reproduit le 25/09/2026)

`utils/maintenance.purger()` passait ses seuils en `datetime.isoformat()` à des
`DELETE … WHERE col < :seuil` écrits en `text()` : le seuil partait en TEXTE,
comparé à un horodatage, et le jour du seuil, toute ligne était
« antérieure », quelle que soit son heure.

Un jeton de session qui expire dans six heures était donc effacé par la purge
du dimanche — le résident perdait sa session, ou son lien de réinitialisation.
La purge de la télémétrie portait le même défaut.

## Les deux contrôles

- le COMPORTEMENT : un jeton qui expire dans 6 h est conservé, un jeton expiré
  il y a 1 h est supprimé — par `purger()` lui-même, sur la base de test ;
- la RÉCIDIVE : aucun `.isoformat()` n'est passé comme valeur à une requête
  `text()` dans `api/app/`. Le motif s'éprouve lui-même.
"""

from __future__ import annotations

import ast
import pathlib
import re
import uuid
from datetime import timedelta

import pytest
from sqlmodel import Session, SQLModel, select

from app.database import engine
from app.models.core import Utilisateur
from app.models.jetons import PasswordResetToken, RefreshToken
from app.utils import horloge
from app.utils.maintenance import purger
from tests import aides_base
from tests.aides_sources import modules_app
from tests.aides_purge import purger_ligne

_APP = pathlib.Path(__file__).resolve().parents[1] / "app"


@pytest.fixture()
def compte():
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        u = aides_base.compte(session, prefixe="purge", nom="P", prenom="J", roles_json="résident")
        yield session, u
        purger_ligne(session, Utilisateur, u.id)
        session.commit()


def test_un_jeton_encore_valide_survit_a_la_purge(compte):
    session, u = compte
    maintenant = horloge.maintenant()
    jetons = {
        "valide": RefreshToken(
            user_id=u.id, token=f"v-{uuid.uuid4().hex}", expires_at=maintenant + timedelta(hours=6)
        ),
        "expire": RefreshToken(
            user_id=u.id, token=f"e-{uuid.uuid4().hex}", expires_at=maintenant - timedelta(hours=1)
        ),
        "lien_valide": PasswordResetToken(
            user_id=u.id, token=f"l-{uuid.uuid4().hex}", expires_at=maintenant + timedelta(hours=6)
        ),
    }
    session.add_all(jetons.values())
    session.commit()
    ids = {k: j.id for k, j in jetons.items()}

    _comptes, erreurs = purger()
    assert not erreurs, erreurs

    session.expire_all()
    restants = {
        j.id for j in session.exec(select(RefreshToken).where(RefreshToken.user_id == u.id))
    }
    liens = {
        j.id
        for j in session.exec(select(PasswordResetToken).where(PasswordResetToken.user_id == u.id))
    }
    assert ids["valide"] in restants, "un jeton qui expire dans 6 h a été effacé"
    assert ids["expire"] not in restants, "un jeton expiré est resté"
    assert ids["lien_valide"] in liens, "un lien de réinitialisation valide a été effacé"


_SQL = re.compile(r"\b(SELECT|DELETE|UPDATE|INSERT)\b", re.I)


def _est_isoformat(noeud) -> int | None:
    for sous in ast.walk(noeud):
        if isinstance(sous, ast.Call) and isinstance(sous.func, ast.Attribute):
            if sous.func.attr == "isoformat":
                return sous.lineno
    return None


def isoformat_lies(source: str) -> list[int]:
    """Les lignes où `.isoformat()` sert de VALEUR à un paramètre SQL.

    Trois formes : un argument de `.bindparams(...)`, ou une entrée de dict dont
    la CLÉ est un paramètre `:clé` d'une requête du même module — que le dict
    parte directement dans `execute(...)` ou transite par un tuple et un
    `**params`, comme dans `maintenance.purger()` (la forme que la première
    version de ce contrôle laissait passer).
    """
    arbre = ast.parse(source)
    parametres = {
        m
        for n in ast.walk(arbre)
        if isinstance(n, ast.Constant) and isinstance(n.value, str) and _SQL.search(n.value)
        for m in re.findall(r":(\w+)", n.value)
    }
    lignes = []
    for noeud in ast.walk(arbre):
        if isinstance(noeud, ast.Call) and isinstance(noeud.func, ast.Attribute):
            if noeud.func.attr == "bindparams":
                lignes += [n for k in noeud.keywords if (n := _est_isoformat(k.value))]
        if isinstance(noeud, ast.Dict):
            for cle, valeur in zip(noeud.keys, noeud.values):
                if isinstance(cle, ast.Constant) and cle.value in parametres:
                    if n := _est_isoformat(valeur):
                        lignes.append(n)
    return sorted(set(lignes))


def test_aucune_date_passee_en_chaine_iso_a_une_requete():
    fichiers = modules_app()
    assert fichiers, f"aucun module sous {_APP} — le contrôle ne mesure rien"
    fautifs = [
        f"{m.chemin.relative_to(_APP)}:{n}" for m in fichiers for n in isoformat_lies(m.source)
    ]
    assert not fautifs, (
        "`.isoformat()` passé comme valeur à une requête SQL : la base compare alors "
        "du texte à un horodatage, et se trompe ou refuse. Lier "
        "le `datetime` lui-même (UTC naïf, `horloge.maintenant()`) :\n" + "\n".join(fautifs)
    )


def test_le_controle_reconnait_la_forme_fautive():
    """La ligne d'avant #1298 est refusée ; la forme corrigée passe."""
    assert isoformat_lies(
        'conn.execute(text("DELETE FROM t WHERE c < :now"), {"now": m.isoformat()})'
    ) == [1]
    assert isoformat_lies('text("…").bindparams(seuil=(m - d).isoformat())') == [1]
    assert isoformat_lies('conn.execute(text("DELETE FROM t WHERE c < :now"), {"now": m})') == []
    #  🔴 La forme de `maintenance.purger()` : le dict transite par un tuple.
    assert isoformat_lies('E = (("DELETE FROM t WHERE c < :now", {"now": m.isoformat()}),)') == [1]
    #  Une date sérialisée hors de toute requête (un journal, un JSON) est libre.
    assert isoformat_lies('journal = {"quand": m.isoformat()}') == []
