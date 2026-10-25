"""Ce qu'un copropriétaire doit savoir sur SON lot, avant qu'il ne le demande (#2215).

« Mes lots » montre ce que l'état descriptif dit d'un lot : où il est, ce qui le dessert,
ses tantièmes. Quand cette désignation est incomplète — ou quand le règlement lui-même ne
tombe pas juste —, l'écran le DIT sur la carte du lot au lieu de montrer un champ vide
dont on ne sait s'il est inconnu ou sans objet.

Des constats, dans la forme commune du patrimoine (`utils/constats`) : l'écran les rend
par le même composant que l'administration (`ConstatsLots`). Ils ne cèdent à personne
le droit d'EXPLIQUER, jamais celui de refuser : aucun n'est bloquant.

🔴 Aucune donnée personnelle : un constat parle du lot et du règlement, jamais d'un compte.

La décision est PURE (`alertes_du_lot`) ; la lecture des sommes de clés vit dans
`utils/lecture_lots`, qui l'appelle.
"""

from __future__ import annotations

from typing import Optional

from app.models.copropriete import NatureLot
from app.utils.constats import AVERTISSEMENT, INFORMATION, Constat, constat
from app.utils.designation_lot import NATURES_ANNEXES
from app.utils.montants import montant_fr


def alertes_du_lot(
    nature_declaree: Optional[NatureLot],
    nature: Optional[NatureLot],
    etage: Optional[int],
    numero_usage: Optional[str],
    desservi: bool,
    voit_les_tantiemes: bool,
    parts: list[tuple[str, int, int]],
    cles_en_ecart: list[tuple[str, int, int]],
) -> list[Constat]:
    """Les constats d'un lot — fonction PURE, du plus important au moins important.

    `nature_declaree` : celle que l'état descriptif a posée (`None` tant qu'il n'est pas
    appliqué) ; `nature` : la déclarée, sinon celle que le type désigne. `parts` : les
    `(libellé, numérateur, dénominateur)` du lot ; `cles_en_ecart` : les
    `(libellé, dénominateur, somme)` des clés dont il fait partie et dont la somme, sur
    tous les lots, n'est pas le dénominateur déclaré.
    """
    if nature_declaree is None:
        return [
            constat(
                "designation_absente",
                INFORMATION,
                "La désignation de ce lot selon le règlement n'est pas encore importée : "
                "porte ou place, desserte et tantièmes s'afficheront ici quand elle le sera.",
            )
        ]
    trouves: list[Constat] = []
    if nature in NATURES_ANNEXES and not desservi:
        trouves.append(
            constat(
                "sans_circulation",
                AVERTISSEMENT,
                "Aucune circulation ne dessert ce lot dans l'application : il ne vous ouvre "
                "ni ascenseur ni escalier. Signalez-le au conseil syndical si le règlement "
                "en prévoit une.",
            )
        )
    if voit_les_tantiemes and not parts:
        trouves.append(
            constat(
                "sans_tantieme",
                AVERTISSEMENT,
                "Aucun tantième n'est enregistré pour ce lot : ses charges ne peuvent pas "
                "être expliquées ici.",
            )
        )
    for libelle, denominateur, somme in cles_en_ecart:
        ecart = denominateur - somme
        sens = (
            f"il en manque {montant_fr(ecart, '')}"
            if ecart > 0
            else f"il y en a {montant_fr(-ecart, '')} de trop"
        )
        trouves.append(
            constat(
                "cle_en_ecart",
                AVERTISSEMENT,
                f"« {libelle} » : les parts lues dans le règlement totalisent "
                f"{montant_fr(somme, '')} pour {montant_fr(denominateur, '')} — {sens}. "
                "Votre part reste celle du règlement ; l'écart est à vérifier à la source.",
            )
        )
    if nature in NATURES_ANNEXES and not numero_usage:
        trouves.append(
            constat(
                "sans_numero_usage",
                INFORMATION,
                "Le numéro de la place ou de la cave n'est pas renseigné.",
            )
        )
    if etage is None:
        trouves.append(
            constat("sans_niveau", INFORMATION, "Le niveau de ce lot n'est pas renseigné.")
        )
    return trouves
