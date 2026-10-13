"""Charger la résidence de démonstration dans une base NEUVE (spec §6, lot D4 #1904).

    python -m app.demo.charger

## Les règles

1. **Seulement en démo, seulement sur une base vierge.** La commande refuse si
   l'installation n'est pas la démo (`MODE_DEMO`) ou si la base porte déjà un
   compte : elle ne doit jamais mêler une résidence fictive à une vraie.
2. **Le patrimoine et les comptes AVANT le seed** : son arbre des périmètres ne crée
   un nœud que pour les bâtiments présents, et son administrateur initial n'est pas
   créé quand un administrateur existe — c'est le personnage « Administrateur ».
3. **Le reste APRÈS le seed** : les affaires, contrats et badges lisent l'arbre des
   périmètres, que le seed pose.
4. **Fabriqué, jamais rechargé d'une archive** : le jeu est produit par le code de
   la version installée, avec des dates relatives au jour — il ne peut ni vieillir
   ni être en retard sur le schéma.

La remise à zéro nocturne (lot D5, #1905) vide la base puis appelle cette commande.
"""

from __future__ import annotations

import sys

from sqlmodel import select

from app import contexte
from app.demo import acces, affaires, comptes, fichiers, gouvernance, identite, legal
from app.demo import patrimoine
from app.demo import prestataires, vie_collective
from app.models.core import Utilisateur
from app.seed import seed
from app.utils.demo import est_demo
from app.utils.perimetres import invalider_cache


class BaseNonVierge(RuntimeError):
    """La base porte déjà des comptes : le jeu de démo ne s'y mêle pas."""


def charger(*, documents: bool = True) -> dict[str, int]:
    """Pose le jeu complet dans la base de la copropriété servie. Rend des comptes.

    `documents=False` saute les PDF, qui exigent WeasyPrint : un poste de
    développement ne l'a pas. La commande, elle, les rend toujours.
    """
    from app.database import create_db_and_tables

    #  Rendus d'abord : un moteur PDF absent arrête tout AVANT la première écriture.
    rendus = fichiers.rendre_documents() if documents else []
    create_db_and_tables()
    with contexte.nouvelle_session() as session:
        if session.exec(select(Utilisateur.id)).first() is not None:
            raise BaseNonVierge("La base porte déjà des comptes : chargement refusé.")
        pat = patrimoine.poser(session)
        les_comptes = comptes.poser(session, pat)
        #  Écrit avant le seed, qui ouvre sa propre session ; les objets, expirés par
        #  le commit, se relisent d'eux-mêmes ensuite.
        session.commit()

        seed()
        invalider_cache()

        identite.poser(session, les_comptes["administrateur"])
        legal.poser(session)
        gouvernance.poser(session, les_comptes)
        prest = prestataires.poser(session, pat, les_comptes["conseil-syndical"].id)
        les_affaires = affaires.poser(session, pat, les_comptes, prest)
        vie_collective.poser(session, les_comptes)
        acces.poser(session, pat)
        fichiers.poser_images(session, les_affaires)
        fichiers.poser_documents(session, les_comptes["conseil-syndical"], rendus)
        session.commit()
    return {
        "comptes": len(les_comptes),
        "lots": len(pat.appartements) + len(pat.parkings),
        "affaires": len(les_affaires),
        "documents": len(rendus),
    }


def main() -> int:
    if not est_demo():
        print("MODE_DEMO n'est pas posé : cette installation n'est pas la démo.", file=sys.stderr)
        return 2
    try:
        bilan = charger()
    except BaseNonVierge as exc:
        print(str(exc), file=sys.stderr)
        return 3
    print("✅ Démo chargée : " + ", ".join(f"{n} {quoi}" for quoi, n in bilan.items()))
    for cle in legal.manques():
        #  Un avertissement, pas un refus : la remise à zéro de la nuit ne doit pas
        #  laisser la démo arrêtée pour un texte. La mise en service, elle, le pose.
        print(f"⚠️ {cle} absent du .env : les textes légaux n'ont pas de contact.", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
