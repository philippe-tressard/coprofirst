"""À QUI part l'e-mail, selon le périmètre choisi — la chaîne entière.

`annonces_hall.py` ligne 139 :

    destinataires = membres_cs_notifiables(session, batiments_du_perimetre(perimetres))

Cette composition est ce que voit un membre du conseil syndical dans sa boîte. Le
lot des périmètres a réécrit `batiments_du_perimetre` — d'une comparaison de
chaînes à une remontée d'arbre — et `test_perimetres_arbre.py` prouve que la
fonction rend les mêmes **identifiants de bâtiment** qu'avant. Il ne prouve pas
que la chaîne complète rende les mêmes **destinataires** : entre les deux il y a
la jointure sur `MembreCS.batiment_id`, l'ajout du gestionnaire du site, et le
filtrage des comptes inactifs ou sans adresse.

Ce fichier couvre cette composition, et lui seul. Il ne poste aucun e-mail : il
vérifie la liste des adresses retenues, qui est ce que le défaut ferait varier.

Aucun envoi réel n'a eu lieu depuis la mise en production de l'arborescence, donc
c'est la seule preuve disponible tant qu'une annonce n'a pas été publiée.
"""

import pytest
from sqlmodel import Session, SQLModel, select

from app.models.core import (
    Batiment,
    ConfigSite,
    Copropriete,
    GenreCivilite,
    MembreCS,
    RoleUtilisateur,
    Utilisateur,
)
from app.database import engine
from app.seed.patrimoine import poser_arborescence
from app.utils import perimetres as P
from app.utils.destinataires import batiments_du_perimetre, membres_cs_notifiables
from app.utils.purge_referentielle import purger
from tests.aides_purge import vider_patrimoine


def _vider(session: Session) -> None:
    """Démonte le patrimoine de test et les comptes qu'il a créés.

    🔴 Le corps de cette fonction était une COPIE de `vider_patrimoine`
    (conftest) — celle-là même que la conftest dit avoir factorisée « parce
    qu'une fixture recopiée diverge comme n'importe quel autre code ». La copie
    avait effectivement divergé : elle effaçait `Perimetre` sans passer par les
    vagues feuilles-vers-racine, ce que la vérification des clés refuse (#546).

    Les comptes partent par `purger`, qui LIT les métadonnées : les supprimer
    directement laissait leurs publications et leurs tickets pointer vers un
    identifiant disparu — invisible tant que les clés n'étaient pas vérifiées.
    """
    vider_patrimoine(session, modeles_sup=(MembreCS,))
    for u in session.exec(select(Utilisateur).where(Utilisateur.email.like("%@cs.test"))).all():
        purger(session, "utilisateur", u.id)
    session.commit()


@pytest.fixture()
def conseil() -> dict:
    """Quatre bâtiments, un membre du CS par bâtiment, plus un gestionnaire de site."""
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        _vider(session)
        copro = Copropriete(nom="Test", adresse="1 rue Test")
        session.add(copro)
        session.flush()
        for numero in ("1", "2", "3", "4"):
            session.add(Batiment(copropriete_id=copro.id, numero=numero))
        session.commit()
        batiments = list(session.exec(select(Batiment.id).order_by(Batiment.id)).all())

        emails = {}
        for identifiant in batiments:
            u = Utilisateur(
                nom="CS", prenom=f"B{identifiant}", email=f"cs{identifiant}@cs.test", actif=True
            )
            session.add(u)
            session.flush()
            session.add(
                MembreCS(
                    user_id=u.id,
                    batiment_id=identifiant,
                    nom="CS",
                    prenom=f"B{identifiant}",
                    genre=GenreCivilite.mme,
                )
            )
            emails[identifiant] = u.email

        #  Le gestionnaire du site, rattaché à AUCUN bâtiment : il doit être ajouté
        #  à tout envoi ciblé, sans quoi personne ne suit les demandes des autres
        #  bâtiments que le sien.
        #  Un administrateur : le gestionnaire du site n'est lu que s'il l'est (#1505).
        gestionnaire = Utilisateur(
            nom="Gest", prenom="Site", email="gest@cs.test", actif=True, role=RoleUtilisateur.admin
        )
        session.add(gestionnaire)
        session.flush()
        session.add(
            MembreCS(
                user_id=gestionnaire.id,
                batiment_id=None,
                nom="Gest",
                prenom="Site",
                genre=GenreCivilite.mme,
            )
        )
        session.add(ConfigSite(cle="site_manager_user_id", valeur=str(gestionnaire.id)))

        #  Un membre du CS au compte DÉSACTIVÉ : il ne doit jamais être retenu.
        inactif = Utilisateur(nom="Parti", prenom="Ex", email="parti@cs.test", actif=False)
        session.add(inactif)
        session.flush()
        session.add(
            MembreCS(
                user_id=inactif.id,
                batiment_id=batiments[0],
                nom="Parti",
                prenom="Ex",
                genre=GenreCivilite.mme,
            )
        )

        session.commit()
        poser_arborescence(session)
        session.commit()
    P.invalider_cache()
    yield {"batiments": batiments, "emails": emails, "gestionnaire": "gest@cs.test"}
    with Session(engine) as session:
        _vider(session)
        cfg = session.get(ConfigSite, "site_manager_user_id")
        if cfg:
            session.delete(cfg)
        session.commit()
    P.invalider_cache()


