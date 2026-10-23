"""Un compte se retrouve par son adresse, QUELLE QUE SOIT LA CASSE — partout (#1550).

Le défaut, rejoué : un compte dont l'adresse stockée porte une majuscule (écrite
avant les validateurs qui abaissent la casse, ou par un chemin qui les contourne)
se connectait, mais le renvoi du lien de vérification et le mot de passe oublié
le cherchaient par égalité stricte. Ils répondaient 204 sans rien envoyer — « pas
d'énumération de comptes » —, et la personne concluait que le courriel
n'arrivait pas.

Ce fichier éprouve le COMPORTEMENT, par les routes : `test_adresse_compte_source_unique`
tient la forme (une seule écriture), celui-ci tient ce que la personne vit.
"""

from __future__ import annotations

from fastapi import BackgroundTasks, Response
from sqlmodel import select

from app.auth.adresse_compte import compte_par_adresse, normaliser_adresse
from app.models.core import EmailVerificationToken, PasswordResetToken
from app.routers import auth, auth_mot_de_passe
from app.routers.bailleur import baux
from app.routers.auth_schemas import LoginRequest
from tests.aides_base import compte
from tests.conftest import requete_de_test

#: L'adresse telle qu'un compte ancien a pu la garder : majuscules ET espace.
STOCKEE = "Casse.Mixte@Exemple.TEST"
SAISIE = "  casse.mixte@exemple.test "


def _compte_ancien(session, **champs):
    """Écrit SANS passer par un validateur : c'est le compte que la base peut contenir."""
    from app.auth.jwt import hash_password

    return compte(session, email=STOCKEE, hashed_password=hash_password("Mdp-Test-1"), **champs)


def test_la_forme_d_une_adresse():
    assert normaliser_adresse("  Jean.Dupont@Exemple.FR ") == "jean.dupont@exemple.fr"
    assert normaliser_adresse(None) == ""
    #  Rien de plus que la casse et les espaces : `jean.dupont` ≠ `jeandupont`,
    #  et la partie après `+` reste — une adresse distincte pour la plupart des
    #  serveurs (`envois_uniques` le disait déjà).
    assert normaliser_adresse("jean.dupont+bal@exemple.fr") == "jean.dupont+bal@exemple.fr"


def test_compte_par_adresse_ignore_casse_et_espaces(session):
    user = _compte_ancien(session)
    assert compte_par_adresse(session, SAISIE).id == user.id
    assert compte_par_adresse(session, "autre@exemple.test") is None
    assert compte_par_adresse(session, "") is None


def test_le_renvoi_du_lien_retrouve_le_compte_ancien(session):
    """Le défaut exact : 204, et aucun jeton émis."""
    user = _compte_ancien(session, actif=False, email_verifie=False)
    auth.resend_verification(
        requete_de_test("/auth/renvoyer-verification"),
        body=auth.RenvoiVerificationRequest(email=SAISIE),
        background_tasks=BackgroundTasks(),
        session=session,
    )
    jetons = session.exec(
        select(EmailVerificationToken).where(EmailVerificationToken.user_id == user.id)
    ).all()
    assert len(jetons) == 1, "le lien n'a pas été renvoyé au compte dont l'adresse a une majuscule"


def test_le_mot_de_passe_oublie_retrouve_le_compte_ancien(session):
    user = _compte_ancien(session)
    auth_mot_de_passe.request_password_reset(
        requete_de_test("/auth/mot-de-passe-oublie"),
        body=auth_mot_de_passe.PasswordResetRequest(email=SAISIE),
        background_tasks=BackgroundTasks(),
        session=session,
    )
    jetons = session.exec(
        select(PasswordResetToken).where(PasswordResetToken.user_id == user.id)
    ).all()
    assert len(jetons) == 1, "aucun lien de réinitialisation pour une adresse à majuscule"


def test_la_connexion_et_la_recherche_d_un_locataire_aussi(session):
    """Les deux autres lecteurs, pour que la règle soit la même partout.

    Un compte LOCATAIRE : la recherche du bailleur ne cherche qu'eux (#2153).
    """
    from app.models.core import StatutUtilisateur

    user = _compte_ancien(session, email_verifie=True, statut=StatutUtilisateur.locataire)
    lu = auth.login(
        requete_de_test("/auth/login"),
        body=LoginRequest(email=SAISIE, password="Mdp-Test-1"),
        response=Response(),
        session=session,
    )
    assert lu.id == user.id
    trouves = baux.search_locataire(
        requete_de_test("/bailleur/search-locataire", "GET"), q=SAISIE, user=user, session=session
    )
    assert [t.id for t in trouves] == [user.id]
