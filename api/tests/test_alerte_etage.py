"""Prévenir l'administrateur quand un résident et son lot se contredisent — `alerte_etage` (#1569).

Demandé le 09/09/2026 : *« notifier s'il y a une différence entre le lot et la
saisie du résident »*. Le module n'était nommé par aucun test ; la DÉCISION
(`divergence_etage`, pure) est tenue par `test_etage_label` et ses voisins, mais
ni la lecture des lots ni l'envoi ne l'étaient. Ici, sur une vraie base :

1. `lots_de` — les lots ACTIVEMENT rattachés, jamais « tous les lots » (pas de
   repli d'administration : il comparerait l'étage d'un admin au lot d'un autre) ;
2. l'alerte part, en file, quand la saisie contredit l'unique logement du compte ;
3. elle reste SILENCIEUSE : saisie absente, étage identique, aucun logement, plusieurs
   logements, lot sans étage, parking — et quand le site n'a personne à prévenir
   (un envoi sans destinataire n'est pas une alerte, c'est une ligne d'erreur).

Les courriels ne partent pas : `BackgroundTasks` les garde, et on lit ce qui est en file.
"""

from __future__ import annotations

import pytest
from fastapi import BackgroundTasks

from app.models.core import ConfigSite, Lot, TypeLien, UserLot
from app.utils.alerte_etage import alerter_divergence_etage
from app.utils.lots_rattaches import lots_de
from app.utils.email import send_email
from tests.aides_base import compte

GESTIONNAIRE = "gestion@exemple.test"


@pytest.fixture()
def resident(session):
    return compte(session, prefixe="etage", prenom="Claire", nom="Roussel")


def _lot(session, *, etage, type_="appartement", numero="12") -> Lot:
    lot = Lot(numero=numero, type=type_, etage=etage)
    session.add(lot)
    session.commit()
    session.refresh(lot)
    return lot


def _rattacher(session, user, lot, *, actif=True) -> None:
    session.add(
        UserLot(user_id=user.id, lot_id=lot.id, type_lien=TypeLien.propriétaire, actif=actif)
    )
    session.commit()


def _config(session, **valeurs) -> None:
    for cle, valeur in valeurs.items():
        session.add(ConfigSite(cle=cle, valeur=valeur))
    session.commit()


def _alerter(session, user, saisi):
    taches = BackgroundTasks()
    alerter_divergence_etage(session, taches, user, saisi)
    return taches.tasks


# ── lots_de ─────────────────────────────────────────────────────────────────


def test_lots_de_rend_les_lots_activement_rattaches(session, resident):
    a, b = _lot(session, etage=1, numero="1"), _lot(session, etage=2, numero="2")
    _rattacher(session, resident, a)
    _rattacher(session, resident, b)

    assert sorted(lot.id for lot in lots_de(session, resident)) == sorted([a.id, b.id])


def test_lots_de_ignore_un_rattachement_inactif(session, resident):
    lot = _lot(session, etage=1)
    _rattacher(session, resident, lot, actif=False)

    assert lots_de(session, resident) == []


def test_lots_de_sans_rattachement_ne_replie_pas_sur_tous_les_lots(session, resident):
    """Même pour un administrateur : ce repli sert à CONSULTER, pas à comparer."""
    _lot(session, etage=4)
    admin = compte(session, prefixe="admin", roles_json="admin")

    assert lots_de(session, resident) == []
    assert lots_de(session, admin) == []


def test_lots_de_ne_rend_pas_les_lots_d_un_autre(session, resident):
    autre = compte(session, prefixe="voisin")
    _rattacher(session, autre, _lot(session, etage=3))

    assert lots_de(session, resident) == []


# ── L'alerte qui part ───────────────────────────────────────────────────────


