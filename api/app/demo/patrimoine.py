"""La résidence fictive : copropriété, bâtiments et lots (spec §6.2).

Posés AVANT le seed : son arbre des périmètres ne crée un nœud que pour les
bâtiments présents en base, et il ne pose sa copropriété « Ma Résidence » que
sur une base qui n'en a aucune.
"""

from __future__ import annotations

from dataclasses import dataclass

from sqlmodel import Session

from app.models.copropriete import Batiment, Copropriete, Lot, TypeLot

#: Le nom de la résidence inventée, affiché partout (`site_nom`).
NOM_RESIDENCE = "Résidence Les Glycines"

#: Trois bâtiments de quatre niveaux, deux appartements par niveau.
BATIMENTS = ("A", "B", "C")
NIVEAUX = 4
PAR_NIVEAU = 2
PARKINGS = 6

_TYPES = ("T2", "T3", "T4", "T3")


@dataclass
class Patrimoine:
    copro: Copropriete
    batiments: dict[str, Batiment]
    #: Les appartements, par numéro (« A01 », « B32 »…).
    appartements: dict[str, Lot]
    parkings: list[Lot]


def poser(session: Session) -> Patrimoine:
    copro = Copropriete(
        nom=NOM_RESIDENCE,
        adresse="12 allée des Glycines, 99000 Ville-Exemple",
        annee_construction=1974,
        nb_lots_total=len(BATIMENTS) * NIVEAUX * PAR_NIVEAU + PARKINGS,
        nb_lots_principaux=len(BATIMENTS) * NIVEAUX * PAR_NIVEAU,
    )
    session.add(copro)
    session.flush()

    batiments = {}
    appartements = {}
    for lettre in BATIMENTS:
        bat = Batiment(
            copropriete_id=copro.id,
            numero=lettre,
            nb_etages=NIVEAUX - 1,
            nb_appartements=NIVEAUX * PAR_NIVEAU,
        )
        session.add(bat)
        session.flush()
        batiments[lettre] = bat
        for niveau in range(NIVEAUX):
            for rang in range(1, PAR_NIVEAU + 1):
                numero = f"{lettre}{niveau}{rang}"
                lot = Lot(
                    numero=numero,
                    type=TypeLot.appartement,
                    batiment_id=bat.id,
                    type_appartement=_TYPES[(niveau + rang) % len(_TYPES)],
                    etage=niveau,
                    superficie=48 + 14 * ((niveau + rang) % 4),
                )
                session.add(lot)
                appartements[numero] = lot

    parkings = []
    for rang in range(1, PARKINGS + 1):
        lot = Lot(numero=f"P{rang:02d}", type=TypeLot.parking)
        session.add(lot)
        parkings.append(lot)
    session.flush()
    return Patrimoine(copro, batiments, appartements, parkings)
