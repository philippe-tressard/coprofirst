r"""Le manuel ne RECOPIE plus de valeur technique — il n'en cite aucune.

## 🔴 Ce fichier remplace deux contrôles, et le remplacement EST la décision

Jusqu'au 02/09/2026, `test_manuel_chiffres.py` et `test_manuel_concordance.py`
vérifiaient que les valeurs recopiées dans le manuel **correspondaient** à celles
du code : « 10 pièces jointes », « 5 Mo par photo, 15 Mo par document », « PDF,
Word, Excel ou texte », les cinq descriptions de catégories de ticket. Ils
existaient parce que ces copies avaient divergé quatre fois, dont une pendant
deux semaines — le manuel promettait deux fois moins de photos que
l'application n'en accepte.

La refonte de #651 a fait le choix inverse : **le manuel ne cite plus ces valeurs
du tout**. Il est passé de 3 111 à environ 1 100 lignes, sur arbitrage —
*« beaucoup trop complexe et trop long ; seule la partie Démarrer est
suffisante »*. Le détail vit dans l'application, où il ne peut pas se périmer.
Le manuel a regrossi, puis maigri : il démarre en trois étapes, puis dit en une ou
deux phrases ce que contient chaque écran, sans aucun « En savoir plus » (#3008,
26/11/2026), et sa longueur est plafonnée par `lint:manuel-volume`. Ce contrôle-ci n'en dépend pas — il ne mesure pas une
longueur, il refuse une valeur recopiée.

Les deux anciens contrôles ont donc perdu leur objet, et un contrôle dont la
cible a disparu est **vert en ne mesurant plus rien**. Les supprimer sans rien
mettre à la place aurait laissé la porte ouverte : rien n'aurait empêché la
première section « pratique » de réintroduire « 15 Mo » un an plus tard.

## Ce que celui-ci vérifie

Non plus la concordance d'une copie, mais **l'absence de copie**. C'est plus fort
et plus simple : on n'a rien à tenir à jour, et le seul moyen de le faire échouer
est d'écrire dans le manuel une valeur dont le code est la source.

⚠️ Il ne prétend pas lire la prose — c'est impossible sans se tromper, et un
contrôle qui crie sur du légitime finit désarmé. Il cherche des **formes
précises** : un nombre suivi d'une unité technique, une extension de fichier, une
énumération de catégories. « 3 minutes pour démarrer » n'en est pas une : aucune
constante du code ne dit combien de temps prend une lecture.
"""

from __future__ import annotations

import html
import pathlib
import re

import pytest

_RACINE = pathlib.Path(__file__).resolve().parents[2]
_MANUEL = _RACINE / "docs" / "manuel-utilisateur.html"

#: Les nombres qu'on écrit en lettres devant une durée — « un » excepté.
NOMBRES_EN_LETTRES = (
    r"(?:deux|trois|quatre|cinq|six|sept|huit|neuf|dix|onze|douze|treize|quatorze|"
    r"quinze|seize|vingt|trente|quarante|cinquante|soixante|cent)(?:-\w+)*"
)

