"""Ce qu'un copropriétaire doit savoir sur son lot (#2215) — fonction pure, lots fictifs."""

from __future__ import annotations

from app.models.copropriete import NatureLot as N
from app.utils import constats as C
from app.utils.alertes_lot import alertes_du_lot, note_de_cle

FINE = " "  # espace fine insécable, comme `montants.montant_fr`


def _codes(constats):
    return [c.code for c in constats]


def _lot(**surcharges):
    """Un logement complet : aucune alerte tant qu'on n'y touche pas."""
    base = dict(
        nature_declaree=N.logement,
        nature=N.logement,
        etage=2,
        numero_usage="12",
        desservi=True,
        voit_les_tantiemes=True,
        parts=[("Générales", 60, 10000)],
    )
    base.update(surcharges)
    return alertes_du_lot(**base)


def test_un_lot_complet_n_a_aucune_alerte():
    assert _lot() == []


def test_tant_que_l_etat_descriptif_n_est_pas_applique_une_seule_information_le_dit():
    """Cas zéro : un lot sans désignation n'est pas un lot qui cumule dix défauts."""
    trouves = _lot(nature_declaree=None, etage=None, numero_usage=None, parts=[], desservi=False)
    assert _codes(trouves) == ["designation_absente"]
    assert trouves[0].gravite == C.INFORMATION


def test_une_place_sans_circulation_avertit():
    trouves = _lot(nature=N.parking, nature_declaree=N.parking, desservi=False)
    assert "sans_circulation" in _codes(trouves)
    assert next(c for c in trouves if c.code == "sans_circulation").gravite == C.AVERTISSEMENT


def test_un_logement_sans_circulation_n_avertit_pas():
    """Un logement est desservi par son bâtiment : l'absence de circulation n'est pas anormale."""
    assert "sans_circulation" not in _codes(_lot(desservi=False))


def test_un_lecteur_sans_droit_aux_tantiemes_n_apprend_pas_qu_ils_manquent():
    assert "sans_tantieme" not in _codes(_lot(voit_les_tantiemes=False, parts=[]))
    assert "sans_tantieme" in _codes(_lot(voit_les_tantiemes=True, parts=[]))


def test_l_ecart_d_une_cle_se_dit_sous_la_cle_sans_alarmer():
    """#2251 : l'écart concerne la copropriété, pas la part du lecteur — une note de la
    clé, plus une alerte du lot."""
    court = note_de_cle(10000, 9900)
    trop = note_de_cle(10000, 10003)
    assert "il en manque 100" in court and f"9{FINE}900 pour 10{FINE}000" in court
    assert "il y en a 3 de trop" in trop
    assert "Votre part, elle, est celle de l'acte." in court
    assert note_de_cle(10000, 10000) is None


def test_aucune_alerte_ne_bloque_et_aucune_ne_nomme_personne():
    pires = _lot(
        nature=N.cave,
        nature_declaree=N.cave,
        etage=None,
        numero_usage=None,
        desservi=False,
        parts=[],
    )
    assert C.applicable(pires)  # « applicable » : ni BLOQUANT ni INCONNU
    assert {c.gravite for c in pires} <= {C.AVERTISSEMENT, C.INFORMATION}
    assert all(not c.lots for c in pires)


def test_les_avertissements_passent_avant_les_informations():
    ordre = [c.gravite for c in _lot(etage=None, parts=[], nature=N.cave, desservi=False)]
    assert ordre == sorted(ordre, key=lambda g: g != C.AVERTISSEMENT)
