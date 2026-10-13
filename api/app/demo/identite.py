"""L'identité affichée de la démo : nom, sous-titre, adresse, gestionnaire du site.

Posée APRÈS le seed, qui n'écrit que les clés absentes : ces valeurs-ci priment.
Les textes légaux de la démo : `legal.py` (lot D7, #1907).
"""

from __future__ import annotations

from sqlmodel import Session

from app.demo.patrimoine import NOM_RESIDENCE
from app.models.core import Utilisateur
from app.utils.config_site import ecrire_cle

URL_DEMO = "https://demo.coprofirst.fr"
SOUS_TITRE = "Résidence de démonstration — données fictives, effacées chaque nuit"


def poser(session: Session, administrateur: Utilisateur) -> None:
    for cle, valeur in {
        "site_nom": NOM_RESIDENCE,
        "login_sous_titre": SOUS_TITRE,
        "site_url": URL_DEMO,
        "site_manager_user_id": str(administrateur.id),
    }.items():
        ecrire_cle(session, cle, valeur)
