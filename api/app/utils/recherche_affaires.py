"""Recherche libre dans les affaires — la règle, sans la base.

## Pourquoi (27/09/2026)

Le filtre « Catégorie » de la page Affaires est remplacé par une recherche libre,
« la plus exhaustive possible » (maquette A, avec l'extrait et les Archives de la
maquette C) : on cherche un mot, pas une case.

« Exhaustive » a une conséquence : la liste chargée par l'écran ne porte ni les
suites, ni les messages, ni les documents d'une affaire. La recherche vit donc au
SERVEUR, et elle y vit **une fois** : l'écran n'a pas de seconde règle pour les
champs qu'il connaît déjà — deux règles pour une même recherche diraient deux
choses sur la même liste.

## Ce qui se cherche

| Champ | D'où |
|---|---|
| `numero`, `titre`, `description` | l'affaire |
| `categorie` | son libellé (`libelle_categorie`), plus le filtre supprimé |
| `lieu` | le libellé du périmètre (`perimetre_label`) |
| `personne` | le rédacteur et la personne pour qui l'affaire est saisie |
| `prestataire`, `equipement` | la section Intervenant / Équipement |
| `suite` | les entrées du fil de suivi — **si** le lecteur peut les lire |
| `message` | la messagerie — notes internes au conseil seulement |
| `piece_jointe` | le nom des fichiers et le titre des documents lisibles |

🔴 Ce module ne décide AUCUN droit : le routeur ne lui passe que ce que le lecteur
a le droit de lire, par les mêmes prédicats que les écrans qui le montrent. Une
recherche qui en saurait plus que l'écran révélerait, par un simple compte de
résultats, qu'un texte existe là où on ne peut pas le lire.

## La correspondance

Chaque mot de la requête doit se trouver **quelque part** dans l'affaire (ET),
sans tenir compte des accents ni des majuscules. Le score pondère l'endroit :
un mot du titre pèse plus qu'un mot d'un message. `--selftest` éprouve la règle.
"""

from __future__ import annotations

import sys
import unicodedata
from dataclasses import dataclass, field
from datetime import datetime
from functools import lru_cache
from typing import Optional

#: L'ordre dit aussi quel endroit l'écran annonce quand plusieurs correspondent :
#: le premier de la liste qui porte le plus de mots.
POIDS: dict[str, int] = {
    "numero": 10,
    "titre": 8,
    "categorie": 5,
    "lieu": 4,
    "personne": 4,
    "prestataire": 4,
    "equipement": 4,
    "description": 3,
    "suite": 2,
    "message": 2,
    "piece_jointe": 2,
}

#: Les endroits dont l'écran montre un EXTRAIT : le titre, le numéro ou la
#: catégorie se lisent déjà sur la carte, un passage de suite non.
AVEC_EXTRAIT = frozenset({"description", "suite", "message", "piece_jointe"})

#: Au-delà, la requête n'est plus une recherche mais un texte collé.
TERMES_MAX = 8
LARGEUR_EXTRAIT = 160
#: Ce qui précède le premier mot trouvé, pour qu'il se lise dans sa phrase.
CONTEXTE_AVANT = 50


@dataclass(frozen=True)
class Texte:
    """Un morceau cherchable d'une affaire, et d'où il vient."""

    champ: str
    texte: str
    date: Optional[datetime] = None
    auteur: Optional[str] = None


@dataclass
class Resultat:
    """Ce que l'écran reçoit pour UNE affaire trouvée."""

    score: int
    ou: str
    extrait: list[dict] = field(default_factory=list)
    date: Optional[datetime] = None
    auteur: Optional[str] = None


@lru_cache(maxsize=4096)
def _plat(car: str) -> str:
    base = "".join(c for c in unicodedata.normalize("NFD", car) if unicodedata.category(c) != "Mn")
    #  UN caractère pour UN caractère : c'est ce qui permet de surligner dans le
    #  texte d'origine la position trouvée dans le texte replié. « ß » → « ss »
    #  décalerait tout ce qui suit.
    return (base.lower() or " ")[:1]


def replier(texte: str | None) -> str:
    """Minuscules, sans accents, **même longueur** que le texte d'origine.

    Pendant serveur de `replier` (`front/src/lib/texte.ts`), à une différence
    près, voulue : celle du front rogne les bords, celle-ci garde chaque position.
    """
    return "".join(_plat(c) for c in (texte or ""))


def termes(requete: str | None) -> list[str]:
    """Les mots cherchés : repliés, dédoublonnés, dans l'ordre de la frappe."""
    vus: list[str] = []
    for mot in replier(requete).split():
        #  « #TK-237133 » : le dièse s'écrit devant un numéro à l'écran, et se
        #  copie avec lui. Il ne fait pas partie du numéro (pendant front :
        #  `termeAffaire`, `#lib/tickets.ts`).
        mot = mot.lstrip("#")
        if mot and mot not in vus:
            vus.append(mot)
    return vus[:TERMES_MAX]


