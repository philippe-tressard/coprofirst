"""Le cycle de vie d'un compte laisse sa trace (#1548, audit du 02/10/2026).

## Le constat

#1040 avait ouvert la porte — `utils/journal_securite.journaliser_securite` — et
y avait fait passer les mots de passe, les rôles, le bannissement. Le reste du
cycle de vie d'un compte n'y passait pas :

- **valider** un compte, le geste qui OUVRE l'accès — fait par le conseil
  syndical, donc par plus de personnes que l'administration ;
- **désactiver** ou **réactiver** un compte ;
- **supprimer** un compte — après l'effacement, plus rien en base ne dit qui
  l'a fait : la ligne de journal est la seule trace qui reste ;
- **créer, accepter, révoquer une délégation** — un tiers qui lit au nom d'un
  résident.

## Ce que ce test tient

`test_journal_securite.py` lit l'arbre syntaxique : il dit que l'appel est
ÉCRIT. Celui-ci passe par les routes, et dit que la ligne est ÉMISE — au bon
niveau (`WARNING`, jamais `ERROR` : le pré-check compte les `ERROR`), avec qui
agit et sur qui, et sans aucune adresse (`standards/14`).

⚠️ Le changement d'adresse n'est pas ici : il appartient au lot de l'adresse du
compte (#1549/#1550).
"""

from __future__ import annotations

import logging

import pytest
from fastapi import BackgroundTasks

from app.models.core import Delegation, StatutDelegation
from app.routers.admin.comptes import CompteAction, traiter_compte
from app.routers.admin.utilisateurs import (
    AdminUserUpdate,
    modifier_utilisateur,
    supprimer_utilisateur,
)
from app.routers.delegations import (
    DelegationCreate,
    accepter_delegation,
    create_delegation,
    revoquer_delegation,
)
from tests.aides_base import compte


@pytest.fixture()
def journal(caplog):
    """Les lignes du journal de sécurité — et rien qu'elles."""
    caplog.set_level(logging.INFO, logger="securite")

    def lignes() -> list[str]:
        return [r.getMessage() for r in caplog.records if r.name == "securite"]

    def niveaux() -> set[int]:
        return {r.levelno for r in caplog.records if r.name == "securite"}

    lignes.niveaux = niveaux
    return lignes


def _admin(session):
    return compte(session, prefixe="admin", roles_json="admin")


def _cs(session):
    return compte(session, prefixe="cs", roles_json="conseil_syndical")


def _sans_adresse(lignes: list[str]) -> None:
    for ligne in lignes:
        assert "@" not in ligne, f"une adresse est passée au journal : {ligne}"


def test_valider_un_compte_laisse_une_trace(session, journal):
    """Le geste qui ouvre l'accès, et le conseil syndical le fait."""
    cs = _cs(session)
    arrivant = compte(session, prefixe="arrivant", actif=False)
    traiter_compte(arrivant.id, CompteAction(action="valider"), BackgroundTasks(), session, cs)
    assert journal() == [f"securite compte_valide acteur={cs.id} cible={arrivant.id}"]
    assert journal.niveaux() == {logging.WARNING}
    _sans_adresse(journal())


def test_refuser_un_compte_laisse_une_trace(session, journal):
    cs = _cs(session)
    arrivant = compte(session, prefixe="arrivant", actif=False)
    corps = CompteAction(action="refuser", motif="inconnu du syndic")
    traiter_compte(arrivant.id, corps, BackgroundTasks(), session, cs)
    #  Le motif est un texte libre : il peut nommer quelqu'un, il reste dehors.
    assert journal() == [f"securite compte_refuse acteur={cs.id} cible={arrivant.id}"]


def test_valider_un_aidant_journalise_la_delegation_posee_d_office(session, journal):
    """Valider un aidant crée une délégation ACTIVE : elle a sa propre ligne."""
    from app.models.core import StatutUtilisateur

    cs = _cs(session)
    aidee = compte(session, prefixe="aidee", prenom="Odile", nom="DURAND")
    aidant = compte(
        session,
        prefixe="aidant",
        actif=False,
        statut=StatutUtilisateur.aidant,
        prenom_aide="Odile",
        nom_aide="Durand",
    )
    traiter_compte(aidant.id, CompteAction(action="valider"), BackgroundTasks(), session, cs)
    assert journal() == [
        f"securite compte_valide acteur={cs.id} cible={aidant.id}",
        f"securite delegation_creee acteur={cs.id} cible={aidee.id} aidant={aidant.id} automatique",
    ]


def test_desactiver_puis_reactiver_un_compte(session, journal):
    admin, resident = _admin(session), compte(session, prefixe="resident")
    modifier_utilisateur(
        resident.id, AdminUserUpdate(actif=False), BackgroundTasks(), session, admin
    )
    modifier_utilisateur(
        resident.id, AdminUserUpdate(actif=True), BackgroundTasks(), session, admin
    )
    assert journal() == [
        f"securite compte_desactive acteur={admin.id} cible={resident.id}",
        f"securite compte_reactive acteur={admin.id} cible={resident.id}",
    ]
    assert journal.niveaux() == {logging.WARNING}


def test_une_modification_qui_ne_touche_pas_actif_ne_journalise_rien(session, journal):
    """Corriger un téléphone n'est pas un geste de sécurité — ni renvoyer le même état."""
    admin, resident = _admin(session), compte(session, prefixe="resident")
    modifier_utilisateur(
        resident.id, AdminUserUpdate(telephone="0600000000"), BackgroundTasks(), session, admin
    )
    modifier_utilisateur(
        resident.id, AdminUserUpdate(actif=True), BackgroundTasks(), session, admin
    )
    assert journal() == []


def test_supprimer_un_compte_laisse_une_trace(session, journal):
    """Après l'effacement, cette ligne est la seule à dire qui l'a fait."""
    admin, resident = _admin(session), compte(session, prefixe="resident")
    cible = resident.id
    supprimer_utilisateur(cible, session, admin)
    assert journal() == [f"securite compte_supprime acteur={admin.id} cible={cible}"]
    assert journal.niveaux() == {logging.WARNING}


def test_le_cycle_d_une_delegation_laisse_trois_traces(session, journal):
    """Créée par le CS, acceptée par l'aidant, révoquée par le mandant."""
    cs = _cs(session)
    mandant, aidant = compte(session, prefixe="mandant"), compte(session, prefixe="aidant")
    corps = DelegationCreate(mandant_id=mandant.id, aidant_id=aidant.id, motif="hospitalisation")
    creee = create_delegation(corps, session, cs)
    accepter_delegation(creee.id, session, aidant)
    revoquer_delegation(creee.id, session, mandant)

    d = session.get(Delegation, creee.id)
    assert d.statut == StatutDelegation.revoquee
    suffixe = f"cible={mandant.id} aidant={aidant.id}"
    assert journal() == [
        f"securite delegation_creee acteur={cs.id} {suffixe}",
        f"securite delegation_acceptee acteur={aidant.id} {suffixe}",
        f"securite delegation_revoquee acteur={mandant.id} {suffixe}",
    ]
    assert journal.niveaux() == {logging.WARNING}
    _sans_adresse(journal())