def _adresses(perimetres: list[str]) -> set[str]:
    """La chaîne complète, telle que `annonces_hall.py` l'appelle."""
    with Session(engine) as session:
        return {
            email
            for _, email in membres_cs_notifiables(session, batiments_du_perimetre(perimetres))
        }


def test_perimetre_global_notifie_tout_le_conseil(conseil):
    """« Copropriété entière » : tout le CS, gestionnaire compris."""
    attendu = set(conseil["emails"].values()) | {conseil["gestionnaire"]}
    assert _adresses(["résidence"]) == attendu


def test_perimetre_de_batiment_ne_notifie_que_le_sien(conseil):
    """Un contenu ciblé sur un bâtiment ne réveille pas les trois autres."""
    second = conseil["batiments"][1]
    assert _adresses([f"bat:{second}"]) == {conseil["emails"][second], conseil["gestionnaire"]}


def test_espace_d_un_batiment_notifie_comme_son_batiment(conseil):
    """« Bât. 2 › Hall d'entrée » n'a pas de bâtiment propre : il l'hérite.

    C'est le cas que la réécriture a introduit, et celui qu'aucun test de l'ancienne
    implémentation ne pouvait couvrir — ces codes n'existaient pas.
    """
    second = conseil["batiments"][1]
    assert _adresses([f"bat:{second}/hall"]) == {conseil["emails"][second], conseil["gestionnaire"]}


def test_enfant_d_un_perimetre_global_notifie_tout_le_conseil(conseil):
    """« Parking › Portail d'accès » concerne tout le monde, par héritage."""
    attendu = set(conseil["emails"].values()) | {conseil["gestionnaire"]}
    assert _adresses(["parking/portail"]) == attendu


def test_deux_batiments_notifient_les_deux(conseil):
    premier, second = conseil["batiments"][0], conseil["batiments"][1]
    assert _adresses([f"bat:{premier}", f"bat:{second}"]) == {
        conseil["emails"][premier],
        conseil["emails"][second],
        conseil["gestionnaire"],
    }


def test_un_compte_desactive_n_est_jamais_notifie(conseil):
    """Un membre parti garde sa ligne dans l'annuaire, pas sa boîte aux lettres."""
    premier = conseil["batiments"][0]
    assert "parti@cs.test" not in _adresses([f"bat:{premier}"])
    assert "parti@cs.test" not in _adresses(["résidence"])


def test_perimetre_introuvable_notifie_TOUT_le_conseil(conseil):
    """Un code supprimé depuis élargit l'envoi — et c'est VOULU.

    ⚠️ L'asymétrie avec la règle de visibilité est délibérée, et mérite d'être lue
    deux fois plutôt qu'une.

    Côté **visibilité**, un code introuvable n'accorde rien : élargir ferait lire un
    document réservé à un autre bâtiment. Le repli va vers le refus.

    Côté **notification**, le même code introuvable joint tout le conseil syndical :
    `batiments_du_perimetre` ne trouve aucun bâtiment, rend `None`, et `None`
    signifie « tout le CS ». Replier vers le refus enverrait l'annonce à personne —
    un message perdu, sans erreur, sans trace, et sans que l'auteur le sache.

    Les deux replis vont donc dans des sens opposés, parce que le risque n'est pas
    le même : une visibilité trop large est une fuite, une notification trop large
    est un e-mail de trop. Ce test existe pour que ce choix reste explicite — et
    pour qu'on le voie changer si quelqu'un « harmonise » les deux fonctions.

    Comportement identique à celui d'avant l'arborescence : l'ancienne
    implémentation rendait `ids or None`, donc `None` sur un code non reconnu.
    """
    attendu = set(conseil["emails"].values()) | {conseil["gestionnaire"]}
    assert _adresses(["periscope-imaginaire"]) == attendu
