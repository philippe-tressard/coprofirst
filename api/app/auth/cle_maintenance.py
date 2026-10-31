"""L'authentification par **clé partagée** des scripts d'exploitation.

## Pourquoi ici, et pas dans un routeur (#1028)

Ce mécanisme vivait dans `routers/admin/rapports_scripts.py`. C'est un **second
moyen de s'authentifier** — ni session, ni cookie, ni rôle — et il était le seul
à ne pas vivre dans `auth/`, donc le seul que `test_autorisation.py` ne pouvait
pas raisonner comme une porte : il rangeait ses quatre routes parmi les
**publiques assumées**, ce qui est faux au sens strict. Elles sont authentifiées,
par une clé.

🔴 La conséquence était un **faux vert latent** : une route déclarée « publique
assumée » reste verte si l'on retire son contrôle d'authentification. Retirer
l'appel à `exiger_cle_maintenance` aurait rendu ces routes réellement publiques,
sans qu'aucun contrôle ne change de couleur.
`api/tests/test_autorisation.py` les classe désormais à part, et vérifie que
chacune appelle bien cette fonction.

## Ce que ce canal ouvre, et ce qu'il n'ouvre pas

Il n'autorise que les tâches planifiées des deux nœuds, qui lisent la clé dans
`/opt/5hostachy/.env`. Il ne donne accès à **aucune donnée de copropriétaire** :
dates d'exécution des tâches, comptes d'échecs d'envoi par gabarit, noms de
tables et de colonnes pour le diagnostic de clés étrangères.

C'est cette **portée** qui rend le canal tenable, pas sa commodité — le jour où
une route de ce genre rendrait une adresse, un sujet de courriel ou un
identifiant de ligne, elle devrait passer par une session d'administrateur.
"""

import hmac
from typing import Optional

from fastapi import HTTPException

from app.config import get_settings
from app.utils.journal_securite import journaliser_securite
from app.utils.leurres import est_cle_maintenance_leurre


def exiger_cle_maintenance(cle_recue: Optional[str]) -> None:
    """Vérifie la clé partagée des scripts d'exploitation.

    Extraite de `maintenance_rapport` le 11/08/2026, quand un second point
    d'entrée a eu besoin du même contrôle : recopier trois lignes
    d'authentification est la façon la plus courante de laisser l'une des deux
    copies s'assouplir. Déplacée dans `auth/` le 19/09/2026, pour la raison
    écrite en tête de ce module.

    ⚠️ **Refuse tout si la clé n'est pas configurée** (503, et non 200) : une clé
    vide comparée à une clé vide serait égale, et le canal s'ouvrirait à qui
    n'envoie rien. Un secret absent ne vaut pas un secret satisfait.
    """
    settings = get_settings()
    if not settings.maintenance_key:
        raise HTTPException(
            status_code=503,
            detail="Maintenance reporting non configuré (MAINTENANCE_KEY vide)",
        )
    #  La fausse clé (#2365), montrée par le faux `.env.bak` : la présenter, c'est
    #  l'avoir volée. Le même 403 qu'une clé fausse, et une ligne que S6 lit en FAIL.
    if est_cle_maintenance_leurre(cle_recue):
        journaliser_securite("cle_maintenance_leurre")
        raise HTTPException(status_code=403, detail="Clé maintenance invalide")
    #  Comparaison à TEMPS CONSTANT (27/09/2026) : `!=` s'arrête au premier octet
    #  qui diffère, et la durée de la réponse dit alors combien d'octets étaient
    #  justes. En octets, pas en `str` : `compare_digest` lève sur un caractère non
    #  ASCII, et une clé exotique rendrait 500 au lieu de 403.
    #  🔒 `test_cle_maintenance.py` refuse un secret comparé par `==` ou `!=`.
    if not hmac.compare_digest(
        (cle_recue or "").encode("utf-8"), settings.maintenance_key.encode("utf-8")
    ):
        raise HTTPException(status_code=403, detail="Clé maintenance invalide")
