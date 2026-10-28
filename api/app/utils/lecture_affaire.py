"""« QUI LA LIT » — le libellé court d'une affaire, pour un document du serveur (#2089).

À l'écran, la pastille de lecture (`PastilleLecture`, `#lib/lecture`) dit qui
lit une affaire : « Copropriétaires », « CS », « Concerné »… Le PDF du point CS
/ Syndic doit dire LA MÊME CHOSE (demandé le 20/10/2026 : « reprendre l'objet
destinataires tel qu'il apparaît sur la page affaire »), et il est rendu par le
serveur.

## La règle n'est pas recopiée : elle est EXÉCUTÉE

Les profils qui lisent se décident en posant la question à la règle du serveur
(`public_cible_visible`), pour un compte de chaque statut, sur les Destinataires
choisis par le conseil — sinon ceux de la nature de l'affaire
(`destinataires_par_defaut`), comme `ticket_visible`. Une affaire confidentielle,
ou réservée au conseil, n'en a aucun.

Seuls les LIBELLÉS sont écrits ici — ceux de `PROFILS` et des combinaisons
nommées de `front/src/lib/lecture.ts`. 🔒 `test_lecture_affaire.py` les compare
au fichier de l'écran, et compare les profils aux cas de
`tests/donnees/lecture_pastille.json`, l'attente commune de l'écran et du serveur.
"""

from __future__ import annotations

import json

from app.models.core import Utilisateur
from app.models.tickets import Ticket
from app.utils.visibility.defauts_affaire import CONCERNE, destinataires_par_defaut
from app.utils.visibility.objets import reservee_au_conseil
from app.utils.visibility.socle import _parse_json_list, public_cible_visible

#: Les profils, dans l'ordre de l'écran : (statut du compte, libellé court).
PROFILS: tuple[tuple[str, str], ...] = (
    ("copropriétaire_résident", "Occupants"),
    ("copropriétaire_bailleur", "Copro-bailleurs"),
    ("mandataire", "Bailleurs"),
    ("locataire", "Locataires"),
)

#: Les combinaisons qui ont un NOM — les autres se composent « A + B ».
NOMMEES: dict[frozenset[str], str] = {
    frozenset(s for s, _ in PROFILS): "Tous",
    frozenset({"copropriétaire_résident", "locataire"}): "Résidents",
    frozenset({"copropriétaire_résident", "copropriétaire_bailleur"}): "Copropriétaires",
    frozenset(
        {"copropriétaire_résident", "copropriétaire_bailleur", "locataire"}
    ): "Copropriétaires + locataires",
}

#: Personne d'autre que le conseil ; ou l'auteur aussi, quand la nature le veut.
CS = "CS"
CONCERNE_COURT = "Concerné"


def _codes(ticket: Ticket) -> list[str]:
    """Les Destinataires qui décident : choisis par le conseil, sinon ceux de sa nature."""
    choisis = _parse_json_list(ticket.public_cible, [])
    return list(choisis) if choisis else destinataires_par_defaut(ticket)


def statuts_lecteurs(ticket: Ticket) -> list[str]:
    """Les statuts de compte qui lisent l'affaire, dans l'ordre de `PROFILS`."""
    if reservee_au_conseil(ticket):
        return []
    codes = json.dumps(_codes(ticket), ensure_ascii=False)
    #  Un compte sans identifiant : la règle ne cherche aucune délégation.
    return [s for s, _ in PROFILS if public_cible_visible(codes, Utilisateur(statut=s))]


def lecture_courte(ticket: Ticket) -> str:
    """« Copropriétaires », « Tous », « CS », « Concerné »… — le mot de la pastille."""
    statuts = statuts_lecteurs(ticket)
    if not statuts:
        concerne = ticket.confidentiel or _codes(ticket) == [CONCERNE]
        return CONCERNE_COURT if concerne else CS
    nommee = NOMMEES.get(frozenset(statuts))
    return nommee or " + ".join(c for s, c in PROFILS if s in statuts)
