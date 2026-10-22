"""Rendu de `docs/carte-reglages.md` — déterministe, LF, sans horodatage (#2061).

Tout ce que le document dit vient de `utils/reglages_carte` (qui règle quoi), de
`utils/reglages` (les clés), de `routers/config` (public, secret), du seed (défaut
d'amorce) et de `Settings` (l'environnement) : il ne porte aucune phrase qu'il
faudrait tenir à la main à côté du code. Régénéré par
`python scripts/ci/carte_reglages.py --ecrire` ; `test_carte_reglages.py` échoue
s'il diffère.
"""

from __future__ import annotations

import re

from app.utils import reglages
from app.utils.llm_usages import USAGES, champs
from app.utils.reglages_carte import (
    LIBELLE_ACCES,
    NOTIONS,
    SECRETS_ENV,
    TEXTE,
    THEMES_ENV,
    TYPES,
    TYPES_CHAMP_USAGE,
    Acces,
    Notion,
)

EN_TETE = """\
<!-- GÉNÉRÉ par `python scripts/ci/carte_reglages.py --ecrire` — ne pas éditer. -->

# Carte des réglages

Qui règle quoi, où, et où la valeur vit — pour chaque réglage de l'application.
Ce document est **généré** depuis le code (`api/app/utils/reglages_carte.py`, la
liste blanche `api/app/utils/reglages.py`, le registre des services, les usages de
l'IA et `Settings`) : la CI le régénère et échoue s'il diffère. Un réglage neuf se
déclare dans le registre, pas ici. Ce qu'on ne peut pas y ranger fait échouer le test.

L'**accès** de chaque notion est confronté, en CI, à la dépendance d'autorisation
que sa route prend réellement : le tableau dit ce que fait le serveur, pas ce que
l'écran laisse espérer. Les écarts connus entre les deux sont listés plus bas.

> Les **écrans** d'Admin se lisent « groupe › onglet » : ce sont ceux de
> `front/src/lib/pages-roles.ts`, confrontés en CI (rangement par niveau, #2062).
"""

#: Les caractères qu'un nœud `mindmap` de Mermaid ne supporte pas.
_NON_MERMAID = re.compile(r"[`()\[\]{}\"]")
ORDRE_ACCES = (Acces.ADMIN, Acces.CS, Acces.OPERATEUR, Acces.EXPLOITANT, Acces.PERSONNE)


def cellule(texte: str) -> str:
    """Une barre verticale fermerait la cellule d'un tableau Markdown."""
    return str(texte).replace("|", "\\|").replace("\n", " ")


def court(libelle: str) -> str:
    """Le nom d'une notion, sans son détail (« Paramètres généraux : … » → « Paramètres généraux »)."""
    return re.split(r"\s[:(—]\s?", libelle, maxsplit=1)[0].strip()


def noeud(texte: str) -> str:
    return _NON_MERMAID.sub("", texte).replace("'", "’").strip()


def _mindmap(notions: tuple[Notion, ...]) -> str:
    lignes = ["```mermaid", "mindmap", "  root((Réglages))"]
    for acces in ORDRE_ACCES:
        lignes.append(f"    {noeud(LIBELLE_ACCES[acces].split(' (')[0])}")
        if acces is Acces.EXPLOITANT:
            enfants = [court(t) for t in THEMES_ENV]
        else:
            enfants = [court(n.libelle) for n in notions if n.acces is acces]
        lignes.extend(f"      {noeud(e)}" for e in enfants)
    lignes.append("```")
    return "\n".join(lignes)


def _route(notion: Notion) -> str:
    if notion.route:
        return f"`{notion.route[0]} {notion.route[1]}`"
    return "—"


def _tableau_notions(notions: tuple[Notion, ...]) -> str:
    sortie = []
    for acces in ORDRE_ACCES:
        if acces is Acces.EXPLOITANT:
            continue
        choisies = [n for n in notions if n.acces is acces]
        if not choisies:
            continue
        sortie += [
            f"### {LIBELLE_ACCES[acces]}",
            "",
            "| Notion | Écran | Stockage | Route |",
            "|---|---|---|---|",
        ]
        for n in choisies:
            sortie.append(
                f"| {cellule(n.libelle)} | {cellule(n.ecran)} | {cellule(n.stockage)} "
                f"| {_route(n)} |"
            )
        sortie.append("")
    return "\n".join(sortie)