#: Ce qui trahit une valeur RECOPIÉE depuis le code, avec ce qu'elle vaut.
#:
#: Chaque motif nomme sa source : c'est elle qui décide, et le manuel n'a pas à
#: la répéter. Une entrée sans source ne serait qu'une interdiction de vocabulaire.
INTERDITS = {
    "une taille de fichier": (
        re.compile(r"\b\d+(?:[.,]\d+)?\s*(?:Mo|Ko|MB|KB)\b"),
        "la source est le plafond de chaque famille, `utils/fichiers.FAMILLES` ; le refus "
        "le dit au moment de joindre un fichier trop lourd",
    ),
    "un nombre de pièces jointes": (
        re.compile(r"\b\d+\s*(?:photos|documents|fichiers|pi[eè]ces jointes)\b", re.IGNORECASE),
        "la source est `MAX_FICHIERS` ; le manuel l'a annoncé faux pendant deux semaines",
    ),
    "une liste d'extensions acceptées": (
        re.compile(r"\.(?:pdf|docx?|xlsx?|txt)\b", re.IGNORECASE),
        "la source est la liste des types acceptés côté serveur",
    ),
    #  Un délai écrit en LETTRES est le même délai (#2906) : « trente jours après »
    #  recopiait le défaut d'un délai réglable, hors de tout motif. « Un jour » n'en
    #  est pas un — c'est une tournure.
    "un délai en jours": (
        re.compile(rf"\b(?:\d+|{NOMBRES_EN_LETTRES})\s*jours?\b", re.IGNORECASE),
        "les délais (archivage, relance, rétention) sont administrables : "
        "les écrire ici les fige à la valeur d'un jour donné",
    ),
    #  🔴 REMIS le 07/09/2026, après l'avoir enfreint moi-même le jour même.
    #
    #  L'ancien `test_manuel_concordance.py` vérifiait « les cinq descriptions de
    #  catégories de ticket ». Il a été supprimé le 02/09 parce que le manuel avait
    #  cessé d'en parler — et le motif est parti avec lui.
    #
    #  En livrant les huit catégories, j'ai recopié la liste ENTIÈRE dans le
    #  manuel, descriptions comprises, sans qu'aucun contrôle ne bronche. C'est
    #  exactement le trou que la docstring de ce fichier annonçait : « rien
    #  n'aurait empêché la première section pratique de réintroduire "15 Mo" un an
    #  plus tard ». Il aura fallu cinq jours, pas un an.
    #
    #  ⚠️ Le motif vise la LISTE, pas le mot : le manuel doit pouvoir écrire
    #  « Nuisance ou Propreté ? » pour expliquer comment choisir — c'est justement
    #  ce que l'écran ne dit pas. Ce qu'il ne doit pas faire, c'est ÉNUMÉRER : chaque
    #  description est déjà affichée sous sa tuile, et la copie diverge.
    #
    #  Le seuil est TROIS entrées de liste : deux catégories citées côte à côte
    #  sont une comparaison, trois sont un catalogue. C'est le même arbitrage que
    #  le seuil de deux clés du contrôle des teintes de rôle — mesuré sur ce que
    #  le manuel écrit légitimement, pas choisi pour faire passer le contrôle.
    "une énumération de catégories de ticket": (
        re.compile(
            r"(?:<li>[^<]*<strong>[^<]*"
            r"(?:Panne|Nuisance|Propreté|Espaces verts|Sinistre|Étude|Question|Bug)"
            r"[^<]*</strong>[^<]*(?:—|–|-|:)[^<]{10,}?</li>\s*){3,}"
        ),
        "la source est `CATEGORIES_TICKET` (front/src/lib/tickets-categories.ts) ; "
        "l'écran "
        "affiche déjà chaque description sous sa tuile, au moment où l'on choisit. "
        "Le manuel dit COMMENT choisir, il n'énumère pas",
    ),
}


def corps_lu(texte: str) -> str:
    """Ce que LIT le lecteur : sans CSS ni icônes, les entités décodées. PURE.

    Le CSS est plein de `.5rem` et de `24px`, et les tracés d'icônes de nombres :
    les scanner ferait échouer le contrôle sur du décor, et un contrôle qui crie
    sur du légitime finit désarmé.

    🔴 Les entités se DÉCODENT (#2906) : le manuel écrit `90&nbsp;jours`, et `\\s`
    ne lit pas `&nbsp;`. Jusqu'au 23/11/2026 ce contrôle était vert sur douze
    valeurs recopiées — il lisait la source, pas le texte.
    """
    texte = texte[texte.index("</style>") :]
    return html.unescape(re.sub(r"<svg.*?</svg>", "", texte, flags=re.S))


def _corps() -> str:
    return corps_lu(_MANUEL.read_text(encoding="utf-8"))


def fautes_de(corps: str) -> list[str]:
    fautes = []
    for quoi, (motif, source) in INTERDITS.items():
        for trouve in set(motif.findall(corps)):
            fautes.append(f"  « {trouve} » — {quoi} : {source}")
    return sorted(fautes)


def test_le_manuel_ne_cite_aucune_valeur_dont_le_code_est_la_source():
    fautes = fautes_de(_corps())
    assert not fautes, (
        "Le manuel recopie des valeurs dont le code est la source :\n"
        + "\n".join(fautes)
        + "\n\nUne valeur recopiée diverge — c'est arrivé quatre fois ici. "
        "Le manuel dit ce qu'on peut faire ; l'application dit avec quelles limites."
    )


