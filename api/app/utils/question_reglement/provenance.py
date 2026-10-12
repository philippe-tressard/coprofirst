"""D'où vient le texte que l'assistant lit — la provenance du règlement (11/10/2026).

Chaque avis se termine par « Rédigé par …, d'après {provenance}. » — par exemple
« la numérisation du RCP et de ses modifications de 1995 et 2005 ». La date de
chargement des fichiers, qui y figurait, ne disait rien au lecteur ; ce qu'il
veut savoir, c'est QUELS actes ont été lus.

## Saisie par l'administration, jamais écrite dans le code

Les actes d'une copropriété ne sont pas ceux d'une autre, et le dépôt est
public : la phrase vit dans `ConfigSite` (clé `CLE`), saisie dans Ma résidence ›
Règlement. Chaque question garde la provenance du moment où elle a été posée
(`QuestionReglement.provenance`) ; une question plus ancienne que la saisie lit
la provenance actuelle.

Du TEXTE : l'écran l'interpole, il ne l'interprète jamais en HTML.
"""

from __future__ import annotations

from typing import Optional

from sqlmodel import Session

from app.models.core import ConfigSite
from app.utils.config_site import ecrire_cle

#: La clé de `ConfigSite` qui porte la provenance de CETTE copropriété.
CLE = "reglement_provenance"
#: Une phrase, pas un inventaire des actes.
MAX_CARACTERES = 300


def lire_provenance(session: Session) -> Optional[str]:
    """La provenance saisie, ou `None` si l'administration n'en a pas saisi."""
    ligne = session.get(ConfigSite, CLE)
    return (ligne.valeur.strip() or None) if ligne else None


def enregistrer_provenance(session: Session, provenance: str) -> str:
    """Écrit la provenance (le schéma de la route a déjà borné sa longueur)."""
    valeur = provenance.strip()
    ecrire_cle(session, CLE, valeur)
    session.commit()
    return valeur


__all__ = ["CLE", "MAX_CARACTERES", "enregistrer_provenance", "lire_provenance"]
