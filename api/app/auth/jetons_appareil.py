"""Le jeton d'un APPAREIL appairé : une portée, et rien d'autre (#2770, #2771).

## Un seul mécanisme, deux portées

Une montre et un écran de hall lisent l'API sans session de personne : chacun porte un
jeton propre, présenté en `Authorization: Bearer`. Deux mécanismes auraient fini avec
deux règles d'accès divergentes (`standards/03` §1, capacité dupliquée) : il n'y en a
qu'UN, et ce qui distingue les deux appareils tient dans une ligne de `PORTEES`.

| Portée | Sujet | Routes ouvertes | Émis par | Échéance |
|---|---|---|---|---|
| `montre` | un compte (et son installation) | `GET /notifications` | le téléphone connecté (`POST /montres`) | fixe, renouvelée par le téléphone |
| `ecran` | un écran de hall, sans personne | `GET /ecrans/moi/affiches` et leurs images | l'appairage RFC 8628, confirmé par le conseil | glissante : chaque lecture la repousse |

## 🔴 La table EST la règle — défaut fermé

`route_ouverte(portée, méthode, chemin)` est la seule question : elle lit le chemin
DEMANDÉ (pas celui que déclare un routeur, que l'inclusion raccourcit) contre les
gabarits de la table. Une route absente, une méthode absente, une portée inconnue :
refus. Aucun routeur ne décide ; une route ne lit un jeton d'appareil que par
`auth/deps._appareil_autorise`, qui pose cette question avant de rendre le sujet.

## Ce qui est commun

- **Empreinte** (`auth/empreinte_jeton`, #1389) : le brut n'est rendu qu'une fois, à
  l'émission ou au renouvellement, et ne vit ensuite que sur l'appareil.
- **Échéance** (`echeance`) et **lecture** (`noter_lecture` : `vu_le`, et l'échéance
  repoussée pour une portée glissante).
- **Rotation** (`renouveler`) : un brut neuf, l'ancien cesse aussitôt de servir.
- **Révocation** : supprimer la ligne. Le jeton d'une montre tombe aussi quand le compte
  change d'empreinte (`_sujet_montre`) ; celui d'un écran, quand le conseil le retire.
- **Purge** des échus (`purger_echus`), au démarrage et par la maintenance — sauf pour
  une portée dont la ligne EST l'objet que l'on voit (`purge=False` : un écran échu
  reste dans la liste du conseil, marqué comme tel, jusqu'à ce qu'il le retire).

🔒 `tests/test_jetons_appareil.py` balaie TOUTES les routes de l'application pour
CHAQUE portée ; `test_jetons_montre.py`, `test_ecrans.py`.
"""

from __future__ import annotations

import re
import secrets
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any, Callable, Optional

from sqlmodel import Session, delete, select

from app.auth.empreinte_jeton import empreinte
from app.auth.jwt import empreinte_du_compte
from app.models.core import Utilisateur
from app.models.ecrans import Ecran
from app.models.jetons import JetonMontre


@dataclass(frozen=True)
class Portee:
    #: `(méthode, gabarit du chemin servi par l'API)` — `{nom}` vaut un segment.
    routes: frozenset[tuple[str, str]]
    #: La durée de vie d'un jeton, à l'émission comme à chaque repoussée.
    duree: timedelta
    #: Vrai : chaque lecture repousse l'échéance (un écran qui lit reste appairé).
    glissante: bool
    #: La table qui porte l'empreinte, l'échéance et la dernière lecture.
    modele: type
    #: Le sujet d'une ligne valide, ou `None` si elle ne doit plus rien ouvrir.
    sujet: Callable[[Session, Any], Any]
    #: Vrai : la maintenance supprime les lignes échues.
    purge: bool


def _sujet_montre(session: Session, jeton: JetonMontre) -> Optional[Utilisateur]:
    """Le compte d'une montre — `None` s'il est inactif ou a changé d'empreinte depuis
    l'émission (mot de passe posé, jeton de rafraîchissement rejoué, #1063)."""
    user = session.get(Utilisateur, jeton.utilisateur_id)
    if user is None or not user.actif:
        return None
    if jeton.empreinte_compte != empreinte_du_compte(
        user.hashed_password, user.generation_sessions
    ):
        return None
    return user


def _sujet_ecran(_session: Session, ecran: Ecran) -> Ecran:
    """Un écran est son propre sujet : aucune personne derrière lui."""
    return ecran


