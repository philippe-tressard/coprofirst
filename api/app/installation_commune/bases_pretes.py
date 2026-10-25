"""Une copropriété dont la base n'est pas prête ne se sert pas (#2053, spec §4.3).

`start.sh` prépare chaque base (`utils/preparer_bases`) ; l'une peut échouer — base
illisible, migration en erreur — sans bloquer les autres. Il faut alors que l'API
la REFUSE au lieu de la servir à moitié : une colonne neuve absente rendrait 500 au
premier écran, et une tâche planifiée écrirait dans un schéma périmé.

`base_prete()` répond pour la copropriété servie : sa base est-elle à la tête de la
chaîne (ou en avance, après un retour arrière) ? La réponse se garde dans l'état de
la copropriété (`contexte.etat`) : oui une fois pour toutes — une base ne recule pas
—, non pour `NOUVEL_ESSAI_S` secondes, puis on relit. Une base réparée à chaud
redevient servie sans redémarrage.

Installation propre à une copropriété : toujours vrai, sans rien lire. Sa base est
préparée par `start.sh` avant uvicorn, qui s'arrête si elle ne l'est pas — rien ne
change pour 5Hostachy.

Lu par : l'intergiciel de résolution (503 pour le seul hôte de cette copropriété),
`contexte.pour_chaque_copropriete` (la tâche la saute) et `/health`.
🔒 `tests/test_etancheite_installation_commune.py` (l'installation commune réelle : une base
injoignable n'isole que son hôte) et `test_installation_commune_aiguillage.py`.
"""

from __future__ import annotations

import time

from app import contexte

#: Le délai avant de relire une base trouvée non prête.
NOUVEL_ESSAI_S = 30

#: La réponse aux requêtes d'une copropriété dont la base n'est pas prête.
INDISPONIBLE = "Cette copropriété est momentanément indisponible."


def base_prete() -> bool:
    """La base de la copropriété servie peut-elle être servie par ce code ?"""
    if not contexte.est_commune():
        return True
    from app.utils.revision_base import servable

    url = contexte.courante().url_base
    memo = contexte.etat("base_prete")
    vu = memo.get(url)
    if vu is not None and (vu[0] or time.monotonic() - vu[1] < NOUVEL_ESSAI_S):
        return vu[0]
    prete = servable(url)
    memo[url] = (prete, time.monotonic())
    return prete


def bilan() -> tuple[int, int]:
    """(copropriétés servables, copropriétés déclarées) — la question de `/health` sur une
    installation commune. Aucun identifiant n'en sort : la route répond à tout hôte, et
    nommer les copropriétés serait les énumérer (§4.1 bis, règle 5)."""
    from sqlalchemy import text

    pretes = 0
    copros = contexte.coproprietes()
    for copro in copros:
        with contexte.dans(copro):
            try:
                if base_prete():
                    with contexte.moteur().connect() as connexion:
                        connexion.execute(text("SELECT 1"))
                    pretes += 1
            except Exception:  # noqa: BLE001 — une base muette n'est pas servable
                continue
    return pretes, len(copros)
