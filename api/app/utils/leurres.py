"""Les leurres de l'application — un seul registre (#2365).

## Pourquoi

L'audit de sécurité nocturne (S1–S6) CONSTATE une intrusion après coup. Un leurre
la fait se trahir au premier geste : un attaquant, humain ou agent, cherche
toujours les mêmes objets, et aucun utilisateur légitime n'y touche jamais. Le
signal est pur, sans faux positif.

## Ce que l'application porte

- **un faux compte** : une connexion tentée sur `LEURRE_ADRESSE` ne peut venir que
  d'une liste volée, ou du faux `.env.bak` — elle rend le même 401 qu'un mauvais
  mot de passe, et journalise `connexion_leurre` ;
- **une fausse clé de maintenance** : `LEURRE_CLE_MAINTENANCE` présentée à une
  route `/admin/maintenance/*` rend le même 403 qu'une clé fausse, et journalise
  `cle_maintenance_leurre` ;
- **de fausses routes** servies par Caddy (`ROUTES_LEURRES`) : un contenu inerte
  qui montre l'adresse et la clé leurres. Les LIRE se compte (S6, ligne OK) — les
  scanners demandent `/.env` chaque nuit, un FAIL à chaque lecture serait du bruit ;
  EMPLOYER ce qu'elles montrent est le FAIL.

Les VALEURS ne vivent que dans le `.env` du nœud (`Settings.leurre_*`) : le dépôt
est public, une valeur écrite ici se reconnaîtrait. Vides, rien ne change.

Le faux `.env.bak` sur l'arbre déployé et la clé SSH leurre se posent sur les
nœuds (#2365, partie infrastructure).

🔒 `test_leurres.py` : chaque leurre est éprouvé (une connexion, une clé, les trois
routes de Caddy) ; les routes de ce registre sont celles du `Caddyfile` et de S6
(`scripts/lib/lib-audit-acces.sh`), et chaque évènement est un code de
`journal_securite._NIVEAUX` repris par S6 en FAIL.
"""

from __future__ import annotations

import hmac
from typing import Optional

from app.auth.adresse_compte import normaliser_adresse
from app.config import get_settings

#: Les chemins que Caddy sert en leurre — la même liste dans le `Caddyfile`
#: (un `handle` chacun) et dans S6 (`ACCES_CHEMINS_LEURRES`).
ROUTES_LEURRES = ("/.env", "/admin/backup.zip", "/api/v1/export")

#: Les codes du journal de sécurité que l'EMPLOI d'un leurre écrit — S6 les lit
#: en FAIL (`ACCES_EVENEMENTS_LEURRES`).
EVENEMENTS_LEURRES = ("connexion_leurre", "cle_maintenance_leurre")


def _egal(a: str, b: str) -> bool:
    """Comparaison à temps constant, en octets (`auth/cle_maintenance`)."""
    return hmac.compare_digest(a.encode("utf-8"), b.encode("utf-8"))


def est_adresse_leurre(adresse: Optional[str]) -> bool:
    """Cette adresse est-elle celle du faux compte ? Jamais vrai sans leurre posé."""
    leurre = normaliser_adresse(get_settings().leurre_adresse)
    return bool(leurre) and _egal(normaliser_adresse(adresse), leurre)


def est_cle_maintenance_leurre(cle: Optional[str]) -> bool:
    """Cette clé est-elle la fausse clé de maintenance ?

    ⚠️ Jamais vrai si la clé leurre égale la vraie : un `.env` mal rempli
    fermerait sinon le canal des scripts d'exploitation.
    """
    s = get_settings()
    leurre = s.leurre_cle_maintenance
    if not leurre or (s.maintenance_key and _egal(leurre, s.maintenance_key)):
        return False
    return _egal(cle or "", leurre)
