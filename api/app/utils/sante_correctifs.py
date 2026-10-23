"""Les correctifs du SYSTÈME de cette installation passent-ils ? (contrôle de 06:00).

`deploiement/standard/correctifs-systeme.sh --rapport` juge chaque matin le serveur
— configuration d'`unattended-upgrades` en service, paquet vu par un passage sans
être posé, redémarrage requis qui n'a pas eu lieu, état illisible — et rend compte
par le canal des scripts d'exploitation (`POST /admin/maintenance/rapport`, tâche
`correctifs_systeme`). La décision est faite sur le serveur ; ici, on la LIT :

- aucun compte rendu, jamais : l'installation n'a pas posé le contrôle (la
  référence, dont les nœuds ont C30) — rien à dire, et rien ne part au registre ;
- le dernier dit `erreur` : en défaut ;
- le dernier date de plus de `MUET_APRES` : le contrôle ne rend plus compte. Son
  silence n'est pas « à jour » (`standards/04` §4, le battement manquant).

Deux lecteurs, une décision (`etat_correctifs`) : le courriel de 06:00
(`problemes_correctifs`) et le rapport nocturne au registre (`inscription/rapport`),
où la référence en fait une alerte. 🔒 `tests/test_sante_correctifs.py`.
"""

from __future__ import annotations

from datetime import timedelta
from typing import Optional

from sqlmodel import Session

from app.models.core import TachePlanifiee
from app.utils import horloge
from app.utils.etat_taches import dernier_rapport

#: Le contrôle tourne chaque jour vers 07:30 : deux jours sans compte rendu, il ne
#: tourne plus (minuteur arrêté, API injoignable à son heure, copie cassée).
MUET_APRES = timedelta(hours=48)


def etat_correctifs(session: Session) -> Optional[str]:
    """`a_jour` | `en_defaut` | `muet` (`contrat.ETATS_CORRECTIFS`), ou None sans contrôle posé."""
    dernier = dernier_rapport(session, TachePlanifiee.correctifs_systeme.value)
    if dernier is None:
        return None
    if horloge.maintenant() - dernier.cree_le > MUET_APRES:
        return "muet"
    return "en_defaut" if dernier.statut == "erreur" else "a_jour"


def problemes_correctifs(session: Session) -> list[str]:
    """Le défaut des correctifs du système, tant qu'il dure — un courriel par jour au plus."""
    etat = etat_correctifs(session)
    if etat == "en_defaut":
        dernier = dernier_rapport(session, TachePlanifiee.correctifs_systeme.value)
        return [
            "Les correctifs du système ne passent plus : "
            + ((dernier.erreur if dernier else None) or "cause non transmise")
            + ". Sur le serveur : sudo deploiement/standard/correctifs-systeme.sh --etat"
        ]
    if etat == "muet":
        return [
            "Le contrôle des correctifs du système ne rend plus compte depuis plus de "
            f"{int(MUET_APRES.total_seconds() // 3600)} h : son état est inconnu. Sur le "
            "serveur : systemctl status coprofirst-correctifs.timer"
        ]
    return []
