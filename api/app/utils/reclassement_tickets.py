"""Proposer une catégorie plus juste pour les tickets déjà ouverts (#821).

Demandé le 07/09/2026 : *« peux-tu regarder les tickets créés et leur affecter la
catégorie la plus adéquate ? Me faire une synthèse et me valider avant
application. »*

## 🔴 Pourquoi un RELEVÉ et pas une correction directe

Deux raisons, et la seconde est la vraie.

1. **Je ne lis pas la base de production.** Le relevé passe par l'API, qui
   applique les droits, comme tout le reste.

2. **Une reclassification automatique est un pari sur du texte libre.** Ces
   mots-clés lisent un titre et une description écrits par des humains ; ils se
   trompent, et une catégorie fausse posée en silence est pire qu'une catégorie
   approximative assumée. Le relevé propose ; quelqu'un tranche.

C'est le même choix que pour les baux sans locataire (#808) : *garder et
observer* avant d'automatiser.

## Comment il propose

Chaque règle nomme sa catégorie et les indices qui la déclenchent, dans l'ordre
de spécificité.

🔴 **« Fuite » n'est PAS un indice de sinistre**, et je l'avais mis là. Arbitré
le 07/09/2026 sur deux cas concrets : *« une fuite goutte-à-goutte dans les
communs, tu la qualifies Panne ou Sinistre ? Idem pour une ampoule grillée. »*
Les deux sont des **pannes**. La frontière n'est pas l'eau, c'est le **dommage**
— de l'eau chez quelqu'un, un plafond taché, un parquet gondolé. Un indice qui
range toutes les fuites en sinistre aurait proposé de déplacer des réparations
vers une procédure d'assurance.

⚠️ Une proposition n'est faite que si elle **diffère** de la catégorie actuelle,
et jamais vers « Panne » : c'est la catégorie par défaut, celle où tombent les
tickets qu'on n'a pas su ranger. Proposer d'y déplacer quelque chose serait
proposer d'effacer une information.

⚠️ `confiance` distingue ce qui est sûr de ce qui est plausible. Un indice
**univoque** (« dégât des eaux », « interphone ») donne « haute » ; un indice
ambigu (« eau », « badge ») donne « moyenne » — le mot « eau » apparaît aussi
dans « fuite d'eau chaude », qui est une panne de chauffe-eau.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass


def _sans_accent(texte: str) -> str:
    """Compare sans accents ni casse : les gens écrivent « degat » et « dégât »."""
    plat = unicodedata.normalize("NFD", texte.lower())
    return "".join(c for c in plat if unicodedata.category(c) != "Mn")


@dataclass(frozen=True)
class Regle:
    categorie: str
    #: Indices SÛRS — ils ne désignent qu'une chose.
    univoques: tuple[str, ...]
    #: Indices PLAUSIBLES — ils peuvent appartenir à une autre catégorie.
    ambigus: tuple[str, ...] = ()


#: L'ordre COMPTE : la première règle qui trouve un indice l'emporte. Le sinistre
#: passe en tête parce que ses indices sont les plus SPÉCIFIQUES — « dégât des
#: eaux » doit gagner sur « eaux ». Ce n'est pas une hiérarchie de gravité.
REGLES: tuple[Regle, ...] = (
    Regle(
        "sinistre",
        univoques=(
            "degat des eaux",
            "degats des eaux",
            "infiltration",
            "incendie",
            "vandalisme",
            "sinistre",
            "assurance",
            "constat amiable",
            "bris de glace",
            "effraction",
        ),
        #  ⚠️ PAS « fuite » : une fuite qu'on répare est une PANNE. Ne restent
        #  que les mots qui disent un DOMMAGE — inondation, dégât.
        ambigus=("inonda", "degat"),
    ),
    Regle(
        "acces_accueil",
        univoques=(
            "interphone",
            "digicode",
            "boite aux lettres",
            "bal ",
            "platine",
            "emmenag",
            "amenag",
            "nouvel arrivant",
            "etiquette",
        ),
        ambigus=("badge", "vigik", "telecommande", "cle ", "acces "),
    ),
    Regle(
        "espaces_verts",
        univoques=(
            "elagage",
            "espaces verts",
            "espace vert",
            "haie",
            "tonte",
            "arrosage",
            "jardin",
            "arbre",
            "taille des",
        ),
        ambigus=("plantation", "massif"),
    ),
    Regle(
        "etude_travaux",
        univoques=(
            "diagnostic",
            "sondage",
            "prelevement",
            "etancheite",
            "devis",
            "appel d'offre",
            "maitre d'oeuvre",
            "expertise",
            "ravalement",
            "audit energetique",
        ),
        ambigus=("travaux", "chantier", "etude"),
    ),
    #  ⚠️ « Nuisance & propreté » depuis la migration 0179 : les indices des DEUX
    #  anciennes catégories vivent ici, et c'est la seule trace que la fusion a
    #  eu lieu du côté du relevé.
    Regle(
        "nuisance",
        univoques=(
            "nuisance",
            "tapage",
            "aboiement",
            "musique",
            "voisin bruyant",
            "stationnement genant",
            "incivilite",
            "proprete",
            "nettoyage",
            "encombrant",
            "poubelle",
            "ordures",
            "menage",
            "salete",
            "detritus",
            "local velo",
        ),
        ambigus=("bruit", "odeur", "stationnement", "tri", "container", "conteneur"),
    ),
)

#: 🔴 On ne propose JAMAIS de déplacer vers « panne » : c'est la catégorie par
#: défaut, celle où tombe ce qu'on n'a pas su ranger. Y déplacer un ticket serait
#: proposer d'effacer une information, pas d'en ajouter une.
JAMAIS_PROPOSEE = ("panne",)


def proposer(titre: str, description: str, categorie_actuelle: str) -> tuple[str, str, str] | None:
    """Rend `(categorie, confiance, indice)` ou `None` si rien de mieux.

    ⚠️ Lit le titre ET la description : un ticket intitulé « Problème au B2 »
    ne dit rien, sa description si. Mais le titre pèse autant — les gens y
    mettent l'essentiel.
    """
    if categorie_actuelle in JAMAIS_PROPOSEE and not titre and not description:
        return None
    texte = _sans_accent(f"{titre} {description}")
    #  Les balises d'une description HTML deviendraient des mots : `<p>fuite</p>`
    #  ne doit pas produire l'indice « p ». On les retire avant de chercher.
    texte = re.sub(r"<[^>]+>", " ", texte)

    for regle in REGLES:
        if regle.categorie == categorie_actuelle:
            continue
        for indice in regle.univoques:
            if indice in texte:
                return (regle.categorie, "haute", indice.strip())
        for indice in regle.ambigus:
            if indice in texte:
                return (regle.categorie, "moyenne", indice.strip())
    return None
