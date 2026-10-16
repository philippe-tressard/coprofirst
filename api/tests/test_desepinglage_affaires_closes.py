"""📌 Une affaire close perd son épingle 24 heures après sa clôture (16/10/2026).

La règle (`utils/desepinglage`) se juge sur l'objet en mémoire, puis la tâche
sur une base : elle retire l'épingle de ce qui est échu, et de rien d'autre.
"""

from datetime import timedelta

from app.models.core import Ticket
from app.utils import horloge
from app.utils.desepinglage import desepingler_affaires_closes, epingle_echue

MAINTENANT = horloge.maintenant()
IL_Y_A_25_H = MAINTENANT - timedelta(hours=25)
IL_Y_A_23_H = MAINTENANT - timedelta(hours=23)


def _affaire(numero="TK-E1", **champs) -> Ticket:
    defauts = dict(
        numero=numero,
        titre="Fuite au sous-sol",
        description="Constat.",
        categorie="panne",
        statut="résolu",
        epingle=True,
        ferme_le=IL_Y_A_25_H,
    )
    defauts.update(champs)
    return Ticket(**defauts)


# ── La règle ────────────────────────────────────────────────────────────────


def test_resolue_depuis_plus_de_24_h():
    assert epingle_echue(_affaire(), MAINTENANT)


def test_annulee_depuis_plus_de_24_h():
    assert epingle_echue(_affaire(statut="annulé"), MAINTENANT)


def test_close_depuis_moins_de_24_h_reste_epinglee():
    assert not epingle_echue(_affaire(ferme_le=IL_Y_A_23_H), MAINTENANT)


def test_rouverte_reste_epinglee():
    """`ferme_le` survit à la réouverture : il ne dit pas, seul, qu'elle est close."""
    assert not epingle_echue(_affaire(statut="en_cours"), MAINTENANT)


def test_sans_date_de_cloture_rien_ne_tombe():
    assert not epingle_echue(_affaire(ferme_le=None), MAINTENANT)


def test_actualite_suivie_close():
    actu = _affaire(categorie="actualite", statut="publie", suivi_actualite="résolu")
    assert epingle_echue(actu, MAINTENANT)


def test_actualite_sans_suivi_reste_epinglee():
    """Son statut `publie` n'est pas une clôture : sa péremption fait le travail."""
    actu = _affaire(categorie="actualite", statut="publie", ferme_le=None)
    assert not epingle_echue(actu, MAINTENANT)


def test_actualite_au_suivi_ouvert_reste_epinglee():
    actu = _affaire(categorie="actualite", statut="publie", suivi_actualite="ouvert")
    assert not epingle_echue(actu, MAINTENANT)


# ── La tâche ────────────────────────────────────────────────────────────────


def test_la_tache_ne_retire_que_les_echues(session):
    echue = _affaire("TK-E1")
    recente = _affaire("TK-E2", ferme_le=IL_Y_A_23_H)
    rouverte = _affaire("TK-E3", statut="en_cours")
    session.add_all([echue, recente, rouverte])
    session.commit()

    assert desepingler_affaires_closes(session, maintenant=MAINTENANT) == 1

    for t in (echue, recente, rouverte):
        session.refresh(t)
    assert (echue.epingle, recente.epingle, rouverte.epingle) == (False, True, True)


def test_une_epingle_remise_apres_24_h_retombe(session):
    """Arbitré le 16/10/2026 : la règle n'a pas d'exception."""
    affaire = _affaire()
    session.add(affaire)
    session.commit()
    desepingler_affaires_closes(session, maintenant=MAINTENANT)

    affaire.epingle = True
    session.add(affaire)
    session.commit()

    assert desepingler_affaires_closes(session, maintenant=MAINTENANT) == 1
    session.refresh(affaire)
    assert affaire.epingle is False


def test_le_retrait_ne_date_pas_une_modification(session):
    """`mis_a_jour_le` sert de référence à l'archivage d'une actualité."""
    affaire = _affaire(mis_a_jour_le=IL_Y_A_25_H)
    session.add(affaire)
    session.commit()

    desepingler_affaires_closes(session, maintenant=MAINTENANT)

    session.refresh(affaire)
    assert affaire.mis_a_jour_le == IL_Y_A_25_H


def test_rien_a_retirer(session):
    """Le cas zéro : la tâche passe, ne retire rien, et le dit."""
    assert desepingler_affaires_closes(session, maintenant=MAINTENANT) == 0
