"""L'administrateur et l'opérateur de la démo : ceux du seed (spec `mode-demo.md` §5.2).

Le seed crée deux comptes techniques (#1985) : l'**administrateur** de la copropriété
(admin seul) et l'**opérateur** de l'installation (admin + opérateur), qui tient
l'inscription au registre (contrat, bail), la santé et la base. Séparés pour que
l'administrateur puisse être CONFIÉ aux visiteurs sans leur livrer l'opérateur :
les routes du registre restent ouvertes en démo (`utils/demo.py`).

Leurs mots de passe sont aléatoires et ne paraissent que dans le journal de la
remise à zéro, qui les recrée chaque nuit — sauf si le `.env` du serveur de démo
les fixe, jamais le dépôt :

- `DEMO_ADMIN_MOT_DE_PASSE` — l'administrateur ; l'auteur peut le publier sur la
  page « Démo » du site vitrine ;
- `DEMO_OPERATEUR_MOT_DE_PASSE` — l'opérateur ; **jamais publié**.

Chacun passe par la règle de robustesse du produit AVANT toute écriture
(`verifier_avant_chargement`) — un mot de passe faible arrête le chargement sur
une base intacte, au lieu de laisser une démo à moitié chargée — puis par la seule
porte qui pose un mot de passe (`poser_mot_de_passe`).
"""

from __future__ import annotations

from sqlmodel import Session

from app.auth.adresse_compte import compte_par_adresse
from app.config import get_settings
from app.models.core import Utilisateur
from app.seed import ADRESSE_ADMIN_INITIAL, ADRESSE_OPERATEUR_INITIAL
from app.utils.mots_de_passe import poser_mot_de_passe, verifier_robustesse

#: Adresse du compte → réglage du `.env` qui fixe son mot de passe.
_SECRETS: dict[str, str] = {
    ADRESSE_ADMIN_INITIAL: "demo_admin_mot_de_passe",
    ADRESSE_OPERATEUR_INITIAL: "demo_operateur_mot_de_passe",
}


def _secret(adresse: str) -> str:
    return getattr(get_settings(), _SECRETS[adresse]).strip()


def verifier_avant_chargement() -> None:
    """Lève `HTTPException` 400 si un mot de passe du `.env` est trop faible."""
    for adresse in _SECRETS:
        if _secret(adresse):
            verifier_robustesse(_secret(adresse))


def _compte(session: Session, adresse: str) -> Utilisateur:
    compte = compte_par_adresse(session, adresse)
    if compte is None:
        raise LookupError(f"Compte technique absent après le seed : {adresse}")
    return compte


def initial(session: Session) -> Utilisateur:
    """L'administrateur de la copropriété que le seed vient de créer (admin seul)."""
    return _compte(session, ADRESSE_ADMIN_INITIAL)


def operateur(session: Session) -> Utilisateur:
    """L'opérateur que le seed vient de créer (admin + opérateur)."""
    return _compte(session, ADRESSE_OPERATEUR_INITIAL)


def fixer_mot_de_passe(session: Session, compte: Utilisateur) -> bool:
    """Pose le mot de passe du `.env` pour ce compte, s'il y en a un. Rend vrai s'il a été posé."""
    if not _secret(compte.email):
        return False
    poser_mot_de_passe(session, compte, _secret(compte.email))
    return True
