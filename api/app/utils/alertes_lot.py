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


def note_de_cle(denominateur: int, somme: int) -> str | None:
    """PURE. Ce qu'il faut savoir d'une clé dont les parts ne font pas le dénominateur (#2251).

    Dit une fois sous la clé, sans alarmer : c'est la copropriété qui n'est pas complète
    au règlement (une division non reportée, un acte manquant), pas la part du lecteur.
    `None` quand la clé tombe juste.
    """
    ecart = denominateur - somme
    if ecart == 0:
        return None
    sens = (
        f"il en manque {montant_fr(ecart, '')}, encore à reporter depuis les actes"
        if ecart > 0
        else f"il y en a {montant_fr(-ecart, '')} de trop, à vérifier dans les actes"
    )
    return (
        f"Les parts que le règlement attribue à l'ensemble des lots totalisent "
        f"{montant_fr(somme, '')} pour {montant_fr(denominateur, '')} : {sens}. "
        "Votre part, elle, est celle de l'acte."
    )


def alertes_du_lot(
    nature_declaree: Optional[NatureLot],
    nature: Optional[NatureLot],
    etage: Optional[int],
    numero_usage: Optional[str],
    desservi: bool,
    voit_les_tantiemes: bool,
    parts: list[tuple[str, int, int]],
    numerotee: bool,
) -> list[Constat]:
    """Les constats d'un lot — fonction PURE, du plus important au moins important.

    `nature_declaree` : celle que l'état descriptif a posée (`None` tant qu'il n'est pas
    appliqué) ; `nature` : la déclarée, sinon celle que le type désigne. `parts` : les
    `(libellé, numérateur, dénominateur)` du lot. `numerotee` : la copropriété numérote-
    t-elle les lots de cette nature (au moins un a son numéro de porte ou de place) ?

    ⚠️ L'écart d'une CLÉ (la somme de tous les lots ≠ le dénominateur) n'est plus une
    alerte du lot (#2251) : il concerne la copropriété, pas cette part, et se dit une
    fois sous la clé, dans le tableau des charges (`note_de_cle`).
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
    #  Seulement si la copropriété numérote ce genre de lot : un règlement qui ne numérote
    #  pas les caves les laisse toutes sans numéro, et l'alerte se lisait comme un oubli —
    #  « or le numéro de ma cave est renseigné : 417 », qui est celui du LOT (25/10/2026).
    if nature in NATURES_ANNEXES and not numero_usage and numerotee:
        quoi = "de la place" if nature == NatureLot.parking else "de la cave"
        trouves.append(
            constat(
                "sans_numero_usage",
                INFORMATION,
                f"Le numéro {quoi} (celui de sa porte ou de son marquage, distinct du numéro "
                "de lot) n'est pas renseigné.",
            )
        )
    if etage is None:
        trouves.append(
            constat("sans_niveau", INFORMATION, "Le niveau de ce lot n'est pas renseigné.")
        )
    return trouves
