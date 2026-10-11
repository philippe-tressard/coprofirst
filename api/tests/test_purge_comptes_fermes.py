"""Les comptes refusés, désactivés ou jamais décidés ont une durée (#1822).

La politique disait qu'un compte refusé ou désactivé « n'est supprimé que sur
décision de l'administration » : aucune durée, donc une conservation sans fin.
Arbitrage du 10/10/2026 :

| Compte | Supprimé |
|---|---|
| refusé | 30 jours après le refus |
| désactivé | deux ans après sa désactivation (la durée des comptes inactifs) |
| en attente, jamais décidé | six mois après l'inscription |

Aucun courriel : le compte ne peut pas se connecter, « connectez-vous pour le
garder » serait faux. La suppression passe par `supprimer_compte`, sous le même
seuil de sûreté, et se journalise.

La date vient de `compte_ferme_le`, posée par `utils/comptes.marquer_decide` : la
première décision (`decision_compte_le`) ne le pouvait pas — un compte validé
puis désactivé gardait la date de sa validation, et serait parti trop tôt.
"""

from __future__ import annotations

import logging
from datetime import timedelta

import pytest

from app.models.core import RoleUtilisateur, Utilisateur
from app.utils import horloge
from app.utils.comptes import DESACTIVATION, REFUS, marquer_decide
from app.utils.purge_comptes import regles
from app.utils.purge_comptes.tache import purger_comptes_inactifs
from tests.aides_base import compte

T = horloge.maintenant()


class _Envois:
    def __init__(self):
        self.recus = []

    def __call__(self, session, user, contexte) -> bool:
        self.recus.append(user.id)
        return True


@pytest.fixture()
def journal(caplog):
    caplog.set_level(logging.INFO, logger="securite")
    return lambda: [r.getMessage() for r in caplog.records if r.name == "securite"]


def _ferme(session, fermeture, il_y_a: timedelta, **champs) -> Utilisateur:
    return compte(
        session,
        prefixe="ferme",
        actif=False,
        decision_compte_le=T - il_y_a,
        fermeture_compte=fermeture,
        compte_ferme_le=T - il_y_a,
        **champs,
    )


def _existe(session, user_id: int) -> bool:
    session.expire_all()
    return session.get(Utilisateur, user_id) is not None


def _passer(session, envois=None):
    return purger_comptes_inactifs(session, maintenant=T, envoyer=envois or _Envois())


# ── Les règles, sans base ────────────────────────────────────────────────────


def test_les_seuils_de_chaque_fermeture(session):
    jour = timedelta(days=1)
    cas = [
        (REFUS, regles.DELAI_REFUS + jour, regles.MOTIF_REFUSE),
        (REFUS, regles.DELAI_REFUS - jour, None),
        (DESACTIVATION, regles.INACTIVITE + jour, regles.MOTIF_DESACTIVE),
        (DESACTIVATION, regles.INACTIVITE - jour, None),
    ]
    for fermeture, age, attendu in cas:
        user = _ferme(session, fermeture, age)
        assert regles.fermeture_echue(user, T) == attendu, (fermeture, age)


def test_en_attente_six_mois_sans_decision(session):
    ancien = compte(session, prefixe="ancien", actif=False, cree_le=T - regles.DELAI_ATTENTE)
    recent = compte(session, prefixe="recent", actif=False, cree_le=T - timedelta(days=150))
    assert regles.fermeture_echue(ancien, T) == regles.MOTIF_EN_ATTENTE
    assert regles.fermeture_echue(recent, T) is None


def test_un_compte_ouvert_n_est_jamais_une_fermeture(session):
    ouvert = compte(session, prefixe="ouvert", actif=True, cree_le=T - timedelta(days=3000))
    assert regles.fermeture_echue(ouvert, T) is None


# ── La date : celle de la fermeture, pas de la première décision ─────────────


