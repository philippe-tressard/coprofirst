"""Deux droits distincts : ÉDITER le contenu, COMMENTER le suivi.

## La règle (arbitrée le 18/08/2026)

> « Seul l'auteur peut l'éditer ou le commenter, avec l'admin (en cas de Pb),
>   mais aussi le CS peut commenter, pas éditer (s'il est au courant de certaines
>   choses et influer sur le workflow ou émettre un commentaire) »

| Geste | Qui |
|---|---|
| **éditer** le contenu (titre, description, périmètre, pièces) | auteur · « saisi pour » · admin |
| **commenter** et faire avancer le workflow | les mêmes **+ conseil syndical** |

## Pourquoi un test, et pas seulement une relecture

C'est un contrôle d'**autorisation**. L'audit du 26/07/2026 a trouvé l'exigence
« globalement respectée » — 276 endpoints, aucun test sur `user.role` — et
pourtant **trois dérives installées sans que rien ne les signale**, dont un
doublon de `require_proprietaire` écrit dans un routeur et *documenté comme
officiel dans les specs*. Le point commun : aucune n'était visible sans rouvrir
le fichier concerné. Une exigence, même critique, ne se maintient pas par la
consigne — elle se maintient par un contrôle qui échoue.

🔴 **Ce que la règle CORRIGE, et qui vaut d'être dit** : avant, `update_ticket`
acceptait tout membre du CS sur **n'importe quel** ticket — donc réécrire la
demande d'un résident — pendant que le résident pour qui un ticket avait été
saisi ne pouvait, lui, rien corriger. Les deux erreurs étaient symétriques.


⚠️ Les fonctions sont PURES et vivent dans `auth/deps.py` : l'objet n'est connu
qu'après lecture en base, une dépendance FastAPI ne peut donc pas trancher. Ce
sont elles qu'on teste — pas leur recopie.
"""

from __future__ import annotations

import uuid

import pytest
from sqlmodel import Session, SQLModel

from app.auth.deps import peut_commenter, peut_editer
from app.database import engine
from app.models.core import RoleUtilisateur, Ticket, Utilisateur
from tests.aides_base import compte

#  🔴 La purge passe par le code de PRODUCTION : supprimer une ligne sans ce
#  qui la référence est ce que les clés étrangères refusent (#546).
from tests.aides_purge import purger_ligne


def _user(role: RoleUtilisateur) -> Utilisateur:
    """Un compte JAMAIS écrit en base — `id` vaut None. Ceux du montage passent par `compte`."""
    return Utilisateur(
        id=None,
        email=f"{role.value}-{uuid.uuid4().hex[:8]}@exemple.test",
        prenom="Test",
        nom=role.value,
        role=role,
    )


@pytest.fixture()
def acteurs():
    """Quatre profils et un ticket, écrits en base pour avoir de vrais `id`."""
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        auteur = compte(session, prefixe="resident", role=RoleUtilisateur.résident)
        beneficiaire = compte(session, prefixe="resident", role=RoleUtilisateur.résident)
        cs = compte(session, prefixe="cs", role=RoleUtilisateur.conseil_syndical)
        admin = compte(session, prefixe="admin", role=RoleUtilisateur.admin)
        tiers = compte(session, prefixe="resident", role=RoleUtilisateur.résident)

        ticket = Ticket(
            #  `numero` est NOT NULL et normalement posé par le routeur : le test
            #  écrit en base directement, il doit donc le fournir.
            numero=90000 + (uuid.uuid4().int % 9000),
            titre="Fuite au 3e",
            description="<p>Goutte à goutte.</p>",
            auteur_id=auteur.id,
            #  Le CS a saisi ce ticket AU NOM d'un résident : c'est le cas que la
            #  règle protège.
            saisi_pour_user_id=beneficiaire.id,
        )
        session.add(ticket)
        session.commit()
        session.refresh(ticket)

        yield ticket, auteur, beneficiaire, cs, admin, tiers

        purger_ligne(session, Ticket, ticket.id)
        for u in (auteur, beneficiaire, cs, admin, tiers):
            purger_ligne(session, Utilisateur, u.id)
        session.commit()


# ── ÉDITER : le contenu de la demande ───────────────────────────────────────


def test_l_auteur_edite(acteurs):
    ticket, auteur, *_ = acteurs
    assert peut_editer(ticket, auteur) is True


