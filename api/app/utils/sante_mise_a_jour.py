"""La mise à jour nocturne d'une réplique a-t-elle échoué ? — contrôle de 06:00 (#1756).

`deploiement/standard/mise-a-jour.sh` rend compte de chaque passage par le canal
des scripts d'exploitation (`POST /admin/maintenance/rapport`, tâche
`mise_a_jour`). Une réplique tient sur UN serveur (D15) : une mise à jour ratée
a déjà été défaite par le script — retour à l'image précédente, puis à la
sauvegarde s'il le fallait —, mais l'exploitant doit le savoir, et le savoir par
un autre canal que l'écran qu'il ne regarde pas.

Ce contrôle ne dit QUE l'échec récent. Il ne juge pas l'absence de passage : la
référence (5Hostachy) ne fait pas de mise à jour nocturne, et sans le rôle de
l'installation (#1761) une absence ne se distingue pas d'une référence. 🔒
`tests/test_sante_mise_a_jour.py`.
"""

from __future__ import annotations

from datetime import timedelta

from sqlmodel import Session

from app.models.core import TachePlanifiee
from app.utils import horloge
from app.utils.etat_taches import dernier_rapport

#: Au-delà, l'échec est déjà dit par le courriel d'hier, ou a été suivi d'un succès.
FENETRE = timedelta(hours=30)


def problemes_mise_a_jour(session: Session) -> list[str]:
    """Le dernier passage, s'il a échoué il y a moins de `FENETRE` — sinon rien."""
    dernier = dernier_rapport(session, TachePlanifiee.mise_a_jour.value)
    if dernier is None or dernier.statut != "erreur":
        return []
    if horloge.maintenant() - dernier.cree_le > FENETRE:
        return []
    return [
        "La mise à jour nocturne a échoué : "
        + (dernier.erreur or "cause non transmise")
        + ". Le script a remis la version précédente ; lire /var/log/coprofirst-maj.log "
        "sur le serveur avant de relancer."
    ]
