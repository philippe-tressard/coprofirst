"""Le rôle de CETTE installation dans la distribution, et l'écart de sa version (#1761).

Lot DI-8 du chantier multi-copropriétés (`specs/architecture/multi-coproprietes.md`
§4.10, règle 11). Exigence de l'auteur, 08/10/2026 : *« savoir si l'instance est
le master (git => main) ou une réplique »*.

| Rôle        | Libellé   | Ce qu'elle suit (`cible_suivie`)                     |
|-------------|-----------|------------------------------------------------------|
| `reference` | Référence | la branche `main`                                    |
| `replique`  | Réplique  | le tag de la version que son bail fait installer     |
| `inconnu`   | Inconnu   | —                                                    |

Une réplique suivait la branche `replica` jusqu'à #3009 (24/11/2026) : depuis #2210,
c'est le bail qui décide de sa version (`registre/canaux.py`), et `replica` est retirée.

## Les règles

1. **Le rôle appartient à l'installation, pas à l'image** : une version promue est
   la même image chez la référence et chez les répliques. Il se DÉCLARE dans la
   configuration (`ROLE_INSTALLATION`, lu par `Settings`), et se lit ICI seulement.
2. **Absent ou mal écrit → « inconnu », jamais « référence »** : une réplique mal
   configurée ne doit pas se croire la référence (`standards/04` §1).
3. **Le fait, pas la déclaration** : le commit qui tourne (`GIT_HASH`, posé à la
   construction de l'image) doit appartenir à l'historique de ce qu'elle suit.
   Le dépôt public le dit (`compare`), et une réponse impossible rend « non
   vérifié », jamais « à jour ».
4. **Rien ne sort sans accord** (§4.10, règle 9) : la vérification interroge
   GitHub, donc elle est un SERVICE, coupé tant que l'administration ne l'active
   pas (`SERVICE_VERIF_VERSION`).
5. **Une ou plusieurs copropriétés : un constat, jamais un réglage** (#2400). Le
   mode se déclare dans le `.env` de l'exploitant (`COPROPRIETES_FICHIER`, #1894) ;
   l'écran le lit ici (`coproprietes_servies`), par `contexte.est_commune()`, et ne
   le recalcule pas. Une déclaration invalide le dit, au lieu d'un nombre.

⚠️ Ne pas confondre avec le rôle d'un NŒUD dans la haute disponibilité (actif /
standby, `.active`) : les deux Raspberry Pi sont ENSEMBLE la référence.
🔒 `tests/test_installation.py`.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

import httpx

from app.config import get_settings
from app.utils import demo
from app.utils import horloge
from app.utils.plateforme import DEPOT_SOURCE

#: rôle → libellé. La seule écriture.
ROLES: dict[str, str] = {"reference": "Référence", "replique": "Réplique"}
INCONNU = "inconnu"

#: L'instant où ce processus a démarré : « en service depuis ». Une constante,
#: posée une fois à l'import — pas un état que le processus modifie.
DEMARREE_LE = horloge.maintenant()

#: Le dépôt public, pour l'API de GitHub (`owner/repo`).
DEPOT = DEPOT_SOURCE.removeprefix("https://github.com/")
#: L'API de GitHub pour ce dépôt — versions publiées, comparaison de commits (#2949).
API_DEPOT = f"https://api.github.com/repos/{DEPOT}"


def role_installation(valeur: Optional[str] = None) -> str:
    """PURE sur sa valeur : `reference`, `replique` ou `inconnu` (règle 2)."""
    brut = get_settings().role_installation if valeur is None else valeur
    role = (brut or "").strip().lower().replace("î", "i").replace("é", "e")
    return role if role in ROLES else INCONNU


def cible_suivie(role: str, version_a_installer: Optional[str]) -> Optional[str]:
    """PURE. Ce contre quoi la version qui tourne se mesure : `main` pour la référence,
    le tag `vX.Y.Z` de la version que le bail fait installer pour une réplique
    (`inscription/constat.version_a_installer`, #3009) ; `None` sinon — jamais une
    cible supposée."""
    #  Dans la fonction : `registre/canaux` importe ce module (son `DEPOT`).
    from app.registre.canaux import CANAL_REFERENCE

    if role == "reference":
        return CANAL_REFERENCE
    if role == "replique" and version_a_installer:
        return f"v{version_a_installer}"
    return None


def est_replique() -> bool:
    """CETTE installation se déclare-t-elle RÉPLIQUE ? Elle n'allume alors que les services
    que la référence autorise (`utils/services.autorise_par_la_reference`, §4.11)."""
    return role_installation() == "replique"


def est_reference() -> bool:
    """CETTE installation est-elle la référence ? La question que pose le registre (§4.11)."""
    return role_installation() == "reference"


@dataclass(frozen=True)
class CoproprietesServies:
    """Combien de copropriétés CETTE installation sert (règle 5)."""

    commune: bool
    #: `None` quand la déclaration ne peut pas servir : jamais un nombre supposé.
    nombre: Optional[int]
    detail: str = ""


def coproprietes_servies() -> CoproprietesServies:
    """Une seule copropriété, ou une installation commune et son nombre (règle 5)."""
    #  Imports dans la fonction : `contexte` lit la déclaration, qui charge la
    #  configuration des copropriétés — rien que ce module ait à porter à l'import.
    from app import contexte
    from app.installation_commune.declaration import DeclarationInvalide

    if not contexte.est_commune():
        return CoproprietesServies(commune=False, nombre=1)
    try:
        return CoproprietesServies(commune=True, nombre=len(contexte.coproprietes()))
    except DeclarationInvalide:
        return CoproprietesServies(
            commune=True, nombre=None, detail="déclaration des copropriétés invalide"
        )


def empreinte(valeur: Optional[str] = None) -> str:
    """Le commit qui tourne, ou `""` quand l'image a été construite sans lui (`dev`)."""
    brut = (get_settings().git_hash if valeur is None else valeur) or ""
    return "" if brut.strip() in ("", "dev") else brut.strip()


def version_logicielle() -> str:
    """Ce qui tourne, tel que le registre le lit (R2 #1878) et que `GET /config` le publie
    (#2833) : la version promue d'une réplique (`COPROFIRST_VERSION`), sinon la release de
    l'image (`VERSION_IMAGE`), sinon le commit de l'image, sinon « inconnue »."""
    reglages = get_settings()
    return (
        reglages.coprofirst_version.strip()
        or reglages.version_image.strip()
        or empreinte()[:12]
        or "inconnue"
    )


@dataclass(frozen=True)
class Verification:
    """Ce que le dépôt dit du commit qui tourne, face à ce qu'il suit."""

    etat: str  #: a_jour · en_retard · ecart · non_verifie
    retard: int = 0  #: commits de la branche absents d'ici (en_retard)
    detail: str = ""


def verdict_comparaison(statut: Optional[str], en_avance: int = 0) -> Verification:
    """PURE. `statut` est celui de `GET /repos/…/compare/{empreinte}...{cible}`.

    `ahead` : la CIBLE a des commits que l'empreinte n'a pas → en retard.
    `identical` → à jour. `behind` ou `diverged` : l'empreinte porte des commits
    absents de la cible — en avance sur elle, ou à part → écart.
    """
    if statut == "identical":
        return Verification("a_jour")
    if statut == "ahead":
        return Verification("en_retard", retard=en_avance)
    if statut in ("behind", "diverged"):
        return Verification(
            "ecart", detail="la version qui tourne n'est pas dans l'historique de ce qu'elle suit"
        )
    return Verification("non_verifie", detail="réponse du dépôt illisible")


def verifier(empreinte_courante: str, cible: str, *, client=None) -> Verification:
    """Interroge le dépôt public. Toute impossibilité rend « non vérifié » (règle 3)."""
    if demo.est_demo():
        return Verification("non_verifie", detail=demo.MESSAGE)  # rien ne sort (#1902)
    if not empreinte_courante:
        return Verification("non_verifie", detail="image construite sans son commit (GIT_HASH)")
    url = f"{API_DEPOT}/compare/{empreinte_courante}...{cible}"
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
