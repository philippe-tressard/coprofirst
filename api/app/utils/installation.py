"""Le rôle de CETTE installation dans la distribution, et son écart à la branche suivie (#1761).

Lot DI-8 du chantier multi-copropriétés (`specs/architecture/multi-coproprietes.md`
§4.10, règle 11). Exigence de l'auteur, 08/10/2026 : *« savoir si l'instance est
le master (git => main) ou une réplique (git => replica) »*.

| Rôle        | Libellé   | Branche suivie |
|-------------|-----------|----------------|
| `reference` | Référence | `main`       |
| `replique`  | Réplique  | `replica`      |
| `inconnu`   | Inconnu   | —              |

## Les règles

1. **Le rôle appartient à l'installation, pas à l'image** : une version promue est
   la même image chez la référence et chez les répliques. Il se DÉCLARE dans la
   configuration (`ROLE_INSTALLATION`, lu par `Settings`), et se lit ICI seulement.
2. **Absent ou mal écrit → « inconnu », jamais « référence »** : une réplique mal
   configurée ne doit pas se croire la référence (`standards/04` §1).
3. **Le fait, pas la déclaration** : le commit qui tourne (`GIT_HASH`, posé à la
   construction de l'image) doit appartenir à l'historique de la branche suivie.
   Le dépôt public le dit (`compare`), et une réponse impossible rend « non
   vérifié », jamais « à jour ».
4. **Rien ne sort sans accord** (§4.10, règle 9) : la vérification interroge
   GitHub, donc elle est un SERVICE, coupé tant que l'administration ne l'active
   pas (`SERVICE_VERIF_VERSION`).

⚠️ Ne pas confondre avec le rôle d'un NŒUD dans la haute disponibilité (actif /
standby, `.active`) : les deux Raspberry Pi sont ENSEMBLE la référence.
🔒 `tests/test_installation.py`.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

import httpx

from app.config import get_settings
from app.utils import horloge
from app.utils.plateforme import DEPOT_SOURCE

#: rôle → (libellé, branche suivie). La seule écriture.
ROLES: dict[str, tuple[str, str]] = {
    "reference": ("Référence", "main"),
    "replique": ("Réplique", "replica"),
}
INCONNU = "inconnu"

#: Les anciens noms d'un rôle, encore lus. `maitre` était celui de la référence
#: jusqu'au 12/10/2026 (renommée à la demande de l'auteur : « ça fait
#: esclavagiste ») ; il reste accepté tant que le `.env` des deux Raspberry Pi le
#: porte — sinon la référence se dirait « Inconnu » au déploiement. À retirer quand
#: les deux `.env` disent `reference`.
ANCIENS_NOMS: dict[str, str] = {"maitre": "reference"}

#: L'instant où ce processus a démarré : « en service depuis ». Une constante,
#: posée une fois à l'import — pas un état que le processus modifie.
DEMARREE_LE = horloge.maintenant()

#: Le dépôt public, pour l'API de GitHub (`owner/repo`).
DEPOT = DEPOT_SOURCE.removeprefix("https://github.com/")


def role_installation(valeur: Optional[str] = None) -> str:
    """PURE sur sa valeur : `reference`, `replique` ou `inconnu` (règle 2)."""
    brut = get_settings().role_installation if valeur is None else valeur
    role = (brut or "").strip().lower().replace("î", "i").replace("é", "e")
    role = ANCIENS_NOMS.get(role, role)
    return role if role in ROLES else INCONNU


def est_reference() -> bool:
    """CETTE installation est-elle la référence ? La question que pose le registre (§4.11)."""
    return role_installation() == "reference"


def empreinte(valeur: Optional[str] = None) -> str:
    """Le commit qui tourne, ou `""` quand l'image a été construite sans lui (`dev`)."""
    brut = (get_settings().git_hash if valeur is None else valeur) or ""
    return "" if brut.strip() in ("", "dev") else brut.strip()


def version_logicielle() -> str:
    """Ce qui tourne, tel que le registre le lit (R2 #1878) : la version promue d'une
    réplique (`COPROFIRST_VERSION`), sinon le commit de l'image, sinon « inconnue »."""
    return get_settings().coprofirst_version.strip() or empreinte()[:12] or "inconnue"


@dataclass(frozen=True)
class Verification:
    """Ce que le dépôt dit du commit qui tourne, face à la branche suivie."""

    etat: str  #: a_jour · en_retard · ecart · non_verifie
    retard: int = 0  #: commits de la branche absents d'ici (en_retard)
    detail: str = ""


def verdict_comparaison(statut: Optional[str], en_avance: int = 0) -> Verification:
    """PURE. `statut` est celui de `GET /repos/…/compare/{empreinte}...{branche}`.

    `ahead` : la BRANCHE a des commits que l'empreinte n'a pas → en retard.
    `identical` → à jour. `behind` ou `diverged` : l'empreinte porte des commits
    absents de la branche → elle n'est PAS une version de cette branche (écart).
    """
    if statut == "identical":
        return Verification("a_jour")
    if statut == "ahead":
        return Verification("en_retard", retard=en_avance)
    if statut in ("behind", "diverged"):
        return Verification(
            "ecart", detail="la version qui tourne n'appartient pas à la branche suivie"
        )
    return Verification("non_verifie", detail="réponse du dépôt illisible")


def verifier(empreinte_courante: str, branche: str, *, client=None) -> Verification:
    """Interroge le dépôt public. Toute impossibilité rend « non vérifié » (règle 3)."""
    if not empreinte_courante:
        return Verification("non_verifie", detail="image construite sans son commit (GIT_HASH)")
    url = f"https://api.github.com/repos/{DEPOT}/compare/{empreinte_courante}...{branche}"
    try:
        if client is None:
            with httpx.Client(timeout=5) as c:
                r = c.get(url, headers={"Accept": "application/vnd.github+json"})
        else:
            r = client.get(url, headers={"Accept": "application/vnd.github+json"})
        if r.status_code != 200:
            return Verification("non_verifie", detail=f"le dépôt a répondu {r.status_code}")
        corps = r.json()
        return verdict_comparaison(corps.get("status"), int(corps.get("ahead_by") or 0))
    except Exception:  # noqa: BLE001 — injoignable, délai, JSON : jamais un verdict
        return Verification("non_verifie", detail="dépôt injoignable")
