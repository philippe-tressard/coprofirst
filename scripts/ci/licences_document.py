"""Rendu de `docs/licences-tierces.md` — déterministe, LF, sans horodatage.

Tout ce que le document dit vient de `licences_politique.py` (exceptions,
contenus tiers) ou de l'inventaire mesuré : il ne porte aucune phrase qu'il
faudrait tenir à la main à côté du code.
"""

from __future__ import annotations

import licences_politique as politique
from licences_image import rendre as rendre_images
from licences_spdx import admise

EN_TETE = """\
<!-- GÉNÉRÉ par `python scripts/ci/licences_tierces.py --ecrire` — ne pas éditer. -->

# Licences tierces

Inventaire des dépendances de `front/`, `whatsapp-bridge/` et `api/` et de leurs
licences (`standards/14` §6.3), des bibliothèques système que les images ajoutent,
puis des fichiers repris d'un projet tiers. La CI
le régénère et échoue s'il diffère : un paquet qui entre ou qui change de licence
se relit ici. La politique — liste blanche, exceptions et leurs motifs — vit dans
`scripts/ci/licences_politique.py`.

> ⚠️ Ce document constate, il ne tranche rien de juridique. Les exceptions
> ci-dessous sont des questions posées par écrit ; leur statut dit lesquelles
> restent à valider par l'auteur — aucune depuis le passage du projet à
> l'AGPL-3.0-or-later (08/10/2026, #1726), dont l'analyse a été validée.
"""

NOTE_API = (
    "Seules les dépendances **directes** de l'API sont figées ici : les transitives "
    "ne sont pas épinglées dans `api/requirements.txt`, et leur métadonnée de "
    "licence changerait ce document sans que le dépôt bouge. Elles sont jugées par "
    "la liste blanche à chaque passage de la CI, comme les directes."
)


def cellule(texte: str) -> str:
    """Une barre verticale fermerait la cellule d'un tableau Markdown."""
    return texte.replace("|", "\\|")


def _exceptions(exceptions) -> list[str]:
    lignes = ["## Exceptions déclarées", ""]
    lignes += ["| Source | Paquets | Licence | Motif | Statut |", "|---|---|---|---|---|"]
    for exc in exceptions:
        paquets = ", ".join(f"`{p}`" for p in exc["paquets"])
        licences = "<br>".join(f"`{cellule(x)}`" for x in exc["licences"])
        lignes.append(
            f"| {exc['source']} | {paquets} | {licences} | {exc['motif']} | {exc['statut']} |"
        )
    return lignes


def _contenus() -> list[str]:
    lignes = ["## Fichiers repris d'un projet tiers", ""]
    lignes += ["| Contenu | Licences | Fichiers | Origine et remarques |", "|---|---|---|---|"]
    for c in politique.CONTENUS_TIERS:
        fichiers = "<br>".join(f"`{f}`" for f in c["fichiers"])
        lignes.append(
            f"| {c['nom']} | {' AND '.join(c['licences'])} | {fichiers} | "
            f"{c['origine']}. {c['detail']} |"
        )
    hors = "; ".join(f"`{k}` : {v}" for k, v in sorted(politique.ICONES_HORS_LUCIDE.items()))
    lignes += [
        "",
        f"Icônes de `{politique.CATALOGUE_ICONES}` qui ne viennent pas de Lucide — {hors}.",
    ]
    return lignes


def _dependances(source: str, paquets: list[dict], admises) -> list[str]:
    qualite = "dépendances directes" if source == "api" else "paquets"
    lignes = [f"## Dépendances — `{source}` ({len(paquets)} {qualite})", ""]
    if source == "api":
        lignes += [NOTE_API, ""]
    lignes += ["| Paquet | Licence | Déclaré | Admise |", "|---|---|---|---|"]
    for p in paquets:
        verdict = "oui" if admise(p["licence"], admises) else "**exception**"
        lignes.append(f"| `{p['nom']}` | `{cellule(p['licence'])}` | {p['portee']} | {verdict} |")
    return lignes


def rendre_document(inventaire: dict[str, list[dict]], exceptions, admises) -> str:
    """Le contenu du document pour cet inventaire. PURE."""
    blocs = [EN_TETE.rstrip("\n").split("\n"), _exceptions(exceptions)]
    blocs += [rendre_images(politique, cellule), _contenus()]
    blocs += [_dependances(s, p, admises) for s, p in inventaire.items()]
    return "\n\n".join("\n".join(b) for b in blocs) + "\n"
