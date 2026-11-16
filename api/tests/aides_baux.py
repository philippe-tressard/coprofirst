"""Un BAIL signé, et une RÉPLIQUE qui le tient — sans registre ni réseau (R6 #1882).

`test_inscription_constat` signait ses baux à la main ; les essais de R6 (plafond,
suspension) en ont besoin aussi, rangés sur le disque d'une réplique : la
fabrique vit ici, une fois.

`replique_au_bail` pose une installation qui se déclare RÉPLIQUE, sa clé, les
clés de la référence et le bail RANGÉ — exactement ce que lit
`inscription.client.constat_courant`. Tout appel à la référence ÉCHOUE : la
référence est ÉTEINTE (D17), ce que les essais de R6 doivent supporter.
"""

from __future__ import annotations

from datetime import datetime, timedelta

import httpx

from app.config import get_settings
from app.inscription import cles, depot
from app.inscription.depot import EtatLocal
from app.registre import signature
from app.registre.contrat import Bail, BailSigne, octets_du_bail
from app.utils import horloge, installation

#: La clé de la référence qui signe les baux des tests.
REF_PRIVEE, REF_PUBLIQUE = signature.generer_paire()
#: L'époque 1, et rien d'autre.
CLES = {1: REF_PUBLIQUE}
IDENTIFIANT = "CF-000042"


def bail_signe(cle_installation: str, maintenant: datetime, **champs) -> dict:
    """Un `BailSigne` sérialisé — `etat`, `echeance`, `services_autorises`, `cle`… se passent."""
    valeurs = dict(
        identifiant=IDENTIFIANT,
        empreinte_cle=signature.empreinte(cle_installation),
        etat="active",
        canal="replica",
        epoque=1,
        delivre_le=maintenant - timedelta(days=1),
        echeance=maintenant + timedelta(days=29),
    )
    valeurs.update({k: v for k, v in champs.items() if k != "cle"})
    bail = Bail(**valeurs)
    cle = champs.get("cle", REF_PRIVEE)
    return BailSigne(bail=bail, signature=signature.signer(cle, octets_du_bail(bail))).model_dump(
        mode="json"
    )


def _reference_eteinte(*_args, **_kwargs):
    raise httpx.ConnectError("la référence est éteinte (essai R6)")


def replique_au_bail(monkeypatch, dossier, **champs_du_bail) -> datetime:
    """Une RÉPLIQUE inscrite, son bail signé RANGÉ, la référence éteinte.

    Rend l'échéance du bail (UTC naïf, comme `horloge.maintenant`). Sans `etat`, le
    bail est actif ; `echeance=` le fait échoir quand on veut.
    """
    reglages = get_settings()
    monkeypatch.setattr(reglages, "installation_dir", str(dossier / "installation"))
    monkeypatch.setattr(reglages, "installation_essai", False)
    monkeypatch.setattr(reglages, "registre_constat", False)
    monkeypatch.setattr(installation, "role_installation", lambda valeur=None: "replique")
    monkeypatch.setattr(cles, "CLES_REFERENCE", CLES)
    monkeypatch.setattr(httpx, "post", _reference_eteinte)
    publique = signature.publique_de(depot.cle_privee())
    maintenant = horloge.maintenant()
    bail = bail_signe(publique, maintenant, **champs_du_bail)
    depot.ecrire(
        EtatLocal(
            identifiant=IDENTIFIANT,
            bail=bail,
            plus_haute_epoque=1,
            dernier_renouvellement_le=maintenant.isoformat(timespec="seconds"),
        )
    )
    return champs_du_bail.get("echeance", maintenant + timedelta(days=29))
