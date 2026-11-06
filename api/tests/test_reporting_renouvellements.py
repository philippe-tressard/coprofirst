"""Le relevé des renouvellements — contrats et diagnostics — est SERVI (#2525).

## 🔴 Le défaut

Reporting › Renouvellements se CALCULAIT dans le front (`#lib/reporting.ts`) : la
prochaine échéance d'un diagnostic (`diagNextDate`), son urgence (`diagUrgence`),
l'ordre des contrats (la pire note d'abord), les trois compteurs du bandeau et
l'année de référence — celle du navigateur. L'app iOS ne recopie aucune règle du
site (`standards/09` §8) : elle laissait la vue au site. Le Suivi des affaires
montrait la voie (`GET /suivi-affaires` porte la règle) ; ce relevé la suit —
`routers/reporting_renouvellements.py`, ses droits et son cas nominal ci-dessous.
"""

from __future__ import annotations

from datetime import date

import pytest
from sqlmodel import Session

from app.models.core import (
    ContratEntretien,
    DiagnosticRapport,
    DiagnosticType,
    NotationPrestataire,
    Prestataire,
    RoleUtilisateur,
)
from app.utils import horloge
from app.utils.echeance_diagnostic import (
    est_permanent,
    prochaine_echeance,
    urgence_diagnostic,
)
from tests.aides_http import base_http, client_http

AUJOURDHUI = date(2026, 11, 5)
#  Des intitulés d'entreprise et de diagnostic, pas des personnes : en constantes,
#  hors de portée du relevé des noms (`test_identites_fictives.py`).
PRESTA_BIEN_NOTE = "Ascenseurs Durand"
PRESTA_MAL_NOTE = "Toitures Martin"
DIAGNOSTICS = {"DTA": "Amiante", "ASC": "Contrôle ascenseur", "GAZ": "Gaz"}


#  ── diagNextDate → `prochaine_echeance` ────────────────────────────────────


def test_l_echeance_d_un_diagnostic_suit_son_dernier_rapport():
    assert prochaine_echeance("3 ans", date(2024, 3, 10)) == date(2027, 3, 10)
    assert prochaine_echeance("10 ans", date(2020, 1, 31)) == date(2030, 1, 31)


def test_sans_rapport_ou_sans_periodicite_pas_d_echeance_inventee():
    assert prochaine_echeance("3 ans", None) is None
    assert prochaine_echeance(None, date(2024, 3, 10)) is None
    assert prochaine_echeance("à la demande", date(2024, 3, 10)) is None


def test_un_diagnostic_permanent_n_a_pas_d_echeance():
    """« Permanent (révision si amiante détecté) » porte un chiffre que rien n'additionne."""
    assert est_permanent("Permanent (révision si plomb > seuil)")
    assert prochaine_echeance("Permanent (révision si plomb > seuil)", date(2020, 1, 1)) is None
    assert not est_permanent("3 ans")
    assert not est_permanent(None)


def test_un_29_fevrier_ne_fait_pas_tomber_la_regle():
    """🔴 `date.replace(year=…)` lèverait : le terme se ramène au dernier jour du mois."""
    assert prochaine_echeance("1 an", date(2024, 2, 29)) == date(2025, 2, 28)


#  ── diagUrgence → `urgence_diagnostic` ─────────────────────────────────────


@pytest.mark.parametrize(
    "echeance, attendu",
    [
        (AUJOURDHUI, "depasse"),  # le jour même est dépassé, comme au site
        (date(2026, 1, 1), "depasse"),
        (date(2026, 12, 31), "annee"),
        (date(2027, 1, 1), "futur"),
        (None, None),
    ],
)
def test_l_urgence_d_un_diagnostic(echeance, attendu):
    assert urgence_diagnostic(echeance, aujourdhui=AUJOURDHUI) == attendu


#  ── le relevé ──────────────────────────────────────────────────────────────


