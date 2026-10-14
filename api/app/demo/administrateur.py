"""L'administrateur de la démo : celui du seed, RÉSERVÉ (spec `mode-demo.md` §5.2, #1932).

Le seed crée l'administrateur initial d'une installation standard — administrateur
de la copropriété ET opérateur de l'installation, donc celui qui tient
l'inscription au registre (contact, bail). Son mot de passe est aléatoire et ne
paraît que dans le journal de la remise à zéro, qui le recrée chaque nuit.

Demandé par l'auteur le 14/10/2026 : un mot de passe **fixe**, comme les comptes
publics — mais **secret**, contrairement à eux : il se lit dans
`DEMO_ADMIN_MOT_DE_PASSE`, le `.env` du serveur de démo, jamais dans le dépôt ni
sur la page « Démo ». Absent, rien ne change : aléatoire, journalisé.

Il passe par la règle de robustesse du produit AVANT toute écriture
(`verifier_avant_chargement`) — un mot de passe faible arrête le chargement sur
une base intacte, au lieu de laisser une démo à moitié chargée — puis par la seule
porte qui pose un mot de passe (`poser_mot_de_passe`).
"""

from __future__ import annotations

from sqlmodel import Session, select

from app.config import get_settings
from app.models.core import RoleUtilisateur, Utilisateur
from app.utils.mots_de_passe import poser_mot_de_passe, verifier_robustesse


def _secret() -> str:
    return get_settings().demo_admin_mot_de_passe.strip()


def verifier_avant_chargement() -> None:
    """Lève `HTTPException` 400 si le mot de passe du `.env` est trop faible."""
    if _secret():
        verifier_robustesse(_secret())


def initial(session: Session) -> Utilisateur:
    """Celui que le seed vient de créer : le seul administrateur de la base."""
    return session.exec(select(Utilisateur).where(Utilisateur.role == RoleUtilisateur.admin)).one()


def fixer_mot_de_passe(session: Session, admin: Utilisateur) -> bool:
    """Pose le mot de passe du `.env`, s'il y en a un. Rend vrai s'il a été posé."""
    if not _secret():
        return False
    poser_mot_de_passe(session, admin, _secret())
    return True