def test_valide_puis_desactive_compte_depuis_la_desactivation(session):
    """Le défaut que `decision_compte_le` seule aurait produit."""
    user = compte(session, prefixe="valide", actif=True)
    marquer_decide(user, None, maintenant=T - timedelta(days=3000))  # validé il y a 8 ans
    user.actif = False
    marquer_decide(user, DESACTIVATION, maintenant=T - timedelta(days=10))
    assert user.decision_compte_le == T - timedelta(days=3000)
    assert user.compte_ferme_le == T - timedelta(days=10)
    assert regles.fermeture_echue(user, T) is None


def test_reactive_il_sort_de_la_regle_et_une_fermeture_repetee_garde_sa_date(session):
    user = compte(session, prefixe="va-et-vient", actif=False)
    marquer_decide(user, DESACTIVATION, maintenant=T - timedelta(days=100))
    marquer_decide(user, DESACTIVATION, maintenant=T)  # même état, renvoyé
    assert user.compte_ferme_le == T - timedelta(days=100)
    user.actif = True
    marquer_decide(user, None, maintenant=T)
    assert (user.fermeture_compte, user.compte_ferme_le) == (None, None)


def test_une_fermeture_inconnue_est_refusee(session):
    with pytest.raises(ValueError):
        marquer_decide(compte(session, prefixe="x"), "suspendu")


# ── La tâche ─────────────────────────────────────────────────────────────────


def test_les_comptes_echus_sont_supprimes_sans_courriel(session, journal):
    refuse = _ferme(session, REFUS, timedelta(days=31))
    desactive = _ferme(session, DESACTIVATION, regles.INACTIVITE + timedelta(days=1))
    attente = compte(session, prefixe="attente", actif=False, cree_le=T - timedelta(days=200))
    refuse_hier = _ferme(session, REFUS, timedelta(days=1))
    #  Une population réaliste : trois suppressions sur quatre comptes dépasseraient
    #  le seuil de sûreté (10 %), à raison — c'est le test qui suit.
    for _ in range(30):
        compte(session, prefixe="voisin", actif=True, derniere_connexion=T)
    envois = _Envois()
    ids = {
        nom: u.id
        for nom, u in [
            ("refuse", refuse),
            ("desactive", desactive),
            ("attente", attente),
            ("refuse_hier", refuse_hier),
        ]
    }

    rendu = _passer(session, envois)

    assert rendu["supprimes_fermes"] == 3
    assert not _existe(session, ids["refuse"])
    assert not _existe(session, ids["desactive"])
    assert not _existe(session, ids["attente"])
    assert _existe(session, ids["refuse_hier"])
    assert envois.recus == [], "un compte fermé ne peut pas se connecter : aucun courriel"
    assert sum("compte_purge_fermeture" in ligne for ligne in journal()) == 3


def test_un_administrateur_ferme_n_est_jamais_supprime(session, journal):
    admin = _ferme(
        session, DESACTIVATION, regles.INACTIVITE + timedelta(days=1), roles_json="admin"
    )
    assert admin.has_role(RoleUtilisateur.admin)
    _passer(session)
    assert _existe(session, admin.id)


def test_le_seuil_de_surete_compte_aussi_les_fermes(session):
    """Une horloge faussée ne doit pas vider la base par ce chemin-là non plus."""
    vises = [
        _ferme(session, REFUS, timedelta(days=40)).id for _ in range(regles.SURETE_NOMBRE_MAX + 1)
    ]
    rendu = _passer(session)
    assert rendu["suspendue"] is True
    assert all(_existe(session, uid) for uid in vises)


def test_la_fermeture_ne_s_ecrit_que_dans_marquer_decide():
    """Une écriture à côté fausserait la durée : un compte partirait trop tôt, ou jamais."""
    import re

    from tests.aides_sources import modules_app

    motif = re.compile(
        r"\.(fermeture_compte|compte_ferme_le|decision_compte_le)\b\s*(,[^=]*)?=(?!=)"
    )
    fautes = [
        f"{m.rel}:{n}"
        for m in modules_app()
        if m.rel != "utils/comptes.py"
        for n, ligne in enumerate(m.source.splitlines(), 1)
        if motif.search(ligne) and not ligne.lstrip().startswith("#")
    ]
    assert not fautes, f"écrire par `utils/comptes.marquer_decide` : {fautes}"
