"""Les bases peuplées qu'éprouvent l'export et l'import d'une copropriété (#1749).

Et les archives retouchées qui éprouvent l'import : une table altérée, une table
qu'un code d'avant exportait (#3098).

Lecteurs : `test_export_copropriete.py`, `test_droit_differer_cles.py` (#3113),
`test_tables_retirees.py` (#3098).
"""

from __future__ import annotations

import io
import json
import tarfile
from collections.abc import Callable

from sqlmodel import Session

from app.models.core import ConfigSite, FaqItem, RoleUtilisateur
from tests.aides_base import compte, moteur_de_test


def base_peuplee():
    """Une base de test peuplée de quelques lignes, accents et apostrophes compris."""
    moteur = moteur_de_test()
    with Session(moteur) as s:
        compte(s, prenom="Élodie", nom="D'Aubigné", role=RoleUtilisateur.conseil_syndical)
        compte(s, prenom="Zoé", nom="Martin", actif=False)
        s.add(ConfigSite(cle="site_nom", valeur="Résidence « Les Tilleuls »"))
        s.add(ConfigSite(cle="vide", valeur=""))
        s.add(
            FaqItem(
                categorie="Vie pratique",
                question="Où sont les poubelles ?",
                reponse="Au sous-sol — porte B.",
            )
        )
        s.commit()
    return moteur


def copropriete_et_batiment(moteur, *, copropriete_id=None):
    """Une copropriété et son bâtiment : deux tables qui se citent en cycle.

    `copropriete_id` imposé : le bâtiment est écrit sans son parent (un orphelin).
    """
    from app.models.copropriete import Batiment, Copropriete

    with Session(moteur) as s:
        if copropriete_id is None:
            copro = Copropriete(nom="Résidence d'essai", adresse="1 rue de l'Essai")
            s.add(copro)
            s.commit()
            copropriete_id = copro.id
        s.add(Batiment(copropriete_id=copropriete_id, numero="A"))
        s.commit()


def reecrire_archive(
    archive,
    sortie,
    retoucher: Callable[[str, bytes], bytes],
    ajouts: dict[str, bytes] | None = None,
) -> None:
    """Recopie `archive` dans `sortie`, chaque membre passé par `retoucher(nom, octets)`."""
    with tarfile.open(archive, "r:gz") as a, tarfile.open(sortie, "w:gz") as b:
        membres = [(m.name, a.extractfile(m).read()) for m in a.getmembers()]
        for nom, donnees in membres + list((ajouts or {}).items()):
            donnees = retoucher(nom, donnees)
            info = tarfile.TarInfo(nom)
            info.size = len(donnees)
            b.addfile(info, io.BytesIO(donnees))


def alterer_archive(archive, sortie, table, remplacer: Callable[[bytes], bytes]) -> None:
    """Les lignes d'une table changées APRÈS l'export : le manifeste ne les couvre plus."""
    membre = f"tables/{table}.jsonl"
    reecrire_archive(archive, sortie, lambda nom, d: remplacer(d) if nom == membre else d)


def _jsonl(lignes: list[dict]) -> bytes:
    """Les lignes d'une table, écrites comme l'export les écrit."""
    return "".join(
        json.dumps(li, ensure_ascii=False, separators=(",", ":")) + "\n" for li in lignes
    ).encode()


def archive_d_une_autre_version(archive, sortie, table, transformer) -> None:
    """L'archive d'un modèle d'avant ou d'après : `tables/<table>.jsonl` réécrit par
    `transformer(ligne)`, et son manifeste avec — l'archive reste COHÉRENTE (#1799)."""
    from app.utils import export_copropriete as ex
    from app.utils import import_copropriete as im

    with tarfile.open(archive, "r:gz") as a:
        membre = a.extractfile(f"tables/{table}.jsonl").read()
    lignes = [transformer(li) for li in im.lignes_jsonl(membre)]
    par_nom = {t.name: t for t in ex.tables()}

    def retoucher(nom: str, donnees: bytes) -> bytes:
        if nom == f"tables/{table}.jsonl":
            return _jsonl(lignes)
        if nom == "manifeste.json":
            manifeste = json.loads(donnees)
            manifeste["tables"][table]["empreinte"] = ex.empreinte_table(par_nom[table], lignes)
            return json.dumps(manifeste, ensure_ascii=False).encode()
        return donnees

    reecrire_archive(archive, sortie, retoucher)


def ajouter_table(archive, sortie, table: str, lignes: list[dict]) -> None:
    """Une table que l'archive porte et que ce code ne déclare plus : celle d'un code
    d'avant, que le retrait du modèle n'efface pas des sauvegardes déjà faites (#3098)."""

    def retoucher(nom: str, donnees: bytes) -> bytes:
        if nom != "manifeste.json":
            return donnees
        manifeste = json.loads(donnees)
        colonnes = sorted({c for li in lignes for c in li})
        manifeste["tables"][table] = {"colonnes": colonnes, "lignes": len(lignes), "empreinte": "-"}
        return json.dumps(manifeste, ensure_ascii=False).encode()

    reecrire_archive(archive, sortie, retoucher, {f"tables/{table}.jsonl": _jsonl(lignes)})
