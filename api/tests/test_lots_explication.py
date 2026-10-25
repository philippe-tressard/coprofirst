"""La phrase qui explique ce qu'un lot emporte (#2215) — fonction pure, lots fictifs."""

from __future__ import annotations

from app.models.copropriete import NatureLot as N
from app.utils.lots_explication import phrase

FINE = " "  # espace fine insécable, comme `montants.montant_fr`


def test_une_place_desservie_par_un_autre_batiment_dit_son_ascenseur_et_sa_part():
    assert phrase(
        N.parking,
        -2,
        ["Bât. 3 › Ascenseur", "Bât. 3 › Escaliers"],
        [("Générales", 8, 10000), ("Ascenseur A", 34, 10000)],
    ) == (
        "Cette place (SS 2) est desservie par Bât. 3 › Ascenseur et Bât. 3 › Escaliers. "
        f"Elle contribue aux charges Générales pour 8/10{FINE}000 et Ascenseur A pour 34/10{FINE}000."
    )


def test_sans_tantiemes_visibles_la_phrase_s_arrete_a_la_desserte():
    """Un locataire ne voit pas les tantièmes : la phrase ne les devine pas."""
    assert phrase(N.logement, 2, ["Bât. 1 › Escaliers"], None) == (
        "Ce logement est desservi par Bât. 1 › Escaliers."
    )


def test_sans_desserte_la_part_porte_le_sujet():
    assert phrase(N.cave, None, [], [("Générales", 3, 10000)]) == (
        f"Cette cave contribue aux charges Générales pour 3/10{FINE}000."
    )


def test_rien_a_expliquer_rend_none_jamais_une_phrase_vide():
    assert phrase(None, None, [], None) is None
    assert phrase(N.parking, -1, [], []) is None
