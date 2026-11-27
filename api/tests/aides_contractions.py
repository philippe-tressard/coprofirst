"""Les contractions annoncées et leurs preuves — les DÉCLARATIONS du contrôle (#1757).

La règle et le contrôle vivent dans `test_migrations_compatibles.py` ; ce module ne
porte que ce qu'un lot écrit pour s'y conformer, et ce que d'autres contrôles en
lisent (`test_tables_retirees.py`, #3098) :

- `CONTRACTIONS` : chaque retrait ou renommage annoncé au premier temps ;
- `PREUVES_SANS_PERTE` : la preuve, lue sur la production, d'un retrait de données ;
- `PREUVE_EXIGEE_APRES` : d'où la preuve est exigée, par chaîne ;
- `tables_et_colonnes_des_modeles` : ce que le code déclare encore.
"""

from __future__ import annotations

import json
from pathlib import Path

_RACINE = Path(__file__).resolve().parents[2]

#: Les contractions annoncées : la cible (`table` ou `table.colonne`), la version
#: du code qui a CESSÉ d'en dépendre, et pourquoi. Une entrée s'écrit au premier
#: temps, avec la version de ce lot ; la migration qui retire vient dans un lot
#: suivant. Une entrée reste après la migration : c'est la trace du retrait.
CONTRACTIONS: dict[str, tuple[str, str]] = {
    "ticket.non_relancable": (
        "2.130.5",
        "la relance syndic propose toute affaire suivie depuis v2.130.2 (#1796) ; "
        "le champ quitte le modèle, la 0272 lui donne un défaut (#1797)",
    ),
    "ticket.non_relancable_motif": ("2.130.5", "le motif du marquage retiré (#1797)"),
    "document.fichier_chemin": (
        "2.142.7",
        "le fichier se situe par sa clé depuis v2.142.3 (0283) ; le chemin absolu "
        "n'est plus ni lu ni écrit, la 0284 lui donne un défaut (#1816)",
    ),
    "diagnostic_rapport.fichier_chemin": ("2.142.7", "même règle que le document (#1816)"),
    "annonce_hall.pdf_chemin": ("2.142.7", "même règle que le document (#1816)"),
    #  Réglages écrits ou déclarés, jamais lus (#2059) : le code cesse d'en dépendre, la 0307
    #  donne un défaut aux colonnes NOT NULL ; le retrait vient dans une version ultérieure.
    "config_sauvegarde.frequence": (
        "3.11.0",
        "la sauvegarde est quotidienne depuis la 0139, rien ne lisait la fréquence (#2059)",
    ),
    "config_sauvegarde.jour_semaine": ("3.11.0", "même règle que la fréquence (#2059)"),
    "config_sauvegarde.jour_mois": ("3.11.0", "même règle que la fréquence (#2059)"),
    "modele_email.corps_texte": (
        "3.11.0",
        "le texte brut d'un modèle n'a jamais servi à l'envoi (#2059)",
    ),
    "copropriete.assurance_compagnie": (
        "3.11.0",
        "la fiche lit l'assurance sur le contrat depuis #490 ; la colonne ne sert plus (#2059)",
    ),
    "copropriete.assurance_numero_police": ("3.11.0", "même règle (#2059)"),
    "copropriete.assurance_echeance": ("3.11.0", "même règle (#2059)"),
    #  Même famille, premier temps de #2182 : la 0310 donne un défaut à la colonne NOT NULL.
    "config_sauvegarde.active": (
        "3.13.8",
        "la sauvegarde ne se coupe plus depuis #2060, rien ne lit ni n'écrit l'interrupteur (#2182)",
    ),
    #  Premier temps de la contraction de #3011 : le code ne lit et n'écrit plus que
    #  `prix_centimes`, la 0353 vide `prix` ; le champ servi `prix` se calcule.
    "petite_annonce.prix": (
        "3.125.9",
        "le prix se lit et s'écrit en centimes entiers ; la colonne en euros flottants est vide (#3011)",
    ),
    #  Base `plateforme` (registre) : le premier retrait d'une TABLE. Ses sauvegardes
    #  d'avant la portent : l'import l'écarte (`import_copropriete.TABLES_RETIREES`).
    #  Version : la dernière posée par un train quand l'annonce part (#2631).
    "canal_distribution": (
        "3.125.9",
        "canal-branche plus lu depuis #2210 ; le workflow qui l'avançait est retiré en "
        "v3.125.1 (#3009) ; le modèle quitte le registre (#3098)",
    ),
}

#: La preuve, lue SUR LA PRODUCTION, qu'un retrait ne perd rien (#2937) :
#: `{cible: "JJ/MM/AAAA — requête jouée sur la base servie → résultat"}`. La requête
#: se joue sur l'actif (`docker exec hostachy_postgres psql …`), donc au poste : une
#: session cloud ne l'écrit pas. Vide tant qu'aucun retrait n'est en cours.
PREUVES_SANS_PERTE: dict[str, str] = {
    "petite_annonce.prix": (
        "25/11/2026 — rpi1 (actif), v3.126.0, alembic 0353 : select count(*), count(prix), "
        "count(prix_centimes) from petite_annonce → 4|0|1 (la 0353 a reporté chaque prix "
        "dans prix_centimes, puis vidé prix ; 0 écart relevé avant elle)"
    ),
    "canal_distribution": (
        "28/11/2026 — rpi1 (actif, primaire), v3.127.1, plateforme 0006 : select nom, version, "
        "version_precedente from canal_distribution → replica|3.11.7|3.6.1 ; count(*) → 1 "
        "(le canal-branche retiré par #3009, lu par aucun code depuis #2210 ; la sauvegarde "
        "du registre du 27/11 l'écarte déjà, `ignorees`)"
    ),
}

#: La règle de la preuve naît avec #2937 : les retraits d'avant (0308, 0311) sont en
#: production depuis v3.13 et n'ont pas à la produire après coup. Seuil fixe, jamais
#: relevé — une migration neuve porte un numéro plus grand. PAR CHAÎNE : leurs
#: numéros ne se comparent pas ; la chaîne `plateforme` n'était lue par aucun de ces
#: contrôles avant le 25/11/2026 (#3098), et n'avait rien retiré (0001–0006).
PREUVE_EXIGEE_APRES = {"copropriete": 346, "plateforme": 6}


def version_du_lot() -> str:
    return json.loads((_RACINE / "front" / "package.json").read_text(encoding="utf-8"))["version"]


def tables_et_colonnes_des_modeles() -> set[str]:
    """`table` et `table.colonne` de chaque modèle enregistré — ceux d'une copropriété
    ET ceux du registre, qui ont leurs propres métadonnées (#3098)."""
    from sqlmodel import SQLModel

    #  `app.models.core` et non `app.models` : c'est lui qui charge tous les modules
    #  de modèles, comme `alembic/env.py` (CLAUDE.md, #1157).
    import app.models.core  # noqa: F401 — enregistre les tables
    from app.registre.modeles import registre_plateforme

    cibles: set[str] = set()
    tables = {**SQLModel.metadata.tables, **registre_plateforme.metadata.tables}
    for nom, table in tables.items():
        cibles.add(nom)
        cibles |= {f"{nom}.{c.name}" for c in table.columns}
    return cibles
