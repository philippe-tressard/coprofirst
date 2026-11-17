"""Le fil d'une période — `GET /flux?du=&au=` (#2834, décision du 17/11/2026).

Ce que ces tests figent (les attendus du ticket) :

- une période vide, des bornes incluses, 32 jours refusés (422), `au < du` refusé (422),
  une seule borne refusée (422) ;
- une échéance FUTURE se range à son jour ; une carte sans échéance, à sa publication ;
- une carte de plusieurs jours paraît une fois par jour couvert (« 2834 b ») ;
- les cartes d'une même affaire ne paraissent qu'une fois par jour, la plus récente ;
- une carte masquée n'y paraît pas ; un compte qui ne voit pas une affaire ne la voit
  pas non plus dans une période ;
- sans paramètres, la réponse est celle d'avant (tri décroissant, `jour` absent).
"""

from __future__ import annotations

from datetime import date, datetime

import pytest
from fastapi import HTTPException
from sqlmodel import Session

from app.models.core import FluxMasque, RoleUtilisateur, Ticket
from app.routers.flux import periode
from app.routers.flux.schemas import FluxItem
from app.utils import horloge
from tests.aides_http import base_http, client_http

MAINTENANT = datetime(2026, 11, 16, 9, 0)  # lundi 16/11/2026, 10 h à Paris


def _carte(id_: str, date_: datetime, **affaire) -> FluxItem:
    meta = {"affaire": {k: v.isoformat() for k, v in affaire.items()}} if affaire else {}
    if affaire:
        meta["ticket_id"] = int(id_.split("_")[-1])
    return FluxItem(id=id_, type="ticket_ouvert", date=date_, titre=id_, meta=meta)


# ── La règle, pure ───────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    "du, au",
    [
        (date(2026, 11, 16), date(2026, 11, 15)),  # au < du
        (date(2026, 11, 1), date(2026, 12, 2)),  # 32 jours
        (date(2026, 11, 16), None),  # une borne seule
        (None, date(2026, 11, 16)),
    ],
)
def test_une_periode_mal_formee_est_refusee(du, au):
    with pytest.raises(HTTPException) as refus:
        periode.valider(du, au)
    assert refus.value.status_code == 422


def test_trente_et_un_jours_passent_et_sans_borne_rien():
    assert periode.valider(date(2026, 11, 1), date(2026, 12, 1)) is not None
    assert periode.valider(None, None) is None


def test_chaque_carte_se_range_a_son_jour_bornes_incluses():
    cartes = [
        _carte("pub_1", datetime(2026, 11, 16, 8)),  # publiée lundi
        _carte("tk_2", datetime(2026, 11, 10, 8), debut=datetime(2026, 11, 19, 7)),  # jeudi
        _carte("pub_3", datetime(2026, 11, 22, 21, 30)),  # dimanche 22 h 30 à Paris
        _carte("pub_4", datetime(2026, 11, 22, 23, 30)),  # lundi 23 à 0 h 30 à Paris : dehors
        _carte("tk_5", datetime(2026, 11, 1, 8), debut=datetime(2026, 11, 30, 8)),  # dehors
    ]
    rangees = periode.ranger(cartes, date(2026, 11, 16), date(2026, 11, 22))
    assert [(c.id, c.jour, c.rattachement) for c in rangees] == [
        ("pub_1", date(2026, 11, 16), "publication"),
        ("tk_2", date(2026, 11, 19), "echeance"),
        ("pub_3", date(2026, 11, 22), "publication"),
    ]


def test_une_carte_de_plusieurs_jours_parait_chaque_jour_couvert():
    coupure = _carte(
        "tk_8",
        datetime(2026, 11, 2),
        debut=datetime(2026, 11, 18, 7),
        fin=datetime(2026, 11, 24, 16),
    )
    rangees = periode.ranger([coupure], date(2026, 11, 16), date(2026, 11, 22))
    assert [c.jour for c in rangees] == [date(2026, 11, d) for d in range(18, 23)]
    assert {c.id for c in rangees} == {"tk_8"}


def test_une_affaire_ne_parait_qu_une_fois_par_jour_la_carte_la_plus_recente():
    ouverture = _carte("tko_9", datetime(2026, 11, 2), debut=datetime(2026, 11, 19, 7))
    reponse = _carte("tkr_9", datetime(2026, 11, 12), debut=datetime(2026, 11, 19, 7))
    rangees = periode.ranger([ouverture, reponse], date(2026, 11, 16), date(2026, 11, 22))
    assert [(c.id, c.jour) for c in rangees] == [("tkr_9", date(2026, 11, 19))]


