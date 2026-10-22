"""Actualité réservée : ce qu'elle **empêche**, en dehors de la lecture.

Qui voit quoi est verrouillé par `test_visibilite_ouverte.py`, qui rejoue tous
les couples (actualité × profil). Ce fichier-ci couvre les deux autres moitiés
du lot #347, qui ne sont pas des règles d'accès mais des règles d'**émission** :

1. **l'affiche de hall est interdite** — une affiche est punaisée dans un hall et
   lue par n'importe qui, il n'y a aucun contrôle d'accès derrière ;
2. **le message WhatsApp ne porte pas le contenu** — le groupe est commun à
   toute la copropriété ; le message garde le périmètre (c'est lui qui fait
   venir les bons résidents) et le lien, qui renvoie vers l'application où la
   règle d'accès s'applique.

La différence de traitement entre les deux n'est pas une nuance de degré : sur
WhatsApp le lecteur doit se connecter pour lire, sur une affiche non.

## Depuis le 23/09/2026 (#1091, lot 4)

L'actualité est une affaire de catégorie « Actualité ». Le « confidentiel » de
la publication s'appelle l'Accès « visible du seul périmètre »
(`reserve_perimetre`), et Destinataires = « Conseil syndical » seul referme
tout (#1096). L'invariant vit dans `tickets/actualite.appliquer_acces`.
"""

from __future__ import annotations

import json
import uuid

import pytest
from sqlmodel import Session, select

from app.database import engine
from app.models.core import AnnonceHall, Ticket, Utilisateur
from app.routers.tickets.actualite import appliquer_acces
from app.utils.whatsapp import TITRE_CONFIDENTIEL, construire_message
from tests.aides_base import compte
from tests.aides_purge import purger_ligne

VRAI_TITRE = "Dégât des eaux chez M. Durand"
VRAI_CONTENU = "<p>Le sinistre concerne l'appartement du 3ᵉ étage.</p>"
LIEN = "https://exemple.test/tickets/42"

CONFIG = {
    "whatsapp_enabled": "1",
    "whatsapp_footer": "— Conseil Syndical",
    "site_url": "https://exemple.test/",
}


@pytest.fixture
def scene():
    """Un auteur et une actualité RÉELS : l'affiche porte leur identifiant."""
    with Session(engine) as session:
        auteur = compte(session, prefixe="affiche", prenom="A", nom="H")
        actu = Ticket(
            numero=f"TK-A{uuid.uuid4().hex[:6]}",
            titre=VRAI_TITRE,
            description=VRAI_CONTENU,
            categorie="actualite",
            statut="publie",
            auteur_id=auteur.id,
        )
        session.add(actu)
        session.commit()
        session.refresh(actu)
        try:
            yield session, actu
        finally:
            session.rollback()
            #  L'affiche survit à son auteur depuis #1821 (contenu gardé, auteur
            #  délié) et `ticket_id` n'est pas une clé étrangère : elle se purge
            #  donc nommément, sinon un test suivant qui reçoit le même
            #  identifiant d'affaire trouve « son » affiche déjà posée.
            for affiche in session.exec(
                select(AnnonceHall).where(AnnonceHall.ticket_id == actu.id)
            ).all():
                purger_ligne(session, AnnonceHall, affiche.id)
            purger_ligne(session, Ticket, actu.id)
            purger_ligne(session, Utilisateur, auteur.id)


def _affiche(session: Session, actu: Ticket) -> AnnonceHall:
    affiche = AnnonceHall(
        titre=VRAI_TITRE, message=VRAI_CONTENU, ticket_id=actu.id, auteur_id=actu.auteur_id
    )
    session.add(affiche)
    session.commit()
    return affiche


def _cibler(actu: Ticket, perimetre: list[str], **champs) -> Ticket:
    actu.perimetre_cible = json.dumps(perimetre, ensure_ascii=False)
    for cle, v in champs.items():
        setattr(actu, cle, v)
    return actu


# ── 1. L'affiche de hall ──────────────────────────────────────────────────────


def test_une_affiche_deja_generee_est_archivee(batiments, scene):
    """Réserver au périmètre une actualité déjà affichée l'en retire.

    L'affiche existante est **archivée** et non supprimée : le PDF a été envoyé
    au CS et fait foi (archiver ≠ supprimer, `standards/11`).
    """
    session, actu = scene
    affiche = _affiche(session, actu)
    appliquer_acces(_cibler(actu, [f"bat:{batiments[0]}"], reserve_perimetre=True), session)
    session.commit()
    assert affiche.archivee is True


def test_reservee_au_conseil_l_affiche_est_archivee_aussi(batiments, scene):
    """#1096 : Destinataires = « Conseil syndical » seul referme tout, le hall compris."""
    session, actu = scene
    affiche = _affiche(session, actu)
    appliquer_acces(
        _cibler(actu, [f"bat:{batiments[0]}"], public_cible='["conseil_syndical"]'), session
    )
    session.commit()
    assert affiche.archivee is True


