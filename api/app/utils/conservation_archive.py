"""L'ARCHIVE des pièces jointes d'affaires échues (#2014, lot L2).

Spécification : `specs/architecture/conservation-affaires.md` §5. Une archive par
copropriété, par exercice et par type — `affaires-<copropriété>-<exercice>-<type>.zip` —
qui contient :

- les pièces jointes, rangées par affaire (`TK-123/photo.jpg`) ;
- un SOMMAIRE en HTML (lisible sans outil) et en CSV (pour un tableur) : numéro,
  titre, catégorie, dates, lieu, équipement, prestataire, contrat, et chaque fichier
  avec son empreinte ;
- 🔴 **aucun nom d'auteur** : une archive qui garderait les noms prolongerait la
  conservation au sens du RGPD (§2). Les photos peuvent encore montrer des
  personnes : c'est écrit dans la politique, pas caché.

## Écrite, puis RELUE

`ecrire_archive` ne rend une archive qu'après l'avoir relue DANS le stockage :
chaque fichier y figure, avec l'empreinte du fichier d'origine. Sinon elle lève
`ArchiveInvalide`, et l'appelant ne retire rien — une archive tronquée n'efface
jamais un fichier (§4, étape 1).

Le fichier vit sous `prive/archives-affaires/` : répliqué par la bascule (le
volume des fichiers), jamais servi par Caddy (`/uploads/prive/*` répond 404).
"""

from __future__ import annotations

import csv
import hashlib
import io
import re
import tempfile
import unicodedata
import zipfile
from dataclasses import dataclass
from html import escape
from pathlib import Path
from typing import Optional

from sqlmodel import Session, col, select

from app import contexte
from app.models.conservation import ArchiveAffaires
from app.models.prestataires import Prestataire
from app.utils.categories_ticket import libelle_categorie
from app.utils.conservation_affaires import Contenu, Echeance
from app.utils.dates_fr import date_courte
from app.utils.equipements import libelle_equipement
from app.utils.perimetres import parse_json_perimetres, perimetre_label
from app.utils.stockage import DOSSIER_PRIVE, stockage

#: Le dossier des archives dans le stockage de la copropriété — privé, jamais servi.
DOSSIER = f"{DOSSIER_PRIVE}/archives-affaires"

#: Le nom d'une archive : la même liste blanche que le poste applique avant de la
#: tirer (`scripts/lib/lib-export-hors-site.sh`, `nom_archive_affaires_valide`).
MOTIF_NOM = re.compile(r"^affaires-[a-z0-9]+(?:-[a-z0-9]+)*\.zip$")

#: Les colonnes du sommaire — les mêmes, dans le même ordre, en HTML et en CSV.
COLONNES = (
    "Numéro",
    "Titre",
    "Catégorie",
    "Ouverte le",
    "Close le",
    "Lieu",
    "Équipement",
    "Prestataire",
    "Contrat",
    "Fichiers",
)


class ArchiveInvalide(Exception):
    """L'archive relue ne porte pas ce qu'on y a mis : rien ne doit être retiré."""


@dataclass(frozen=True)
class Piece:
    """Un fichier d'affaire tel qu'il entre dans l'archive."""

    chemin: Path
    #: son chemin DANS l'archive : `TK-123/nom.ext`
    nom: str
    empreinte: str
    octets: int


def empreinte_de(chemin: Path) -> str:
    """Le SHA-256 d'un fichier, lu par morceaux."""
    h = hashlib.sha256()
    with chemin.open("rb") as flux:
        for morceau in iter(lambda: flux.read(1 << 20), b""):
            h.update(morceau)
    return h.hexdigest()


def _segment(texte: str) -> str:
    """Une portion de nom de fichier : minuscules, sans accent, chiffres et tirets."""
    sans_accent = unicodedata.normalize("NFKD", texte).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", "-", sans_accent.lower()).strip("-") or "x"


def nom_archive(session: Session, groupe: Echeance) -> str:
    """`affaires-<copropriété>-<exercice>-<type>.zip`, suffixé d'un rang s'il est pris.

    Un même exercice et un même type peuvent revenir : une affaire rouverte puis
    close de nouveau à une date passée. Le nom ne se réutilise jamais — la copie
    du PC porte le même.
    """
    base = "-".join(
        _segment(s) for s in ("affaires", contexte.courante().identifiant, groupe.exercice_cloture)
    )
    base = f"{base}-{groupe.type.code}"
    pris = set(
        session.exec(
            select(ArchiveAffaires.nom).where(col(ArchiveAffaires.nom).startswith(base))
        ).all()
    )
    nom, rang = f"{base}.zip", 2
    while nom in pris:
        nom, rang = f"{base}-{rang}.zip", rang + 1
    return nom


def pieces_de(contenu: Contenu) -> list[Piece]:
    """Les fichiers PRÉSENTS d'une affaire, nommés sans collision dans son dossier."""
    pieces: list[Piece] = []
    vus: set[str] = set()
    for chemin in contenu.fichiers():
        if chemin is None or not chemin.is_file():
            continue
        nom = f"{contenu.ticket.numero}/{chemin.name}"
        rang = 2
        while nom in vus:
            nom = f"{contenu.ticket.numero}/{rang}-{chemin.name}"
            rang += 1
        vus.add(nom)
        pieces.append(Piece(chemin, nom, empreinte_de(chemin), chemin.stat().st_size))
    return pieces


def _prestataire(session: Session, prestataire_id: Optional[int]) -> str:
    p = session.get(Prestataire, prestataire_id) if prestataire_id else None
    return p.nom if p else ""