def test_le_saisi_pour_edite(acteurs):
    """🔴 Le cœur de la règle : un ticket déposé PAR le CS AU NOM d'un résident
    appartient à ce résident. Sans cela, il serait le seul à ne pas pouvoir
    corriger ce qui parle de lui."""
    ticket, _auteur, beneficiaire, *_ = acteurs
    assert peut_editer(ticket, beneficiaire) is True


def test_l_admin_edite(acteurs):
    ticket, _a, _b, _cs, admin, _t = acteurs
    assert peut_editer(ticket, admin) is True


def test_le_CS_n_edite_PAS(acteurs):
    """Le point qui change. Le conseil syndical suit les dossiers ; réécrire la
    demande d'un résident n'est pas son rôle — et il le pouvait, sur n'importe
    quel ticket."""
    ticket, _a, _b, cs, *_ = acteurs
    assert peut_editer(ticket, cs) is False, (
        "un membre du CS peut réécrire le contenu du ticket d'un résident"
    )


def test_un_tiers_n_edite_pas(acteurs):
    ticket, _a, _b, _cs, _admin, tiers = acteurs
    assert peut_editer(ticket, tiers) is False


# ── COMMENTER : le suivi ────────────────────────────────────────────────────


def test_le_CS_commente(acteurs):
    """L'autre moitié de la règle, et sa raison d'être : « s'il est au courant de
    certaines choses et influer sur le workflow »."""
    ticket, _a, _b, cs, *_ = acteurs
    assert peut_commenter(ticket, cs) is True


@pytest.mark.parametrize("qui", [1, 2, 4])
def test_ceux_qui_editent_commentent_aussi(acteurs, qui):
    """Qui peut le plus peut le moins — écrit comme tel (`peut_commenter` appelle
    `peut_editer`), pour que les deux listes ne puissent pas diverger."""
    ticket = acteurs[0]
    assert peut_commenter(ticket, acteurs[qui]) is True


def test_un_tiers_ne_commente_pas(acteurs):
    ticket, _a, _b, _cs, _admin, tiers = acteurs
    assert peut_commenter(ticket, tiers) is False


# ── Un objet SANS « saisi pour » ────────────────────────────────────────────


def test_un_utilisateur_sans_identifiant_n_a_aucun_droit():
    """⚠️ La garde `None == None`, dans l'autre sens.

    Un utilisateur authentifié a toujours un `id` — c'est donc défensif. Mais
    sans cette garde, `getattr(objet, "auteur_id", None) == uid` serait VRAI dès
    que les deux valent `None`, et l'édition s'ouvrirait à qui n'a pas d'identité.

    Le jumeau front (`#lib/droits.ts`) portait déjà la garde : les deux écritures
    d'une même règle doivent dire la même chose **jusque dans leurs cas limites**,
    sinon les comparer côte à côte ne prouve rien. C'est l'audit du 18/08/2026 qui
    a relevé l'écart.
    """
    anonyme = _user(RoleUtilisateur.résident)  # jamais écrit en base : `id` est None
    assert anonyme.id is None
    orphelin = Ticket(numero=99998, titre="Sans auteur", description="x", auteur_id=None)
    assert peut_editer(orphelin, anonyme) is False
    assert peut_commenter(orphelin, anonyme) is False


def test_sans_saisi_pour_la_regle_ne_s_elargit_pas(acteurs):
    """`saisi_pour_user_id` vaut `None` sur la plupart des objets — et sur TOUS
    ceux des autres entités (événement, annonce), qui n'ont pas ce champ.

    ⚠️ `getattr(objet, 'saisi_pour_user_id', None) == user.id` doit alors être
    faux, pas vrai : un `None == None` accidentel ouvrirait l'édition à quiconque
    n'a pas d'identifiant. Le test existe pour ce cas-là.
    """
    _t, auteur, _b, _cs, _admin, tiers = acteurs
    #  En mémoire seulement : la règle est pure, elle n'a pas besoin de la base.
    orphelin = Ticket(numero=99999, titre="Sans bénéficiaire", description="x", auteur_id=auteur.id)
    assert orphelin.saisi_pour_user_id is None
    assert peut_editer(orphelin, tiers) is False
    assert peut_editer(orphelin, auteur) is True
