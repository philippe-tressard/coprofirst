"""Flux — rubrique Prestataires : les nouvelles fiches.

Extrait de `flux.py` le 08/08/2026. Voir `__init__.py` pour la règle de découpage.

La source renvoie vers une page (`/prestataires`) **réservée au CS et aux admins**
(`require_cs_or_admin`). Une ligne qui y renverrait un résident lui donnerait un
lien mort ; c'est pourquoi la fiche n'est pas proposée aux autres rôles.

⚠️ Ce module collectait aussi les DEVIS, jusqu'au retrait de la prestation
ponctuelle. Il part ici et non avec les routes de l'API, alors que le reste du
lot suit l'ordre « le front d'abord, l'API ensuite » — parce que la dépendance
est en sens inverse : `lien_element("dv", …)` fabrique une URL **vers le front**,
et `EMPLACEMENTS` (`utils/liens.py`) lève un `KeyError` sur un préfixe inconnu.
Retirer l'onglet sans retirer la ligne qui le vise aurait laissé le fil produire
un lien vers un onglet disparu ; retirer la ligne sans retirer l'appelant aurait
fait lever le fil en production. Les deux voyagent donc ensemble, et
`test_liens_front.py` l'a démontré avant la mise en production.
"""

from sqlmodel import select

from app.models.core import Prestataire
from app.utils.liens import lien_element
from .commun import ContexteFlux
from .schemas import FluxItem
from app.auth.deps import est_moderateur


def _reserve_au_cs(ctx: ContexteFlux) -> bool:
    return est_moderateur(ctx.user)


def _collecter_fiches(ctx: ContexteFlux) -> list[FluxItem]:
    #  On ne remonte une nouvelle fiche qu'au CS/admin : pour les autres, le lien
    #  mènerait à une page qu'ils n'ont pas le droit d'ouvrir.
    if not _reserve_au_cs(ctx):
        return []
    prestas = ctx.session.exec(
        select(Prestataire)
        .where(Prestataire.actif, Prestataire.cree_le >= ctx.since)
        .order_by(Prestataire.cree_le.desc())
    ).all()
    return [
        FluxItem(
            id=f"presta_{pr.id}",
            type="prestataire",
            date=pr.cree_le,
            cree_le=pr.cree_le,
            titre=pr.nom,
            #  L'équipement part en VALEUR (`meta`) et l'écran le traduit : il
            #  s'affichait « interphone_digicode », deux fois (26/09/2026). Les
            #  libellés vivent côté front (`#lib/prestataires`, `EQUIPEMENTS`),
            #  comparés au serveur par `test_types_equipement.py`.
            detail="Nouveau prestataire",
            icon="🛠️",
            badges=[],
            lien=lien_element("presta", pr.id),
            meta={"prestataire_id": pr.id, "specialite": pr.specialite},
        )
        for pr in prestas
    ]


def collecter(ctx: ContexteFlux) -> list[FluxItem]:
    return _collecter_fiches(ctx)
