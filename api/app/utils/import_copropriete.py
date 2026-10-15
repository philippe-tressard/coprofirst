"""L'IMPORT vérifié d'une archive de copropriété (#1749, #1782, #1799).

Le format, l'export et la ligne de commande vivent dans `export_copropriete` ;
ce module-ci écrit une archive dans une base CIBLE et la VÉRIFIE, ou la
réimporte dans une base jetable pour dire qu'elle se restaure. Séparé de
l'export au plafond de 500 lignes : les deux moitiés ne partagent que le format
(`FORMAT`, `tables`, `empreinte_table`, `valeur_typee`, `lire`), qu'elles
lisent au même endroit.

🔒 `tests/test_export_copropriete.py`.
"""

from __future__ import annotations

import hashlib
import json
import os
import tarfile
from dataclasses import dataclass, field
from pathlib import Path

from sqlalchemy import and_, exists, func, select, text
from sqlmodel import SQLModel

from app.dialecte import differer_cles_etrangeres
from app.utils.export_copropriete import (
    FORMAT,
    empreinte_table,
    exporter,
    lire,
    tables,
    valeur_typee,
)


# ── L'import, vérifié ─────────────────────────────────────────────────────────


class ImportRefuse(Exception):
    """La base cible ne porte pas EXACTEMENT ce que l'archive annonce."""


@dataclass
class Bilan:
    tables: int = 0
    lignes: int = 0
    fichiers: int = 0
    ecarts: list[str] = field(default_factory=list)
    #: « table.colonne » que l'archive porte et que le modèle n'a plus (retirée) :
    #: écartées, jamais une erreur (#1799).
    colonnes_ecartees: list[str] = field(default_factory=list)
    #: « table.colonne » que le modèle porte et que l'archive n'a pas (ajoutée
    #: depuis) : la base leur donne leur défaut.
    colonnes_par_defaut: list[str] = field(default_factory=list)


def _verifier_contre_manifeste(table, lignes: list[dict], attendu: dict) -> None:
    """L'archive est-elle INTÈGRE ? Ses lignes contre son propre manifeste, avant toute projection.

    Comparer après coup la base relue au manifeste ne marche plus dès qu'une
    colonne a été retirée ou ajoutée au modèle : l'empreinte du manifeste couvre
    les colonnes de la version qui a exporté (#1799).
    """
    if len(lignes) != attendu["lignes"]:
        raise ImportRefuse(
            f"{table.name} : {len(lignes)} ligne(s), le manifeste en annonce {attendu['lignes']}"
        )
    if empreinte_table(table, lignes) != attendu["empreinte"]:
        raise ImportRefuse(f"{table.name} : contenu différent du manifeste (archive altérée)")


def _colonnes_communes(table, lignes: list[dict], bilan: Bilan) -> set[str]:
    """Les colonnes que l'archive ET le modèle courant portent ; les autres sont nommées au bilan."""
    du_modele = {c.name for c in table.columns}
    if not lignes:
        return du_modele
    de_l_archive = set().union(*lignes)
    bilan.colonnes_ecartees += [f"{table.name}.{c}" for c in sorted(de_l_archive - du_modele)]
    bilan.colonnes_par_defaut += [f"{table.name}.{c}" for c in sorted(du_modele - de_l_archive)]
    return de_l_archive & du_modele


def _projeter(ligne: dict, colonnes: set[str]) -> dict:
    return {k: v for k, v in ligne.items() if k in colonnes}


def _recaler_sequences(connexion, metadata=None) -> None:
    """PostgreSQL : après des identifiants écrits à la main, la séquence repart après eux."""
    if connexion.dialect.name != "postgresql":
        return
    for t in tables(metadata):
        cles = list(t.primary_key.columns)
        if (
            len(cles) == 1
            and cles[0].autoincrement in (True, "auto")
            and str(cles[0].type) == "INTEGER"
        ):
            connexion.execute(
                text(
                    f"SELECT setval(pg_get_serial_sequence('{t.name}', '{cles[0].name}'), "  # noqa: S608 — identifiants des modèles
                    f"COALESCE((SELECT MAX({cles[0].name}) FROM {t.name}), 0) + 1, false)"
                )
            )


