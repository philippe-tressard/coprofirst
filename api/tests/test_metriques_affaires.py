"""Les métriques d'un ensemble d'affaires closes — bilan du carnet (#1645), fiche prestataire (#1646).

Le calcul vit dans `utils/synthese_affaire/agregats` ; les deux portes sont
`routers/carnet` (`GET /carnet-entretien/metriques`) et
`routers/prestataires_metriques` (`GET /prestataires/{id}/metriques`).

Ce fichier tient :

1. **les moyennes** sur un jeu fictif dont chaque durée se compte à la main
   (jours ouvrés, 9 h–17 h, semaines de mars 2026 sans jour férié) ;
2. **les bornes d'exercice** — civil, ou ouvert en juillet, jusqu'à la minute de
   Paris qui sépare deux exercices ;
3. **la porte** — anonyme 401, copropriétaire 403 (arbitré le 04/10/2026 : le
   conseil syndical seul), conseil et administration 200, prestataire inconnu 404 ;
4. **le cas zéro** — aucune affaire : des moyennes `None`, jamais 0 ;
5. **la source** — toutes les affaires closes, annulées comprises, affaires du
   carnet seulement pour le bilan, toutes pour un prestataire.
"""

from __future__ import annotations

from datetime import date, datetime

import pytest
from sqlmodel import Session, select

from app.utils.categories_ticket import libelle_categorie
from app.models.copropriete import Copropriete
from app.models.core import RoleUtilisateur, Ticket, TicketEvolution
from app.models.prestataires import Prestataire
from app.utils import horloge
from app.utils.synthese_affaire import agregats as A
from tests.aides_base import compte
from tests.aides_http import base_http, client_http

AUJOURDHUI = date(2026, 5, 15)
ROUTE_CARNET = "/carnet-entretien/metriques"


@pytest.fixture(name="moteur")
def moteur_fixture(monkeypatch):
    monkeypatch.setattr(horloge, "aujourd_hui", lambda: AUJOURDHUI)
    with base_http() as moteur:
        yield moteur


def _utc(*x) -> datetime:
    return datetime(*x)


