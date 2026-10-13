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
    "resident": 0,
    "Jean Dupont": 0,
    "Odile Perrin": 1,
    "Luc Faure": 0,
    "Paul Morel": 2,
    "Camille Robin": 0,
    "Marcel Roy": 1,
}
_VOTES_FETE = {
    "resident": 1,
    "conseil-syndical": 1,
    "Alice Mercier": 0,
    "Hélène Caron": 1,
    "Inès Zeller": 1,
    "Christophe Renard": 0,
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
        "conseil-syndical",
        dans(10),
        ("Oui", "Non", "Sans avis"),
        _VOTES_BORNES,
    )
    _sondage(
        session,
        comptes,
        "Quelle date pour la fête des voisins ?",
        "Le vote est clos : la fête aura lieu le samedi.",
        "conseil-syndical",
        il_y_a(20),
        ("Vendredi soir", "Samedi midi"),
        _VOTES_FETE,
    )

    for titre, description, auteur, statut, jours, votants in (
        (
            "Un composteur partagé au fond du jardin",
            "Pour réduire nos déchets et nourrir les massifs.",
            "Alice Mercier",
            "retenue",
            30,
            ("resident", "Odile Perrin", "Inès Zeller"),
        ),
        (
            "Une boîte à livres dans le hall du bâtiment A",
            "Déposer et emprunter des livres librement.",
            "resident",
            "ouverte",
            7,
            ("Paul Morel", "Nadia Rossi"),
        ),
        (
            "Des nichoirs dans les arbres",
            "Pour accueillir les mésanges au printemps.",
            "Camille Robin",
            "ouverte",
            3,
            ("locataire",),
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
            "Luc Faure",
            "vente",
            "divers",
            40,
        ),
        (
            "Donne cartons de déménagement",
            "<p>Une vingtaine, à venir chercher.</p>",
            "Zoé Dupré",
            "don",
            "divers",
            None,
        ),
        (
            "Cherche place de parking à louer",
            "<p>Pour une petite voiture, à l'année.</p>",
            "locataire",
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