def test_une_saisie_qui_contredit_le_lot_alerte_le_gestionnaire(session, resident):
    _rattacher(session, resident, _lot(session, etage=3))
    _config(session, site_email=GESTIONNAIRE, site_nom="Résidence Exemple")

    [tache] = _alerter(session, resident, 1)

    assert tache.func is send_email
    assert tache.kwargs["code"] == "etage_divergent"
    assert tache.kwargs["to"] == GESTIONNAIRE
    contexte = tache.kwargs["context"]
    #  Les libellés sont calculés ICI : le gabarit ne porte ni « RDC » ni « 3ème ».
    assert contexte["etage"] == {"saisi": "1er", "lot": "3ème"}
    assert contexte["residence"]["nom"] == "Résidence Exemple"
    assert contexte["utilisateur"]["email"] == resident.email
    assert {"utilisateur", "etage", "residence", "app"} <= set(contexte)


def test_le_rez_de_chaussee_se_dit_rdc(session, resident):
    _rattacher(session, resident, _lot(session, etage=0))
    _config(session, site_email=GESTIONNAIRE)

    [tache] = _alerter(session, resident, 2)

    assert tache.kwargs["context"]["etage"] == {"saisi": "2ème", "lot": "RDC"}


# ── Les silences ────────────────────────────────────────────────────────────


def test_une_saisie_identique_au_lot_ne_dit_rien(session, resident):
    _rattacher(session, resident, _lot(session, etage=3))
    _config(session, site_email=GESTIONNAIRE)

    assert _alerter(session, resident, 3) == []


def test_une_saisie_absente_n_est_pas_une_divergence(session, resident):
    _rattacher(session, resident, _lot(session, etage=3))
    _config(session, site_email=GESTIONNAIRE)

    assert _alerter(session, resident, None) == []


def test_sans_aucun_lot_il_n_y_a_rien_a_contredire(session, resident):
    _config(session, site_email=GESTIONNAIRE)

    assert _alerter(session, resident, 5) == []


def test_un_lot_sans_etage_ne_fait_pas_inventer_de_divergence(session, resident):
    _rattacher(session, resident, _lot(session, etage=None))
    _config(session, site_email=GESTIONNAIRE)

    assert _alerter(session, resident, 5) == []


def test_un_parking_n_est_pas_un_logement(session, resident):
    """Un copropriétaire dont l'unique lot est un parking n'habite pas son lot."""
    _rattacher(session, resident, _lot(session, etage=-1, type_="parking"))
    _config(session, site_email=GESTIONNAIRE)

    assert _alerter(session, resident, 2) == []


def test_deux_logements_on_ne_sait_pas_lequel_il_habite(session, resident):
    _rattacher(session, resident, _lot(session, etage=1, numero="1"))
    _rattacher(session, resident, _lot(session, etage=4, numero="2"))
    _config(session, site_email=GESTIONNAIRE)

    assert _alerter(session, resident, 2) == []


def test_sans_adresse_de_gestionnaire_rien_ne_part(session, resident):
    """Pas d'envoi sans destinataire : une ligne d'erreur dans un journal que personne ne lit."""
    _rattacher(session, resident, _lot(session, etage=3))

    assert _alerter(session, resident, 1) == []


def test_une_adresse_blanche_n_est_pas_un_destinataire(session, resident):
    _rattacher(session, resident, _lot(session, etage=3))
    _config(session, site_email="   ")

    assert _alerter(session, resident, 1) == []


def test_le_gestionnaire_administrateur_prime_sur_l_adresse_du_site(session, resident):
    """Le gestionnaire se lit par son compte (un administrateur), à défaut `site_email`."""
    admin = compte(session, prefixe="gest", roles_json="admin")
    _rattacher(session, resident, _lot(session, etage=3))
    _config(session, site_email=GESTIONNAIRE, site_manager_user_id=str(admin.id))

    [tache] = _alerter(session, resident, 1)

    assert tache.kwargs["to"] == admin.email


def test_un_gestionnaire_qui_n_est_plus_administrateur_retombe_sur_l_adresse_du_site(
    session, resident
):
    ancien = compte(session, prefixe="ancien", roles_json="résident")
    _rattacher(session, resident, _lot(session, etage=3))
    _config(session, site_email=GESTIONNAIRE, site_manager_user_id=str(ancien.id))

    [tache] = _alerter(session, resident, 1)

    assert tache.kwargs["to"] == GESTIONNAIRE
