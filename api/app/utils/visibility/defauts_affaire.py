"""Les DESTINATAIRES d'une affaire SANS choix du conseil — ce que sa catégorie décide.

Extrait de `objets.py` le 28/09/2026 (#1436), qui touchait les 500 lignes en
recevant la table des défauts par catégorie. C'est une notion à part : QUI une
affaire regarde quand personne n'a choisi, que `ticket_visible` applique et que
`reservee_au_conseil` lit pour ne rien laisser sortir. Son miroir à l'écran est
`front/src/lib/lecture.ts`, et `tests/donnees/lecture_pastille.json` les tient
d'accord — un cas par catégorie.

## 🔴 Le standard du 30/09/2026 : Carnet = Affaires = Kanban

Arbitré par l'utilisateur (« ne t'écarte pas de ce nouveau standard ») : ce
qu'un copropriétaire lit au carnet d'entretien, il le lit dans les affaires et
au kanban, et réciproquement — une seule règle, `ticket_visible`, que le carnet
applique aussi. Sans choix du conseil :

* 🛠️ Panne — tous les copropriétaires, et les locataires du périmètre ;
* 🧰 Entretien — tous les copropriétaires ;
* 🏗️ Étude & travaux — le conseil seul, puis tous les copropriétaires dès
  qu'elle est en AG (ils votent), chez le prestataire, résolue ou annulée ;
* 💧 Sinistre et les autres « Résident concerné » — inchangés.

« Tous les copropriétaires » : un copropriétaire que le défaut vise le lit
dans TOUTE la résidence, quel que soit le périmètre
(`lus_dans_toute_la_residence`) ; un locataire, dans le périmètre seulement.
« Réservé au périmètre sélectionné » coché referme cette ouverture : seuls les
destinataires du périmètre lisent (22/10/2026).
Un choix du conseil (Destinataires, « Confidentielle ») prime, et se lit
toujours dans le périmètre.
"""

from __future__ import annotations

from app.models.core import Ticket
from app.models.tickets import STATUTS_ETUDE_OUVERTE
from app.utils.nature_affaire import est_actualite
from app.utils.valeurs import valeur

#: « Résident concerné » : l'auteur, la personne pour qui l'affaire a été
#: saisie, et le conseil — ce que `confidentiel` veut dire sur une affaire.
#: Un DÉFAUT, jamais un code que l'écran envoie : le conseil qui le choisit
#: coche le drapeau. Inconnu de `public_cible_visible`, il ne ferait lire
#: personne — mais `ticket_visible` le traite avant, en toutes lettres.
CONCERNE = "concerné"

#: « Copropriétaires » : occupants et bailleurs — les deux codes que proposent
#: les pastilles (`copropriétaires` ne l'est plus depuis #1301), et que l'écran
#: nomme d'un mot. Ni locataires, ni mandataires.
_COPROPRIETAIRES = ["copropriétaires_occupants", "bailleurs"]

#: Une Panne sans choix du conseil : tous les copropriétaires, et les locataires
#: de son périmètre (30/09/2026). Elle lisait ceux qui vivent dans le bâtiment
#: — occupants et locataires, pas les bailleurs — depuis #1343, et tous hors
#: bâtiment : le carnet la montrait pourtant à tous les copropriétaires.
#: Ni les mandataires, que « tous » comprenait hors bâtiment.
_DEFAUT_PANNE = [*_COPROPRIETAIRES, "locataires"]

#  Les états où une Étude & travaux sort du conseil — `STATUTS_ETUDE_OUVERTE`,
#  déclarés avec les autres listes d'états (`models/tickets.py`) : en AG, les
#  copropriétaires la votent ; chez le prestataire, résolue ou annulée, elle est
#  un fait du bâti — celui que le carnet d'entretien consigne.

