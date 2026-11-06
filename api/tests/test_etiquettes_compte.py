"""Les étiquettes d'un compte ont un troisième état : « sans objet » (26/09/2026).

Les trois comptes signalés à l'écran, et les cas zéro : une étiquette ne passe
jamais au gris quand la chose EXISTE, ni quand elle était attendue.
"""

from __future__ import annotations

from app.utils.etiquettes_compte import MANQUE, OK, SANS_OBJET, etiquettes
from app.utils.types_acces import TELECOMMANDE, VIGIK


def _etats(**kw):
    base = dict(
        a_lot=True,
        a_tc=False,
        a_vigik=False,
        a_bail=False,
        types_lots=set(),
        statut="copropriétaire_résident",
        types_tc=TELECOMMANDE.types_lot,
        types_vigik=VIGIK.types_lot,
    )
    base.update(kw)
    return etiquettes(**base)


def test_coproprietaire_sans_parking_la_tc_est_sans_objet():
    e = _etats(a_vigik=True, types_lots={"appartement", "cave"}, statut="copropriétaire_bailleur")
    assert (e["tc"], e["vigik"], e["bail"]) == (SANS_OBJET, OK, MANQUE)


def test_proprietaire_d_un_seul_parking_le_vigik_est_sans_objet():
    e = _etats(a_tc=True, types_lots={"parking"}, statut="copropriétaire_bailleur")
    assert (e["tc"], e["vigik"]) == (OK, SANS_OBJET)


def test_locataire_d_un_appartement_sans_vigik_remis_reste_rouge():
    """Le Vigik est attendu (il a un appartement) : rouge, c'est l'écart à corriger."""
    e = _etats(a_tc=True, types_lots={"parking", "appartement", "cave"}, statut="locataire")
    assert (e["vigik"], e["bail"]) == (MANQUE, MANQUE)


def test_un_resident_n_a_pas_de_bail_attendu():
    assert _etats(types_lots={"appartement"})["bail"] == SANS_OBJET


def test_cas_zero_ce_qui_existe_reste_vert_quel_que_soit_le_profil():
    e = _etats(a_tc=True, a_vigik=True, a_bail=True, types_lots=set(), statut="syndic")
    assert (e["tc"], e["vigik"], e["bail"]) == (OK, OK, OK)


def test_cas_zero_le_lot_est_toujours_attendu():
    assert _etats(a_lot=False)["loti"] == MANQUE
