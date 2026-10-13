"""Ce que vaut l'inscription d'une installation — la décision PURE (R2 #1878, §4.11).

Chaque raison de ne pas croire un bail est un cas : signature, clé inconnue ou
révoquée, époque inférieure, bail d'une autre clé, échéance. Et un bail illisible
vaut « limitée », jamais une exception.
"""

from __future__ import annotations

from datetime import datetime, timedelta

import pytest

from app.inscription import constat
from app.inscription.depot import EtatLocal
from app.registre import signature
from app.registre.contrat import Bail, BailSigne, octets_du_bail

MAINTENANT = datetime(2026, 10, 13, 12, 0, 0)

REF_PRIVEE, REF_PUBLIQUE = signature.generer_paire()
INST_PRIVEE, INST_PUBLIQUE = signature.generer_paire()
CLES = {1: REF_PUBLIQUE}


def _bail(**champs) -> dict:
    valeurs = dict(
        identifiant="CF-000042",
        empreinte_cle=signature.empreinte(INST_PUBLIQUE),
        etat="active",
        canal="replica",
        epoque=1,
        delivre_le=MAINTENANT - timedelta(days=1),
        echeance=MAINTENANT + timedelta(days=29),
    )
    valeurs.update({k: v for k, v in champs.items() if k != "cle"})
    bail = Bail(**valeurs)
    cle = champs.get("cle", REF_PRIVEE)
    return BailSigne(bail=bail, signature=signature.signer(cle, octets_du_bail(bail))).model_dump(
        mode="json"
    )


def _etat(bail=None, **autres) -> EtatLocal:
    valeurs = dict(
        identifiant="CF-000042",
        bail=bail,
        plus_haute_epoque=1,
        dernier_renouvellement_le=(MAINTENANT - timedelta(hours=10)).isoformat(),
    )
    valeurs.update(autres)
    return EtatLocal(**valeurs)


def _constat(etat, **k):
    return constat.constater(
        etat,
        maintenant=MAINTENANT,
        cle_installation=k.pop("cle_installation", INST_PUBLIQUE),
        role=k.pop("role", "replique"),
        essai=k.pop("essai", False),
        cles=k.pop("cles", CLES),
        **k,
    )


def test_un_bail_signe_et_valide_rend_active():
    verdict = _constat(_etat(_bail()))
    assert (verdict.etat, verdict.identifiant, verdict.canal) == ("active", "CF-000042", "replica")
    assert not verdict.renouvellement_en_retard


def test_un_bail_suspendu_rend_suspendue():
    assert _constat(_etat(_bail(etat="suspendue"))).etat == "suspendue"


@pytest.mark.parametrize("etat, raison", [("en_attente", "attente"), ("resiliee", "résiliée")])
def test_attente_et_resiliation_rendent_limitee(etat, raison):
    verdict = _constat(_etat(_bail(etat=etat)))
    assert verdict.etat == "limitee" and raison in verdict.raison


def test_la_reference_et_l_essai_ne_sont_jamais_limites():
    assert _constat(EtatLocal(), role="reference").etat == "reference"
    assert _constat(EtatLocal(), essai=True).etat == "essai"


@pytest.mark.parametrize(
    "etat, raison",
    [
        (EtatLocal(), "non inscrite"),
        (EtatLocal(illisible=True), "illisible"),
        (_etat(None), "aucun bail"),
        (_etat(None, etat_inscription="en_attente"), "attente"),
        (_etat({"bail": "n'importe quoi"}), "bail illisible"),
    ],
)
def test_sans_bail_cru_l_installation_est_limitee(etat, raison):
    verdict = _constat(etat)
    assert verdict.etat == "limitee" and raison in verdict.raison


@pytest.mark.parametrize(
    "bail, options, raison",
    [
        # signé par une autre clé que celle de la référence
        (lambda: _bail(cle=signature.generer_paire()[0]), {}, "signature"),
        # époque dont l'image n'a pas la clé
        (lambda: _bail(epoque=2), {}, "inconnue pour l'époque 2"),
        # la clé de la référence a été révoquée
        (lambda: _bail(), {"revoquees": frozenset({REF_PUBLIQUE})}, "révoquée"),
        # le bail d'une autre installation (clone, copie d'état)
        (lambda: _bail(empreinte_cle="0" * 16), {}, "autre installation"),
        (lambda: _bail(identifiant="CF-000099"), {}, "autre installation"),
        # échu
        (lambda: _bail(echeance=MAINTENANT - timedelta(seconds=1)), {}, "échu"),
    ],
)
def test_chaque_raison_de_ne_pas_croire_un_bail_se_nomme(bail, options, raison):
    verdict = _constat(_etat(bail()), **options)
    assert verdict.etat == "limitee"
    assert raison in verdict.raison


def test_un_bail_d_une_epoque_inferieure_est_refuse():
    """Jamais deux références : une installation qui a vu l'époque 2 ne croit plus la 1."""
    cles = {1: REF_PUBLIQUE, 2: signature.generer_paire()[1]}
    verdict = _constat(_etat(_bail(), plus_haute_epoque=2), cles=cles)
    assert verdict.etat == "limitee" and "ancienne référence" in verdict.raison


def test_sans_renouvellement_depuis_trois_jours_l_alerte_est_due():
    etat = _etat(_bail(), dernier_renouvellement_le=(MAINTENANT - timedelta(days=4)).isoformat())
    verdict = _constat(etat)
    assert verdict.etat == "active" and verdict.renouvellement_en_retard


def test_sans_cle_de_reference_dans_l_image_aucun_bail_n_est_cru():
    """L'état de la livraison : la clé de l'époque 1 n'est pas encore versée (#1878)."""
    verdict = _constat(_etat(_bail()), cles={})
    assert verdict.etat == "limitee" and "inconnue" in verdict.raison
