"""L'échéance d'une affaire datée : « J-8 », « Jour J », « En cours », « Passé ».

La gouttière du fil la LIT (maquette C, 10/11/2026) : la règle n'existe qu'au
serveur (`utils/echeance_affaire`), en jours civils de Paris. Le jour de
référence est INJECTÉ : aucun de ces tests ne lit l'horloge réelle.
"""

from __future__ import annotations

from datetime import date, datetime
from types import SimpleNamespace

import pytest

from app.models.core import Ticket
from app.routers.flux.commun import pastilles_affaire
from app.utils.echeance_affaire import LIBELLES_ETAT, echeance

JOUR = date(2026, 11, 9)


def _affaire(debut=None, fin=None, statut="en_cours"):
    return SimpleNamespace(debut=debut, fin=fin, statut=statut)


def test_sans_date_il_n_y_a_pas_d_echeance():
    assert echeance(_affaire(), aujourd_hui=JOUR) is None


@pytest.mark.parametrize(
    ("debut", "fin", "etat", "jours", "libelle"),
    [
        (datetime(2026, 11, 17, 9), None, "a_venir", 8, "J-8"),
        (datetime(2026, 11, 10, 9), None, "a_venir", 1, "J-1"),
        (datetime(2026, 11, 9, 15), None, "jour_j", 0, "Jour J"),
        (datetime(2026, 11, 7, 9), datetime(2026, 11, 9, 17), "en_cours", -2, "En cours"),
        (datetime(2026, 11, 7, 9), datetime(2026, 11, 8, 17), "passee", -2, "Passé"),
        (datetime(2026, 11, 8, 9), None, "passee", -1, "Passé"),
    ],
)
def test_les_etats_et_leur_libelle(debut, fin, etat, jours, libelle):
    rendu = echeance(_affaire(debut, fin), aujourd_hui=JOUR)
    assert (rendu["etat"], rendu["jours"], rendu["libelle"]) == (etat, jours, libelle)


def test_une_affaire_close_ne_compte_plus():
    """« J-8 » sur une intervention annulée annoncerait ce qui n'aura pas lieu."""
    rendu = echeance(_affaire(datetime(2026, 11, 17, 9), statut="annulé"), aujourd_hui=JOUR)
    assert rendu["etat"] == "close" and rendu["libelle"] is None
    assert LIBELLES_ETAT["close"] is None


def test_plusieurs_jours_seulement_si_la_fin_tombe_un_autre_jour():
    meme_jour = _affaire(datetime(2026, 11, 17, 8), datetime(2026, 11, 17, 16))
    trois_jours = _affaire(datetime(2026, 11, 17, 8), datetime(2026, 11, 19, 16))
    a_l_envers = _affaire(datetime(2026, 11, 17, 8), datetime(2026, 11, 15, 16))
    assert echeance(meme_jour, aujourd_hui=JOUR)["plusieurs_jours"] is False
    assert echeance(trois_jours, aujourd_hui=JOUR)["plusieurs_jours"] is True
    assert echeance(a_l_envers, aujourd_hui=JOUR)["plusieurs_jours"] is False


def test_le_jour_est_celui_de_PARIS():
    """23 h 30 UTC le 16 : à Paris, c'est déjà le 17 — J-8 et non J-7 depuis le 9."""
    rendu = echeance(_affaire(datetime(2026, 11, 16, 23, 30)), aujourd_hui=JOUR)
    assert rendu["libelle"] == "J-8"


def test_le_fil_sert_l_echeance_et_la_fin():
    """La carte du fil reçoit de quoi rendre la vignette : l'échéance et les deux dates."""
    affaire = Ticket(
        id=7,
        numero="TK-109008",
        titre="Vérification incendie",
        description="Visite du prestataire",
        auteur_id=1,
        categorie="entretien",
        statut="annulé",
        debut=datetime(2026, 11, 17, 9),
        fin=datetime(2026, 11, 19, 17),
    )
    rendu = pastilles_affaire(affaire)
    assert rendu["echeance"] == {
        "etat": "close",
        "jours": rendu["echeance"]["jours"],
        "libelle": None,
        "plusieurs_jours": True,
    }
    assert rendu["debut"] and rendu["fin"]
    assert (
        pastilles_affaire(Ticket(**{**affaire.model_dump(), "debut": None, "fin": None}))[
            "echeance"
        ]
        is None
    )