#: 🔴 LA table des routes ouvertes par portée. Ajouter une ligne ici ouvre une route à
#: un appareil : c'est une décision de sécurité, tenue par `test_jetons_appareil.py`.
PORTEES: dict[str, Portee] = {
    #  La cloche de la personne, en lecture (#2771, arrêté le 16/11/2026) : ni `/auth/me`,
    #  ni marquage comme lu. La même pour Apple Watch et Wear OS.
    "montre": Portee(
        routes=frozenset({("GET", "/notifications")}),
        duree=timedelta(days=30),
        glissante=False,
        modele=JetonMontre,
        sujet=_sujet_montre,
        purge=True,
    ),
    #  Les affiches de son périmètre, et leurs images (#2770) : un lieu lu par tous, la
    #  sortie ne porte aucune donnée personnelle (`utils/ecran_affiches`).
    "ecran": Portee(
        routes=frozenset(
            {
                ("GET", "/ecrans/moi/affiches"),
                ("GET", "/ecrans/moi/affiches/{affiche_id}/images/{rang}"),
            }
        ),
        duree=timedelta(days=30),
        glissante=True,
        modele=Ecran,
        sujet=_sujet_ecran,
        purge=False,
    ),
}


def _motif(gabarit: str) -> re.Pattern[str]:
    """`/a/{x}/b` → `^/a/[^/]+/b$` : un paramètre de chemin vaut UN segment, jamais `/`."""
    morceaux = re.split(r"\{[^}/]+\}", gabarit)
    return re.compile(
        "".join(re.escape(m) + "[^/]+" for m in morceaux[:-1]) + re.escape(morceaux[-1])
    )


def route_ouverte(portee: str, methode: str, chemin: str) -> bool:
    """Cette portée ouvre-t-elle cette requête ? Défaut FERMÉ : portée ou route inconnue → non."""
    p = PORTEES.get(portee)
    if p is None:
        return False
    return any(m == methode and _motif(g).fullmatch(chemin) for m, g in p.routes)


def echeance(portee: str, maintenant: datetime) -> datetime:
    return maintenant + PORTEES[portee].duree


def nouveau_brut() -> str:
    """Un jeton brut : 256 bits, rendu une fois, jamais stocké tel quel."""
    return secrets.token_urlsafe(32)


@dataclass(frozen=True)
class JetonLu:
    """Un jeton d'appareil reconnu : sa portée, sa ligne, son sujet."""

    portee: str
    ligne: Any
    sujet: Any


def jeton_lu(session: Session, brut: str, maintenant: datetime) -> Optional[JetonLu]:
    """Le jeton d'appareil valide qui porte ce brut, ou `None` : inconnu, échu, retiré, ou
    dont le sujet ne doit plus rien ouvrir. Sans effet : `noter_lecture` vient après la
    question de la route."""
    if not brut:
        return None
    for nom, p in PORTEES.items():
        ligne = session.exec(select(p.modele).where(p.modele.empreinte == empreinte(brut))).first()
        if ligne is None:
            continue
        if ligne.expire_le <= maintenant:
            return None
        sujet = p.sujet(session, ligne)
        return None if sujet is None else JetonLu(nom, ligne, sujet)
    return None


def noter_lecture(session: Session, lu: JetonLu, maintenant: datetime) -> None:
    """La dernière lecture (`vu_le`) ; l'échéance repoussée si la portée est glissante."""
    lu.ligne.vu_le = maintenant
    if PORTEES[lu.portee].glissante:
        lu.ligne.expire_le = echeance(lu.portee, maintenant)
    session.add(lu.ligne)
    session.commit()


def renouveler(session: Session, portee: str, ligne: Any, maintenant: datetime) -> str:
    """Rotation : un brut neuf, l'échéance repoussée. L'ancien brut cesse aussitôt de
    servir. Rend le neuf ; ne valide pas la transaction."""
    brut = nouveau_brut()
    ligne.empreinte = empreinte(brut)
    ligne.expire_le = echeance(portee, maintenant)
    session.add(ligne)
    return brut


def purger_echus(session: Session, maintenant: datetime) -> int:
    """Supprime les jetons échus des portées qui se purgent. Ne valide pas la transaction."""
    total = 0
    for p in PORTEES.values():
        if p.purge:
            resultat = session.exec(delete(p.modele).where(p.modele.expire_le <= maintenant))
            total += resultat.rowcount or 0
    return total
