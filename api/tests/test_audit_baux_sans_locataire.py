"""Un bail sans compte locataire rattaché : lequel est un DÉFAUT, lequel est normal.

## Pourquoi ce relevé, et pourquoi ce test (#808, 07/09/2026)

Le rattachement d'un compte locataire à son bail est automatique, sur l'**e-mail
exact** (`_auto_match_baux_locataire`). Il échoue dès que le bail porte une autre
adresse, ou aucune — et surtout quand le bail est créé **après** l'inscription,
puisque le rapprochement n'a lieu qu'à la validation du compte.

🔴 **Et il échoue en silence.** La fonction rend `0`, personne n'est prévenu.
Côté locataire : compte actif, mais ni lot, ni badges, ni fiche de location.

Arbitrage du 06/09/2026 : *garder et observer*. Ce relevé est le moyen
d'observer.

## 🔴 Ce que ce test protège vraiment

**La distinction entre les deux catégories.** Un relevé qui les confondrait
crierait sur le cas NORMAL — un locataire qui ne s'est jamais inscrit — et
serait désarmé en trois jours. C'est la leçon de `standards/04` sur les
contrôles bruyants, appliquée à un écran.

| Catégorie | Ce que c'est |
|---|---|
| `compte_probable` | un compte existe au nom du locataire → le rattachement MANQUE |
| `sans_compte` | personne ne s'est inscrit → **normal**, à ne pas lire comme un défaut |

⚠️ Le test vérifie aussi qu'un bail **terminé** n'y figure pas : un bail conclu
n'a plus besoin d'être rattaché, et l'y faire apparaître ferait grossir le relevé
d'un bruit qui ne se résorbe jamais.
"""

from __future__ import annotations

from datetime import date

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session

from app.database import get_session
from app.main import app
from app.models.copropriete import Copropriete
from app.models.core import (
    Batiment,
    LocationBail,
    Lot,
    RoleUtilisateur,
    StatutBail,
    StatutUtilisateur,
    Utilisateur,
)
from tests.aides_base import moteur_de_test


@pytest.fixture(name="session")
def session_fixture():
    moteur = moteur_de_test()
    with Session(moteur) as session:
        yield session


@pytest.fixture(name="client")
def client_fixture(session: Session):
    from app.auth.deps import require_cs_or_admin

    admin = Utilisateur(
        email="admin@test.fr",
        hashed_password="x",
        nom="Admin",
        prenom="Test",
        role=RoleUtilisateur.admin,
        roles_json=RoleUtilisateur.admin.value,
        statut=StatutUtilisateur.copropriétaire_résident,
    )
    session.add(admin)
    session.commit()

    app.dependency_overrides[get_session] = lambda: session
    app.dependency_overrides[require_cs_or_admin] = lambda: admin
    yield TestClient(app)
    app.dependency_overrides.clear()


def _decor(session: Session) -> tuple[int, int]:
    """Une copropriété, un bâtiment, un lot, un bailleur — le minimum pour un bail."""
    copro = Copropriete(nom="Test", adresse="1 rue Test")
    session.add(copro)
    session.commit()
    bat = Batiment(numero="1", copropriete_id=copro.id)
    session.add(bat)
    session.commit()
    lot = Lot(numero="12", type="appartement", batiment_id=bat.id)
    bailleur = Utilisateur(
        email="bailleur@test.fr",
        hashed_password="x",
        nom="Proprio",
        prenom="Paul",
        statut=StatutUtilisateur.copropriétaire_bailleur,
    )
    session.add(lot)
    session.add(bailleur)
    session.commit()
    return lot.id, bailleur.id


def test_un_bail_dont_le_locataire_A_un_compte_est_signale_comme_RATTRAPABLE(
    session: Session, client: TestClient
):
    """Le cas qui coûte : le compte existe, le lien manque."""
    lot_id, bailleur_id = _decor(session)
    #  Le locataire s'est inscrit — avec une AUTRE adresse que celle du bail.
    #  C'est exactement ce qui fait échouer l'appariement automatique.
    session.add(
        Utilisateur(
            email="jean.perso@exemple.test",
            hashed_password="x",
            nom="Durand",
            prenom="Jean",
            statut=StatutUtilisateur.locataire,
            #  ⚠️ `Utilisateur.actif` vaut False par DÉFAUT : un compte doit être
            #  validé pour se connecter. Le relevé ne propose que des comptes
            #  actifs — un compte en attente ne verrait rien de toute façon, et
            #  le proposer enverrait rattacher un bail à quelqu'un qui n'entre
            #  pas encore. C'est ce test qui me l'a appris.
            actif=True,
        )
    )
    session.add(
        LocationBail(
            lot_id=lot_id,
            bailleur_id=bailleur_id,
            locataire_nom="Durand",
            locataire_prenom="Jean",
            locataire_email="j.durand@ancienne-adresse.fr",
            date_entree=date(2026, 1, 1),
            statut=StatutBail.actif,
        )
    )
    session.commit()

    lignes = client.get("/admin/audit/baux-sans-locataire").json()
    assert len(lignes) == 1
    assert lignes[0]["categorie"] == "compte_probable"
    assert lignes[0]["candidats"], "le compte trouvé doit être proposé, sinon le relevé n'aide pas"
    assert lignes[0]["candidats"][0]["email"] == "jean.perso@exemple.test"