class _Jeu:
    """Le jeu fictif : deux intervenants, cinq affaires closes, une ouverte."""

    def __init__(self, moteur, mois_debut_exercice=None):
        with Session(moteur) as s:
            if mois_debut_exercice:
                s.add(
                    Copropriete(
                        nom="Résidence témoin",
                        adresse="1 rue de l'Exemple",
                        mois_debut_exercice=mois_debut_exercice,
                    )
                )
            self.auteur = compte(s, prefixe="metriques", prenom="Camille", nom="Sorel").id
            p1 = Prestataire(nom="Ascenseurs Témoin", specialite="ascenseur")
            p2 = Prestataire(nom="Plomberie Témoin", specialite="plomberie")
            s.add(p1)
            s.add(p2)
            s.commit()
            self.p1, self.p2 = p1.id, p2.id
            self.n = 0

            #  A — panne, P1 : ouvert 2 j (lun.–mar.), chez le prestataire 3 j
            #  (mer.–ven.), close le lundi suivant à 9 h. Total 5 j. (CET : 8 h UTC = 9 h.)
            self._affaire(
                s,
                "panne",
                self.p1,
                _utc(2026, 3, 2, 8),
                [
                    ("etat", _utc(2026, 3, 4, 8), "ouvert", "chez_prestataire", None),
                    ("etat", _utc(2026, 3, 9, 8), "chez_prestataire", "résolu", None),
                ],
            )
            #  B — panne, P2 : ouvert 1 j, une relance mardi 11 h, la réponse du
            #  syndic (courriel) mercredi 11 h — 1 j —, chez le prestataire 2 j.
            self._affaire(
                s,
                "panne",
                self.p2,
                _utc(2026, 3, 16, 8),
                [
                    ("etat", _utc(2026, 3, 17, 8), "ouvert", "chez_prestataire", None),
                    ("relance", _utc(2026, 3, 17, 10), None, None, None),
                    ("commentaire", _utc(2026, 3, 18, 10), None, None, "Réponse reçue."),
                    ("etat", _utc(2026, 3, 19, 8), "chez_prestataire", "résolu", None),
                ],
            )
            #  C — sinistre ANNULÉ le lendemain : 1 j.
            self._affaire(
                s,
                "sinistre",
                None,
                _utc(2026, 3, 2, 8),
                [("etat", _utc(2026, 3, 3, 8), "ouvert", "annulé", None)],
            )
            #  D — une QUESTION (hors carnet), P1 : chez le prestataire 1 j.
            self._affaire(
                s,
                "question",
                self.p1,
                _utc(2026, 3, 9, 8),
                [
                    ("etat", _utc(2026, 3, 9, 8), "ouvert", "chez_prestataire", None),
                    ("etat", _utc(2026, 3, 10, 8), "chez_prestataire", "résolu", None),
                ],
            )
            #  E — panne de l'exercice PRÉCÉDENT, P1 (CEST : 7 h UTC = 9 h) :
            #  ouvert 1 j, chez le prestataire 2 j. Total 3 j.
            self._affaire(
                s,
                "panne",
                self.p1,
                _utc(2025, 6, 2, 7),
                [
                    ("etat", _utc(2025, 6, 3, 7), "ouvert", "chez_prestataire", None),
                    ("etat", _utc(2025, 6, 5, 7), "chez_prestataire", "résolu", None),
                ],
            )
            #  F — une panne OUVERTE de P1 : ne compte nulle part.
            self._affaire(s, "panne", self.p1, _utc(2026, 3, 2, 8), [], statut="ouvert")

    def _affaire(self, s, categorie, prestataire_id, cree_le, faits, statut=None):
        self.n += 1
        ferme_le = faits[-1][1] if faits and statut is None else None
        t = Ticket(
            numero=f"MET-{self.n:03d}",
            titre=f"Affaire témoin {self.n}",
            description="…",
            categorie=categorie,
            statut=statut or faits[-1][3],
            auteur_id=self.auteur,
            prestataire_id=prestataire_id,
            cree_le=cree_le,
            ferme_le=ferme_le,
        )
        s.add(t)
        s.commit()
        for type_, quand, avant, apres, origine in faits:
            s.add(
                TicketEvolution(
                    ticket_id=t.id,
                    type=type_,
                    ancien_statut=avant,
                    nouveau_statut=apres,
                    contenu=origine,
                    contenu_origine=origine,
                    auteur_id=self.auteur,
                    cree_le=quand,
                )
            )
        s.commit()


def _cs(moteur):
    http, _ = client_http(moteur, RoleUtilisateur.conseil_syndical)
    return http


def _par_categorie(bilan: dict) -> dict:
    return {c["categorie"]: c for c in bilan["categories"]}


def _etapes(resume: dict) -> dict:
    return {e["statut"]: (e["jours"], e["nombre"]) for e in resume["etapes"]}


# ── La porte ────────────────────────────────────────────────────────────────


def _routes(moteur) -> list[str]:
    with Session(moteur) as s:
        p = Prestataire(nom="Ascenseurs Témoin", specialite="ascenseur")
        s.add(p)
        s.commit()
        return [ROUTE_CARNET, f"/prestataires/{p.id}/metriques"]


def test_un_anonyme_est_refuse(moteur):
    http, _ = client_http(moteur, None)
    for route in _routes(moteur):
        assert http.get(route).status_code == 401, route


@pytest.mark.parametrize("role", [RoleUtilisateur.propriétaire, RoleUtilisateur.résident])
def test_un_coproprietaire_non_cs_est_refuse(moteur, role):
    """Le carnet est ouvert aux copropriétaires ; son BILAN, au conseil seul."""
    http, _ = client_http(moteur, role)
    for route in _routes(moteur):
        assert http.get(route).status_code == 403, route


@pytest.mark.parametrize("role", [RoleUtilisateur.conseil_syndical, RoleUtilisateur.admin])
def test_le_conseil_et_l_administration_passent(moteur, role):
    http, _ = client_http(moteur, role)
    for route in _routes(moteur):
        assert http.get(route).status_code == 200, route


def test_un_prestataire_inconnu_rend_404(moteur):
    assert _cs(moteur).get("/prestataires/9999/metriques").status_code == 404


# ── Le cas zéro ─────────────────────────────────────────────────────────────


