"""Les ÉTIQUETTES d'un compte dans la liste des utilisateurs (Admin) — Loti, TC,
Vigik, Bail — et leur TROISIÈME état : « sans objet » (26/09/2026).

Chaque étiquette était verte ou rouge. Rouge disait « non » — et se lisait
« anomalie » : une copropriétaire sans parking portait un « TC » rouge alors
qu'il n'y avait aucune télécommande à lui rattacher, un propriétaire
d'un seul parking un « Vigik » rouge. Signalé à l'écran, capture à
l'appui ; arbitré : une pastille grise « sans objet ».

La règle, et elle seule :

| Étiquette | Sans objet quand… |
|---|---|
| TC | aucun lot actif de type parking (`TELECOMMANDE.types_lot`) |
| Vigik | aucun lot actif de type appartement (`VIGIK.types_lot`) |
| Bail | le profil n'est ni copropriétaire bailleur, ni locataire |
| Loti | jamais : tout compte résident est censé avoir un lot |

Ce qui EST présent reste vert, quel que soit le profil : l'étiquette dit ce qui
existe avant de dire ce qui manque. PURE : les ensembles viennent de l'appelant.
"""

from __future__ import annotations

#: Les profils pour qui un bail a un sens.
STATUTS_AVEC_BAIL = frozenset({"copropriétaire_bailleur", "locataire"})

OK, MANQUE, SANS_OBJET = "ok", "manque", "sans_objet"


def etat(present: bool, applicable: bool) -> str:
    """Vert si présent ; sinon rouge s'il était attendu, gris s'il n'a pas lieu d'être."""
    if present:
        return OK
    return MANQUE if applicable else SANS_OBJET


def etiquettes(
    *,
    a_lot: bool,
    a_tc: bool,
    a_vigik: bool,
    a_bail: bool,
    types_lots: set[str],
    statut: str,
    types_tc: tuple[str, ...],
    types_vigik: tuple[str, ...],
) -> dict[str, str]:
    """L'état des quatre étiquettes d'un compte."""
    return {
        "loti": etat(a_lot, True),
        "tc": etat(a_tc, bool(types_lots & set(types_tc))),
        "vigik": etat(a_vigik, bool(types_lots & set(types_vigik))),
        "bail": etat(a_bail, statut in STATUTS_AVEC_BAIL),
    }
