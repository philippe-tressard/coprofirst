"""Le battement des contrôles de fiabilité prolonge une ligne, il n'en crée pas (#1396).

Le 27/09/2026, l'écran affichait « rapport de 17:06 » à 17:29, et on a cru que
`check-reliability.sh` ne tournait plus : il ne rend un rapport que quand ses
constats CHANGENT. Le passage qui n'a rien de neuf avance désormais
`terminee_le` — « dernier contrôle » —, et laisse `cree_le` — « constats
depuis ». La table n'en garde que vingt par tâche : une ligne par passage en
chasserait tout le reste en cinq heures.
"""

from __future__ import annotations

import json
from datetime import datetime

import pytest
from fastapi import HTTPException
from sqlmodel import select

from app.models.core import HistoriqueMaintenance
from app.routers.admin import rapports_scripts
from app.routers.admin.rapports_scripts import BattementTache, maintenance_battement

DEPUIS = datetime(2026, 9, 27, 15, 6, 0)


@pytest.fixture
def session(session, monkeypatch):
    #  La porte par clé est éprouvée par `test_autorisation.py` ; ici, le geste.
    monkeypatch.setattr(rapports_scripts, "exiger_cle_maintenance", lambda cle: None)
    return session


def _ligne(noeud: str, cree_le: datetime) -> HistoriqueMaintenance:
    return HistoriqueMaintenance(
        tache="reliability",
        noeud=noeud,
        statut="avertissement",
        cree_le=cree_le,
        terminee_le=cree_le,
    )


def test_le_battement_avance_le_DERNIER_controle_sans_creer_de_ligne(session):
    session.add(_ligne("rpi1", DEPUIS))
    session.commit()
    maintenance_battement(BattementTache(tache="reliability", noeud="rpi1"), None, session)
    lignes = session.exec(select(HistoriqueMaintenance)).all()
    assert len(lignes) == 1, "un battement a créé une ligne : la table serait pleine en cinq heures"
    assert lignes[0].cree_le == DEPUIS, "« constats depuis » ne doit pas bouger"
    assert lignes[0].terminee_le > DEPUIS, "« dernier contrôle » n'a pas avancé"


def test_il_prolonge_la_plus_RECENTE_du_bon_noeud(session):
    ancienne = _ligne("rpi1", datetime(2026, 9, 26, 10, 0))
    recente = _ligne("rpi1", DEPUIS)
    autre = _ligne("rpi2", DEPUIS)
    session.add_all([ancienne, recente, autre])
    session.commit()
    maintenance_battement(BattementTache(tache="reliability", noeud="rpi1"), None, session)
    session.refresh(ancienne), session.refresh(recente), session.refresh(autre)
    assert recente.terminee_le > DEPUIS
    assert ancienne.terminee_le == datetime(2026, 9, 26, 10, 0), (
        "une ancienne ligne a été prolongée"
    )
    assert autre.terminee_le == DEPUIS, "le battement de rpi1 a prolongé la ligne de rpi2"


def test_rien_a_prolonger_rend_404(session):
    """Le script efface alors sa mémoire, et renvoie un rapport complet au passage suivant."""
    with pytest.raises(HTTPException) as err:
        maintenance_battement(BattementTache(tache="reliability", noeud="rpi1"), None, session)
    assert err.value.status_code == 404


#  #1805 (10/10/2026) — l'écran disait « 1 erreur sur 965 requêtes » à 13:21
#  quand le contrôle en comptait 3 sur 1904 : la signature des constats ignore
#  les chiffres, et le battement ne portait que l'heure. Il porte désormais les
#  constats du passage, qui remplacent ceux de la ligne prolongée.
AVANT = {"fail": 0, "warn": 1, "constats": ["[WARN] 1 erreur(s) sur 965 requêtes"]}
APRES = {"fail": 0, "warn": 1, "constats": ["[WARN] 3 erreur(s) sur 1904 requêtes"]}


def test_le_battement_rafraichit_les_CHIFFRES_des_constats(session):
    ligne = _ligne("rpi1", DEPUIS)
    ligne.details = json.dumps(AVANT, ensure_ascii=False)
    ligne.erreur = "Site public KO (HTTP 502)"
    session.add(ligne)
    session.commit()
    maintenance_battement(
        BattementTache(
            tache="reliability", noeud="rpi1", details=APRES, erreur="Site public KO (HTTP 503)"
        ),
        None,
        session,
    )
    lignes = session.exec(select(HistoriqueMaintenance)).all()
    assert len(lignes) == 1, "le rafraîchissement a créé une ligne"
    assert json.loads(lignes[0].details) == APRES, (
        "l'écran garderait les chiffres du premier relevé"
    )
    assert lignes[0].erreur == "Site public KO (HTTP 503)", "« Anomalies récentes » resterait figé"
    assert lignes[0].cree_le == DEPUIS, "« constats depuis » ne doit pas bouger"


def test_un_battement_SANS_constats_garde_ceux_de_la_ligne(session):
    """Un nœud dont le script n'est pas encore redéployé n'efface rien."""
    ligne = _ligne("rpi1", DEPUIS)
    ligne.details = json.dumps(AVANT, ensure_ascii=False)
    ligne.erreur = "Site public KO (HTTP 502)"
    session.add(ligne)
    session.commit()
    maintenance_battement(BattementTache(tache="reliability", noeud="rpi1"), None, session)
    session.refresh(ligne)
    assert json.loads(ligne.details) == AVANT
    assert ligne.erreur == "Site public KO (HTTP 502)"


#  #2199 (23/10/2026) — « 0 s » sur chaque ligne : la durée s'écrivait en dur, et
#  le battement ne la portait pas. Il porte celle du passage qui prolonge la ligne.
def test_le_battement_porte_la_DUREE_du_passage(session):
    ligne = _ligne("rpi1", DEPUIS)
    ligne.duree_secondes = 31
    session.add(ligne)
    session.commit()
    maintenance_battement(
        BattementTache(tache="reliability", noeud="rpi1", duree_secondes=24), None, session
    )
    session.refresh(ligne)
    assert ligne.duree_secondes == 24, "l'écran garderait la durée du premier relevé"


def test_un_battement_SANS_duree_garde_celle_de_la_ligne(session):
    """Un nœud dont le script n'est pas encore redéployé n'écrit pas de zéro."""
    ligne = _ligne("rpi1", DEPUIS)
    ligne.duree_secondes = 31
    session.add(ligne)
    session.commit()
    maintenance_battement(BattementTache(tache="reliability", noeud="rpi1"), None, session)
    session.refresh(ligne)
    assert ligne.duree_secondes == 31
