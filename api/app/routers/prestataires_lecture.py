"""La LECTURE d'un prestataire et d'un contrat — ce qui s'en déduit compris.

Sortie de `routers/prestataires.py` le 04/11/2026 (#2507), qui touchait les 500
lignes : les champs servis à l'app iOS (note moyenne, prochaine visite, échéance,
fréquence, équipement effectif) s'ajoutaient à la lecture, pas aux routes. La
liste, les archives (`prestataires_archivage`), la création, la correction et la
synthèse d'un prestataire passent toutes par ici : un champ déduit ne garde pas sa
valeur par défaut sur l'une d'elles (#1687, classe de #1563).
"""

from __future__ import annotations

import json

from sqlalchemy import func
from sqlmodel import Session, select

from app.models.core import ContratEntretien, Prestataire
from app.routers.prestataires_schemas import ContratRead, PrestataireRead
from app.utils.archivage import est_archivable
from app.utils.carnet_entretien import type_equipement_resolu
from app.utils.echeance_contrat import poser_echeance
from app.utils.frequence_contrat import frequence_libelle
from app.utils.notes_prestataires import SANS_AVIS, notes_des_prestataires
from app.utils.recuperer import ou_rien, precharger


def lire_prestataires(session: Session, prests: list[Prestataire]) -> list[PrestataireRead]:
    """Les fiches, leur note et leur prochaine visite lues en une fois pour la liste."""
    ids = [p.id for p in prests]
    notes = notes_des_prestataires(session, ids)
    #  La prochaine visite d'un prestataire : la plus proche de ses contrats EN COURS
    #  (les archivés ne prévoient plus rien) — ce que la carte montrait, calculé
    #  dans l'écran sur la liste des contrats chargée (`nextVisitForPrest`).
    visites: dict[int, object] = {}
    if ids:
        for c in session.exec(
            select(ContratEntretien).where(ContratEntretien.prestataire_id.in_(ids))  # type: ignore[union-attr]
        ).all():
            if c.prochaine_visite and not est_archivable("contrat", c):
                courante = visites.get(c.prestataire_id)
                if courante is None or c.prochaine_visite < courante:
                    visites[c.prestataire_id] = c.prochaine_visite
    lus = []
    for p in prests:
        data = PrestataireRead.model_validate(p)
        #  Calculé par la règle déclarée, jamais relu de `actif` par l'écran (#1538).
        data.archivee = est_archivable("prestataire", p)
        if p.contacts_json:
            try:
                data.contacts = json.loads(p.contacts_json)
            except Exception:
                data.contacts = []
        data.note_moyenne, data.nb_notations = notes.get(p.id, SANS_AVIS)
        data.prochaine_visite = visites.get(p.id)
        lus.append(data)
    return lus


def lire_prestataire(session: Session, p: Prestataire) -> PrestataireRead:
    """Une fiche, par le même chemin que la liste."""
    return lire_prestataires(session, [p])[0]


def lister_prestataires(session: Session, archivees: bool) -> list[PrestataireRead]:
    """Les fiches courantes, ou celles des Archives (`GET /prestataires/archives`).

    Par ordre ALPHABÉTIQUE (#1145) : on cherche une entreprise par son nom, et
    l'ordre d'insertion n'aidait personne. Sans tenir compte de la casse.
    📦 Le partage courants / Archives suit la règle déclarée (#1538), comme les
    affiches de hall : la décision vit dans `REGLES`, pas dans un `WHERE`.
    """
    prests = session.exec(select(Prestataire).order_by(func.lower(Prestataire.nom))).all()
    return lire_prestataires(
        session, [p for p in prests if est_archivable("prestataire", p) == archivees]
    )


def lister_contrats(session: Session, archivees: bool) -> list[ContratRead]:
    """Les contrats courants, ou ceux des Archives (`GET …/contrats/archives`)."""
    contrats = [
        c
        for c in session.exec(select(ContratEntretien)).all()
        if est_archivable("contrat", c) == archivees
    ]
    return lire_contrats(session, contrats)


def lire_contrats(session: Session, contrats: list[ContratEntretien]) -> list[ContratRead]:
    """La lecture d'un contrat, ce qui s'en DÉDUIT compris : échéance, archivage, ✨.

    La liste et la synthèse d'un prestataire passent par elle : la synthèse les
    relisait par `ContratRead.model_validate` seul, et `date_fin`, `reconduit`,
    `echu`… y gardaient leur valeur par défaut (#1687, classe de #1563).
    """
    #  ⚠️ La configuration de l'assistant se lit UNE fois, pas par contrat : elle
    #  est la même pour tous, et la relire à chaque ligne ferait autant d'allers
    #  en base que de contrats pour une réponse identique.
    from app.utils.llm import config_llm
    from app.utils.llm_usages import USAGE_SYNTHESE_CONTRAT
    from app.utils.synthese_contrat import documents_du_contrat

    cfg = config_llm(session, USAGE_SYNTHESE_CONTRAT)
    #  La MÊME règle que `synthese_disponible` — activation aux deux étages, clé,
    #  modèle de l'usage —, lue une fois ; seule la partie « ce contrat a-t-il
    #  un document » se rejoue par ligne.
    assistant_pret = cfg.pret
    #  Les prestataires des contrats, chargés d'une requête : l'équipement effectif
    #  lit leur spécialité (#1838). La liste est GARDÉE tant que les lectures durent.
    prestataires = precharger(session, Prestataire, [c.prestataire_id for c in contrats])

    lus = []
    for c in contrats:
        lu = poser_echeance(ContratRead.model_validate(c), c)
        lu.archivee = est_archivable("contrat", c)
        lu.synthese_disponible = assistant_pret and (
            not cfg.envoi_document or bool(documents_du_contrat(session, c))
        )
        lu.frequence_libelle = frequence_libelle(c.frequence_type, c.frequence_valeur)
        prest = ou_rien(session, Prestataire, c.prestataire_id)
        lu.equipement_effectif = type_equipement_resolu(c, prest.specialite if prest else None)
        lus.append(lu)
    del prestataires
    return lus


def lire_contrat(session: Session, c: ContratEntretien) -> ContratRead:
    """Un contrat, par le même chemin que la liste."""
    return lire_contrats(session, [c])[0]


__all__ = [
    "lire_contrat",
    "lire_contrats",
    "lire_prestataire",
    "lire_prestataires",
    "lister_contrats",
    "lister_prestataires",
]