def _segments(texte: str, plie: str, mots: list[str]) -> list[dict]:
    """Le texte découpé en morceaux surlignés ou non — jamais du HTML.

    L'écran les rend un par un : aucun balisage ne transite, donc rien à assainir.
    """
    surligne = [False] * len(texte)
    for mot in mots:
        debut = plie.find(mot)
        while debut != -1:
            for i in range(debut, debut + len(mot)):
                surligne[i] = True
            debut = plie.find(mot, debut + len(mot))
    segments: list[dict] = []
    for i, car in enumerate(texte):
        if segments and segments[-1]["surligne"] == surligne[i]:
            segments[-1]["texte"] += car
        else:
            segments.append({"texte": car, "surligne": surligne[i]})
    return segments


def extrait(texte: str, mots: list[str], largeur: int = LARGEUR_EXTRAIT) -> list[dict]:
    """La fenêtre du texte autour du premier mot trouvé, en segments."""
    plie = replier(texte)
    positions = [p for p in (plie.find(m) for m in mots) if p != -1]
    premier = min(positions) if positions else 0
    debut = max(0, premier - CONTEXTE_AVANT)
    #  On recule jusqu'au début d'un mot : « …age de la colonne » ne se lit pas.
    if debut > 0:
        espace = texte.rfind(" ", 0, debut)
        debut = espace + 1 if espace != -1 and debut - espace < 20 else debut
    fin = min(len(texte), debut + largeur)
    if fin < len(texte):
        espace = texte.rfind(" ", debut, fin)
        fin = espace if espace > premier else fin
    segments = _segments(texte[debut:fin], plie[debut:fin], mots)
    if debut > 0:
        segments.insert(0, {"texte": "… ", "surligne": False})
    if fin < len(texte):
        segments.append({"texte": " …", "surligne": False})
    return segments


def correspondance(textes: list[Texte], mots: list[str]) -> Optional[Resultat]:
    """L'affaire répond-elle à TOUS les mots ? Si oui, où, et avec quel extrait."""
    if not mots:
        return None
    plies = [(t, replier(t.texte)) for t in textes if t.texte]
    if not all(any(m in p for _, p in plies) for m in mots):
        return None
    ordre = list(POIDS)
    score = 0
    meilleur: tuple[int, int, int] | None = None  # (mots trouvés, -rang du champ, -index)
    choisi: tuple[Texte, str] | None = None
    for index, (texte, plie) in enumerate(plies):
        trouves = sum(m in plie for m in mots)
        if not trouves:
            continue
        score += POIDS.get(texte.champ, 1) * trouves
        cle = (trouves, -ordre.index(texte.champ), -index)
        if meilleur is None or cle > meilleur:
            meilleur, choisi = cle, (texte, plie)
    assert choisi is not None  # au moins un mot est trouvé, donc un texte
    texte, _ = choisi
    return Resultat(
        score=score,
        ou=texte.champ,
        extrait=extrait(texte.texte, mots) if texte.champ in AVEC_EXTRAIT else [],
        date=texte.date,
        auteur=texte.auteur,
    )


def _selftest() -> int:
    """La règle sur des cas écrits à la main — sans base, sans réseau."""
    echecs = 0

    def verifier(nom: str, obtenu, attendu) -> None:
        nonlocal echecs
        if obtenu != attendu:
            echecs += 1
            print(f"ÉCHEC {nom} : {obtenu!r} ≠ {attendu!r}")

    verifier("replier garde la longueur", len(replier("Dégât ß œ")), len("Dégât ß œ"))
    verifier("replier", replier("DÉGÂT"), "degat")
    verifier("termes", termes("  Fuite  fuite PLAFOND "), ["fuite", "plafond"])
    verifier(
        "le dièse d'un numéro ne se tape pas", termes("#TK-237133 fuite"), ["tk-237133", "fuite"]
    )
    verifier("un dièse seul n'est pas un mot", termes("# ##"), [])
    fiche = [
        Texte("titre", "Tache au plafond"),
        Texte("suite", "Le plombier confirme une fuite sur la colonne"),
    ]
    r = correspondance(fiche, termes("fuite"))
    verifier("trouvé dans la suite", r and r.ou, "suite")
    verifier(
        "extrait surligné",
        [s["texte"] for s in (r.extrait if r else []) if s["surligne"]],
        ["fuite"],
    )
    verifier("tous les mots exigés", correspondance(fiche, termes("fuite toiture")), None)
    r = correspondance(fiche, termes("plafond fuite"))
    verifier("les mots peuvent être à deux endroits", r is not None, True)
    verifier("accents ignorés", correspondance(fiche, termes("PLAFÔND")) is not None, True)
    verifier("rien de cherché, rien de trouvé", correspondance(fiche, []), None)
    long = "mot " * 60 + "cible " + "suite " * 60
    seg = extrait(long.strip(), ["cible"])
    verifier("fenêtre bornée", len("".join(s["texte"] for s in seg)) <= LARGEUR_EXTRAIT + 4, True)
    verifier("ellipse en tête", seg[0]["texte"], "… ")
    print("OK" if not echecs else f"{echecs} échec(s)")
    return 1 if echecs else 0


if __name__ == "__main__":
    if "--selftest" in sys.argv:
        sys.exit(_selftest())