def test_sans_aucune_affaire_le_bilan_est_vide_et_l_exercice_en_cours_propose(moteur):
    bilan = _cs(moteur).get(ROUTE_CARNET).json()
    assert bilan["categories"] == []
    assert bilan["nombre"] == 0
    assert bilan["exercice"] == {
        "annee": 2026,
        "libelle": "2026",
        "debut": "2026-01-01",
        "fin": "2026-12-31",
    }
    assert bilan["exercices"] == [{"annee": 2026, "libelle": "2026"}]


def test_un_prestataire_sans_affaire_rend_des_moyennes_absentes_jamais_zero(moteur):
    [_, route] = _routes(moteur)
    corps = _cs(moteur).get(route).json()
    assert corps["exercices"] == []
    ensemble = corps["ensemble"]
    assert ensemble["nombre"] == 0
    assert ensemble["etapes"] == []
    for cle in ("duree_totale", "relances_par_affaire", "reaction_relance", "suites"):
        assert ensemble[cle] is None, cle


# ── Les moyennes ────────────────────────────────────────────────────────────


def test_le_bilan_de_l_exercice_en_cours_moyenne_les_affaires_du_carnet(moteur):
    _Jeu(moteur)
    bilan = _cs(moteur).get(ROUTE_CARNET).json()

    assert bilan["exercice"]["libelle"] == "2026"
    assert [e["annee"] for e in bilan["exercices"]] == [2026, 2025]
    #  A, B (panne) et C (sinistre) — ni la question D, ni la panne ouverte F.
    assert bilan["nombre"] == 3
    cats = _par_categorie(bilan)
    assert set(cats) == {"panne", "sinistre"}
    assert [c["categorie"] for c in bilan["categories"]] == ["panne", "sinistre"]
    #  Le libellé est SERVI (#2511) : le site et l'app le lisent, sans table à eux.
    assert [c["categorie_libelle"] for c in bilan["categories"]] == [
        libelle_categorie("panne"),
        libelle_categorie("sinistre"),
    ]
    assert cats["panne"]["categorie_libelle"] != "panne"

    panne = cats["panne"]
    assert panne["nombre"] == 2 and panne["annulees"] == 0
    assert panne["duree_totale"] == 4.0  # (5 + 3) / 2
    assert _etapes(panne) == {"ouvert": (1.5, 2), "chez_prestataire": (2.5, 2)}
    assert panne["relances"] == 1
    assert panne["relances_par_affaire"] == 0.5
    assert panne["reaction_relance"] == 1.0
    assert panne["reactions"] == 1
    #  Les plus lents d'abord : P1 (3 j) puis P2 (2 j).
    assert [(p["nom"], p["jours"], p["nombre"]) for p in panne["prestataires"]] == [
        ("Ascenseurs Témoin", 3.0, 1),
        ("Plomberie Témoin", 2.0, 1),
    ]

    sinistre = cats["sinistre"]
    assert sinistre["nombre"] == 1 and sinistre["annulees"] == 1
    assert sinistre["duree_totale"] == 1.0
    assert sinistre["prestataires"] == []
    #  Sans relance, le délai de réaction est ABSENT — pas 0.
    assert sinistre["reaction_relance"] is None and sinistre["reactions"] == 0


def test_un_exercice_precedent_se_choisit_et_un_exercice_sans_affaire_est_vide(moteur):
    _Jeu(moteur)
    http = _cs(moteur)
    precedent = http.get(ROUTE_CARNET, params={"exercice": 2025}).json()
    assert precedent["exercice"]["libelle"] == "2025"
    assert precedent["nombre"] == 1
    [panne] = precedent["categories"]
    assert panne["duree_totale"] == 3.0
    assert [(p["nom"], p["jours"]) for p in panne["prestataires"]] == [("Ascenseurs Témoin", 2.0)]

    vide = http.get(ROUTE_CARNET, params={"exercice": 2020}).json()
    assert vide["categories"] == [] and vide["nombre"] == 0
    assert [e["annee"] for e in vide["exercices"]] == [2026, 2025]


