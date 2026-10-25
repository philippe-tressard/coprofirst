"""Une base de test et des comptes de test, écrits une fois (#1495).

## Pourquoi cette aide existe (30/09/2026)

- **La base de test** (un moteur + `create_all`) était
  recopiée dans trente-quatre fichiers ; la version « de référence » vivait dans
  `aides_badges.py`, un nom qui n'avait rien à voir, importé par des tests qui
  ne parlaient pas de badges. Elle est ici, et `conftest.py` en fait la fixture
  `session` que tout test reçoit sans l'importer.
- **La fabrique de compte** était recopiée dans quarante-huit fichiers — avec,
  dans chacun, un mot de passe passé sous un nom de champ qui **n'existe
  pas** dans `Utilisateur` (le vrai est `hashed_password`). SQLModel l'ignorait sans un mot ; la
  copie s'est propagée parce que personne ne pouvait la voir échouer.
"""

from __future__ import annotations

import os
import uuid
import warnings
from collections.abc import Callable

from sqlmodel import Session, SQLModel

from app.dialecte import poser_schema, retirer_schema, schema_jetable, url_dans_schema
from app.models.core import Utilisateur


def url_des_tests() -> str:
    """Le serveur PostgreSQL des tests (`TESTS_BASE_URL`) — sans lui, aucune base."""
    url = os.environ.get("TESTS_BASE_URL")
    assert url, (
        "TESTS_BASE_URL absent : la suite exige un serveur PostgreSQL "
        "(postgresql+psycopg://essai:essai@127.0.0.1:5432/essai)"
    )
    return url


def moteur_de_test(*, schema: bool = True, cles_etrangeres: bool = False):
    """Une base PostgreSQL propre à l'appelant : un SCHÉMA neuf, retiré à la fin du test.

    `schema=False` rend une base VIDE : c'est ce qu'il faut pour éprouver une
    migration sur les tables qu'elle trouvait, écrites à la main par le test.

    **Les clés sont suspendues sauf `cles_etrangeres=True`** : bien des fixtures
    écrivent un enfant sans son parent. Un test qui juge une SUPPRESSION ou une
    contrainte les demande, et reçoit la règle de la production.

    🔴 **Retiré à la fin du TEST, pas à la libération du moteur** : un moteur gardé
    en vie par une référence de module (un `engine` remplacé, une fermeture) ne
    l'était qu'à la sortie du processus. Deux mesures complètes ont rempli ainsi
    le disque de la base d'essai, en plein passage (09/10/2026). Et chaque
    connexion se FERME dès qu'elle est rendue (`NullPool`) : avec un pool, la
    suite dépassait `max_connections` (« too many clients », 09/10/2026).
    """
    moteur, retirer = schema_jetable(url_des_tests(), cles_etrangeres=cles_etrangeres)
    _A_RETIRER.append(retirer)
    if schema:
        #  `checkfirst=False` : le schéma est NEUF, aucune table n'y existe. La
        #  vérification coûtait une requête au catalogue par table — 89 —, et
        #  ces requêtes ralentissent avec chaque schéma resté sur le serveur.
        SQLModel.metadata.create_all(moteur, checkfirst=False)
    return moteur


def adresse_de_test() -> tuple[str, Callable[[], None]]:
    """L'adresse d'un schéma neuf, pour ce qui prend une URL ; et le geste qui le retire.

    Pour une base qui dure plus qu'un test (fixture de module) ou qu'un autre
    processus ouvre (une ligne de commande). L'appelant libère ses moteurs avant
    de retirer : un pool garde ses connexions, et le retrait les attendrait.
    """
    url = url_des_tests()
    nom = poser_schema(url)
    adresse = url_dans_schema(url, nom).render_as_string(hide_password=False)
    return adresse, lambda: retirer_schema(url, nom)


#: Les schémas posés pendant le test en cours — retirés par la fixture
#: `_retirer_schemas_du_test` de `conftest.py` à la fin du test.
_A_RETIRER: list = []


def retirer_schemas_du_test() -> None:
    """Retire les schémas posés par le test qui s'achève — appelé par `conftest.py`."""
    while _A_RETIRER:
        retirer = _A_RETIRER.pop()
        try:
            retirer()
        except Exception as exc:  # noqa: BLE001 — un retrait manqué ne fait pas échouer le test
            warnings.warn(f"schéma de test non retiré : {exc}", stacklevel=1)


def compte(session: Session, *, prefixe: str = "compte", **champs) -> Utilisateur:
    """Un compte ACTIF, de courriel unique, écrit et relu.

    Tout champ d'`Utilisateur` se passe par nom (`roles_json=`, `statut=`,
    `role=`, `prenom=`…) et prime sur les défauts. Un nom qui n'est PAS un champ
    lève : c'est ce qui a manqué pendant que le faux champ se recopiait.
    """
    inconnus = set(champs) - set(Utilisateur.model_fields)
    assert not inconnus, f"champ(s) inconnu(s) d'Utilisateur : {sorted(inconnus)}"
    valeurs = {
        "email": f"{prefixe}-{uuid.uuid4().hex[:8]}@exemple.test",
        "hashed_password": "x",
        "prenom": "Prénom",
        "nom": "Nom",
        "actif": True,
    }
    valeurs.update(champs)
    u = Utilisateur(**valeurs)
    session.add(u)
    session.commit()
    session.refresh(u)
    return u