def test_un_bail_dont_personne_ne_s_est_inscrit_est_NORMAL_et_le_dit(
    session: Session, client: TestClient
):
    """🔴 Le cas qu'il ne faut PAS crier.

    Un locataire qui n'utilise pas le site est la situation ordinaire. Le ranger
    avec les rattachements manquants ferait un relevé bruyant, donc un relevé
    qu'on cesse de lire.
    """
    lot_id, bailleur_id = _decor(session)
    session.add(
        LocationBail(
            lot_id=lot_id,
            bailleur_id=bailleur_id,
            locataire_nom="Inconnu",
            locataire_prenom="Ida",
            date_entree=date(2026, 1, 1),
            statut=StatutBail.actif,
        )
    )
    session.commit()

    lignes = client.get("/admin/audit/baux-sans-locataire").json()
    assert len(lignes) == 1
    assert lignes[0]["categorie"] == "sans_compte"
    assert lignes[0]["candidats"] == []


def test_un_bail_TERMINE_ne_figure_pas_au_releve(session: Session, client: TestClient):
    """Un bail conclu n'a plus besoin d'être rattaché.

    L'y laisser ferait grossir le relevé d'un bruit qui ne se résorbe jamais —
    et un compteur qui ne peut que monter cesse d'être lu.
    """
    lot_id, bailleur_id = _decor(session)
    session.add(
        LocationBail(
            lot_id=lot_id,
            bailleur_id=bailleur_id,
            locataire_nom="Ancien",
            date_entree=date(2024, 1, 1),
            date_sortie_reelle=date(2025, 1, 1),
            statut=StatutBail.termine,
        )
    )
    session.commit()

    assert client.get("/admin/audit/baux-sans-locataire").json() == []


def test_un_bail_DEJA_rattache_ne_figure_pas_non_plus(session: Session, client: TestClient):
    """Le cas zéro : sans lui, le relevé pourrait tout lister et paraître juste."""
    lot_id, bailleur_id = _decor(session)
    locataire = Utilisateur(
        email="ok@test.fr",
        hashed_password="x",
        nom="Lié",
        prenom="Luc",
        statut=StatutUtilisateur.locataire,
    )
    session.add(locataire)
    session.commit()
    session.add(
        LocationBail(
            lot_id=lot_id,
            bailleur_id=bailleur_id,
            locataire_id=locataire.id,
            locataire_nom="Lié",
            date_entree=date(2026, 1, 1),
            statut=StatutBail.actif,
        )
    )
    session.commit()

    assert client.get("/admin/audit/baux-sans-locataire").json() == []


def test_les_rattrapables_sont_en_TETE(session: Session, client: TestClient):
    """L'ordre porte l'intention : ce sur quoi on peut agir se lit en premier."""
    lot_id, bailleur_id = _decor(session)
    session.add(
        Utilisateur(
            email="zoe@test.fr",
            hashed_password="x",
            nom="Zeller",
            prenom="Zoé",
            statut=StatutUtilisateur.locataire,
            actif=True,
        )
    )
    for nom, prenom in (("Alard", "Anne"), ("Zeller", "Zoé")):
        session.add(
            LocationBail(
                lot_id=lot_id,
                bailleur_id=bailleur_id,
                locataire_nom=nom,
                locataire_prenom=prenom,
                date_entree=date(2026, 1, 1),
                statut=StatutBail.actif,
            )
        )
    session.commit()

    lignes = client.get("/admin/audit/baux-sans-locataire").json()
    assert [ligne["categorie"] for ligne in lignes] == ["compte_probable", "sans_compte"], (
        "le rattachement manquant doit passer avant le locataire non inscrit, "
        "même quand l'ordre alphabétique dit l'inverse"
    )