def lignes_jsonl(octets: bytes) -> list[dict]:
    """PURE. Les enregistrements d'un `.jsonl` de l'archive — coupés sur « \\n » SEUL.

    🔴 Jamais `splitlines()` : il coupe aussi sur U+2028, U+0085, U+000B…, que
    `json.dumps(ensure_ascii=False)` laisse tels quels dans une chaîne. Un texte
    de la résidence en contenait : la répétition de la bascule des données sur
    l'archive réelle (09/10/2026) s'est arrêtée sur une ligne JSON coupée en deux.
    Le saut de ligne, lui, est toujours échappé par `json.dumps`.
    """
    return [json.loads(li) for li in octets.decode().split("\n") if li]


def lignes_sans_parent(connexion, metadata=None) -> list[str]:
    """Chaque clé étrangère dont des lignes désignent un parent absent : « table.col → parent (n) ».

    Portable — une requête par clé, sur les métadonnées des modèles —, parce que
    PostgreSQL, ses clés différées par `differer_cles_etrangeres`, ne vérifie plus
    rien de lui-même le temps de l'import. Une clé dont une colonne est NULL ne
    désigne rien : elle n'est pas orpheline.
    """
    fautes = []
    for t in tables(metadata):
        for cle in t.foreign_key_constraints:
            parent = cle.referred_table.alias()
            designe = and_(*[parent.c[e.column.name] == e.parent for e in cle.elements])
            n = connexion.execute(
                select(func.count())
                .select_from(t)
                .where(*[c.isnot(None) for c in cle.columns])
                .where(~exists(select(1).select_from(parent).where(designe)))
            ).scalar()
            if n:
                colonnes = ", ".join(c.name for c in cle.columns)
                fautes.append(f"{t.name}.{colonnes} → {cle.referred_table.name} ({n})")
    return fautes


