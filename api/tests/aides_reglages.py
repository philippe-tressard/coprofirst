"""Poser des réglages (`ConfigSite`) dans la base d'un test — écrit une fois (#2950).

`test_alerte_etage.py` (`_config`), `test_assistant_description.py` et
`test_effort_raisonnement.py` (`_poser`) portaient la même boucle, au corps
identique. Elle AJOUTE des lignes : la clé ne doit pas déjà exister dans la base
du test (la fixture `session` du conftest part d'une base neuve). Qui doit
remplacer une valeur déjà posée emploie `aides_synthese_contrat._config`.
"""

from __future__ import annotations

from sqlmodel import Session

from app.models.core import ConfigSite


def poser_reglages(session: Session, **valeurs: str) -> None:
    """Une ligne `ConfigSite` par réglage nommé, puis `commit`."""
    for cle, valeur in valeurs.items():
        session.add(ConfigSite(cle=cle, valeur=valeur))
    session.commit()
