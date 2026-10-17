"""L'alias d'une copropriété : `code postal` + nom, normalisés en nom d'hôte (#1894).

Spec §4.1 bis, règles 3 et 4 : `75015` + « Les Tilleuls » → `75015-les-tilleuls`,
d'où l'adresse dérivée `75015-les-tilleuls.<hôte commun>`. Accents, casse,
ponctuation et espaces sont normalisés (`utils/slug.en_slug`) ; il ne reste que des
minuscules, des chiffres et des tirets — jamais `_`, interdit dans un nom d'hôte.

L'alias est une CLÉ DE RECHERCHE, pas une identité : l'identifiant de la copropriété
ne change pas quand son nom change, et l'ancien alias redirige vers le nouveau.

Il commence TOUJOURS par cinq chiffres : il ne peut donc jamais valoir un nom fixe
de l'hébergeur (`www`, `registre`…), ni un chemin du site (`/auth`, `/tableau-de-bord`).
"""

from __future__ import annotations

import re

from app.utils.slug import en_slug

#: Un code postal français : cinq chiffres (la Corse compris, `20xxx`).
MOTIF_CODE_POSTAL = re.compile(r"\d{5}")

#: La forme d'un alias : le code postal, puis au moins un mot.
MOTIF_ALIAS = re.compile(r"\d{5}(-[a-z0-9]+)+")

#: Un label de nom d'hôte : 63 caractères au plus (RFC 1035) ; un nom complet, 253.
LONGUEUR_LABEL = 63
LONGUEUR_NOM = 253

_LABEL = re.compile(r"[a-z0-9]([a-z0-9-]*[a-z0-9])?")


def alias_de(code_postal: str, nom: str) -> str | None:
    """L'alias que forment ce code postal et ce nom, ou `None` s'ils n'en forment pas.

    La correspondance est EXACTE après normalisation : « les tilleuls » et
    « Les Tilleuls » forment le même alias, « tilleuls » un autre. Ni préfixe, ni
    proximité — l'aiguillage ne devine rien (règle 5).
    """
    cp = (code_postal or "").strip()
    if not MOTIF_CODE_POSTAL.fullmatch(cp):
        return None
    mots = en_slug(nom or "")
    if not mots:
        return None
    alias = f"{cp}-{mots}"
    return alias if est_alias(alias) else None


def est_alias(valeur: str) -> bool:
    """`valeur` a-t-elle la forme d'un alias, et tient-elle dans un label de nom d'hôte ?"""
    return len(valeur) <= LONGUEUR_LABEL and MOTIF_ALIAS.fullmatch(valeur) is not None


def est_nom_d_hote(valeur: str) -> bool:
    """Un nom d'hôte valide, en minuscules : labels de lettres, chiffres et tirets,
    au moins deux labels — jamais une adresse IP, jamais `_`."""
    if not valeur or len(valeur) > LONGUEUR_NOM:
        return False
    labels = valeur.split(".")
    if len(labels) < 2 or labels[-1].isdigit():
        return False
    return all(len(lab) <= LONGUEUR_LABEL and _LABEL.fullmatch(lab) for lab in labels)