def _ecarts(notions: tuple[Notion, ...]) -> str:
    avec = [n for n in notions if n.ecart]
    if not avec:
        return "_Aucun écart connu entre un écran et sa route._"
    return "\n".join(f"- **{court(n.libelle)}** ({n.ecran}) — {n.ecart}" for n in avec)


# ── Les clés de `config_site` ───────────────────────────────────────────────────


def _type_de(cle: str) -> str:
    return TYPES.get(cle, TEXTE)


def _defaut_de(cle: str) -> str:
    from app.seed import CONFIG_SITE_PAR_DEFAUT

    if cle in TYPES and TYPES[cle] == "secret":
        return "—"
    if cle not in CONFIG_SITE_PAR_DEFAUT:
        return "—"
    valeur = CONFIG_SITE_PAR_DEFAUT[cle]
    if valeur == "":
        return "vide"
    return "texte du produit (seed)" if len(valeur) > 40 else f"`{valeur}`"


def _lignes_cles(onglet: str) -> list[str]:
    from app.routers.config import _est_public

    lignes = []
    cles = sorted(reglages.PAR_ONGLET[onglet])
    if onglet == "ia":
        parusage = {u.cle(c) for u in USAGES.values() for c in champs(u)}
        cles = [c for c in cles if c not in parusage]
    for cle in cles:
        public = "oui" if _est_public(cle) else "non"
        lignes.append(f"| `{cle}` | {_type_de(cle)} | {_defaut_de(cle)} | {public} |")
    if onglet == "ia":
        champs_vus: dict[str, list[str]] = {}
        for u in USAGES.values():
            for c in champs(u):
                champs_vus.setdefault(c, []).append(u.code)
        for champ, usages in champs_vus.items():
            type_ = TYPES_CHAMP_USAGE.get(champ, TEXTE)
            lignes.append(f"| `llm_<usage>_{champ}` ({len(usages)} usages) | {type_} | — | non |")
    return lignes


def _tableau_cles(notions: tuple[Notion, ...]) -> str:
    sortie = []
    for n in notions:
        if n.onglet is None:
            continue
        sortie += [
            f"### {court(n.libelle)} — {n.ecran}",
            "",
            "| Clé | Type | Défaut d'amorce | Lisible sans connexion |",
            "|---|---|---|---|",
            *_lignes_cles(n.onglet),
        ]
        if n.onglet == "pages":
            sortie.append("| `page_config_<page>` | JSON | — | oui |")
        sortie.append("")
    return "\n".join(sortie)


# ── L'environnement ─────────────────────────────────────────────────────────────


def _tableau_environnement() -> str:
    from app.config import Settings

    sortie = []
    for theme, noms in THEMES_ENV.items():
        sortie += [f"### {theme}", "", "| Variable | Type | Défaut |", "|---|---|---|"]
        for nom in noms:
            champ = Settings.model_fields[nom]
            type_ = getattr(champ.annotation, "__name__", str(champ.annotation))
            if champ.is_required():
                defaut = "**obligatoire**"
            elif nom in SECRETS_ENV:
                defaut = "secret"
            elif champ.default == "":
                defaut = "vide"
            else:
                defaut = f"`{champ.default}`"
            sortie.append(f"| `{nom.upper()}` | {type_} | {defaut} |")
        sortie.append("")
    return "\n".join(sortie)


def rendre_document(notions: tuple[Notion, ...] = NOTIONS) -> str:
    """Le document complet. PURE (hors lecture des registres), déterministe."""
    parties = [
        EN_TETE,
        "## Vue d'ensemble\n\n" + _mindmap(notions),
        "## Qui règle quoi\n\n" + _tableau_notions(notions),
        "## Écarts connus\n\n" + _ecarts(notions),
        "## Les clés de `config_site`\n\n"
        "Écrites par `PUT /config` (administrateur), onglet par onglet : une clé n'appartient "
        "qu'à un seul onglet (#2057).\n\n" + _tableau_cles(notions),
        "## L'environnement (`.env`) — exploitant du serveur\n\n"
        "Les champs de `Settings` (`api/app/config.py`). Un `.env` qui porte une variable "
        "inconnue démarre quand même : elle est ignorée.\n\n" + _tableau_environnement(),
    ]
    return "\n\n".join(p.rstrip("\n") for p in parties) + "\n"
