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

## La rubrique et le renvoi (08/11/2026, #2597)

Le recueil n'a pas d'articles numérotés : le « § » d'un extrait est le chemin
des titres qui le contiennent — le chapitre (`## CHAPITRE DEUX : CHARGES`), puis
la section (`### ASSURANCES`) ; pour une AG, la résolution
(`## Résolution n° 7 — …`). Il est DÉDUIT du texte, comme la page.

Le renvoi (`R1`, `AG2`) relie une phrase de l'avis à son extrait. Le modèle le
propose, le code le garde s'il est cohérent — préfixe conforme à la source
retrouvée, numéro libre —, sinon en attribue un (`attribuer_renvois`). Un renvoi
cité dans l'avis sans extrait derrière se relève (`renvois_sans_extrait`).

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
#: Un titre de chapitre ou de section — niveaux 2 à 4 (`## CHAPITRE…`, `### ASSURANCES`).
_TITRE_RUBRIQUE = re.compile(r"^(#{2,4}) +(.+?)\s*$", re.MULTILINE)
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
    #: Le chapitre, puis la section qui le contiennent — ou la résolution d'une AG.
    #: Déduit du texte, comme la page (08/11/2026).
    rubrique: Optional[str] = None
    #: Le renvoi par lequel l'avis le cite : `R1`, `AG2`… (`attribuer_renvois`).
    renvoi: Optional[str] = None


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


def _titre_propre(titre: str) -> str:
    """Un titre sans emphase Markdown ni deux-points final, borné."""
    return titre.replace("*", "").strip(" :")[:200]


class Index:
    """Le texte d'un règlement, préparé une fois pour toutes ses citations."""

    def __init__(self, texte: str):
        self.texte = texte
        self.reperes = [(m.start(), m.group(1).strip()) for m in _REPERE.finditer(texte)]
        self.titres = [(m.start(), m.group(1).strip()) for m in _TITRE_1.finditer(texte)]
        self.rubriques = [
            (m.start(), len(m.group(1)), _titre_propre(m.group(2)))
            for m in _TITRE_RUBRIQUE.finditer(texte)
        ]
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

    def rubrique_de(self, position: int) -> Optional[str]:
        """Le chemin des titres qui contiennent une position : le dernier titre de
        niveau 2 (chapitre, résolution), puis le dernier plus fin qui le suit."""
        avant = [r for r in self.rubriques if r[0] <= position]
        chapitres = [r for r in avant if r[1] == 2]
        if not chapitres:
            return avant[-1][2] if avant else None
        chapitre = chapitres[-1]
        sections = [r for r in avant if r[1] > 2 and r[0] > chapitre[0]]
        if not sections:
            return chapitre[2]
        return f"{chapitre[2]} › {sections[-1][2]}"[:300]


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
                rubrique=index.rubrique_de(position) if position is not None else None,
                renvoi=b.get("renvoi") or None,
            )
        )
    return attribuer_renvois(sortie)


# ── Les renvois ────────────────────────────────────────────────────────────

_RENVOI = re.compile(r"^(R|AG)([1-9][0-9]?)$")
#: Un renvoi dans le texte de l'avis : `[R2]`, `[AG1]`, `[R1, R3]`.
_GROUPE_RENVOIS = re.compile(r"\[\s*((?:R|AG)\d+(?:\s*[,;]\s*(?:R|AG)\d+)*)\s*\]")
_CODE_RENVOI = re.compile(r"(?:R|AG)\d+")


def _prefixe(source: Optional[str]) -> str:
    return "AG" if source == SOURCE_AG else "R"


def _renvoi_propre(brut: Optional[str]) -> str:
    return (brut or "").strip().strip("[]").replace(" ", "").upper()


def attribuer_renvois(extraits: list[Extrait]) -> list[Extrait]:
    """PURE. Un renvoi unique et cohérent par extrait.

    Le renvoi proposé par le modèle est gardé quand son préfixe dit la source que
    le CODE a retrouvée (`R` pour le règlement, `AG` pour une décision) et que son
    numéro n'est pas déjà pris ; sinon l'extrait reçoit le premier numéro libre de
    son préfixe. Un extrait non retrouvé se range avec le règlement, comme à l'écran."""
    pris: set[str] = set()
    for e in extraits:
        voulu = _renvoi_propre(e.renvoi)
        coherent = _RENVOI.match(voulu) and voulu.startswith(_prefixe(e.source))
        if coherent and voulu not in pris:
            e.renvoi = voulu
            pris.add(voulu)
        else:
            e.renvoi = None
    for e in extraits:
        if e.renvoi is None:
            prefixe, n = _prefixe(e.source), 1
            while f"{prefixe}{n}" in pris:
                n += 1
            e.renvoi = f"{prefixe}{n}"
            pris.add(e.renvoi)
    return extraits


def renvois_cites(*textes: Optional[str]) -> list[str]:
    """PURE. Les renvois écrits dans les textes d'un avis, sans doublon, dans l'ordre."""
    vus: list[str] = []
    for texte in textes:
        for groupe in _GROUPE_RENVOIS.findall(texte or ""):
            for code in _CODE_RENVOI.findall(groupe):
                if code not in vus:
                    vus.append(code)
    return vus


def sans_renvois(texte: Optional[str]) -> str:
    """PURE. Le texte d'un avis sans ses renvois — pour l'aperçu d'une carte, le fil
    et la FAQ, où « [R2] » ne renverrait à rien. L'espace qui les précède part avec eux."""
    return re.sub(r"\s*" + _GROUPE_RENVOIS.pattern, "", texte or "")


def renvois_sans_extrait(textes: list[Optional[str]], extraits: list[dict]) -> list[str]:
    """PURE. Les renvois cités par l'avis qu'aucun extrait ne porte — l'écran le dit
    plutôt que de laisser un [R4] qui ne mène nulle part."""
    portes = {e.get("renvoi") for e in extraits}
    return [c for c in renvois_cites(*textes) if c not in portes]


def en_json(extraits: list[Extrait]) -> list[dict]:
    return [asdict(e) for e in extraits]


__all__ = [
    "SOURCE_AG",
    "SOURCE_REGLEMENT",
    "Extrait",
    "Index",
    "attribuer_renvois",
    "en_json",
    "renvois_cites",
    "renvois_sans_extrait",
    "sans_renvois",
    "source_de",
    "verifier",
]
