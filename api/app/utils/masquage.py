"""Masquer ce que publie un autre résident — pour soi seul (#2861).

## Pourquoi

Google Play (contenu des utilisateurs) et l'App Store (règle 1.2) demandent qu'un
utilisateur puisse **bloquer** un utilisateur abusif. Philippe a tranché le
17/11/2026 (« 1a ») : « Masquer ce que publie X », par compte, côté serveur.

## La règle

- Un résident masque un autre résident : ce que celui-ci publie — idées, annonces,
  sondages, réponses et commentaires, affaires, suites et messages d'affaire —
  disparaît de SES listes et de SON fil. Rien n'est supprimé, rien n'est dit à
  l'autre, et le geste se défait dans le Profil.
- 🔴 **Le conseil syndical et l'administration voient tout** : ils modèrent, et un
  masque leur cacherait ce qu'on leur signale. Ils ne masquent pas, et ne sont pas
  masquables : ce qu'ils publient (actualités, consignes, réponses officielles) est
  l'information de la copropriété.
- Masquer n'est pas un droit de lecture : le filtre s'applique APRÈS la visibilité,
  au point où chaque liste est assemblée, par `garder` — jamais une copie.

🔒 `tests/test_masquages.py`.
"""

from __future__ import annotations

from typing import Callable, Iterable, Optional, TypeVar

from sqlmodel import Session, col, select

from app.auth.deps import est_moderateur
from app.models.core import Utilisateur
from app.models.masquages import MasquageAuteur

T = TypeVar("T")

REFUS_SOI = "On ne se masque pas soi-même."
REFUS_MODERATEUR_CIBLE = (
    "Ce que publient le conseil syndical et l'administration ne se masque pas : "
    "c'est l'information de la copropriété."
)
REFUS_MODERATEUR = "Le conseil syndical et l'administration voient tout ce qu'ils modèrent."


def auteurs_masques(session: Session, lecteur: Utilisateur) -> frozenset[int]:
    """Les comptes dont ce lecteur ne veut plus voir les publications — aucun pour
    qui modère, quoi que dise la table."""
    if est_moderateur(lecteur):
        return frozenset()
    ids = session.exec(
        select(MasquageAuteur.auteur_id).where(MasquageAuteur.masque_par_id == lecteur.id)
    ).all()
    if not ids:
        return frozenset()
    #  Un résident masqué puis entré au conseil n'est plus masquable : relu ici,
    #  à chaque lecture, pas figé au moment du geste.
    auteurs = session.exec(select(Utilisateur).where(col(Utilisateur.id).in_(ids))).all()
    return frozenset(u.id for u in auteurs if not est_moderateur(u))


def _auteur(element) -> Optional[int]:
    if isinstance(element, dict):
        return element.get("auteur_id")
    return getattr(element, "auteur_id", None)


def garder(
    elements: Iterable[T],
    masques: frozenset[int],
    auteur: Callable[[T], Optional[int]] = _auteur,
) -> list[T]:
    """Les éléments dont l'auteur n'est pas masqué ; un élément sans auteur reste."""
    if not masques:
        return list(elements)
    return [e for e in elements if auteur(e) not in masques]


def motif_de_refus(lecteur: Utilisateur, auteur: Utilisateur) -> Optional[str]:
    """Pourquoi ce masque ne se pose pas — ou `None` s'il se pose."""
    if est_moderateur(lecteur):
        return REFUS_MODERATEUR
    if auteur.id == lecteur.id:
        return REFUS_SOI
    if est_moderateur(auteur):
        return REFUS_MODERATEUR_CIBLE
    return None


def masques_de(session: Session, lecteur: Utilisateur) -> list[MasquageAuteur]:
    """Les masques de ce lecteur, du plus récent au plus ancien — l'écran du Profil."""
    return list(
        session.exec(
            select(MasquageAuteur)
            .where(MasquageAuteur.masque_par_id == lecteur.id)
            .order_by(col(MasquageAuteur.cree_le).desc())
        ).all()
    )
