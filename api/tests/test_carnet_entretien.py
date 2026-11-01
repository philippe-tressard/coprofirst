"""Le carnet d'entretien — sa seule décision, et son cas zéro.

Le carnet est une **vue** : l'essentiel de son code lit trois tables et les
concatène. Une seule ligne y décide quelque chose — *cette visite est-elle en
retard ?* —, et c'est elle qui est éprouvée ici, sans base ni session.

La règle de FILTRE, elle, a quitté ce module le 10/09/2026 : elle s'appelle
`couvre()` et vit dans l'arbre des périmètres, avec ses neuf cas —
`test_perimetre_couvre.py`. Un filtre par périmètre n'est pas une affaire de
carnet d'entretien : c'est la même question sur toutes les pages qui filtrent.

Le reste est vérifié par ce qui l'entoure : `test_liens_front.py` refuse un lien
vers une route que `pages.ts` ne déclare pas (le préfixe `contrat` a été ajouté
avec ce lot), et `test_types_equipement.py` tient déjà la correspondance entre
la table des équipements (#2442) et leur cache à l'écran.
"""

from __future__ import annotations

from datetime import date

import pytest

from app.utils.carnet_entretien import CATEGORIES_BATI, alerte_visite

AUJOURDHUI = date(2026, 9, 10)


def test_aucune_echeance_n_est_pas_un_retard():
    """Un contrat sans visite programmée ne dit rien — il ne dit pas l'inverse."""
    assert alerte_visite(None, AUJOURDHUI) is None


def test_une_echeance_a_venir_ne_crie_pas():
    assert alerte_visite(date(2026, 12, 1), AUJOURDHUI) is None


def test_le_JOUR_MEME_n_est_pas_un_retard():
    """🔴 Le bord qui ferait crier le carnet sur un contrat parfaitement tenu.

    Une visite attendue aujourd'hui peut encore avoir lieu cet après-midi. Un
    `<=` au lieu d'un `<` mettrait en alerte, chaque matin, tous les contrats du
    jour — et une alerte qui crie sur du normal finit ignorée.
    """
    assert alerte_visite(AUJOURDHUI, AUJOURDHUI) is None


def test_un_retard_dit_COMBIEN():
    """Trois jours et deux ans ne demandent pas le même geste."""
    assert alerte_visite(date(2026, 9, 7), AUJOURDHUI) == "visite attendue depuis 3 jours"
    assert alerte_visite(date(2024, 9, 10), AUJOURDHUI) == "visite attendue depuis 730 jours"


def test_le_pluriel_s_accorde():
    """Un jour de retard s'écrit au singulier — la grammaire est calculée ici,
    jamais dans un gabarit, comme pour les modèles d'e-mail."""
    assert alerte_visite(date(2026, 9, 9), AUJOURDHUI) == "visite attendue depuis 1 jour"


def test_les_categories_retenues_parlent_du_BATI():
    """Cas zéro : si le filtre devenait vide ou total, le carnet mentirait.

    Vide, il n'afficherait aucun incident ; total, il y noierait les questions et
    les signalements de bug, que ni un acquéreur ni un syndic n'y cherchent.
    """
    from app.models.tickets import CategorieTicket

    valeurs = {c.value for c in CATEGORIES_BATI}
    #  « entretien » : les maintenances du calendrier, devenues affaires (#1092).
    assert valeurs == {"panne", "espaces_verts", "sinistre", "etude_travaux", "entretien"}
    #  Et le filtre EXCLUT bien quelque chose : un ensemble qui contiendrait tout
    #  passerait ce test-ci sans rien filtrer.
    assert CategorieTicket.question not in CATEGORIES_BATI
    assert CategorieTicket.bug not in CATEGORIES_BATI


@pytest.mark.parametrize("prefixe", ["contrat"])
def test_les_liens_du_carnet_sont_declares(prefixe):
    """Un lien fabriqué à la main échapperait à `test_liens_front`."""
    from app.utils.liens import EMPLACEMENTS

    assert prefixe in EMPLACEMENTS


def test_une_affaire_se_dit_par_sa_categorie_jamais_incident():
    """« Réflexion sur le remplacement des pelouses » paraissait sous le badge
    « Incident », avec « etude_travaux » en clair (26/09/2026, signalé à
    l'écran). L'entrée porte désormais la VALEUR de sa catégorie, que l'écran
    rend par son libellé, et son détail ne recopie plus rien de brut."""
    import uuid
    from datetime import datetime

    from sqlmodel import Session, SQLModel

    from app.database import engine
    from app.models.core import StatutTicket, Ticket, Utilisateur
    from app.utils.carnet_entretien import construire_carnet
    from tests.aides_base import compte
    from tests.aides_purge import purger_ligne

    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        auteur = compte(
            session,
            prefixe="carnet",
            prenom="Camille",
            nom="Sorel",
            roles_json="conseil_syndical",
        )
        ticket = Ticket(
            numero=f"T-{uuid.uuid4().hex[:6]}",
            titre="Réflexion sur le remplacement des pelouses",
            description="…",
            categorie="etude_travaux",
            auteur_id=auteur.id,
            statut=StatutTicket.résolu,
            ferme_le=datetime(2026, 9, 25, 10, 0),
        )
        session.add(ticket)
        session.commit()
        try:
            lignes = [
                e
                for e in construire_carnet(session, lecteur=auteur)
                if e["lien"].endswith(f"/{ticket.id}")
            ]
            assert len(lignes) == 1
            ligne = lignes[0]
            assert ligne["origine"] == "affaire"
            assert ligne["categorie"] == "etude_travaux"
            assert "etude_travaux" not in ligne["detail"]
            #  Le n° d'affaire est dit par le pied de la carte, pas par son détail.
            assert ligne["numero"] == ticket.numero
            assert ticket.numero not in ligne["detail"]
        finally:
            purger_ligne(session, Ticket, ticket.id)
            purger_ligne(session, Utilisateur, auteur.id)
            session.commit()