def test_une_periode_sans_carte_est_vide():
    assert periode.ranger([], date(2026, 11, 16), date(2026, 11, 22)) == []


# ── La route ─────────────────────────────────────────────────────────────────


@pytest.fixture()
def fil(monkeypatch):
    """Une affaire datée jeudi 19 (créée le 10), une actualité du lundi 16, et une
    affaire confidentielle d'un autre, datée mercredi 18."""
    with base_http() as moteur:
        http, admin_id = client_http(moteur, RoleUtilisateur.admin)
        resident, _ = client_http(moteur, RoleUtilisateur.propriétaire)
        #  Figée APRÈS les connexions : leurs jetons naissent à l'heure réelle.
        monkeypatch.setattr(horloge, "maintenant", lambda: MAINTENANT)
        with Session(moteur) as s:
            commun = dict(auteur_id=admin_id, description="—", statut="ouvert")
            s.add(
                Ticket(
                    numero="TK-1",
                    titre="Coupure d'eau",
                    categorie="panne",
                    debut=datetime(2026, 11, 19, 7),
                    cree_le=datetime(2026, 11, 10, 8),
                    mis_a_jour_le=datetime(2026, 11, 10, 8),
                    **commun,
                )
            )
            s.add(
                Ticket(
                    numero="TK-2",
                    titre="Le mot du conseil",
                    categorie="actualite",
                    cree_le=datetime(2026, 11, 16, 8),
                    mis_a_jour_le=datetime(2026, 11, 16, 8),
                    **{**commun, "statut": "publie"},
                )
            )
            s.add(
                Ticket(
                    numero="TK-3",
                    titre="Dossier confidentiel",
                    categorie="panne",
                    confidentiel=True,
                    debut=datetime(2026, 11, 18, 7),
                    cree_le=datetime(2026, 11, 9, 8),
                    mis_a_jour_le=datetime(2026, 11, 9, 8),
                    **commun,
                )
            )
            s.commit()
        yield http, moteur, resident


def _periode(http, du="2026-11-16", au="2026-11-22"):
    reponse = http.get("/flux", params={"du": du, "au": au})
    assert reponse.status_code == 200, reponse.text
    return [(i["titre"], i["jour"], i["rattachement"]) for i in reponse.json()["items"]]


def test_la_route_range_l_echeance_future_et_la_publication(fil):
    http, _, _ = fil
    rangees = _periode(http)
    assert ("Coupure d'eau", "2026-11-19", "echeance") in rangees
    assert ("Le mot du conseil", "2026-11-16", "publication") in rangees
    assert [j for _, j, _ in rangees] == sorted(j for _, j, _ in rangees)


@pytest.mark.parametrize("du, au", [("2026-11-22", "2026-11-16"), ("2026-11-01", "2026-12-02")])
def test_la_route_refuse_une_periode_mal_formee(fil, du, au):
    http, _, _ = fil
    assert http.get("/flux", params={"du": du, "au": au}).status_code == 422


def test_une_carte_masquee_n_y_parait_pas(fil):
    http, moteur, _ = fil
    ident = next(
        i["id"] for i in http.get("/flux").json()["items"] if i["titre"] == "Coupure d'eau"
    )
    with Session(moteur) as s:
        s.add(FluxMasque(item_id=ident))
        s.commit()
    assert all(t != "Coupure d'eau" for t, _, _ in _periode(http))


def test_un_compte_ne_voit_dans_une_periode_que_ce_que_voit_son_fil(fil):
    http, _, resident = fil
    #  Le contrôle mord : l'administrateur, lui, la voit à son jour.
    assert ("Dossier confidentiel", "2026-11-18", "echeance") in _periode(http)
    fil_resident = {i["titre"] for i in resident.get("/flux").json()["items"]}
    periode_resident = {t for t, _, _ in _periode(resident)}
    assert periode_resident <= fil_resident
    assert "Dossier confidentiel" not in periode_resident


def test_sans_parametre_le_fil_est_celui_d_avant(fil):
    http, _, _ = fil
    items = http.get("/flux").json()["items"]
    assert [i["date"] for i in items] == sorted((i["date"] for i in items), reverse=True)
    assert all(i["jour"] is None and i["rattachement"] is None for i in items)
