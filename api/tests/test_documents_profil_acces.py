"""Le profil d'accès d'un document : une règle, deux lectures qui disent pareil (#1551).

`document_visible` (ouvrir un document) et `GET /documents/categories` (les
catégories qu'on vous propose) posaient la même question — « ce profil admet-il
ce lecteur ? » — chacun avec sa copie, mot pour mot. Elles appellent désormais
`visibility.profil_admet`, et `test_autorisation.py` refuse une troisième
lecture de `roles_autorises`.

Ces tests fixent ce que la forme ne garantit pas : que les deux lectures
**répondent** pareil, lecteur par lecteur, et sur le cas limite où une copie
diverge d'abord — le lecteur admis par son STATUT et non par un rôle (le syndic,
migration 0159).

⚠️ Hors de portée, et signalé au rapport de #1551 : un document dont le profil
est SURCHARGÉ (`profil_acces_override_id`) n'est pas reflété par la liste des
catégories, qui ne lit que le profil de la catégorie. Ce n'est pas une copie de
la règle — c'est une autre question (« la catégorie », pas « ce document ») —,
et la liste ne montre que des libellés.
"""

from __future__ import annotations

import json

import pytest

from app.models.core import (
    CategorieDocument,
    Document,
    ProfilAccesDocument,
    RoleUtilisateur,
    StatutUtilisateur,
)
from app.routers.documents import list_categories
from app.utils.visibility import document_visible, profil_admet
from tests.aides_base import compte

#: Un profil par façon d'être admis : par rôle, par statut, ou les deux.
PROFILS = {
    "proprietaires": ["propriétaire"],
    "syndic": ["syndic"],
    "tous": ["propriétaire", "résident", "syndic"],
}

#: Qui lit quoi — écrit ici une fois, et vérifié des DEUX côtés.
ATTENDU = {
    "syndic": {"syndic", "tous"},
    "copropriétaire": {"proprietaires", "tous"},
    "locataire": {"tous"},
    "conseil": set(PROFILS),
}

LECTEURS = {
    "syndic": {"role": RoleUtilisateur.externe, "statut": StatutUtilisateur.syndic},
    "copropriétaire": {"roles_json": "propriétaire"},
    "locataire": {"role": RoleUtilisateur.résident, "statut": StatutUtilisateur.locataire},
    "conseil": {"roles_json": "conseil_syndical"},
}


@pytest.fixture()
def bibliotheque(session):
    """Une catégorie et un document par profil — `{code du profil: document}`."""
    auteur = compte(session, prefixe="cs", roles_json="conseil_syndical")
    documents = {}
    for code, roles in PROFILS.items():
        profil = ProfilAccesDocument(code=code, libelle=code, roles_autorises=json.dumps(roles))
        session.add(profil)
        session.commit()
        categorie = CategorieDocument(code=f"cat-{code}", libelle=code, profil_acces_id=profil.id)
        session.add(categorie)
        session.commit()
        doc = Document(
            titre=code,
            fichier_nom="f.pdf",
            categorie_id=categorie.id,
            publie_par_id=auteur.id,
        )
        session.add(doc)
        session.commit()
        session.refresh(doc)
        documents[code] = doc
    return documents


@pytest.mark.parametrize("lecteur", sorted(LECTEURS))
def test_la_liste_des_categories_et_l_ouverture_disent_pareil(session, bibliotheque, lecteur):
    user = compte(session, prefixe=lecteur, **LECTEURS[lecteur])
    proposees = {
        c["code"].removeprefix("cat-") for c in list_categories(session=session, user=user)
    }
    ouvrables = {code for code, doc in bibliotheque.items() if document_visible(user, doc, session)}
    assert proposees == ouvrables == ATTENDU[lecteur], (
        f"{lecteur} : catégories proposées {sorted(proposees)}, documents ouvrables "
        f"{sorted(ouvrables)}, attendu {sorted(ATTENDU[lecteur])}"
    )


def test_sans_profil_personne_n_est_admis(session):
    """« Aucune règle » n'est jamais une autorisation (`standards/04`)."""
    user = compte(session, prefixe="copro", roles_json="propriétaire")
    assert profil_admet(user, None) is False
