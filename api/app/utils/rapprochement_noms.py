"""Deux noms désignent-ils la même personne ? — la comparaison seule.

Extrait de `utils/auto_match_service.py` le 28/09/2026, au fil de l'eau (#779) :
le service faisait 573 lignes et mêlait deux notions — COMPARER des noms (pur :
aucune base, aucune session) et RATTACHER les lignes d'import à un compte.
Cinq modules importaient déjà ces fonctions depuis le service, faute d'un lieu
à elles (`resolution_lots`, `resolution_acces`, `rattachement_bailleur`,
`lot_des_imports`) ; elles l'ont.
"""

from __future__ import annotations

import re
import unicodedata
from typing import Optional


def _cle_de_nom(s: Optional[str]) -> str:
    """La clé de COMPARAISON d'un nom — pas la normalisation d'une cellule (#829).

    🔴 Cette fonction s'appelait `_norm`, comme celle de `routers/lots.py` — qui
    fait autre chose. Deux homonymes au comportement différent dans deux fichiers
    voisins, et la conséquence était visible dix lignes plus bas : il avait fallu
    réécrire la BONNE version à l'intérieur d'une fonction (`_norm2`) pour
    l'avoir sous la main. Un nom qui ment produit une copie, pas une erreur.

    Ce qu'elle fait de plus que `import_xlsx.normaliser` : elle réduit
    apostrophes, traits d'union et ponctuation à des séparateurs neutres, pour
    que « O'Brien », « O BRIEN » et « O-Brien » s'apparient. C'est une tolérance
    volontaire, et elle n'a rien à faire dans la lecture d'un classeur.
    """
    if not s:
        return ""
    s = s.strip().casefold()
    s = "".join(c for c in unicodedata.normalize("NFKD", s) if unicodedata.category(c) != "Mn")
    # Uniformise apostrophes/traits d'union/ponctuation en séparateurs neutres.
    s = re.sub(r"[^0-9a-z]+", " ", s)
    return " ".join(s.split())


def _split_name_candidates(raw_name: Optional[str]) -> list[str]:
    """Découpe une cellule de noms potentiellement multi-occupants en candidats."""
    if not raw_name:
        return []
    raw = str(raw_name).strip()
    if not raw:
        return []
    # Séparateurs rencontrés dans les imports : ';', '/', '|', '&', '+', ' ET ', ' OU '.
    parts = re.split(r"\s*(?:;|/|\||&|\+)\s*|\s+(?:et|ou)\s+", raw, flags=re.IGNORECASE)
    return [p.strip() for p in parts if p and p.strip()]


def _tokens(s: Optional[str]) -> list[str]:
    """Retourne les tokens significatifs (>3 car) d'une chaîne normalisée."""
    return [t for t in _cle_de_nom(s).split() if len(t) > 3]


def _user_keys(nom: str, prenom: str) -> set[str]:
    """Ensemble des clés de recherche pour un user.

    N'inclut PAS le prénom seul ni les tokens individuels du nom
    pour éviter les faux positifs (ex. prénom commun "PHILIPPE"
    qui matcherait un autre copropriétaire homonyme de prénom).

    Clés générées :
      - NOM complet normalisé (ex. "de la fontaine" ou "dupont")
      - NOM PRENOM et PRENOM NOM
      - Variantes compactes (sans espaces) des combinaisons
    """
    n = _cle_de_nom(nom)
    p = _cle_de_nom(prenom)
    keys = set()
    if n:
        keys.add(n)
        keys.add(n.replace(" ", ""))
        # PAS de tokens individuels du nom — trop de faux positifs
    # PAS de prénom seul — "philippe" matcherait tout le monde
    if n and p:
        keys.add(f"{n} {p}")
        keys.add(f"{p} {n}")
        keys.add(f"{n}{p}".replace(" ", ""))
        keys.add(f"{p}{n}".replace(" ", ""))
    return keys


def _matches_user(raw_name: str, user_keys: set[str]) -> bool:
    """True si le nom brut de l'Excel correspond au user.

    Stratégies (du plus strict au plus souple) :
      1. Nom complet normalisé exact (ex. "dupont jean")
      2. Variante compacte sans espaces (ex. "dupontjean")
      3. Bigrammes consécutifs pour noms avec bruit (ex. "M. DUPONT JEAN")
      4. Chaque mot significatif (>3 car) testé contre les clés NOM
         (gère "M. DUPONT" → "dupont", mais aussi "ABEL CARON" → "caron")
         user_keys ne contient PAS le prénom seul → pas de faux positif.
    """
    for part in _split_name_candidates(raw_name):
        norm = _cle_de_nom(part)
        if not norm:
            continue
        if norm in user_keys:
            return True
        compact = norm.replace(" ", "")
        if compact and compact in user_keys:
            return True
        # Bigrammes pour capter "NOM PRENOM" avec ponctuation/titres bruitées
        words = [w for w in norm.split() if len(w) > 2]
        for i in range(len(words) - 1):
            if f"{words[i]} {words[i + 1]}" in user_keys:
                return True
        # Tenter chaque mot significatif individuellement contre les clés NOM.
        # user_keys ne contient PAS le prénom seul → pas de faux positif
        # sur un prénom commun. Permet de matcher "ABEL CARON" → user "Christophe CARON"
        # via la clé NOM "caron".
        for w in words:
            if len(w) > 3 and w in user_keys:
                return True
    return False
