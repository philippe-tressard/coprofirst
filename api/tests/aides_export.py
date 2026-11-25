"""Les bases peuplées qu'éprouvent l'export et l'import d'une copropriété (#1749).

Lecteurs : `test_export_copropriete.py`, `test_droit_differer_cles.py` (#3113).
"""

from __future__ import annotations

from sqlmodel import Session

from app.models.core import ConfigSite, FaqItem, RoleUtilisateur
from tests.aides_base import compte, moteur_de_test


def base_peuplee():
    """Une base de test peuplée de quelques lignes, accents et apostrophes compris."""
    moteur = moteur_de_test()
    with Session(moteur) as s:
        compte(s, prenom="Élodie", nom="D'Aubigné", role=RoleUtilisateur.conseil_syndical)
        compte(s, prenom="Zoé", nom="Martin", actif=False)
        s.add(ConfigSite(cle="site_nom", valeur="Résidence « Les Tilleuls »"))
        s.add(ConfigSite(cle="vide", valeur=""))
        s.add(
            FaqItem(
                categorie="Vie pratique",
                question="Où sont les poubelles ?",
                reponse="Au sous-sol — porte B.",
            )
        )
        s.commit()
    return moteur


def copropriete_et_batiment(moteur, *, copropriete_id=None):
    """Une copropriété et son bâtiment : deux tables qui se citent en cycle.

    `copropriete_id` imposé : le bâtiment est écrit sans son parent (un orphelin).
    """
    from app.models.copropriete import Batiment, Copropriete

    with Session(moteur) as s:
        if copropriete_id is None:
            copro = Copropriete(nom="Résidence d'essai", adresse="1 rue de l'Essai")
            s.add(copro)
            s.commit()
            copropriete_id = copro.id
        s.add(Batiment(copropriete_id=copropriete_id, numero="A"))
        s.commit()
