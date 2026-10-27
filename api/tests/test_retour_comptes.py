"""Les comptes dormants et le retour des nouveaux arrivants (#1629).

Jeu fictif, au jour près :

| Compte | Ce qu'il a fait | Ce qu'on attend |
|---|---|---|
| actif | venu il y a 2 jours (évènement brut) | ni dormant ni arrivant |
| dormant 61 j | dernière visite il y a 61 jours (`derniere_visite`) | dormant à 60, pas à 90 |
| dormant 95 j | dernière visite il y a 95 jours | dormant à 60 et à 90 |
| jamais vu | validé il y a 100 jours, aucune visite connue | dormant à 60 et à 90 |
| refus | dormant de fait, mais a refusé la mesure | exclu, compté à part |
| fermé | désactivé | ignoré |
| arrivant revenu | validé il y a 10 jours, revenu à J+3 | revenu |
| arrivant jamais revenu | validé il y a 12 jours, venu seulement à J+9 | jamais revenu |
| arrivant en attente | validé il y a 2 jours, pas encore venu | en attente |
| ancien arrivant | validé il y a 40 jours | hors période |

Et l'écriture : l'agrégation note le JOUR de la dernière visite, jamais celui
d'un compte qui a refusé la mesure ; la purge l'efface après 12 mois.
"""

from __future__ import annotations

from datetime import timedelta

import pytest
from sqlmodel import Session, select

from app.models.telemetrie import DerniereVisite, TelemetryEvent
from app.utils import horloge
from app.utils.retour_comptes import (
    FENETRE_RETOUR_JOURS,
    SEUILS_DORMANCE,
    noter_visites,
    retour_comptes,
)
from tests.aides_base import compte, moteur_de_test
from tests.aides_horloge import il_y_a_jours

#  Les anciennetés se comptent en jours civils de Paris : chaque test se rejoue aux deux heures où
#  24 h × N et N jours ne sont pas la même chose (#2257).
pytestmark = pytest.mark.usefixtures("heure_hostile")


def _jour_il_y_a(jours: int) -> str:
    return (horloge.aujourd_hui() - timedelta(days=jours)).isoformat()


def _jeu(s: Session) -> dict[str, int]:
    ancien = il_y_a_jours(200)
    ids = {}
    ids["actif"] = compte(s, prenom="Alice", nom="Martin", cree_le=ancien).id
    ids["dormant61"] = compte(s, prenom="Bruno", nom="Durand", cree_le=ancien).id
    ids["dormant95"] = compte(s, prenom="Claire", nom="Leroy", cree_le=ancien).id
    ids["jamais_vu"] = compte(
        s, prenom="Elise", nom="Faure", cree_le=ancien, decision_compte_le=il_y_a_jours(100)
    ).id
    ids["refus"] = compte(s, cree_le=ancien, opt_out_telemetrie=True).id
    ids["ferme"] = compte(s, cree_le=ancien, actif=False).id
    ids["revenu"] = compte(s, decision_compte_le=il_y_a_jours(10)).id
    ids["jamais_revenu"] = compte(s, decision_compte_le=il_y_a_jours(12)).id
    ids["en_attente"] = compte(s, decision_compte_le=il_y_a_jours(2)).id
    ids["ancien_arrivant"] = compte(s, decision_compte_le=il_y_a_jours(40)).id

    s.add(TelemetryEvent(user_id=ids["actif"], page="/", cree_le=il_y_a_jours(2)))
    s.add(TelemetryEvent(user_id=ids["revenu"], page="/", cree_le=il_y_a_jours(10 - 3)))
    s.add(TelemetryEvent(user_id=ids["jamais_revenu"], page="/", cree_le=il_y_a_jours(12 - 9)))
    s.add(TelemetryEvent(user_id=ids["ancien_arrivant"], page="/", cree_le=il_y_a_jours(5)))
    s.add(DerniereVisite(user_id=ids["dormant61"], jour=_jour_il_y_a(61)))
    s.add(DerniereVisite(user_id=ids["dormant95"], jour=_jour_il_y_a(95)))
    s.add(DerniereVisite(user_id=ids["refus"], jour=_jour_il_y_a(120)))
    #  Une date de dernière visite PLUS ANCIENNE qu'un évènement brut : l'évènement l'emporte.
    s.add(DerniereVisite(user_id=ids["actif"], jour=_jour_il_y_a(70)))
    s.commit()
    return ids


