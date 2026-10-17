"""Ce que l'API fait au démarrage, pour CHAQUE copropriété (#2053, spec §4.6).

Ces trois gestes vivaient dans le `lifespan` de `main.py`, sans copropriété nommée :
ils s'appliquaient à « la » copropriété de la configuration. Une installation
COMMUNE n'en a pas (`contexte.HorsCopropriete`) ; chacune de ses copropriétés a sa
base, donc ses données de démarrage, ses jetons à purger et ses sauvegardes
orphelines.

- **installation propre à une copropriété** (5Hostachy) : un tour, et une erreur
  ARRÊTE le démarrage, comme avant ;
- **installation commune** : un tour par copropriété, l'échec de l'une ne bloque pas
  les autres (`pour_chaque_copropriete`), et une base non prête est sautée.
"""

from __future__ import annotations

import logging
from datetime import timedelta

from sqlmodel import select

from app import contexte
from app.utils import horloge

logger = logging.getLogger("hostachy.api")


def _purger_les_jetons() -> None:
    """Les jetons de rafraîchissement échus — les échangés restent jusqu'à leur
    expiration : c'est par eux qu'un jeton rejoué se reconnaît."""
    from app.auth.jetons_rafraichissement import purger

    with contexte.nouvelle_session() as session:
        purger(session, horloge.maintenant())
        session.commit()


def _sauvegardes_orphelines() -> None:
    """Une sauvegarde restée « en cours » par un redémarrage en plein travail faussait
    le contrôle de santé « dernière sauvegarde réussie » : elle passe en échec."""
    from app.models.core import HistoriqueSauvegarde, StatutSauvegarde

    with contexte.nouvelle_session() as session:
        seuil = horloge.maintenant() - timedelta(hours=2)
        orphelines = session.exec(
            select(HistoriqueSauvegarde).where(
                (HistoriqueSauvegarde.statut == StatutSauvegarde.en_cours)
                & (HistoriqueSauvegarde.cree_le < seuil)
            )
        ).all()
        for sauvegarde in orphelines:
            sauvegarde.statut = StatutSauvegarde.echouee
            sauvegarde.message_erreur = "Interrompue par redémarrage du conteneur"
            sauvegarde.terminee_le = horloge.maintenant()
            session.add(sauvegarde)
        if orphelines:
            session.commit()
            logger.info(
                "Sauvegardes orphelines nettoyées : %d marquée(s) en échec.", len(orphelines)
            )


def preparer_la_copropriete() -> None:
    """Les données de démarrage absentes, les jetons échus, les sauvegardes orphelines
    — dans la base de la copropriété servie."""
    from app.seed import seed

    seed()
    _purger_les_jetons()
    _sauvegardes_orphelines()


def preparer_les_coproprietes() -> None:
    """`preparer_la_copropriete` pour chacune. Une déclaration invalide ne sert rien
    (503 à tous les hôtes) : rien à préparer, et l'API démarre pour le dire."""
    from app.installation_commune.declaration import DeclarationInvalide

    try:
        contexte.pour_chaque_copropriete(
            preparer_la_copropriete, "demarrage", isoler=contexte.est_commune()
        )()
    except DeclarationInvalide:
        logger.exception("demarrage : declaration des coproprietes invalide, rien de prepare")
