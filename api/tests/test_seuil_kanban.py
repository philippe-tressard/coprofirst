"""Les deux kanbans du site basculent en vue étroite au MÊME seuil.

## 🔴 Pourquoi (01/09/2026, signalé à l'écran)

> « un iPad en mode vertical/portrait, le kanban s'affiche mal sur le fil
>   d'actualité »

Le site rend le kanban à **deux** endroits :

| Rendu | Vue étroite | Seuil |
|---|---|---|
| page **Calendrier** (complet) | colonnes empilées, pleine largeur | 900 px |
| **tableau de bord** (condensé) | une colonne à la fois, avec navigation | **767 px** |

Les deux règles vivent dans `front/src/styles/` : `.kanban` dans `kanban.css`,
`.kb-desktop`/`.kb-mobile` dans `normes.css`. La seconde a quitté la page le
01/09/2026 — ce sont des interrupteurs de responsive, pas une mise en forme
d'écran, et le contrôle de modularité refusait d'agrandir la page pour les loger.

Un iPad en portrait fait 768 à 820 px : il tombait **entre les deux**. Le kanban
du Calendrier y était lisible ; celui du tableau de bord recevait la grille, avec
cinq colonnes de 130 px minimum dans ~640 px utiles. `auto-fit` en rejetait une à
la ligne — un kanban dont les colonnes ne sont plus côte à côte ne se lit plus
comme un kanban — et les titres étaient tronqués à trois mots.

⚠️ **Aucun des deux seuils n'était faux en soi.** Le défaut est leur écart, et il
n'existe qu'entre 768 et 900 px : une largeur que ni un téléphone ni un ordinateur
n'ont, mais que toutes les tablettes en portrait ont.

C'est le motif du cadre : *un objet a plusieurs rendus, et toute divergence entre
eux se déclare*. Ici elle ne se déclarait nulle part, parce qu'elle n'était visible
que sur un appareil que personne n'avait sous la main.

## Ce que ce test vérifie

Que les deux valeurs sont **égales**. Il ne dit pas laquelle est la bonne : c'est
un arbitrage d'ergonomie qui peut changer. Il dit qu'elles doivent changer
**ensemble**.

⚠️ Il lit le CSS, ce qui est grossier — mais le défaut EST dans le CSS, et il ne
se manifeste qu'à une largeur donnée, sur un appareil donné. Aucun test de
comportement ne l'aurait vu sans piloter un navigateur à 810 px de large.
"""

from __future__ import annotations

import re
from pathlib import Path

_RACINE = Path(__file__).resolve().parents[2]
_FRONT = _RACINE / "front" / "src"

#: Où chaque kanban déclare sa bascule, et le sélecteur qui l'identifie.
#:
#: ⚠️ Le sélecteur fait partie du contrôle : chercher « la dernière media-query du
#: fichier » aurait suivi n'importe quel ajout ultérieur, et le test aurait mesuré
#: autre chose sans le dire.
_SOURCES = [
    #  ⚠️ `kanban.css` et non `composants.css` depuis le 19/09/2026 : la famille
    #  entière a quitté le fichier de composants, que le garde-fou de modularité
    #  refusait d'agrandir. Le sélecteur, lui, n'a pas bougé.
    (_FRONT / "styles" / "kanban.css", r"\.kanban \{\s*\n\s*flex-direction: column;"),
]


def _constante_seuil() -> int:
    """`SEUIL_KANBAN_ETROIT` dans `#lib/kanban.ts` — le seuil du condensé."""
    fichier = _FRONT / "lib" / "kanban.ts"
    assert fichier.exists(), f"{fichier} est introuvable — ce test ne mesure plus rien."
    m = re.search(
        r"^export const SEUIL_KANBAN_ETROIT = (\d+);", fichier.read_text(encoding="utf-8"), re.M
    )
    assert m, (
        "`SEUIL_KANBAN_ETROIT` introuvable — renommée, ou la bascule est repassée "
        "au CSS. Dans les deux cas ce test ne surveille plus rien (INCONNU, pas OK)."
    )
    return int(m.group(1))


def _seuil_de(chemin: Path, selecteur: str) -> int:
    """La largeur de la `@media (max-width: …)` qui contient ce sélecteur."""
    assert chemin.exists(), f"{chemin} est introuvable — ce test ne mesure plus rien."
    source = chemin.read_text(encoding="utf-8")

    correspondance = re.search(selecteur, source)
    assert correspondance, (
        f"Le sélecteur attendu n'est plus dans {chemin.name} — la vue étroite a "
        "changé de forme, et ce test ne surveille plus rien (INCONNU, pas OK)."
    )

    #  La `@media` la plus proche EN AMONT du sélecteur : c'est celle qui le
    #  contient. Prendre la première du fichier attraperait une règle sans rapport.
    avant = source[: correspondance.start()]
    medias = re.findall(r"@media \(max-width:\s*(\d+)px\)", avant)
    assert medias, f"Aucune `@media (max-width: …)` avant le sélecteur dans {chemin.name}."
    return int(medias[-1])


def test_les_deux_kanbans_basculent_au_meme_seuil():
    """Un objet, deux rendus, un seul seuil.

    ⚠️ Les deux ne basculent plus de la même FAÇON : le complet par une requête
    de média, le condensé par un `{#if}` sur une constante — deux bascules CSS
    ayant échoué le même soir. Ce test compare donc une media-query à une
    constante TypeScript, et c'est voulu : ce qui doit rester d'accord est la
    VALEUR, pas le mécanisme.
    """
    seuils = {chemin.name: _seuil_de(chemin, sel) for chemin, sel in _SOURCES}
    seuils["kanban.ts"] = _constante_seuil()

    valeurs = set(seuils.values())
    assert len(valeurs) == 1, (
        "Les deux kanbans basculent en vue étroite à des largeurs différentes : "
        + ", ".join(f"{nom} → {v} px" for nom, v in seuils.items())
        + "\n  Entre les deux valeurs, un rendu est lisible et l'autre ne l'est "
        "pas — c'est la plage des tablettes en portrait (768 à 820 px), que ni un "
        "téléphone ni un ordinateur n'occupent.\n"
        "  Changer les deux dans le même lot, ou déclarer pourquoi ils diffèrent."
    )