def _resultat() -> tuple[dict, dict[str, int]]:
    moteur = moteur_de_test()
    with Session(moteur) as s:
        ids = _jeu(s)
        return retour_comptes(s), ids


def test_les_seuils_sont_ceux_du_ticket():
    assert SEUILS_DORMANCE == (60, 90)
    assert FENETRE_RETOUR_JOURS == 7


def test_les_dormants_a_60_et_90_jours():
    r, _ = _resultat()
    assert r["dormants"] == [{"seuil": 60, "nombre": 3}, {"seuil": 90, "nombre": 2}]


def test_la_liste_nominative_dit_qui_et_depuis_quand():
    r, ids = _resultat()
    liste = {d["user_id"]: d for d in r["liste_dormants"]}
    assert set(liste) == {ids["dormant61"], ids["dormant95"], ids["jamais_vu"]}
    assert liste[ids["dormant61"]]["jours"] == 61
    assert liste[ids["dormant61"]]["derniere_visite"] == _jour_il_y_a(61)
    assert liste[ids["dormant61"]]["nom"] == "Bruno DURAND"
    #  Jamais vu : la date de validation sert de point de départ, aucune visite n'est inventée.
    assert liste[ids["jamais_vu"]]["derniere_visite"] is None
    assert liste[ids["jamais_vu"]]["jours"] == 100
    #  Du plus ancien au plus récent.
    assert [d["jours"] for d in r["liste_dormants"]] == sorted(
        (d["jours"] for d in r["liste_dormants"]), reverse=True
    )


def test_le_refus_et_le_compte_ferme_sont_hors_de_la_mesure():
    r, ids = _resultat()
    assert r["refus"] == 1
    assert ids["refus"] not in {d["user_id"] for d in r["liste_dormants"]}
    assert ids["ferme"] not in {d["user_id"] for d in r["liste_dormants"]}
    #  Dix comptes ouverts, moins le refus.
    assert r["comptes_mesures"] == 8


def test_le_retour_des_arrivants_sur_30_jours():
    r, _ = _resultat()
    assert r["arrivants"] == {
        "periode": "30 derniers jours",
        "fenetre_jours": 7,
        "valides": 3,
        "revenus": 1,
        "jamais_revenus": 1,
        "en_attente": 1,
        #  Sur les issues connues seulement : 1 revenu sur 2.
        "taux": 50,
    }


def test_un_arrivant_n_est_pas_un_dormant():
    """Validé il y a 12 jours et jamais revenu : c'est le retour qui le dit, pas la dormance."""
    r, ids = _resultat()
    assert ids["jamais_revenu"] not in {d["user_id"] for d in r["liste_dormants"]}


def test_aucun_compte_rien_a_dire():
    moteur = moteur_de_test()
    with Session(moteur) as s:
        r = retour_comptes(s)
    assert r["dormants"] == [{"seuil": 60, "nombre": 0}, {"seuil": 90, "nombre": 0}]
    assert r["arrivants"]["taux"] is None
    assert r["liste_dormants"] == []


def test_noter_une_visite_garde_le_jour_le_plus_recent_et_ignore_le_refus():
    moteur = moteur_de_test()
    with Session(moteur) as s:
        venu = compte(s).id
        refus = compte(s, opt_out_telemetrie=True).id
        noter_visites(s, {venu, refus}, "2026-09-20")
        noter_visites(s, {venu}, "2026-09-10")  # un jour réagrégé plus ancien ne recule pas
        noter_visites(s, {venu}, "2026-09-25")
        s.commit()
        lignes = {d.user_id: d.jour for d in s.exec(select(DerniereVisite)).all()}
    assert lignes == {venu: "2026-09-25"}
