"""Préparer CHAQUE base de l'installation avant de servir — lu par `start.sh` (#2053).

## Pourquoi

`start.sh` attendait, migrait et posait le schéma initial de `DATABASE_URL`, et de
lui seul. Une installation COMMUNE (#1894) sert une base par copropriété (spec
§4.3) : les autres restaient au schéma de leur création, et la première requête
qui touchait une colonne neuve tombait en 500.

## Ce que fait `preparer_base` — la décision, écrite une fois

| La base…                                  | Verdict      | Geste                                   |
|-------------------------------------------|--------------|-----------------------------------------|
| ne répond pas dans le délai               | `illisible`  | rien : on ne migre jamais ce qu'on n'a pas lu |
| est EN AVANCE sur ce code (retour arrière, #1756) | `en_avance` | rien, et on le dit — les migrations sont compatibles (#1757) |
| est neuve (aucune table)                  | `posee`      | schéma courant d'un coup, marqué à la tête (`utils/schema_initial`), puis la chaîne |
| a déjà ses tables                         | `migree`     | `alembic upgrade head`                  |
| ne se lit pas au moment du schéma         | `illisible`  | rien — une base peut-être vide ne se marque pas |

C'était la logique de `start.sh`, en shell ; elle n'a pas changé, elle vit ici
pour servir deux appelants sans être écrite deux fois.

## Les deux installations

- **propre à une copropriété** (5Hostachy) : `DATABASE_URL`, comme avant. Une base
  illisible rend 1, et `start.sh` (`set -e`) s'arrête — Docker relance ;
- **commune** : chaque base déclarée, l'une après l'autre. Une base illisible ou
  en échec **ne bloque pas les autres**, et sa ligne le dit ; l'API la refuse
  ensuite (`installation_commune/bases_pretes`, 503 pour son seul hôte). Rend 1
  seulement si AUCUNE n'est prête.

Ne journalise ni URL ni secret : une ligne nomme la copropriété par son identifiant.
🔒 `tests/test_preparer_bases.py`.
"""

from __future__ import annotations

import sys

from alembic import command

from app.utils.attendre_base import DELAI_SECONDES, attendre
from app.utils.revision_base import config_alembic, etat_revision
from app.utils.schema_initial import poser_si_neuve

#: Après la première base, le serveur répond déjà : les suivantes n'attendent pas
#: 90 s chacune — une installation de vingt copropriétés démarrerait en une demi-heure.
DELAI_SUIVANTES = 10

#: Les verdicts qui laissent la base servable.
PRETES = frozenset({"posee", "migree", "en_avance"})


def _migrer(url: str) -> None:
    """`alembic upgrade head` sur CETTE base — la connexion transmise l'emporte sur
    `DATABASE_URL` (`alembic/env.py`)."""
    from sqlalchemy import create_engine

    config = config_alembic()
    moteur = create_engine(url)
    try:
        with moteur.begin() as connexion:
            config.attributes["connection"] = connexion
            command.upgrade(config, "head")
    finally:
        moteur.dispose()


def preparer_base(url: str, delai: float = DELAI_SECONDES) -> str:
    """`posee` | `migree` | `en_avance` | `illisible` — voir la table du module.

    Une migration qui lève remonte : l'appelant décide (arrêt pour l'installation
    propre, isolement pour la commune).
    """
    if not attendre(url, delai=delai):
        return "illisible"
    if etat_revision(url) == "en_avance":
        return "en_avance"
    schema = poser_si_neuve(url)
    if schema == "inconnu":
        return "illisible"
    _migrer(url)
    return "posee" if schema == "posee" else "migree"


def preparer_commune(coproprietes, ecrire=print) -> int:
    """Chaque copropriété, isolée des autres. Rend le code de sortie de `start.sh`."""
    pretes = 0
    for rang, copro in enumerate(coproprietes):
        try:
            verdict = preparer_base(
                copro.url_base, DELAI_SECONDES if rang == 0 else DELAI_SUIVANTES
            )
        except Exception as exc:  # noqa: BLE001 — l'échec d'une base n'arrête pas les autres
            #  Le type seul : le message d'un pilote peut citer l'URL, donc le mot de passe.
            verdict = f"echec ({type(exc).__name__})"
        pretes += verdict in PRETES
        ecrire(f"copropriete {copro.identifiant} : {verdict}")
    ecrire(f"{pretes} base(s) prete(s) sur {len(coproprietes)}")
    return 0 if pretes else 1


def main() -> int:
    from app import contexte
    from app.installation_commune.declaration import DeclarationInvalide

    if not contexte.est_commune():
        verdict = preparer_base(contexte.de_la_configuration().url_base, DELAI_SECONDES)
        print(f"base : {verdict}")
        return 0 if verdict in PRETES else 1
    try:
        coproprietes = contexte.coproprietes()
    except DeclarationInvalide:
        #  Rien à préparer : l'API servira 503 à tous les hôtes, et le dira
        #  (`ResolutionCopropriete`). Elle démarre quand même, pour le dire.
        print(
            "declaration invalide : aucune base preparee (verifier : installation_commune.verifier)"
        )
        return 0
    return preparer_commune(coproprietes)


if __name__ == "__main__":
    sys.exit(main())
