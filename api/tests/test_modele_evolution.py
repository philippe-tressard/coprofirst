"""Une entrée de fil — `models/evolution.py`, le mixin des deux historiques (#1569).

Le module n'était nommé par aucun test (le mot « evolution » n'apparaissait qu'au
pluriel ou dans des noms de classe). Le mixin porte ce que les entrées de fil ont en
commun ; ce fichier tient, sur le comportement des TABLES réelles :

1. les champs communs existent, avec les mêmes défauts, sur chaque modèle qui l'hérite
   (`fichiers_urls` valait `"[]"` ici et `None` là : deux comportements pour « aucune pièce
   jointe » — c'est la divergence que le mixin a supprimée) ;
2. ce qui DISTINGUE chaque modèle reste chez lui : la clé du porteur, le périmètre du ticket ;
3. `auteur_id` GARDE sa clé étrangère, sur les deux tables : une base neuve et une base
   migrée décrivent la même chose ;
4. une entrée s'enregistre et se relit ; la marque `assiste_ia` a son défaut SERVEUR, pour
   qu'un INSERT qui ne la nomme pas passe sur une base neuve (#1327).
"""

from __future__ import annotations

import pytest
from sqlalchemy import text
from sqlmodel import SQLModel

from app.models.evenement import EvenementEvolution
from app.models.evolution import EvolutionMixin
from app.models.tickets import TicketEvolution
from tests.aides_base import compte

MODELES = [
    pytest.param(TicketEvolution, "ticket_id", id="ticket"),
    pytest.param(EvenementEvolution, "evenement_id", id="evenement"),
]

CHAMPS_COMMUNS = {
    "id",
    "type",
    "contenu",
    "ancien_statut",
    "nouveau_statut",
    "auteur_id",
    "cree_le",
    "fichiers_urls",
    "contenu_origine",
    "assiste_ia",
}


def _entree(modele, cle_porteur: str, auteur_id: int, **champs):
    return modele(**{cle_porteur: 1, "type": "commentaire", "auteur_id": auteur_id, **champs})


@pytest.mark.parametrize("modele,cle", MODELES)
def test_le_modele_herite_du_mixin(modele, cle):
    assert issubclass(modele, EvolutionMixin)


@pytest.mark.parametrize("modele,cle", MODELES)
def test_les_champs_communs_sont_des_colonnes_du_modele(modele, cle):
    colonnes = set(modele.__table__.columns.keys())

    assert CHAMPS_COMMUNS <= colonnes, f"colonnes communes absentes : {CHAMPS_COMMUNS - colonnes}"
    assert cle in colonnes, "la clé du porteur reste propre à chaque modèle"


def test_le_mixin_ne_porte_aucune_cle_de_porteur():
    """Elle nomme la table d'en face : c'est précisément ce qui distingue les modèles."""
    champs = set(EvolutionMixin.model_fields)

    assert champs == CHAMPS_COMMUNS
    assert not {"ticket_id", "evenement_id", "publication_id"} & champs


def test_les_champs_communs_ont_la_meme_forme_sur_les_deux_tables():
    """Même type, même nullabilité, même défaut : un champ recopié diverge au premier ajout."""
    formes = {}
    for modele in (TicketEvolution, EvenementEvolution):
        formes[modele] = {
            nom: (
                str(modele.__table__.columns[nom].type),
                modele.__table__.columns[nom].nullable,
                modele.model_fields[nom].default,
            )
            for nom in CHAMPS_COMMUNS - {"id"}
        }

    assert formes[TicketEvolution] == formes[EvenementEvolution]


def test_le_perimetre_est_une_propriete_du_ticket_seul():
    assert "perimetre_cible" in TicketEvolution.__table__.columns
    assert "perimetre_cible" not in EvenementEvolution.__table__.columns


@pytest.mark.parametrize("modele,cle", MODELES)
def test_les_valeurs_par_defaut_d_une_entree_neuve(modele, cle):
    e = _entree(modele, cle, auteur_id=1)

    assert e.contenu is None
    assert (e.ancien_statut, e.nouveau_statut) == (None, None)
    #  « Aucune pièce jointe » est une liste vide, pas une absence de réponse.
    assert e.fichiers_urls == "[]"
    assert e.contenu_origine is None
    assert e.assiste_ia is False
    assert e.cree_le is not None


@pytest.mark.parametrize("modele,cle", MODELES)
def test_auteur_id_garde_sa_cle_etrangere(modele, cle):
    cles = {fk.target_fullname for fk in modele.__table__.columns["auteur_id"].foreign_keys}

    assert cles == {"utilisateur.id"}


@pytest.mark.parametrize("modele,cle", MODELES)
def test_une_entree_s_enregistre_et_se_relit(session, modele, cle):
    auteur = compte(session, prefixe="evol")
    e = _entree(
        modele,
        cle,
        auteur.id,
        type="etat",
        ancien_statut="ouvert",
        nouveau_statut="en_cours",
        fichiers_urls='["/uploads/a.png"]',
        contenu_origine="Texte reçu",
        assiste_ia=True,
    )
    session.add(e)
    session.commit()
    session.refresh(e)

    relu = session.get(modele, e.id)

    assert (relu.type, relu.ancien_statut, relu.nouveau_statut) == ("etat", "ouvert", "en_cours")
    assert relu.fichiers_urls == '["/uploads/a.png"]'
    assert relu.contenu_origine == "Texte reçu"
    assert relu.assiste_ia is True


@pytest.mark.parametrize("table", ["ticket_evolution", "evenement_evolution"])
def test_un_insert_qui_ne_nomme_pas_assiste_ia_passe_sur_une_base_neuve(session, table):
    """#1327 : le défaut SERVEUR existe, comme sur les bases migrées."""
    auteur = compte(session, prefixe="evol")
    cle = "ticket_id" if table == "ticket_evolution" else "evenement_id"

    session.execute(
        text(
            f"INSERT INTO {table} ({cle}, type, auteur_id, cree_le, fichiers_urls) "
            "VALUES (1, 'commentaire', :a, '2026-10-02 10:00:00', '[]')"
        ),
        {"a": auteur.id},
    )
    session.commit()

    assert session.execute(text(f"SELECT assiste_ia FROM {table}")).scalar() == 0


def test_les_tables_sont_enregistrees_aupres_de_sqlmodel():
    assert {"ticket_evolution", "evenement_evolution"} <= set(SQLModel.metadata.tables)
