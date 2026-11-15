"""La version d'une réplique, au registre, est celle qu'elle SERT (#2750).

Le 15/11/2026, la fiche CF-000003 disait « v3.91.1 » quand la démo servait v3.96.0
depuis 04:31 : `mise-a-jour.sh` renouvelle le bail AVANT d'installer, et le registre
gardait la version d'avant jusqu'au bail suivant, une nuit plus tard. Le correctif :
au démarrage, l'API annonce sa version si ce n'est pas celle qu'elle a annoncée la
dernière fois (`client.run_annonce_version`) — quelle que soit la voie de la mise à
jour (le script, une montée à la main, une installation commune).

Les deux côtés parlent pour de vrai (`installation_branchee`).
"""

from __future__ import annotations

import pytest
from sqlmodel import Session, select

from app.config import get_settings
from app.inscription import client, depot
from app.inscription.depot import Contact
from app.registre.modeles import Installation
from tests.aides_registre import installation_branchee

CONTACT = Contact(prenom="Alix", nom="Durand", courriel="alix@example.org")


@pytest.fixture
def registre(monkeypatch, tmp_path):
    with installation_branchee(monkeypatch, tmp_path) as moteur:
        yield moteur


def _version_au_registre(moteur) -> str | None:
    with Session(moteur) as s:
        inst = s.exec(select(Installation).where(Installation.identifiant == "CF-000001")).one()
        return inst.version_logicielle


def _compter_appels(monkeypatch) -> list[str]:
    """Les chemins que l'installation poste au registre, dans l'ordre."""
    appels: list[str] = []
    poster = client.httpx.post

    def compter(url, **kw):
        appels.append(url)
        return poster(url, **kw)

    monkeypatch.setattr(client.httpx, "post", compter)
    return appels


def test_bail_en_n_puis_mise_a_jour_vers_n_plus_1_le_registre_dit_n_plus_1(registre, monkeypatch):
    reglages = get_settings()
    monkeypatch.setattr(reglages, "coprofirst_version", "3.91.1")
    client.inscrire(CONTACT)  # bail demandé : le registre lit 3.91.1
    assert _version_au_registre(registre) == "3.91.1"

    #  La mise à jour pose la nouvelle version, puis l'API redémarre sur elle.
    monkeypatch.setattr(reglages, "coprofirst_version", "3.96.0")
    client.run_annonce_version()

    assert _version_au_registre(registre) == "3.96.0"
    assert depot.lire().version_annoncee == "3.96.0"


def test_une_version_deja_annoncee_n_appelle_pas_le_registre(registre, monkeypatch):
    monkeypatch.setattr(get_settings(), "coprofirst_version", "3.96.0")
    client.inscrire(CONTACT)
    appels = _compter_appels(monkeypatch)

    client.run_annonce_version()  # redémarrage sans changement de version

    assert appels == []


def test_un_registre_injoignable_au_demarrage_laisse_l_annonce_au_bail_de_la_nuit(
    registre, monkeypatch
):
    reglages = get_settings()
    monkeypatch.setattr(reglages, "coprofirst_version", "3.91.1")
    client.inscrire(CONTACT)
    monkeypatch.setattr(reglages, "coprofirst_version", "3.96.0")

    def injoignable(*_a, **_kw):
        raise client.httpx.ConnectError("registre injoignable")

    monkeypatch.setattr(client.httpx, "post", injoignable)
    client.run_annonce_version()  # ne lève pas : le démarrage n'en dépend pas

    assert depot.lire().version_annoncee == "3.91.1"  # rien n'est cru annoncé
    assert _version_au_registre(registre) == "3.91.1"


def test_l_essai_n_annonce_rien(registre, monkeypatch):
    monkeypatch.setattr(get_settings(), "coprofirst_version", "3.91.1")
    client.inscrire(CONTACT)
    monkeypatch.setattr(get_settings(), "coprofirst_version", "3.96.0")
    monkeypatch.setattr(client, "essai_admis", lambda: True)
    appels = _compter_appels(monkeypatch)

    client.run_annonce_version()

    assert appels == []