def importer(
    archive_chemin: Path,
    moteur,
    *,
    fichiers: Path | None = None,
    metadata=None,
    cles_differees: bool = True,
) -> Bilan:
    """Écrit l'archive dans une base CIBLE au schéma posé et vide, puis la VÉRIFIE.

    Tout écart lève `ImportRefuse`, et la transaction est annulée : la base cible
    reste vide plutôt que fausse. `metadata` : comme `export_copropriete.tables`.

    `cles_differees=False` : les clés se vérifient ligne à ligne, dans l'ordre des
    tables (parents d'abord) — pour des tables SANS cycle, sous un rôle qui n'est
    pas superutilisateur : celui du registre (#1972), à qui PostgreSQL refuserait
    `differer_cles_etrangeres`.
    """
    with tarfile.open(archive_chemin, "r:gz") as archive:
        manifeste = json.loads(archive.extractfile("manifeste.json").read())
        if manifeste.get("format") != FORMAT:
            raise ImportRefuse(f"format {manifeste.get('format')} inconnu (attendu {FORMAT})")
        par_nom = {t.name: t for t in tables(metadata)}
        inconnues = sorted(set(manifeste["tables"]) - set(par_nom))
        if inconnues:
            raise ImportRefuse(f"tables absentes des modèles de ce code : {inconnues}")
        bilan = Bilan()
        with moteur.connect() as connexion, connexion.begin():
            #  Huit tables se citent en cycle (copropriété, bâtiment, lot…) : aucun
            #  ordre d'écriture ne satisfait leurs clés ligne à ligne. Elles se
            #  vérifient donc À LA FIN, par le relevé ci-dessous (DI-7c, 09/10/2026).
            if cles_differees:
                differer_cles_etrangeres(connexion)
            ecrites: dict[str, tuple[list[dict], set[str]]] = {}
            for t in tables(metadata):
                if t.name not in manifeste["tables"]:
                    continue
                lignes = lignes_jsonl(archive.extractfile(f"tables/{t.name}.jsonl").read())
                _verifier_contre_manifeste(t, lignes, manifeste["tables"][t.name])
                communes = _colonnes_communes(t, lignes, bilan)
                if lignes:
                    colonnes = {c.name: c for c in t.columns}
                    connexion.execute(
                        t.insert(),
                        [
                            {
                                k: valeur_typee(colonnes[k], v)
                                for k, v in li.items()
                                if k in communes
                            }
                            for li in lignes
                        ],
                    )
                ecrites[t.name] = (lignes, communes)
                bilan.tables += 1
                bilan.lignes += len(lignes)
            _recaler_sequences(connexion, metadata)
            orphelines = lignes_sans_parent(connexion, metadata)
            if orphelines:
                raise ImportRefuse("clés sans parent : " + "; ".join(orphelines))
            relu, _ignorees, _rev = lire(connexion, metadata)
            #  La base relue se compare à l'archive PROJETÉE sur les colonnes que
            #  les deux portent : une colonne retirée du modèle n'a pas été écrite,
            #  une colonne ajoutée a reçu son défaut — ni l'une ni l'autre n'est un écart.
            for nom, (lignes, communes) in ecrites.items():
                obtenu = [_projeter(li, communes) for li in relu.get(nom, [])]
                attendu = [_projeter(li, communes) for li in lignes]
                if len(obtenu) != len(attendu):
                    bilan.ecarts.append(
                        f"{nom} : {len(obtenu)} ligne(s), l'archive en annonce {len(attendu)}"
                    )
                elif empreinte_table(par_nom[nom], obtenu) != empreinte_table(
                    par_nom[nom], attendu
                ):
                    bilan.ecarts.append(f"{nom} : contenu différent de l'archive (empreinte)")
            if bilan.ecarts:
                raise ImportRefuse("; ".join(bilan.ecarts))
        if fichiers is not None:
            for f in manifeste.get("fichiers", []):
                donnees = archive.extractfile(f"fichiers/{f['chemin']}").read()
                if hashlib.sha256(donnees).hexdigest() != f["sha256"]:
                    raise ImportRefuse(f"fichier {f['chemin']} altéré dans l'archive")
                cible = fichiers / f["chemin"]
                cible.parent.mkdir(parents=True, exist_ok=True)
                cible.write_bytes(donnees)
                bilan.fichiers += 1
    return bilan


def resume(bilan: Bilan) -> list[str]:
    """Ce que dit une ligne de commande après un import réussi — la même pour toutes (#1972)."""
    lignes = [
        f"Importé et vérifié : {bilan.tables} tables, {bilan.lignes} lignes, "
        f"{bilan.fichiers} fichiers."
    ]
    if bilan.colonnes_ecartees:
        lignes.append(
            f"Colonnes retirées du modèle, écartées : {', '.join(bilan.colonnes_ecartees)}."
        )
    if bilan.colonnes_par_defaut:
        lignes.append(
            "Colonnes absentes de l'archive, à leur défaut : "
            f"{', '.join(bilan.colonnes_par_defaut)}."
        )
    return lignes


def verifier_archive(archive: Path, url_hote, metadata=None) -> Bilan:
    """Réimporte une archive dans une base NEUVE et jetable du serveur `url_hote`, puis la retire.

    La base jetable est un schéma neuf du même serveur (`dialecte.base_jetable`),
    jamais la base qui sert. Une archive qui ne se restaure pas lève `ImportRefuse`.
    """
    from app.dialecte import base_jetable

    with base_jetable(url_hote) as moteur_cible:
        (metadata or SQLModel.metadata).create_all(moteur_cible)
        return importer(archive, moteur_cible, metadata=metadata)


def verifier_restauration(moteur_source, dossier: Path) -> tuple[dict, Bilan]:
    """Exporte la base (sans fichiers) puis la réimporte dans une base neuve et jetable.

    Rend le manifeste et le bilan. Une base qui ne se restaure pas lève
    `ImportRefuse` : c'est précisément ce que ce geste doit dire.
    """
    archive = dossier / "verification.tar.gz"
    try:
        manifeste = exporter(moteur_source, archive)
        bilan = verifier_archive(archive, moteur_source.url)
    finally:
        if archive.exists():
            os.remove(archive)
    return manifeste, bilan
