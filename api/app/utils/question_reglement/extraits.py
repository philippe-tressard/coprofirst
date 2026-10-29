"""Vérifier qu'un extrait cité figure dans le règlement, et dire où (03/10/2026).

## 🔴 Pourquoi le code vérifie ce que le modèle cite

Un modèle de langage peut « citer » une phrase qu'il a reformulée, ou qu'il a
inventée. Un avis de juriste dont les extraits sont faux est pire qu'une
absence d'avis : il a l'air vérifiable. Chaque extrait est donc RECHERCHÉ dans
le texte chargé, et l'écran dit lequel a été retrouvé et lequel ne l'a pas été.

Le repère de page n'est pas non plus cru sur parole : quand l'extrait est
retrouvé, la page est celle du dernier repère ⟦ … ⟧ qui le précède dans le
texte, et l'acte celui du dernier titre de premier niveau (`# LIVRE I — …`).
La référence donnée par le modèle reste affichée à côté — deux sources, et
leur désaccord se voit.

## Ce que la recherche tolère, et pourquoi

| Écart | Exemple | Raison |
|---|---|---|
| casse, espaces, retours à la ligne | « La  destination » | une citation se recopie sur une ligne |
| apostrophes et guillemets typographiques | ’ « » contre ' " | le modèle les normalise souvent |
| emphase Markdown | `**Article 5**` | le modèle cite le texte, pas la balise |
| un repère de page au milieu | une phrase à cheval sur deux pages | le repère n'est pas du texte de l'acte |
| une coupure marquée […] ou … | une clause longue abrégée | chaque morceau doit être retrouvé, dans l'ordre |

Rien d'autre : un mot changé fait échouer la recherche, et c'est voulu.

Module PUR : ni base, ni appel.
"""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass
from typing import Optional

#: Un repère de page de la transcription : ⟦ RCP 1993 — PDF p. 45 — folio 44 ⟧.
_REPERE = re.compile(r"⟦([^⟧]*)⟧")
#: Un titre de premier niveau — l'acte (« # LIVRE I — … »).
_TITRE_1 = re.compile(r"^# +(.+?)\s*$", re.MULTILINE)
#: Une coupure dans une citation.
_COUPURE = re.compile(r"\[\s*(?:…|\.\.\.)\s*\]|…|\.\.\.")
#: Un morceau plus court ne prouve rien : « de la » se trouve partout.
MIN_MORCEAU = 12

_EQUIVALENTS = {
    "’": "'",
    "‘": "'",
    "`": "'",
    "«": '"',
    "»": '"',
    "“": '"',
    "”": '"',
    "–": "-",
    "—": "-",
    "\xa0": " ",
    " ": " ",
}
#: L'emphase Markdown et les marques de citation : retirées des deux côtés.
_IGNORES = set("*_#>")


@dataclass
class Extrait:
    """Un extrait tel que l'écran le montre."""

    citation: str
    #: La référence DONNÉE par le modèle.
    reference: str
    #: Ce que l'extrait établit, selon le modèle.
    apport: str
    #: Retrouvé dans le texte chargé — vérifié par le code.
    verifie: bool
    #: Le repère ⟦ … ⟧ qui le précède, quand il a été retrouvé.
    page: Optional[str] = None
    #: L'acte (le titre de premier niveau) qui le contient.
    acte: Optional[str] = None
    #: `reglement` ou `ag` — déduit de sa POSITION dans le texte, jamais du modèle ;
    #: `None` s'il n'a pas été retrouvé, ou sans décision d'AG jointe (29/10/2026).
    source: Optional[str] = None


