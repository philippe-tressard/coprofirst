"""La vie collective : sondages (ouvert et clos), idées, petites annonces (spec §6.2)."""

from __future__ import annotations

from sqlmodel import Session

from app.demo.dates import dans, il_y_a
from app.models.communaute import (
    Idee,
    OptionSondage,
    PetiteAnnonce,
    Sondage,
    VoteIdee,
    VoteSondage,
)
from app.models.core import Utilisateur

#: Les votants, par clé de compte, et l'option choisie (son rang).
_VOTES_BORNES = {
    "user-copro": 0,
    "Jean": 0,
    "Odile": 1,
    "Luc": 0,
    "Paul": 2,
    "Camille": 0,
    "Marcel": 1,
}
_VOTES_FETE = {
    "user-copro": 1,
    "user-cs": 1,
    "Alice": 0,
    "Hélène": 1,
    "Inès": 1,
    "Christophe": 0,
}


def _sondage(session, comptes, question, description, auteur, cloture, options, votes) -> None:
    sondage = Sondage(
        question=question,
        description=description,
        auteur_id=comptes[auteur].id,
        cloture_le=cloture,
        cree_le=il_y_a(18),
    )
    session.add(sondage)
    session.flush()
    rangs = []
    for ordre, libelle in enumerate(options):
        option = OptionSondage(sondage_id=sondage.id, libelle=libelle, ordre=ordre)
        session.add(option)
        rangs.append(option)
    session.flush()
    for cle, rang in votes.items():
        session.add(
            VoteSondage(sondage_id=sondage.id, option_id=rangs[rang].id, user_id=comptes[cle].id)
        )


def poser(session: Session, comptes: dict[str, Utilisateur]) -> None:
    _sondage(
        session,
        comptes,
        "Faut-il installer des bornes de recharge au parking ?",
        "Le conseil étudie l'équipement de quatre places. Votre avis compte.",
        "user-cs",
        dans(10),
        ("Oui", "Non", "Sans avis"),
        _VOTES_BORNES,
    )
    _sondage(
        session,
        comptes,
        "Quelle date pour la fête des voisins ?",
        "Le vote est clos : la fête aura lieu le samedi.",
        "user-cs",
        il_y_a(20),
        ("Vendredi soir", "Samedi midi"),
        _VOTES_FETE,
    )

    for titre, description, auteur, statut, jours, votants in (
        (
            "Un composteur partagé au fond du jardin",
            "Pour réduire nos déchets et nourrir les massifs.",
            "Alice",
            "retenue",
            30,
            ("user-copro", "Odile", "Inès"),
        ),
        (
            "Une boîte à livres dans le hall du bâtiment A",
            "Déposer et emprunter des livres librement.",
            "user-copro",
            "ouverte",
            7,
            ("Paul", "Nadia"),
        ),
        (
            "Des nichoirs dans les arbres",
            "Pour accueillir les mésanges au printemps.",
            "Camille",
            "ouverte",
            3,
            ("user-loc",),
        ),
    ):
        idee = Idee(
            titre=titre,
            description=description,
            auteur_id=comptes[auteur].id,
            statut=statut,
            statut_change_le=il_y_a(jours - 2) if statut != "ouverte" else None,
            cree_le=il_y_a(jours),
        )
        session.add(idee)
        session.flush()
        for cle in votants:
            session.add(VoteIdee(idee_id=idee.id, user_id=comptes[cle].id))

    for titre, description, auteur, type_annonce, categorie, prix in (
        (
            "Vélo enfant 16 pouces",
            "<p>Très bon état, casque offert.</p>",
            "Luc",
            "vente",
            "divers",
            40,
        ),
        (
            "Donne cartons de déménagement",
            "<p>Une vingtaine, à venir chercher.</p>",
            "Zoé",
            "don",
            "divers",
            None,
        ),
        (
            "Cherche place de parking à louer",
            "<p>Pour une petite voiture, à l'année.</p>",
            "user-loc",
            "recherche",
            "parking_cave",
            None,
        ),
    ):
        session.add(
            PetiteAnnonce(
                titre=titre,
                description=description,
                auteur_id=comptes[auteur].id,
                type_annonce=type_annonce,
                categorie=categorie,
                prix=prix,
            )
        )