def test_la_fiche_prestataire_compte_toutes_ses_affaires_closes_par_exercice(moteur):
    jeu = _Jeu(moteur)
    corps = _cs(moteur).get(f"/prestataires/{jeu.p1}/metriques").json()

    #  A, D (la question, hors carnet) et E — pas la panne ouverte F.
    ensemble = corps["ensemble"]
    assert ensemble["nombre"] == 3
    assert ensemble["duree_totale"] == 3.0  # (5 + 1 + 3) / 3
    assert _etapes(ensemble)["chez_prestataire"] == (2.0, 3)  # (3 + 1 + 2) / 3

    assert [(e["libelle"], e["nombre"]) for e in corps["exercices"]] == [("2026", 2), ("2025", 1)]
    [courant, precedent] = corps["exercices"]
    assert _etapes(courant)["chez_prestataire"] == (2.0, 2)  # (3 + 1) / 2
    assert precedent["duree_totale"] == 3.0


def test_une_affaire_a_deux_intervenants_compte_pour_chacun(moteur):
    """#2704, Q8 : l'étape « Chez le prestataire » ne dit pas lequel a traîné —
    sa durée est attribuée à chacun, au bilan du carnet comme sur la fiche."""
    from app.models.tickets import TicketPrestataire

    jeu = _Jeu(moteur)
    with Session(moteur) as s:
        #  G — panne, P2 puis P1 : chez les prestataires 1 j.
        jeu._affaire(
            s,
            "panne",
            jeu.p2,
            _utc(2026, 3, 23, 8),
            [
                ("etat", _utc(2026, 3, 24, 8), "ouvert", "chez_prestataire", None),
                ("etat", _utc(2026, 3, 25, 8), "chez_prestataire", "résolu", None),
            ],
        )
        g = s.exec(select(Ticket).where(Ticket.numero == f"MET-{jeu.n:03d}")).one()
        s.add(TicketPrestataire(ticket_id=g.id, prestataire_id=jeu.p2, rang=0))
        s.add(TicketPrestataire(ticket_id=g.id, prestataire_id=jeu.p1, rang=1))
        s.commit()
    http = _cs(moteur)
    panne = _par_categorie(http.get(ROUTE_CARNET).json())["panne"]
    assert [(p["nom"], p["jours"], p["nombre"]) for p in panne["prestataires"]] == [
        ("Ascenseurs Témoin", 2.0, 2),  # (3 + 1) / 2
        ("Plomberie Témoin", 1.5, 2),  # (2 + 1) / 2
    ]
    #  La fiche du SECOND intervenant compte G : A, D, E, puis G.
    assert http.get(f"/prestataires/{jeu.p1}/metriques").json()["ensemble"]["nombre"] == 4


# ── Les bornes d'exercice ───────────────────────────────────────────────────


def test_un_exercice_ouvert_en_juillet_se_nomme_et_se_borne_sur_deux_annees(moteur):
    _Jeu(moteur, mois_debut_exercice=7)
    bilan = _cs(moteur).get(ROUTE_CARNET).json()
    #  Le 15/05/2026 tombe dans l'exercice 2025-2026, qui porte les affaires de mars.
    assert bilan["exercice"] == {
        "annee": 2025,
        "libelle": "2025-2026",
        "debut": "2025-07-01",
        "fin": "2026-06-30",
    }
    assert bilan["nombre"] == 3
    #  La panne de juin 2025 appartient à l'exercice d'avant.
    assert bilan["exercices"] == [
        {"annee": 2025, "libelle": "2025-2026"},
        {"annee": 2024, "libelle": "2024-2025"},
    ]


def test_la_frontiere_d_exercice_est_minuit_a_paris():
    ex = A.exercice_commence_en(2025, 7)
    assert (ex.debut, ex.fin, ex.libelle) == (date(2025, 7, 1), date(2026, 7, 1), "2025-2026")
    #  Le 1ᵉʳ juillet 2026 commence à 22 h UTC la veille (heure d'été).
    assert ex.contient(datetime(2026, 6, 30, 21, 59))
    assert not ex.contient(datetime(2026, 6, 30, 22, 0))
    #  Et le premier jour à minuit de Paris, le 30 juin 2025 à 22 h UTC.
    assert ex.contient(datetime(2025, 6, 30, 22, 0))
    assert not ex.contient(datetime(2025, 6, 30, 21, 59))


@pytest.mark.parametrize("mois", [None, 1, 4, 7, 12])
def test_l_exercice_qui_commence_une_annee_est_celui_de_cette_annee(mois):
    assert A.exercice_commence_en(2024, mois).annee == 2024