def _normaliser(texte: str, sauter: list[tuple[int, int]] = ()) -> tuple[str, list[int]]:
    """Le texte normalisé, et pour chaque caractère sa position dans l'original.

    `sauter` : des intervalles de l'original à ignorer (les repères de page).
    """
    sortie: list[str] = []
    positions: list[int] = []
    zones = iter(sorted(sauter))
    zone = next(zones, None)
    for i, c in enumerate(texte):
        while zone is not None and i >= zone[1]:
            zone = next(zones, None)
        if zone is not None and zone[0] <= i < zone[1]:
            continue
        c = _EQUIVALENTS.get(c, c)
        if c in _IGNORES:
            continue
        if c.isspace():
            if sortie and sortie[-1] == " ":
                continue
            c = " "
        sortie.append(c.lower())
        positions.append(i)
    return "".join(sortie), positions


class Index:
    """Le texte d'un règlement, préparé une fois pour toutes ses citations."""

    def __init__(self, texte: str):
        self.texte = texte
        self.reperes = [(m.start(), m.group(1).strip()) for m in _REPERE.finditer(texte)]
        self.titres = [(m.start(), m.group(1).strip()) for m in _TITRE_1.finditer(texte)]
        sauter = [(m.start(), m.end()) for m in _REPERE.finditer(texte)]
        self.normal, self.positions = _normaliser(texte, sauter)

    def trouver(self, citation: str) -> Optional[int]:
        """La position, dans l'original, du début de la citation — ou `None`."""
        morceaux = [
            m.strip(" .,;:\"'") for m in (_normaliser(x)[0] for x in _COUPURE.split(citation))
        ]
        morceaux = [m for m in morceaux if m]
        if not morceaux or all(len(m) < MIN_MORCEAU for m in morceaux):
            return None
        debut: Optional[int] = None
        curseur = 0
        for m in morceaux:
            if len(m) < MIN_MORCEAU and debut is not None:
                continue
            trouve = self.normal.find(m, curseur)
            if trouve < 0:
                return None
            if debut is None:
                debut = trouve
            curseur = trouve + len(m)
        return None if debut is None else self.positions[debut]

    @staticmethod
    def _dernier(liste: list[tuple[int, str]], position: int) -> Optional[str]:
        avant = [libelle for debut, libelle in liste if debut <= position]
        return avant[-1] if avant else None

    def situer(self, position: int) -> tuple[Optional[str], Optional[str]]:
        """(page, acte) d'une position de l'original."""
        acte = self._dernier(self.titres, position)
        if acte and " — " in acte:
            acte = acte.split(" — ", 1)[0]
        return self._dernier(self.reperes, position), acte


#: Les deux sources d'un extrait — et l'ordre où l'écran les montre.
SOURCE_REGLEMENT = "reglement"
SOURCE_AG = "ag"


def source_de(position: Optional[int], debut_ag: Optional[int]) -> Optional[str]:
    """PURE. D'où vient un extrait retrouvé : le règlement, ou une AG."""
    if position is None or debut_ag is None:
        return None
    return SOURCE_AG if position >= debut_ag else SOURCE_REGLEMENT


def verifier(texte: str, bruts: list[dict], debut_ag: Optional[int] = None) -> list[Extrait]:
    """PURE. Les extraits bruts du modèle, recherchés dans le texte et situés.

    `debut_ag` : où commencent les décisions d'AG dans `texte` (`TexteAssemble`).
    Sans décision jointe, la source reste vide — l'écran n'a qu'une liste."""
    index = Index(texte)
    sortie = []
    for b in bruts:
        position = index.trouver(b["citation"])
        page, acte = index.situer(position) if position is not None else (None, None)
        sortie.append(
            Extrait(
                citation=b["citation"],
                reference=b.get("reference", ""),
                apport=b.get("apport", ""),
                verifie=position is not None,
                page=page,
                acte=acte,
                source=source_de(position, debut_ag),
            )
        )
    return sortie


def en_json(extraits: list[Extrait]) -> list[dict]:
    return [asdict(e) for e in extraits]


__all__ = ["SOURCE_AG", "SOURCE_REGLEMENT", "Extrait", "Index", "en_json", "source_de", "verifier"]
