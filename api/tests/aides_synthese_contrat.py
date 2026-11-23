"""Les aides des tests de la synthèse d'un contrat — la fixture, un contrat, un document.

Deux fichiers s'en servent : `test_synthese_contrat.py` (le geste, les exemples,
la consigne) et `test_synthese_contrat_documents.py` (ce qui part au modèle et le
budget de la requête). Elles vivent ici plutôt que d'être recopiées ; `session`
est une fixture : un fichier de tests l'IMPORTE pour que pytest la trouve.
"""

from __future__ import annotations

from datetime import date

import pytest

from app.models.core import ConfigSite
from app.models.documents import Document
from app.models.prestataires import ContratEntretien, Prestataire


@pytest.fixture()
def session(session):
    session.add(Prestataire(id=1, nom="5M Services", specialite="ascenseur"))
    session.commit()
    return session


def _config(session, **kw):
    #  Les DEUX étages (#984) : le commun, et l'usage `synthese_contrat` avec
    #  son activation et son modèle — un usage sans modèle ne part pas.
    valeurs = {
        "llm_actif": "1",
        "llm_api_key": "sk-x",
        "llm_envoi_document": "1",
        "llm_synthese_contrat_actif": "1",
        "llm_synthese_contrat_modele": "gpt-4o-mini",
    }
    valeurs.update(kw)
    for cle, valeur in valeurs.items():
        existant = session.get(ConfigSite, cle)
        if existant:
            existant.valeur = valeur
            session.add(existant)
        else:
            session.add(ConfigSite(cle=cle, valeur=valeur))
    session.commit()


def _contrat(session, libelle="Ascenseur Bât. 1", **kw):
    c = ContratEntretien(
        copropriete_id=1,
        prestataire_id=1,
        libelle=libelle,
        date_debut=date(2024, 1, 1),
        **kw,
    )
    session.add(c)
    session.commit()
    session.refresh(c)
    return c


def _document(session, contrat, **kw):
    kw.setdefault("titre", "Contrat")
    kw.setdefault("fichier_cle", "prive/introuvable.pdf")
    d = Document(
        fichier_nom="c.pdf",
        mime_type="application/pdf",
        contrat_id=contrat.id,
        publie_par_id=1,
        **kw,
    )
    session.add(d)
    session.commit()
    session.refresh(d)
    return d