def test_le_controle_lit_bien_le_manuel():
    """Cas zéro. Un fichier introuvable ou un corps vide rendrait la même
    liste vide qu'un manuel irréprochable.
    """
    corps = _corps()
    #  Plancher calé sur le manuel refondu (~15 900 caractères de corps), pas sur
    #  l'ancien de 3 000 lignes : un plancher trop haut ferait échouer le contrôle
    #  sur sa propre réussite, et un plancher à zéro ne distinguerait rien.
    assert len(corps) > 10_000, f"corps de {len(corps)} caractères : rien n'a été lu"
    assert "ecran-card" in corps, "la grille des écrans est absente : ce n'est pas le manuel"
    #  Et les motifs doivent mordre quand il y a de quoi mordre.
    assert INTERDITS["une taille de fichier"][0].search("jusqu'à 15 Mo par fichier")
    assert INTERDITS["un nombre de pièces jointes"][0].search("5 photos maximum")
    assert not INTERDITS["un délai en jours"][0].search("3 minutes pour démarrer")


@pytest.mark.parametrize(
    "source",
    [
        "<p>rouge au-delà de 90&nbsp;jours</p>",
        "<p>une image de 2&nbsp;Mo au plus</p>",
        "<p>conservée 90&#160;jours</p>",
        "<p>Résolu trente jours après</p>",
        "<p>sous quinze jours</p>",
        "<p>quatre-vingt-dix jours</p>",
    ],
)
def test_temoin_une_valeur_ecrite_avec_une_entite_ou_en_lettres_mord(source):
    """Cas zéro (#2906) : ce que le lecteur lit, le contrôle le lit."""
    assert fautes_de(corps_lu("<style></style>" + source))


@pytest.mark.parametrize(
    "source",
    ["<p>un jour</p>", "<p>Mois (les jours du mois)</p>", "<p>trois écrans, les jours fériés</p>"],
)
def test_temoin_une_tournure_ne_mord_pas(source):
    assert not fautes_de(corps_lu("<style></style>" + source))


def test_le_motif_des_CATEGORIES_refuse_bien_la_version_que_j_ai_ecrite():
    """Cas zéro — la liste réellement écrite le 07/09/2026, puis retirée.

    🔴 Sans ce cas, le motif serait invérifiable : il ne s'applique à rien dans le
    manuel actuel, donc il resterait vert quoi qu'il contienne. C'est le défaut
    exact des deux contrôles que ce fichier remplace — verts en ne mesurant plus
    rien parce que leur cible avait disparu.

    Les deux sens sont éprouvés, et le second est le plus important : le manuel
    DOIT pouvoir opposer deux catégories pour expliquer comment choisir. Un motif
    qui le refuserait ferait retirer l'explication, c'est-à-dire la seule chose
    que le manuel apporte que l'écran n'apporte pas.
    """
    motif = INTERDITS["une énumération de catégories de ticket"][0]

    catalogue = (
        "<ul>\n"
        "<li><strong>🛠️ Panne</strong> — un équipement ne marche plus : ascenseur.</li>\n"
        "<li><strong>📢 Nuisance</strong> — bruit, odeurs, stationnement gênant.</li>\n"
        "<li><strong>🧹 Propreté</strong> — parties communes, encombrants abandonnés.</li>\n"
        "</ul>"
    )
    assert motif.search(catalogue), "le catalogue doit être refusé"

    explication = (
        "<li><strong>Nuisance ou Propreté ?</strong> Elles se touchent, et c'est "
        "normal — choisissez selon ce qui doit se passer ensuite.</li>"
    )
    assert not motif.search(explication), "l'explication doit passer"

    #  Deux entrées : une comparaison, pas un catalogue.
    comparaison = (
        "<li><strong>Nuisance</strong> — il y a quelqu'un à qui parler.</li>\n"
        "<li><strong>Propreté</strong> — il y a une prestation à commander.</li>"
    )
    assert not motif.search(comparaison), "deux entrées ne font pas une liste"
