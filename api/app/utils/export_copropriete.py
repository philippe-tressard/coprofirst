"""Exporter et réimporter une copropriété, dans un format NEUTRE et VÉRIFIÉ (#1749).

Lot P2-7 du chantier multi-copropriétés (`specs/architecture/multi-coproprietes.md`
§4.3 et §4.9). Un même outil, trois usages :

- **aujourd'hui** : prouver qu'une base se RESTAURE, au lieu de le supposer
  (`verifier_restauration`, bouton d'Administration › Maintenance) ;
- **demain** : faire changer la résidence de moteur de base, vers PostgreSQL
  (DI-7, #1759) — le format ne doit rien au moteur d'origine ;
- **ensuite** : rendre ses données à une copropriété qui part (réversibilité).

## Le format

Une archive `.tar.gz` :

| Chemin | Contenu |
|---|---|
| `manifeste.json` | version du format, révision Alembic, date, et pour CHAQUE table : colonnes, nombre de lignes, empreinte SHA-256 |
| `tables/<table>.jsonl` | une ligne JSON par enregistrement, valeurs neutres (`valeur_neutre`) |
| `fichiers/…` | les fichiers téléversés, avec leur empreinte dans le manifeste (si demandés) |

L'empreinte d'une table se calcule sur ses lignes NEUTRES, triées par clé
primaire : elle ne dépend ni du moteur, ni de l'ordre de lecture. C'est elle qui
rend l'import VÉRIFIÉ — après l'écriture, il relit la base cible, recalcule
chaque empreinte et REFUSE un écart (la transaction est annulée).

## Ce que l'outil ne fait pas, et le dit

- Une table présente en base mais absente des modèles (une table historique)
  n'est pas exportée : elle est NOMMÉE dans le manifeste (`ignorees`).
- 🔴 Règle d'or : l'export lit la base de l'APPLICATION dans le processus de
  l'API (l'endpoint), en une seule transaction de lecture — jamais depuis un
  processus tiers tant que l'API tourne (CLAUDE.md). L'import écrit dans une
  base CIBLE, jamais dans celle qui sert.

L'import vérifié vit dans `import_copropriete` (le même format, l'autre sens).

🔒 `tests/test_export_copropriete.py`.
"""

from __future__ import annotations

import base64
import hashlib
import io
import json
import os
import tarfile
from datetime import date, datetime, time
from decimal import Decimal
from enum import Enum
from pathlib import Path
from uuid import UUID

from sqlalchemy import (
    Date,
    DateTime,
    LargeBinary,
    Numeric,
    Time,
    inspect,
    select,
    text,
)
from sqlmodel import SQLModel

from app.utils import horloge
import app.models.core  # noqa: F401 — enregistre TOUTES les tables (#1157)

FORMAT = 1


# ── Les valeurs neutres (PURES) ───────────────────────────────────────────────


def valeur_neutre(v):
    """Une valeur de base en JSON sans perte, identique quel que soit le moteur.

    Un type inconnu LÈVE : une valeur rendue au hasard ferait une empreinte fausse,
    et un export « réussi » qui ne se réimporte pas à l'identique.
    """
    if v is None or isinstance(v, (bool, int, str, float)):
        return v
    if isinstance(v, Enum):
        return v.name
    if isinstance(v, datetime):
        return v.isoformat()
    if isinstance(v, (date, time)):
        return v.isoformat()
    if isinstance(v, Decimal):
        return str(v)
    if isinstance(v, UUID):
        return str(v)
    if isinstance(v, (bytes, bytearray, memoryview)):
        return {"$b64": base64.b64encode(bytes(v)).decode("ascii")}
    if isinstance(v, (dict, list)):
        return v
    raise TypeError(f"valeur de type {type(v).__name__} sans forme neutre déclarée")


