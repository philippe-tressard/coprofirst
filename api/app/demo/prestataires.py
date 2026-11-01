"""Les prestataires et leurs contrats — le carnet d'entretien s'en déduit (spec §6.2).

Entreprises inventées, téléphones dans la plage que l'ARCEP réserve à la fiction
(01 99 00 xx xx). Le périmètre d'un contrat passe par la règle du routeur
(`_appliquer_perimetre`), seul point qui en dérive le bâtiment.
"""

from __future__ import annotations

from dataclasses import dataclass

from sqlmodel import Session

from app.demo.dates import jour
from app.demo.patrimoine import Patrimoine
from app.models.prestataires import (
    ContratEntretien,
    NotationPrestataire,
    Prestataire,
    TypePrestataire,
)
from app.routers.prestataires import _appliquer_perimetre
from app.utils.equipements import SYNDIC


@dataclass
class Prestataires:
    par_code: dict[str, Prestataire]
    contrats: dict[str, ContratEntretien]


def _prestataire(session, code, **champs) -> tuple[str, Prestataire]:
    p = Prestataire(**champs)
    session.add(p)
    return code, p


def poser(session: Session, pat: Patrimoine, auteur_id: int) -> Prestataires:
    par_code = dict(
        (
            _prestataire(
                session,
                "ascenseurs",
                nom="Ascenseurs Collard",
                specialite="Ascenseurs",
                type_prestataire=TypePrestataire.maintenance_depannage,
                telephone="01 99 00 10 01",
            ),
            _prestataire(
                session,
                "plomberie",
                nom="Plomberie Renard",
                specialite="Plomberie",
                type_prestataire=TypePrestataire.maintenance_depannage,
                telephone="01 99 00 10 02",
            ),
            _prestataire(
                session,
                "jardins",
                nom="Espaces verts Robin",
                specialite="Espaces verts",
                type_prestataire=TypePrestataire.maintenance_depannage,
                telephone="01 99 00 10 03",
            ),
            _prestataire(
                session,
                "incendie",
                nom="Sécurité incendie Morel",
                specialite="Extincteurs",
                type_prestataire=TypePrestataire.reglementaire,
                telephone="01 99 00 10 04",
            ),
            _prestataire(
                session,
                "syndic",
                nom="Cabinet Kerbrat",
                specialite="Syndic de copropriété",
                type_prestataire=TypePrestataire.gestion,
                telephone="01 99 00 10 05",
            ),
        )
    )
    session.flush()

    bat_a = f"bat:{pat.batiments['A'].id}"
    contrats = {}
    for code, prest, equipement, libelle, debut, frequence, visite, codes in (
        (
            "ascenseurs",
            "ascenseurs",
            "ascenseur",
            "Maintenance des ascenseurs",
            -400,
            ("mois", 1),
            9,
            [bat_a],
        ),
        (
            "jardins",
            "jardins",
            "espaces_verts",
            "Entretien des espaces verts",
            -200,
            ("mois", 1),
            4,
            None,
        ),
        (
            "extincteurs",
            "incendie",
            "extincteurs",
            "Vérification des extincteurs",
            -310,
            ("fois_par_an", 1),
            55,
            None,
        ),
        ("syndic", "syndic", SYNDIC, "Contrat de syndic", -300, None, None, None),
    ):
        contrat = ContratEntretien(
            copropriete_id=pat.copro.id,
            prestataire_id=par_code[prest].id,
            type_equipement=equipement,
            libelle=libelle,
            numero_contrat=f"DEMO-{code.upper()}",
            date_debut=jour(debut),
            duree_initiale_valeur=1,
            duree_initiale_unite="ans",
            frequence_type=frequence[0] if frequence else None,
            frequence_valeur=frequence[1] if frequence else None,
            prochaine_visite=jour(visite) if visite is not None else None,
        )
        _appliquer_perimetre(contrat, codes or [])
        session.add(contrat)
        contrats[code] = contrat
    session.flush()
    pat.copro.syndic_contrat_id = contrats["syndic"].id
    session.add(pat.copro)

    for prest, note, commentaire in (
        ("ascenseurs", 4, "Intervention rapide, bon suivi."),
        ("jardins", 5, "Travail soigné."),
    ):
        session.add(
            NotationPrestataire(
                prestataire_id=par_code[prest].id,
                note=note,
                commentaire=commentaire,
                contrat_id=contrats[prest].id,
                auteur_id=auteur_id,
            )
        )
    return Prestataires(par_code, contrats)