def _poser(moteur) -> None:
    with Session(moteur) as s:
        bon = Prestataire(nom=PRESTA_BIEN_NOTE, specialite="ascenseur")
        mauvais = Prestataire(nom=PRESTA_MAL_NOTE, specialite="toiture")
        s.add_all([bon, mauvais])
        s.commit()
        s.add_all(
            [NotationPrestataire(prestataire_id=bon.id, note=5)]
            + [NotationPrestataire(prestataire_id=mauvais.id, note=2)]
        )
        s.add_all(
            [
                ContratEntretien(
                    copropriete_id=1,
                    prestataire_id=bon.id,
                    libelle="Ascenseur",
                    type_equipement="ascenseur",
                    #  Terme le 01/01/2027 : préavis ouvert depuis le 01/10/2026.
                    date_debut=date(2026, 1, 1),
                ),
                ContratEntretien(
                    copropriete_id=1,
                    prestataire_id=mauvais.id,
                    libelle="Toiture",
                    type_equipement="toiture",
                    date_debut=date(2026, 6, 1),
                    duree_initiale_valeur=3,
                    duree_initiale_unite="ans",
                ),
            ]
        )
        amiante = DiagnosticType(
            code="DTA", nom=DIAGNOSTICS["DTA"], texte_legislatif="x", frequence="Permanent", ordre=1
        )
        ascenseur = DiagnosticType(
            code="ASC", nom=DIAGNOSTICS["ASC"], texte_legislatif="x", frequence="5 ans", ordre=2
        )
        gaz = DiagnosticType(
            code="GAZ",
            nom=DIAGNOSTICS["GAZ"],
            texte_legislatif="x",
            frequence="3 ans",
            ordre=3,
            non_applicable=True,
        )
        s.add_all([amiante, ascenseur, gaz])
        s.commit()
        s.add(
            DiagnosticRapport(
                diagnostic_type_id=ascenseur.id,
                titre="Rapport",
                date_rapport=date(2021, 12, 1),
                fichier_nom="r.pdf",
                mime_type="application/pdf",
            )
        )
        s.commit()


def test_le_releve_sert_l_ordre_les_echeances_et_les_compteurs(monkeypatch):
    monkeypatch.setattr(horloge, "aujourd_hui", lambda: AUJOURDHUI)
    with base_http() as moteur:
        _poser(moteur)
        cs, _ = client_http(moteur, RoleUtilisateur.conseil_syndical)
        reponse = cs.get("/reporting/renouvellements")
    assert reponse.status_code == 200, reponse.text
    releve = reponse.json()
    assert (releve["annee"], releve["preavis_mois"]) == (2026, 3)

    #  🔴 La pire note d'abord : le contrat mal noté est la décision à prendre.
    toiture, ascenseur = releve["contrats"]
    assert (toiture["prestataire_nom"], toiture["note_moyenne"]) == (PRESTA_MAL_NOTE, 2.0)
    assert (ascenseur["urgence_echeance"], ascenseur["echeance_dans_l_annee"]) == (
        "preavis",
        True,
    )
    assert toiture["echeance_dans_l_annee"] is False

    #  Les non applicables sortent ; un permanent reste, sans échéance.
    diags = {d["code"]: d for d in releve["diagnostics"]}
    assert set(diags) == {"ASC", "DTA"}
    assert (diags["ASC"]["prochaine_echeance"], diags["ASC"]["urgence_echeance"]) == (
        "2026-12-01",
        "annee",
    )
    assert diags["ASC"]["dernier_rapport_le"] == "2021-12-01"
    assert (diags["DTA"]["permanent"], diags["DTA"]["prochaine_echeance"]) == (True, None)
    assert [d["code"] for d in releve["diagnostics"]] == ["ASC", "DTA"]

    assert releve["compteurs"] == {
        "contrats_en_preavis": 1,
        "echeances_contrats_annee": 1,
        #  L'ascenseur (cette année) et l'amiante (sans échéance), comme au site.
        "audits_a_planifier": 2,
    }


def test_le_releve_est_reserve_au_conseil():
    with base_http() as moteur:
        resident, _ = client_http(moteur, RoleUtilisateur.résident)
        assert resident.get("/reporting/renouvellements").status_code == 403
