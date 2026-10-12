"""Migrer la base `plateforme`, puis y inscrire la référence — `python -m app.registre.migrer`.

Appelé par `api/start.sh` au démarrage, SANS `set -e` sur son résultat : un échec ici
se dit (« registre : … ») et laisse la résidence démarrer — le registre ne doit
jamais arrêter la résidence (`registre/base.py`). Sa dernière ligne est le verdict :
`eteint`, `pret`, ou `echec: <raison>`.
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlmodel import Session, select

from app.registre.base import moteur, registre_actif
from app.registre.modeles import IDENTIFIANT_REFERENCE, EtatInscription, Installation
from app.utils import horloge

logger = logging.getLogger("hostachy.registre")

#: Le dossier des migrations de la plateforme, à côté de celui de la résidence.
SCRIPTS = Path(__file__).resolve().parents[2] / "alembic_plateforme"


def configuration(connection) -> Config:
    """La configuration Alembic de la chaîne `plateforme`, sur une connexion donnée."""
    cfg = Config()
    cfg.set_main_option("script_location", str(SCRIPTS))
    cfg.attributes["connection"] = connection
    return cfg


def migrer(engine) -> None:
    """Porte la base `plateforme` à la tête de sa chaîne."""
    with engine.begin() as connection:
        command.upgrade(configuration(connection), "head")


def inscrire_reference(session: Session) -> Installation:
    """La référence figure dans son propre registre, canal `main`, active (§4.11, règle 7)."""
    reference = session.exec(
        select(Installation).where(Installation.identifiant == IDENTIFIANT_REFERENCE)
    ).first()
    if reference is None:
        reference = Installation(
            identifiant=IDENTIFIANT_REFERENCE, etat=EtatInscription.active, canal="main"
        )
        session.add(reference)
        session.commit()
        session.refresh(reference)
    return reference


def preparer() -> str:
    """Le verdict du démarrage : `eteint`, `pret` ou `echec: …` — jamais une exception."""
    if not registre_actif():
        return "eteint"
    try:
        engine = moteur()
        migrer(engine)
        with Session(engine) as session:
            reference = inscrire_reference(session)
            reference.vue_le = horloge.maintenant()
            session.add(reference)
            session.commit()
    except Exception as exc:  # noqa: BLE001 — le verdict le dit, la résidence démarre
        logger.warning("registre : base plateforme non préparée (%s)", type(exc).__name__)
        return f"echec: {type(exc).__name__}"
    return "pret"


if __name__ == "__main__":
    print(preparer())
    sys.exit(0)
