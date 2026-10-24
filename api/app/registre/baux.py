"""Le BAIL — ce que la référence accorde à une installation, et signe (R2 #1878, D19).

Spec `specs/architecture/multi-coproprietes.md` §4.11, règles 3 à 5 et 11.

- Le bail porte l'identifiant, la clé de l'installation (par son empreinte), son
  état, son canal, la version cible, les services autorisés, l'**époque de
  référence** et son **échéance** (30 jours). Il se renouvelle chaque nuit.
- Il est signé par la **clé des baux** (`CLE_SIGNATURE_BAUX`), la seule pièce
  secrète du registre ; sa clé publique est dans l'image des installations
  (`app/inscription/cles.py`).
- **La référence ne pousse jamais** (règle 5) : ses décisions — valider,
  suspendre, changer de canal — voyagent dans le bail, que l'installation TIRE.

Ce module est PUR sauf `cle_de_signature`, qui lit le réglage : `delivrer` reçoit
l'installation, les versions publiées et l'instant, et rend le bail signé.

🔴 **Le format du bail ne s'étend pas** (`contrat.Bail`, R5 #1881) : il refuse les
champs inconnus, et une installation pas encore à jour REJETTERAIT un bail portant
un champ neuf — donc plus de mise à jour automatique, donc jamais à jour. Ce que
R5 décide (canal, vague) voyage dans `version_cible`, déjà au contrat.
🔒 `tests/test_registre_canaux.py` fige ses champs.
"""

from __future__ import annotations

from collections.abc import Iterable
from datetime import datetime, timedelta, timezone

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from app.config import get_settings
from app.registre import signature
from app.registre.contrat import Bail, BailSigne, octets_du_bail
from app.registre.canaux import suivi_de, version_cible
from app.registre.decisions import services_de
from app.registre.modeles import Installation, VersionDisponible
from app.utils.valeurs import valeur

#: L'ÉPOQUE de cette référence. Elle ne change que par un transfert du rôle de
#: référence (R8, D24) : l'acte de transfert, signé par l'ancienne clé, porte n+1,
#: et une installation refuse ensuite tout bail d'une époque inférieure.
EPOQUE = 1

#: La durée d'un bail (D19) : 30 jours couvrent toute panne vraisemblable de la
#: référence, qui est sur deux Raspberry Pi derrière une box résidentielle.
DUREE = timedelta(days=30)


def cle_de_signature() -> Ed25519PrivateKey | None:
    """La clé des baux, ou None : réglage absent ou illisible — aucun bail ne part."""
    return signature.privee_de(get_settings().cle_signature_baux)


def delivrer(
    inst: Installation,
    cle: Ed25519PrivateKey,
    maintenant: datetime,
    versions: Iterable[VersionDisponible] = (),
) -> BailSigne:
    """Le bail de `inst`, daté de `maintenant`, signé par `cle` — sa version cible
    calculée sur `versions`, les versions publiées (`registre/canaux`)."""
    #  Des dates CONSCIENTES de leur fuseau (UTC) : les octets signés sont ceux de
    #  `model_dump(mode="json")`, et une date naïve y sortirait sans « Z » — que la
    #  réponse de l'API (`UTCJSONResponse`) ajoute ENSUITE : l'installation vérifierait
    #  d'autres octets que ceux signés. Consciente, elle s'écrit pareil partout.
    delivre = maintenant.replace(microsecond=0, tzinfo=timezone.utc)
    bail = Bail(
        identifiant=inst.identifiant,
        empreinte_cle=inst.empreinte_cle or "",
        etat=valeur(inst.etat),
        canal=suivi_de(inst)[0],
        version_cible=version_cible(inst, versions, maintenant),  # R5 (#1881)
        services_autorises=services_de(inst),  # accordés par l'opérateur (R4 #1880)
        epoque=EPOQUE,
        delivre_le=delivre,
        echeance=delivre + DUREE,
    )
    return BailSigne(bail=bail, signature=signature.signer(cle, octets_du_bail(bail)))