def _ligne(session: Session, contenu: Contenu, pieces: list[Piece]) -> list[str]:
    """Une affaire, en cellules — jamais un nom de personne."""
    t = contenu.ticket
    return [
        t.numero,
        t.titre,
        libelle_categorie(t.categorie),
        date_courte(t.cree_le),
        date_courte(contenu.cloture),
        perimetre_label(parse_json_perimetres(t.perimetre_cible)),
        libelle_equipement(session, t.equipement),
        _prestataire(session, t.prestataire_id),
        f"n° {t.contrat_id}" if t.contrat_id else "",
        " · ".join(f"{p.nom} ({p.empreinte[:12]}…)" for p in pieces),
    ]


def sommaire_csv(lignes: list[list[str]], pieces: list[Piece]) -> str:
    """Le sommaire pour un tableur : une ligne par affaire, puis une par fichier."""
    sortie = io.StringIO()
    ecrivain = csv.writer(sortie, delimiter=";")
    ecrivain.writerow(COLONNES)
    ecrivain.writerows(lignes)
    ecrivain.writerow([])
    ecrivain.writerow(["Fichier", "Octets", "SHA-256"])
    ecrivain.writerows([p.nom, p.octets, p.empreinte] for p in pieces)
    return sortie.getvalue()


def sommaire_html(groupe: Echeance, lignes: list[list[str]], pieces: list[Piece]) -> str:
    """Le sommaire lisible sans outil : un tableau des affaires, puis des fichiers."""
    entete = "".join(f"<th>{escape(c)}</th>" for c in COLONNES)
    corps = "".join(
        "<tr>" + "".join(f"<td>{escape(c)}</td>" for c in ligne) + "</tr>" for ligne in lignes
    )
    fichiers = "".join(
        f"<tr><td>{escape(p.nom)}</td><td>{p.octets}</td><td><code>{p.empreinte}</code></td></tr>"
        for p in pieces
    )
    titre = escape(f"{groupe.type.libelle} — exercice {groupe.exercice_cloture}")
    return (
        '<!doctype html><html lang="fr"><head><meta charset="utf-8">'
        f"<title>{titre}</title><style>body{{font-family:sans-serif}}"
        "table{border-collapse:collapse}td,th{border:1px solid #999;padding:4px;"
        "vertical-align:top}</style></head><body>"
        f"<h1>{titre}</h1>"
        f"<p>Affaires closes pendant l'exercice {escape(groupe.exercice_cloture)}, "
        f"conservées {groupe.type.exercices} exercices ({escape(groupe.type.fondement)}). "
        "Leurs pièces jointes sont dans les dossiers de cette archive ; les auteurs "
        "n'y sont pas nommés.</p>"
        f"<table><tr>{entete}</tr>{corps}</table>"
        f"<h2>Fichiers</h2><table><tr><th>Fichier</th><th>Octets</th><th>SHA-256</th></tr>"
        f"{fichiers}</table></body></html>"
    )


def _verifier(chemin: Path, pieces: list[Piece]) -> None:
    """L'archive écrite porte-t-elle chaque fichier, à l'empreinte d'origine ?"""
    try:
        with zipfile.ZipFile(chemin) as archive:
            if archive.testzip() is not None:
                raise ArchiveInvalide("un membre de l'archive est corrompu")
            noms = set(archive.namelist())
            for piece in pieces:
                if piece.nom not in noms:
                    raise ArchiveInvalide(f"{piece.nom} absent de l'archive")
                h = hashlib.sha256()
                with archive.open(piece.nom) as membre:
                    for morceau in iter(lambda: membre.read(1 << 20), b""):
                        h.update(morceau)
                if h.hexdigest() != piece.empreinte:
                    raise ArchiveInvalide(f"{piece.nom} : empreinte différente")
    except zipfile.BadZipFile as exc:
        raise ArchiveInvalide(f"archive illisible : {exc}") from exc


def ecrire_archive(
    session: Session, groupe: Echeance, contenus: list[Contenu]
) -> tuple[ArchiveAffaires, list[Piece]]:
    """Écrit l'archive d'un groupe, la RELIT, et rend sa ligne (non enregistrée).

    Lève `ArchiveInvalide` si la relecture échoue : le fichier écrit est alors
    retiré, et aucun fichier d'origine ne doit l'être.
    """
    par_affaire = [(c, pieces_de(c)) for c in contenus]
    pieces = [p for _, ps in par_affaire for p in ps]
    lignes = [_ligne(session, c, ps) for c, ps in par_affaire]
    nom = nom_archive(session, groupe)
    cle = f"{DOSSIER}/{nom}"
    st = stockage()

    with tempfile.TemporaryFile() as tampon:
        with zipfile.ZipFile(tampon, "w", zipfile.ZIP_DEFLATED) as archive:
            archive.writestr("sommaire.html", sommaire_html(groupe, lignes, pieces))
            archive.writestr("sommaire.csv", "﻿" + sommaire_csv(lignes, pieces))
            for piece in pieces:
                archive.write(piece.chemin, piece.nom)
        tampon.seek(0)
        #  Un fichier PRODUIT par l'application : déclaré dans
        #  `test_televersement_source_unique.ECRIVAINS_DU_STOCKAGE`.
        st.ecrire_flux(cle, tampon)

    chemin = st.chemin(cle)
    try:
        _verifier(chemin, pieces)
    except ArchiveInvalide:
        st.supprimer(cle)
        raise
    ligne = ArchiveAffaires(
        nom=nom,
        cle=cle,
        exercice=groupe.exercice_cloture,
        type=groupe.type.code,
        empreinte=empreinte_de(chemin),
        octets=chemin.stat().st_size,
        affaires=len(contenus),
        fichiers=len(pieces),
    )
    return ligne, pieces
