"""Les aides des tests du Reporting CS — une affaire posée en base.

Elle vivait dans `test_suivi_affaires.py` ; le point conseil syndical / syndic
(#2041) en a besoin aussi : elle vit ici plutôt que d'être recopiée (#1495).
"""

from __future__ import annotations

import json

from sqlmodel import Session

from app.models.tickets import Ticket
from tests.aides_base import compte
from tests.aides_horloge import il_y_a_jours

_numero = [0]


def affaire_ouverte(moteur, titre="Interphone muet", *, jours=0, **champs) -> int:
    """Une affaire ouverte il y a `jours` jours, panne de toute la résidence par défaut."""
    _numero[0] += 1
    champs.setdefault("categorie", "panne")
    champs.setdefault("statut", "ouvert")
    champs.setdefault("perimetre_cible", json.dumps(["résidence"], ensure_ascii=False))
    with Session(moteur) as s:
        #  `auteur_id=None` : une affaire sans auteur résident (saisie par le conseil).
        if "auteur_id" not in champs:
            champs["auteur_id"] = compte(s, prefixe="auteur", nom="Durand", prenom="Reine").id
        t = Ticket(
            numero=f"S-{_numero[0]:04d}",
            titre=titre,
            description="<p>La platine ne sonne <strong>plus</strong>.</p>",
            cree_le=il_y_a_jours(jours),
            **champs,
        )
        s.add(t)
        s.commit()
        return t.id