def test_l_affiche_survit_a_une_actualite_qui_reste_publique(batiments, scene):
    """Le contrôle sait aussi ne RIEN faire — sinon il archiverait tout."""
    session, actu = scene
    affiche = _affiche(session, actu)
    appliquer_acces(_cibler(actu, [f"bat:{batiments[0]}"]), session)
    session.commit()
    assert affiche.archivee is False


def test_un_perimetre_qui_concerne_tout_le_monde_decoche_la_case(batiments, scene):
    """Un cadenas qui ne ferme rien est pire qu'aucun cadenas.

    « Copropriété entière » — et tout nœud à portée globale — reste visible de
    tous quel que soit ce drapeau. Le conserver afficherait un 🔒 sur une
    actualité que tout le monde lit.
    """
    session, actu = scene
    from app.utils.perimetres import code_par_defaut

    appliquer_acces(_cibler(actu, [code_par_defaut()], reserve_perimetre=True), session)
    assert actu.reserve_perimetre is False
    appliquer_acces(_cibler(actu, [], reserve_perimetre=True), session)
    assert actu.reserve_perimetre is False


def test_un_perimetre_de_batiment_conserve_la_case(batiments, scene):
    """Le pendant du précédent : là, la réserve mord vraiment."""
    session, actu = scene
    appliquer_acces(_cibler(actu, [f"bat:{batiments[1]}"], reserve_perimetre=True), session)
    assert actu.reserve_perimetre is True


# ── 2. Le message WhatsApp ────────────────────────────────────────────────────


@pytest.fixture
def message_confidentiel() -> str:
    return construire_message(
        VRAI_TITRE,
        VRAI_CONTENU,
        urgente=False,
        perimetre_cible='["bat:3"]',
        config=CONFIG,
        public_cible='["résidents"]',
        confidentiel=True,
        lien=LIEN,
    )


def test_le_message_whatsapp_porte_le_titre_mais_JAMAIS_le_contenu(message_confidentiel):
    """🔴 ARBITRAGE RENVERSÉ le 29/08/2026 (#623), après celui de #347.

    #347 masquait le titre, au motif que « Dégât des eaux chez M. Durand » en dit
    déjà l'essentiel au groupe entier. Le raisonnement était juste, mais il
    traitait le titre comme une donnée SUBIE. Le nouvel arbitrage le traite comme
    une donnée **écrite** : le titre part, et son auteur est averti à l'écran de
    n'y rien mettre de confidentiel.

    ⚠️ Ce qui n'a pas bougé, et qui est le cœur de la protection : le **contenu**
    ne part jamais. C'est lui qui porte le détail — « l'appartement du 3ᵉ étage ».
    Les deux assertions ci-dessous ne sont pas redondantes : la première dit ce
    qui a changé, la seconde ce qui ne doit pas changer avec.
    """
    assert VRAI_TITRE in message_confidentiel
    assert "3ᵉ étage" not in message_confidentiel
    assert "sinistre concerne" not in message_confidentiel


def test_le_titre_de_repli_ne_sert_QUE_aux_actualites_sans_titre():
    """`TITRE_CONFIDENTIEL` n'est plus le titre des confidentielles.

    Il reste comme repli — une actualité sans titre ne doit pas produire un
    message qui commence par un tiret. Ce test empêche qu'on le supprime en
    croyant l'arbitrage clos, et qu'on obtienne alors un message décapité.
    """
    message = construire_message(
        "",
        VRAI_CONTENU,
        urgente=False,
        perimetre_cible='["bat:3"]',
        config=CONFIG,
        public_cible='["résidents"]',
        confidentiel=True,
    )
    assert TITRE_CONFIDENTIEL in message


def test_le_message_whatsapp_garde_le_perimetre_et_le_lien(message_confidentiel):
    """C'est tout l'objet du message : faire venir les bons résidents.

    Par son LIBELLÉ, jamais son code — le groupe lisait « bat:4/ascenseur »
    (22/10/2026) ; `perimetre_label`, le rendu de tout le site.
    """
    assert "Bât. 3" in message_confidentiel
    assert "bat:3" not in message_confidentiel
    assert LIEN in message_confidentiel


def test_une_actualite_ordinaire_garde_son_message_complet():
    """Le contrôle sait rougir dans l'autre sens : rien n'a changé sans la case."""
    message = construire_message(
        VRAI_TITRE,
        VRAI_CONTENU,
        urgente=False,
        perimetre_cible='["bat:3"]',
        config=CONFIG,
        public_cible='["résidents"]',
        confidentiel=False,
    )
    assert VRAI_TITRE in message
    assert "3ᵉ étage" in message
    assert TITRE_CONFIDENTIEL not in message


def test_le_public_restreint_garde_son_vrai_titre():
    """Les deux usages du message court ne se confondent pas.

    Une actualité à public restreint (locataires, CS…) affiche son titre : le
    groupe voit de quoi il s'agit, seul le contenu est retenu. C'est la
    confidentialité — l'axe bâtiment — qui retire aussi le titre.
    """
    message = construire_message(
        VRAI_TITRE,
        VRAI_CONTENU,
        urgente=False,
        perimetre_cible='["bat:3"]',
        config=CONFIG,
        public_cible='["locataires"]',
        confidentiel=False,
    )
    assert VRAI_TITRE in message
    assert "3ᵉ étage" not in message