#: Ce qu'une affaire lit SANS choix du conseil, selon sa catégorie (#1436,
#: arbitré le 28/09/2026). La Panne a sa règle (le bâtiment).
#:
#: 🔴 ÉTUDE & TRAVAUX : LE CONSEIL SEUL (arbitré le 29/09/2026) — tant qu'elle
#: n'est pas dans `STATUTS_ETUDE_OUVERTE` (30/09/2026). Elle gardait
#: la règle historique — les copropriétaires du périmètre — et en était la
#: dernière. Une étude est le dossier du conseil (devis, diagnostics,
#: arbitrages en cours) : il l'ouvre en choisissant ses Destinataires. La
#: règle historique n'ayant plus de catégorie, elle a quitté `ticket_visible` ;
#: une catégorie absente de cette table retombe sur `DEFAUT_INCONNU`, fermé.
#:
#: 🔴 ENTRETIEN : LES COPROPRIÉTAIRES (arbitré le 30/09/2026) — de toute la
#: résidence depuis le standard du même soir. Il revenait au
#: conseil seul depuis #1436 (« contrats, fournisseurs, pièces ») : occupants
#: et bailleurs le lisent désormais, jamais les locataires ni les mandataires.
#: Les maintenances que 0232 avait adressées au conseil reviennent à la règle
#: (migration 0243). Le conseil garde la main : Destinataires ou
#: « Confidentielle » le referment, affaire par affaire.
#:
#: Une nuisance nomme souvent un voisin, un sinistre touche un lot, une
#: question est personnelle : les lire à tout un bâtiment exposait des données
#: personnelles.
#:
#: ⚠️ Miroir : `DEFAUT_PAR_CATEGORIE` (`front/src/lib/lecture.ts`), tenus
#: d'accord par `tests/donnees/lecture_pastille.json` — un cas par catégorie.
DEFAUT_PAR_CATEGORIE: dict[str, list[str]] = {
    "nuisance": [CONCERNE],
    "acces_accueil": [CONCERNE],
    "espaces_verts": ["résidents"],
    "sinistre": [CONCERNE],
    "etude_travaux": ["conseil_syndical"],
    "entretien": _COPROPRIETAIRES,
    "question": [CONCERNE],
    "bug": [CONCERNE],
}

#: Une catégorie que la table ne connaît pas : le conseil seul. Une donnée
#: inattendue ne peut que restreindre (#789) — `test_destinataires_affaire`
#: exige que chaque catégorie y figure, pour que ce repli ne serve jamais.
DEFAUT_INCONNU = ["conseil_syndical"]

#: Les défauts qui ne laissent lire que le conseil — et l'auteur : rien ne sort.
_DEFAUTS_FERMES = ([CONCERNE], ["conseil_syndical"])


def destinataires_par_defaut(ticket: Ticket) -> list[str]:
    """Les Destinataires qu'une affaire a SANS choix du conseil : ceux de sa
    catégorie (#1343, #1436) — et de son état pour une Étude & travaux
    (standard du 30/09/2026, voir l'en-tête du module).

    ⚠️ Miroir : `destinatairesParDefaut` (`front/src/lib/lecture.ts`), tenus
    d'accord par `tests/donnees/lecture_pastille.json`.
    """
    #  Une actualité s'adresse à tous (`actualite_visible` en décide, pas
    #  cette table) — miroir de l'écran. Sans ce cas, elle tomberait sur
    #  `DEFAUT_INCONNU` et `reservee_au_conseil` la retiendrait du hall.
    if est_actualite(ticket):
        return ["résidents"]
    categorie = valeur(ticket.categorie)
    if categorie == "panne":
        return _DEFAUT_PANNE
    if categorie == "etude_travaux" and valeur(ticket.statut) in STATUTS_ETUDE_OUVERTE:
        return _COPROPRIETAIRES
    return DEFAUT_PAR_CATEGORIE.get(categorie, DEFAUT_INCONNU)


def lus_dans_toute_la_residence(ticket: Ticket) -> list[str]:
    """Les codes du défaut qui lisent l'affaire QUEL QUE SOIT son périmètre.

    Les copropriétaires que le défaut vise, et eux seuls : « tous les
    copropriétaires » (standard du 30/09/2026) — le carnet d'entretien, qui
    leur montre le bâti de toute la résidence, ne doit rien leur montrer que
    les affaires leur cachent. Un locataire, lui, lit dans le périmètre.

    Vide pour une actualité (sa règle est ailleurs) : ce n'est pas un défaut
    d'affaire. `ticket_visible` ne l'appelle que sans choix du conseil.

    🔒 Vide aussi quand « Réservé au périmètre sélectionné » est coché — et
    seulement alors : seuls les destinataires DU périmètre lisent (arbitré par
    l'utilisateur le 22/10/2026, après un code d'ascenseur lu de toute la
    résidence). Miroir : `lectureDe` (`front/src/lib/lecture.ts`).
    """
    if est_actualite(ticket) or ticket.reserve_perimetre:
        return []
    return [c for c in destinataires_par_defaut(ticket) if c in _COPROPRIETAIRES]