def valeur_typee(colonne, v):
    """L'inverse de `valeur_neutre`, guidé par le TYPE de la colonne cible."""
    if v is None:
        return None
    if isinstance(v, dict) and set(v) == {"$b64"}:
        return base64.b64decode(v["$b64"])
    t = colonne.type
    if isinstance(t, DateTime):
        return datetime.fromisoformat(v)
    if isinstance(t, Date):
        return date.fromisoformat(v)
    if isinstance(t, Time):
        return time.fromisoformat(v)
    if isinstance(t, Numeric) and isinstance(v, str):
        return Decimal(v)
    if isinstance(t, LargeBinary) and isinstance(v, str):
        return base64.b64decode(v)
    return v


def ligne_neutre(ligne) -> dict:
    return {nom: valeur_neutre(v) for nom, v in ligne.items()}


def _cle_de_tri(table, ligne: dict):
    cles = [c.name for c in table.primary_key.columns] or sorted(ligne)
    return tuple((ligne[c] is None, str(ligne[c])) for c in cles)


def empreinte_table(table, lignes: list[dict]) -> str:
    """PURE. SHA-256 des lignes neutres triées par clé primaire, colonnes triées."""
    h = hashlib.sha256()
    for ligne in sorted(lignes, key=lambda li: _cle_de_tri(table, li)):
        h.update(
            json.dumps(ligne, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode()
        )
        h.update(b"\n")
    return h.hexdigest()


# ── La lecture d'une base ─────────────────────────────────────────────────────


def tables(metadata=None) -> list:
    """Les tables des modèles, dans l'ordre des clés étrangères (parents d'abord).

    `metadata` : celles d'une copropriété par défaut ; la base `plateforme` passe
    les siennes (`registre_plateforme.metadata`, #1892) — même format, même
    vérification, autre jeu de tables.
    """
    return list((metadata or SQLModel.metadata).sorted_tables)


def lire(connexion, metadata=None) -> tuple[dict[str, list[dict]], list[str], str | None]:
    """Toutes les tables (lignes neutres), les tables ignorées, la révision Alembic."""
    presentes = set(inspect(connexion).get_table_names())
    contenu = {
        t.name: [ligne_neutre(li) for li in connexion.execute(select(t)).mappings()]
        for t in tables(metadata)
        if t.name in presentes
    }
    connues = {t.name for t in tables(metadata)} | {"alembic_version"}
    ignorees = sorted(presentes - connues)
    revision = None
    if "alembic_version" in presentes:
        revision = connexion.execute(text("SELECT version_num FROM alembic_version")).scalar()
    return contenu, ignorees, revision


def manifeste_de(
    contenu: dict[str, list[dict]], ignorees: list[str], revision, metadata=None
) -> dict:
    par_nom = {t.name: t for t in tables(metadata)}
    return {
        "format": FORMAT,
        "revision": revision,
        "cree_le": horloge.maintenant().isoformat(timespec="seconds"),  # UTC
        "ignorees": ignorees,
        "tables": {
            nom: {
                "colonnes": sorted(c.name for c in par_nom[nom].columns),
                "lignes": len(lignes),
                "empreinte": empreinte_table(par_nom[nom], lignes),
            }
            for nom, lignes in contenu.items()
        },
    }


# ── L'export ──────────────────────────────────────────────────────────────────


def _ajouter(archive: tarfile.TarFile, chemin: str, donnees: bytes) -> None:
    info = tarfile.TarInfo(chemin)
    info.size = len(donnees)
    archive.addfile(info, io.BytesIO(donnees))


def exporter(moteur, sortie: Path, *, fichiers: Path | None = None, metadata=None) -> dict:
    """Écrit l'archive ; rend son manifeste. Une seule transaction de lecture."""
    with moteur.connect() as connexion, connexion.begin():
        contenu, ignorees, revision = lire(connexion, metadata)
    manifeste = manifeste_de(contenu, ignorees, revision, metadata)
    inventaire = []
    with tarfile.open(sortie, "w:gz") as archive:
        for nom, lignes in contenu.items():
            corps = "".join(
                json.dumps(li, ensure_ascii=False, separators=(",", ":")) + "\n" for li in lignes
            )
            _ajouter(archive, f"tables/{nom}.jsonl", corps.encode())
        if fichiers is not None and fichiers.is_dir():
            for chemin in sorted(p for p in fichiers.rglob("*") if p.is_file()):
                rel = chemin.relative_to(fichiers).as_posix()
                donnees = chemin.read_bytes()
                inventaire.append(
                    {
                        "chemin": rel,
                        "octets": len(donnees),
                        "sha256": hashlib.sha256(donnees).hexdigest(),
                    }
                )
                _ajouter(archive, f"fichiers/{rel}", donnees)
        manifeste["fichiers"] = inventaire
        _ajouter(
            archive, "manifeste.json", json.dumps(manifeste, ensure_ascii=False, indent=1).encode()
        )
    return manifeste


# ── En ligne de commande : l'IMPORT dans une base cible (DI-7) ────────────────
#
#     python -m app.utils.export_copropriete importer <archive> <url-cible> [<dossier-fichiers>]
#
#  Pour le passage à PostgreSQL (DI-7, #1759) : la cible est une base NEUVE, au
#  schéma posé. 🔴 Jamais la base qui sert : l'export, lui, ne se lance que par
#  l'administration, dans le processus de l'API (règle d'or).
def adresse(argument: str) -> str:
    """L'URL d'une base, en clair ou lue dans l'environnement (`env:NOM`).

    `env:` garde le mot de passe d'une base serveur hors de la ligne de commande —
    donc hors de `ps` et des journaux (DI-7c, `scripts/exploitation/basculer-donnees.sh`).
    """
    if argument.startswith("env:"):
        nom = argument.removeprefix("env:")
        valeur = os.environ.get(nom, "")
        if not valeur:
            raise SystemExit(f"variable d'environnement {nom} absente ou vide")
        return valeur
    return argument


_USAGE = (
    "usage : python -m app.utils.export_copropriete exporter <url-source> <archive>\n"
    "        python -m app.utils.export_copropriete importer <archive> <url-cible> [<fichiers>]\n"
    "        python -m app.utils.export_copropriete verifier <archive>\n"
    "        (une URL peut s'écrire env:NOM — lue dans l'environnement)"
)

if __name__ == "__main__":
    import sys

    from app.utils.import_copropriete import ImportRefuse, importer, resume, verifier_archive

    from sqlmodel import create_engine

    _ARITE = {"exporter": 4, "importer": 4, "verifier": 3}
    if len(sys.argv) < _ARITE.get(sys.argv[1] if len(sys.argv) > 1 else "", 99):
        sys.exit(_USAGE)
    if sys.argv[1] == "verifier":
        #  La sauvegarde d'une réplique, avant sa mise à jour (DI-4) : réimportée
        #  dans une base jetable, à côté, jamais dans la base qui sert.
        import tempfile

        try:
            with tempfile.TemporaryDirectory() as _dossier:
                _bilan = verifier_archive(Path(sys.argv[2]), Path(_dossier))
        except ImportRefuse as _refus:
            sys.exit(f"ARCHIVE REFUSÉE : {_refus}")
        print(f"Archive vérifiée : {_bilan.tables} tables, {_bilan.lignes} lignes.")
        sys.exit(0)
    if sys.argv[1] == "exporter":
        #  🔴 La base SOURCE doit être au repos : l'appelant arrête l'API avant
        #  (règle d'or, CLAUDE.md). Cette commande lit, elle ne fige rien.
        _source = create_engine(adresse(sys.argv[2]))
        _manifeste = exporter(_source, Path(sys.argv[3]))
        _source.dispose()
        _lignes = sum(t["lignes"] for t in _manifeste["tables"].values())
        print(
            f"Exporté : {len(_manifeste['tables'])} tables, {_lignes} lignes, révision "
            f"{_manifeste['revision']} ; non exportées : {_manifeste['ignorees'] or 'aucune'}."
        )
        sys.exit(0)
    _cible = create_engine(adresse(sys.argv[3]))
    SQLModel.metadata.create_all(_cible)
    try:
        _bilan = importer(
            Path(sys.argv[2]), _cible, fichiers=Path(sys.argv[4]) if len(sys.argv) > 4 else None
        )
    except ImportRefuse as _refus:
        sys.exit(f"IMPORT REFUSÉ : {_refus}")
    print("\n".join(resume(_bilan)))
