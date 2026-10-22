"""Les CHAMPS d'un texte légal, et leur rendu pour la copropriété servie (#2065).

Le gabarit du produit (`seed/contenus_legaux.py`) et le texte que l'administrateur
édite portent des champs — `[[copropriete]]`, `[[syndic]]`, `[[operateur]]`… —
que `rendre` remplace par l'identité de la copropriété servie
(`identite.identite_legale`). Un même texte nomme donc, pour chaque copropriété,
SON syndicat et SON syndic : il ne se recopie pas d'une copropriété à l'autre.

🔴 Un champ sans valeur se rend « À RENSEIGNER », suivi de ce qui manque — jamais
vide : une page publique qui tait l'éditeur a l'air finie, et personne ne la lit
jusqu'à ce que quelqu'un cherche qui contacter (03/09/2026, en tête du gabarit).
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from html import escape

from app.utils.textes_legaux.identite import IdentiteLegale

#: La marque d'une mention manquante — la même dans le gabarit et dans le rendu.
A_RENSEIGNER = "À RENSEIGNER"

#: Où l'opérateur renseigne ce qui appartient à l'INSTALLATION, pas à la copropriété.
_PAR_L_OPERATEUR = "réglage de l'installation ({}), par son opérateur"


@dataclass(frozen=True)
class Champ:
    nom: str
    #: Ce qui manque, dit à l'administrateur ET sur la page publique.
    libelle: str
    #: Où le renseigner.
    ou: str
    #: Une adresse électronique : rendue en lien `mailto:`.
    courriel: bool = False


#: 🔴 La SEULE liste des champs : le rendu, le constat et l'écran la lisent.
CHAMPS: tuple[Champ, ...] = (
    Champ("copropriete", "le nom de la copropriété", "Administration › Copropriété › Identité"),
    Champ(
        "adresse_copropriete",
        "l'adresse de la copropriété",
        "Administration › Copropriété › Identité",
    ),
    Champ("syndic", "le nom du syndic", "Annuaire › Syndic, ou le contrat de syndic"),
    Champ("adresse_syndic", "l'adresse du syndic", "Annuaire › Syndic"),
    Champ(
        "contact",
        "l'adresse où exercer ses droits",
        "Administration › Pages légales",
        courriel=True,
    ),
    Champ("operateur", "le nom de l'opérateur", _PAR_L_OPERATEUR.format("OPERATEUR_NOM")),
    Champ(
        "adresse_operateur",
        "l'adresse de l'opérateur",
        _PAR_L_OPERATEUR.format("OPERATEUR_ADRESSE"),
    ),
    Champ(
        "contact_operateur",
        "le contact de l'opérateur",
        _PAR_L_OPERATEUR.format("OPERATEUR_CONTACT"),
        courriel=True,
    ),
    Champ("hebergeur", "l'hébergeur", _PAR_L_OPERATEUR.format("HEBERGEUR")),
    Champ("pays_donnees", "le pays des données", _PAR_L_OPERATEUR.format("HEBERGEUR_PAYS")),
)
_PAR_NOM = {c.nom: c for c in CHAMPS}

#: `[[nom]]` — des crochets doubles : ni Jinja, ni Svelte, ni l'éditeur riche ne les lisent.
MOTIF = re.compile(r"\[\[\s*([a-z_]+)\s*\]\]")


def valeur(identite: IdentiteLegale, nom: str) -> str | None:
    return getattr(identite, nom)


def _rendu(champ: Champ, identite: IdentiteLegale) -> str:
    brut = valeur(identite, champ.nom)
    if brut is None:
        return f"<strong>{A_RENSEIGNER}</strong> ({champ.libelle})"
    texte = escape(brut)
    if champ.courriel and "@" in brut:
        return f'<a href="mailto:{texte}">{texte}</a>'
    return texte


def rendre(texte: str, identite: IdentiteLegale) -> str:
    """Le texte, ses champs remplis. Un champ inconnu reste écrit tel quel : le
    constat le signale (`inconnus`), et le corriger appartient à l'administrateur."""

    def remplacer(m: re.Match) -> str:
        champ = _PAR_NOM.get(m.group(1))
        return _rendu(champ, identite) if champ else m.group(0)

    return MOTIF.sub(remplacer, texte or "")


def champs_vides(texte: str, identite: IdentiteLegale) -> list[Champ]:
    """Les champs que le texte emploie et que l'identité ne remplit pas, dans l'ordre de `CHAMPS`."""
    employes = set(MOTIF.findall(texte or ""))
    return [c for c in CHAMPS if c.nom in employes and valeur(identite, c.nom) is None]


def inconnus(texte: str) -> list[str]:
    """Les champs écrits dans le texte que `CHAMPS` ne connaît pas — une faute de frappe."""
    return sorted({n for n in MOTIF.findall(texte or "") if n not in _PAR_NOM})


def mentions_a_renseigner(texte: str) -> int:
    """Les « À RENSEIGNER » écrits EN TOUTES LETTRES dans le texte source : ceux qu'aucun
    champ ne remplit (quel groupe de messagerie, quel fournisseur d'IA…)."""
    return (texte or "").count(A_RENSEIGNER)
