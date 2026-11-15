"""Les constantes de l'API que les apps natives GÉNÈRENT, publiées avec la release (#2686).

## Pourquoi

Une note, un plafond, un défaut que l'écran doit connaître AVANT tout appel ne se
sert pas en champ : l'app le compile. Les apps les lisaient dans les SOURCES de l'API
(l'iOS par motif dans `api/app/utils/*.py`, l'Android en constantes recopiées) : un
remaniement d'un de ces modules cassait leur montée sans que la CI du serveur le dise.

Ce module en tient le registre et produit `api/app/contrat/constantes-clients.json`,
joint à la release à côté d'`openapi.json` et de `front/tables-clients.json`
(`scripts/ci/lib-contrat-version.sh`). C'est le pendant, côté API, de
`front/scripts/tables-clients.mjs` : front et API ne partagent aucun fichier (#335),
chaque côté publie le sien.

Chaque valeur est LUE dans son module — jamais recopiée ici.

- `python scripts/ci/exporter_openapi.py --ecrire-constantes` : écrit la référence
  (les modules lus importent les réglages, que l'exporteur pose sans base). Un retrait ou un changement de type non annoncé dans
  `RETRAITS_CONSTANTES` est refusé, et rien n'est écrit.
- 🔒 `tests/test_constantes_clients.py` : la référence est celle que le code produit,
  et chaque refus sur son cas.
"""

from __future__ import annotations

import importlib
import json
from dataclasses import dataclass
from pathlib import Path

REFERENCE = Path(__file__).with_name("constantes-clients.json")
ECRIRE = "python scripts/ci/exporter_openapi.py --ecrire-constantes"
FORMAT = 1


@dataclass(frozen=True)
class Constante:
    module: str  #: `app.utils.<module>`
    nom: str  #: la constante du module, lue telle quelle
    quoi: str  #: ce qu'elle dit, en une ligne


#: Clé : le nom PUBLIÉ (stable : c'est lui que les apps lisent).
CONSTANTES: dict[str, Constante] = {
    "schemasDeLien": Constante(
        "app.utils.html_sur",
        "SCHEMAS_URL",
        "les schémas qu'un lien du texte riche peut porter (le relatif en plus) (#2757)",
    ),
    "defautsPreferences": Constante(
        "app.utils.preferences_mail",
        "DEFAUTS",
        "la valeur d'une préférence de notification jamais réglée, par clé (#2755)",
    ),
    "longueurMinMotDePasse": Constante(
        "app.utils.mots_de_passe",
        "LONGUEUR_MIN_MOT_DE_PASSE",
        "le nombre de caractères qu'un mot de passe doit atteindre (#2755)",
    ),
    "noteMin": Constante("app.utils.avis", "NOTE_MIN", "la note la plus basse d'un avis"),
    "noteMax": Constante("app.utils.avis", "NOTE_MAX", "la note la plus haute d'un avis"),
    "noteRemarque": Constante(
        "app.utils.avis", "NOTE_REMARQUE", "sous cette note, l'avis dit ce qui a manqué"
    ),
    "notePubliable": Constante(
        "app.utils.avis",
        "NOTE_PUBLIABLE",
        "à partir de cette note, l'auteur dit s'il accepte que l'avis paraisse",
    ),
}

#: Une constante retirée, ou dont le type change, s'ANNONCE ici : nom → (ticket, raison).
#: Une annonce qui ne sert plus (la constante est toujours publiée sous ce type) échoue.
RETRAITS_CONSTANTES: dict[str, tuple[str, str]] = {}


def en_json(valeur):
    """Un ensemble devient une liste TRIÉE (l'ordre d'un `frozenset` n'en est pas un)."""
    if isinstance(valeur, (set, frozenset)):
        return sorted(valeur)
    if isinstance(valeur, dict):
        return {k: en_json(v) for k, v in valeur.items()}
    if isinstance(valeur, (list, tuple)):
        return [en_json(v) for v in valeur]
    if isinstance(valeur, (str, int, float, bool)) or valeur is None:
        return valeur
    raise TypeError(f"{type(valeur).__name__} ne se publie pas")


def lire(constantes: dict[str, Constante] = CONSTANTES) -> dict:
    """Chaque constante, lue dans son module. Une constante absente lève en la nommant."""
    sortie = {}
    for nom in sorted(constantes):
        c = constantes[nom]
        module = importlib.import_module(c.module)
        if not hasattr(module, c.nom):
            raise LookupError(f"{nom} : {c.module}.{c.nom} n'existe plus")
        sortie[nom] = {
            "source": f"api/{c.module.replace('.', '/')}.py#{c.nom}",
            "quoi": c.quoi,
            "valeur": en_json(getattr(module, c.nom)),
        }
    return sortie


def type_de(valeur) -> str:
    """La FORME d'une valeur publiée : son type, et celui des valeurs d'un objet."""
    if isinstance(valeur, dict):
        return "objet{" + ",".join(f"{k}:{type_de(v)}" for k, v in sorted(valeur.items())) + "}"
    if isinstance(valeur, list):
        return "liste"
    return type(valeur).__name__


def refus(ancien: dict, nouveau: dict, annonces: dict = RETRAITS_CONSTANTES) -> list[str]:
    """Les retraits et changements de forme NON annoncés, et les annonces qui ne servent plus."""
    ecarts = {
        nom
        for nom, t in ancien.items()
        if nom not in nouveau or type_de(t["valeur"]) != type_de(nouveau[nom]["valeur"])
    }
    messages = [
        f"{n} : retirée ou de forme changée, sans annonce" for n in sorted(ecarts - set(annonces))
    ]
    messages += [f"{n} : annoncée, mais rien n'est retiré" for n in sorted(set(annonces) - ecarts)]
    return messages


def version_suivante(version: str, ancien: dict, nouveau: dict) -> str:
    """Majeure sur un retrait (annoncé), mineure sur tout autre écart, sinon la même."""
    majeure, mineure, _ = (int(x) for x in version.split("."))
    if any(
        n not in nouveau or type_de(t["valeur"]) != type_de(nouveau[n]["valeur"])
        for n, t in ancien.items()
    ):
        return f"{majeure + 1}.0.0"
    if ancien != nouveau:
        return f"{majeure}.{mineure + 1}.0"
    return version


def texte(version: str, constantes: dict) -> str:
    return (
        json.dumps(
            {"format": FORMAT, "version": version, "constantes": constantes},
            ensure_ascii=False,
            indent=2,
        )
        + "\n"
    )


def juger(ecrire: bool = False) -> list[str]:
    """Le contrôle et l'écriture : rend les messages d'échec (vide = conforme)."""
    lue = json.loads(REFERENCE.read_text(encoding="utf-8")) if REFERENCE.exists() else None
    if lue is None and not ecrire:
        return [f"{REFERENCE.name} absente : {ECRIRE}"]
    ancien = (lue or {}).get("constantes", {})
    courant = lire()
    messages = refus(ancien, courant)
    if messages:
        return messages
    version = version_suivante(lue["version"], ancien, courant) if lue else "1.0.0"
    attendu = texte(version, courant)
    if ecrire:
        REFERENCE.write_text(attendu, encoding="utf-8")
        return []
    if REFERENCE.read_text(encoding="utf-8") != attendu:
        return [f"{REFERENCE.name} n'est pas ce que le code produit : {ECRIRE}"]
    return []
