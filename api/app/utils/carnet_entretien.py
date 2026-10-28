"""Le carnet d'entretien — l'histoire du bâti, rassemblée depuis ce qui existe.

Obligatoire depuis le **décret n° 2001-477** : le syndic le tient, tout
copropriétaire peut le consulter, et un acquéreur peut le réclamer via son
vendeur. Il n'était nulle part — mais il était déjà **écrit**, en morceaux, dans
quatre écrans qui ne se parlent pas.

## 🔴 Une VUE, pas un module

Aucun modèle, aucune migration, aucune saisie nouvelle. Trois tables déjà
alimentées répondent chacune à une moitié de la question *« qu'est-il arrivé à ce
bâtiment ? »* :

| Source | Ce qu'elle apporte | Filtre |
|---|---|---|
| `ContratEntretien` | l'équipement suivi, son prestataire, sa périodicité | `actif` |
| `Ticket` Entretien | l'intervention réellement faite | résolue (#1092 : les événements
  du calendrier sont devenus des affaires Entretien le 23/09/2026) |
| `Ticket` du bâti | l'affaire résolue, sous sa catégorie | `ferme_le` + catégorie du bâti, hors Entretien — |
|  |  | rangé sous l'équipement désigné par le conseil, s'il l'a été (#1097) |

Créer une table `carnet` aurait produit une **quatrième** version de faits déjà
enregistrés trois fois, à ressaisir à la main et libre de diverger dès le premier
oubli. Le carnet n'a rien à retenir : il a à *relire*.

## Ce qu'il montre et que rien d'autre ne montre : les TROUS

Ranger par équipement fait apparaître ce qui manque. Un contrat dont la
`prochaine_visite` est dépassée porte une alerte — aujourd'hui, rien ne le dit :
la date existe en base, aucun écran ne la compare à aujourd'hui.

⚠️ **Ce n'est pas une alerte de plus**, c'est la même donnée lue à l'endroit où
elle veut dire quelque chose. Un contrôle réglementaire non fait depuis deux ans
ne se voit dans aucune liste triée par date de création.

## 🔴 Ce qu'un lecteur y voit : ce que les affaires lui montrent

Standard du 30/09/2026, arbitré par l'utilisateur : **Carnet = Affaires =
Kanban**. Une affaire n'entre au carnet d'un lecteur que s'il peut la LIRE
(`ticket_visible`, la règle de la liste et de la fiche) ; sinon elle en
disparaît — pas de ligne neutre. Le carnet montrait jusque-là à tout
copropriétaire le titre, le numéro et le lien de toute affaire résolue du bâti,
confidentielle ou adressée au seul conseil comprise, et la fiche refusait
ensuite de s'ouvrir. Les contrats, eux, ne sont pas des affaires : le droit du
carnet (`require_proprietaire`) les couvre.

## Ce qui n'est PAS ici

Les montants. Ils vivent dans les documents et les devis, et les faire remonter
demanderait de décider qui les voit — une question distincte de celle du carnet.
Le lot suivant, s'il est demandé.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from app.utils import horloge
from typing import Optional

from sqlmodel import Session, select

from app.models.core import Ticket, Utilisateur
from app.models.prestataires import ContratEntretien, Prestataire
from app.models.tickets import CategorieTicket, StatutTicket
from app.utils.affaire_absorbee import pas_absorbee
from app.utils.liens import lien_element, lien_ticket
from app.utils.perimetres import couvre, parse_json_perimetres
from app.utils.valeurs import valeur
from app.utils.visibility import ticket_visible

#: Les catégories de ticket qui parlent du **bâti**. Les autres — une question,
#: un signalement de bug, une nuisance de voisinage, une demande d'accès — sont
#: de la vie de la copropriété, pas de son entretien. Les inclure noierait le
#: carnet dans des faits qu'un acquéreur ou un syndic n'y cherche pas.
CATEGORIES_BATI = frozenset(
    {
        CategorieTicket.panne,
        CategorieTicket.espaces_verts,
        CategorieTicket.sinistre,
        CategorieTicket.etude_travaux,
        CategorieTicket.entretien,  # les maintenances du calendrier (#1092)
    }
)


def est_du_bati(categorie) -> bool:
    """La catégorie parle-t-elle du bâti ? — énumération ou valeur, indifféremment.

    🔒 La seule lecture de `CATEGORIES_BATI` hors de ce module passe par ici
    (`test_synthese_eligibilite.py`) : l'intervenant, la synthèse d'une affaire
    close et le carnet posent la même question, et une copie de l'ensemble
    divergerait à la première catégorie ajoutée.
    """
    return valeur(categorie) in {valeur(c) for c in CATEGORIES_BATI}


def contribue_au_carnet(ticket) -> bool:
    """L'affaire contribue-t-elle au carnet d'entretien ? — sa catégorie parle du bâti.

    C'est la règle d'éligibilité de la synthèse d'une affaire close (#1643,
    arbitré : « uniquement les affaires du carnet »). L'équipement n'y entre
    PAS : le carnet range une affaire sans équipement sous « Sans équipement
    rattaché » (revirement du 24/09/2026) — elle y figure, donc elle est
    éligible. v2.99.0 exigeait l'équipement, comme le disait le ticket, et
    l'utilisateur l'a relevé à l'écran : « pourquoi faut-il un équipement
    puisqu'il est dans le carnet d'entretien ? » (03/10/2026).
    """
    return est_du_bati(ticket.categorie)


@dataclass
class EntreeCarnet:
    """Un fait daté qui concerne le bâti.

    `equipement` porte la **valeur** de `TypeEquipement` (`"ascenseur"`), jamais
    son libellé : la table des libellés vit côté front (`#lib/prestataires`,
    `EQUIPEMENTS`) et `test_types_equipement.py` la compare déjà à l'énumération
    du serveur. En rendre une seconde ici en ferait une troisième écriture.
    """

    date_fait: date
    libelle: str
    origine: str  # contrat | intervention | affaire
    detail: str = ""
    #: Le n° de l'affaire (`TK-109008`) — le pied de la carte le dit (24/10/2026),
    #: il n'est plus une ligne du détail.
    numero: Optional[str] = None
    #: La VALEUR de la catégorie d'une affaire (`etude_travaux`) — l'écran la
    #: rend par son libellé. Le badge disait « Incident » pour TOUTE affaire du
    #: bâti, une étude de remplacement des pelouses comprise (26/09/2026).
    categorie: Optional[str] = None
    equipement: Optional[str] = None
    #: Les codes de périmètre de la ligne — l'écran les rend par `perimetreLabel`,
    #: comme partout ailleurs. Remplace `batiment_id` (10/09/2026) : un contrat
    #: sur « Parking » n'a pas de bâtiment, et n'en est pas moins situé.
    perimetre: list[str] = field(default_factory=list)
    lien: str = ""
    alerte: Optional[str] = None
    #: L'affaire d'où vient la ligne — pour y joindre sa synthèse validée (#1643).
    ticket_id: Optional[int] = None
    #: La synthèse VALIDÉE de l'affaire, dans la partie pliée de la ligne.
    synthese: Optional[dict] = None
    #: Les trois lignes d'aperçu de la carte (24/10/2026) : la DEMANDE de
    #: l'affaire, remplacée par « Ce qui s'est passé » quand une synthèse validée
    #: le raconte (`_joindre_syntheses`). Un contrat n'en a pas.
    extrait: str = ""

    def en_dict(self) -> dict:
        return {
            #  ISO : c'est une clé de tri et de comparaison, pas un affichage.
            #  Le format français est appliqué par l'écran, qui a `fmtDate`.
            "date": self.date_fait.isoformat(),
            "libelle": self.libelle,
            "origine": self.origine,
            "detail": self.detail,
            "numero": self.numero,
            "categorie": self.categorie,
            "equipement": self.equipement,
            "perimetre": self.perimetre,
            "lien": self.lien,
            "alerte": self.alerte,
            "synthese": self.synthese,
            "extrait": self.extrait,
        }


def _jour(valeur) -> Optional[date]:
    """La date d'un fait, que la colonne soit `date` ou `datetime`.

    ⚠️ `datetime` est une sous-classe de `date` : tester `date` en premier
    rendrait un `datetime` tel quel, et deux entrées du carnet ne se compareraient
    plus entre elles (`'<' not supported between datetime and date`).
    """
    if isinstance(valeur, datetime):
        return valeur.date()
    if isinstance(valeur, date):
        return valeur
    return None


def _codes_de(valeur: Optional[str]) -> list[str]:
    """Le périmètre d'une ligne, quelle que soit la forme de sa colonne.

    `Ticket` et `ContratEntretien` portent un tableau JSON, `Evenement` une
    chaîne simple (`"résidence"`, `"bat:3"`). Une seule lecture pour les trois :
    trois lectures auraient divergé sur le JSON illisible, et c'est toujours la
    troisième qui oublie le `try`.
    """
    if not valeur:
        return []
    texte = valeur.strip()
    if texte.startswith("["):
        return parse_json_perimetres(texte)
    return [texte]


def alerte_visite(echeance: Optional[date], aujourdhui: date) -> Optional[str]:
    """« visite attendue depuis N jours », ou rien.

    Fonction à part, et publique, pour une raison : c'est **la seule décision** de
    ce module — tout le reste est de la lecture de tables. Une décision se teste
    sans base ni session, et celle-ci a trois bords qui méritent d'être fixés :
    l'échéance absente, l'échéance du jour même, et l'accord du pluriel.

    ⚠️ Le jour même n'est **pas** un retard. Une visite attendue aujourd'hui peut
    encore avoir lieu cet après-midi ; l'annoncer en retard ferait crier le carnet
    sur un contrat parfaitement tenu — et une alerte qui crie sur du normal finit
    ignorée (`standards/04` §7).
    """
    if echeance is None or echeance >= aujourdhui:
        return None
    retard = (aujourdhui - echeance).days
    #  Le nombre de JOURS, pas « en retard » : un contrôle en retard de trois
    #  jours et un de deux ans ne demandent pas le même geste, et c'est l'écart
    #  qui le dit.
    return f"visite attendue depuis {retard} jour{'s' if retard > 1 else ''}"


def type_equipement_resolu(contrat, specialite_prestataire: Optional[str]) -> Optional[str]:
    """La catégorie d'un contrat — celle qu'il porte, ou celle de son prestataire.

    🔴 **Le carnet lisait le champ BRUT et l'écran Contrats la valeur DÉDUITE.**
    Un contrat de VMC enregistré en « autre », confié à un prestataire de
    spécialité `vmc`, apparaissait donc « VMC » dans l'onglet Contrats et
    « Autre » dans le carnet. Signalé à l'écran le 10/09/2026.

    La règle vit côté front depuis longtemps (`#lib/reporting`,
    `typeEquipementDuContrat`) et servait quatre écrans. Le carnet est le premier
    lecteur SERVEUR de cette notion : la copie est obligatoire — les contextes de
    build sont `./api` et `./front` —, et `test_type_equipement_resolu.py` refuse
    qu'elles divergent, comme pour le libellé d'étage et celui des périmètres.

    ⚠️ « autre » n'est pas une catégorie, c'est une ABSENCE de catégorie : c'est
    pour cela qu'elle laisse la spécialité du prestataire prendre le relais. Une
    catégorie réelle, elle, n'est jamais remplacée.
    """
    brut = getattr(contrat, "type_equipement", None)
    propre = str(valeur(brut)) if brut else None
    if propre and propre != "autre":
        return propre
    return specialite_prestataire or propre or "autre"


def _entrees_contrats(session: Session, perimetre: Optional[str]) -> list[EntreeCarnet]:
    """Un contrat en cours est un fait du carnet : il dit ce qui est SUIVI.

    Et sa `prochaine_visite` dépassée est le seul endroit du produit où une
    échéance d'entretien manquée devient visible.
    """
    requete = select(ContratEntretien).where(ContratEntretien.actif == True)  # noqa: E712

    aujourdhui = horloge.aujourd_hui()
    entrees: list[EntreeCarnet] = []
    for contrat in session.exec(requete).all():
        debut = _jour(contrat.date_debut)
        if debut is None:
            continue
        codes = _codes_de(contrat.perimetre_cible)
        if not couvre(codes, perimetre):
            continue
        prestataire = session.get(Prestataire, contrat.prestataire_id)
        detail = prestataire.nom if prestataire and prestataire.nom else "prestataire inconnu"
        if contrat.numero_contrat:
            detail = f"{detail} · contrat {contrat.numero_contrat}"

        alerte = alerte_visite(_jour(contrat.prochaine_visite), aujourdhui)

        entrees.append(
            EntreeCarnet(
                date_fait=debut,
                libelle=contrat.libelle,
                origine="contrat",
                detail=detail,
                equipement=type_equipement_resolu(
                    contrat, prestataire.specialite if prestataire else None
                ),
                perimetre=codes,
                lien=lien_element("contrat", contrat.id),
                alerte=alerte,
            )
        )
    return entrees


def cadre_intervention(contrat: Optional[ContratEntretien], avec_prestataire: bool) -> str:
    """« sous contrat n° 1234 », « hors contrat », ou rien sans intervenant (#1445).

    Le numéro d'un contrat est facultatif : son libellé le remplace alors.
    """
    if contrat is not None:
        if contrat.numero_contrat:
            return f"sous contrat n° {contrat.numero_contrat}"
        return f"sous contrat « {contrat.libelle} »"
    return "hors contrat" if avec_prestataire else ""


def _entrees_interventions(
    session: Session, perimetre: Optional[str], lecteur: Utilisateur
) -> list[EntreeCarnet]:
    """Ce qui a été FAIT — une affaire Entretien résolue, avec son intervenant.

    Elle lisait les événements « Terminé » du calendrier jusqu'au 23/09/2026 :
    ils sont devenus des affaires Entretien (0212), et une affaire ne se lit
    qu'une fois — ici, jamais aussi parmi les incidents.
    """
    requete = select(Ticket).where(
        Ticket.categorie == CategorieTicket.entretien,
        Ticket.statut == StatutTicket.résolu,
        pas_absorbee(),  # comptée dans sa principale (#1704)
    )
    entrees: list[EntreeCarnet] = []
    for ticket in session.exec(requete).all():
        if not ticket_visible(ticket, lecteur):
            continue
        quand = _jour(ticket.debut) or _jour(ticket.ferme_le)
        if quand is None:
            continue
        codes = _codes_de(ticket.perimetre_cible)
        if not couvre(codes, perimetre):
            continue
        prestataire = (
            session.get(Prestataire, ticket.prestataire_id) if ticket.prestataire_id else None
        )
        contrat = session.get(ContratEntretien, ticket.contrat_id) if ticket.contrat_id else None
        cadre = cadre_intervention(contrat, prestataire is not None)
        entrees.append(
            EntreeCarnet(
                date_fait=quand,
                libelle=ticket.titre,
                origine="intervention",
                #  « Otis · sous contrat n° 1234 » / « Otis · hors contrat » (#1445).
                detail=" · ".join(x for x in (prestataire.nom if prestataire else "", cadre) if x),
                #  Celui que le conseil a désigné, sinon la spécialité de
                #  l'intervenant — la règle des contrats, jamais une déduction du titre.
                equipement=ticket.equipement or (prestataire.specialite if prestataire else None),
                perimetre=codes,
                lien=lien_ticket(ticket.id),
                ticket_id=ticket.id,
                extrait=ticket.description or "",
            )
        )
    return entrees


def _entrees_affaires(
    session: Session, perimetre: Optional[str], lecteur: Utilisateur
) -> list[EntreeCarnet]:
    """Un incident résolu sur le bâti — ce que le carnet appelle un sinistre.

    L'équipement posé par le conseil (#1097) le RANGE ; son absence ne
    l'exclut pas. 🔴 Revirement, arbitré le 24/09/2026, à l'écran : « on a perdu les affaires, c'est dommage » :
    la v2.31.0 réservait le carnet aux affaires équipées, et toutes celles
    résolues auparavant — aucune n'avait d'équipement — en avaient disparu.
    Elles reviennent sous « Sans équipement rattaché », jusqu'à ce que le
    conseil les range. L'équipement n'est jamais deviné du titre (#1079) : le
    carnet est opposable.
    """
    requete = select(Ticket).where(
        Ticket.statut == StatutTicket.résolu,
        Ticket.ferme_le.isnot(None),
        pas_absorbee(),  # comptée dans sa principale (#1704)
    )

    entrees: list[EntreeCarnet] = []
    for ticket in session.exec(requete).all():
        #  L'Entretien est une INTERVENTION (ci-dessus), pas un incident.
        if not est_du_bati(ticket.categorie) or ticket.categorie == CategorieTicket.entretien:
            continue
        if not couvre(_codes_de(ticket.perimetre_cible), perimetre):
            continue
        if not ticket_visible(ticket, lecteur):
            continue
        quand = _jour(ticket.ferme_le)
        if quand is None:
            continue
        entrees.append(
            EntreeCarnet(
                date_fait=quand,
                libelle=ticket.titre,
                #  Une AFFAIRE, et sa catégorie dit laquelle : « incident » la
                #  qualifiait toutes, une étude ou des travaux compris.
                origine="affaire",
                categorie=valeur(ticket.categorie),
                numero=ticket.numero,
                equipement=ticket.equipement,
                perimetre=_codes_de(ticket.perimetre_cible),
                lien=lien_ticket(ticket.id),
                ticket_id=ticket.id,
                extrait=ticket.description or "",
            )
        )
    return entrees


def construire_carnet(
    session: Session, *, lecteur: Utilisateur, perimetre: Optional[str] = None
) -> list[dict]:
    """Le carnet de CE lecteur, du fait le plus récent au plus ancien.

    `lecteur` est obligatoire, et sans valeur par défaut : un carnet construit
    « pour personne » serait celui de tout le monde — le défaut qu'il a porté
    jusqu'au 30/09/2026.

    ⚠️ Le tri est **décroissant sur la date du fait**, pas sur la date de saisie :
    un contrat signé en 2019 et enregistré hier appartient à 2019. C'est la
    distinction que le fil d'activité fait déjà — *dater du dernier fait, jamais
    du premier* —, appliquée à l'envers : ici on date de ce qui s'est passé.
    """
    entrees = (
        _entrees_contrats(session, perimetre)
        + _entrees_interventions(session, perimetre, lecteur)
        + _entrees_affaires(session, perimetre, lecteur)
    )
    entrees.sort(key=lambda e: e.date_fait, reverse=True)
    _joindre_syntheses(session, entrees)
    return [entree.en_dict() for entree in entrees]


def _joindre_syntheses(session: Session, entrees: list[EntreeCarnet]) -> None:
    """La synthèse VALIDÉE de chaque affaire (#1643) — un brouillon n'entre jamais
    au carnet. Le lecteur a déjà passé `ticket_visible` pour la ligne : c'est la
    règle d'une synthèse validée, il n'y en a pas d'autre à rejouer ici.

    Son récit — « Ce qui s'est passé » — devient l'extrait de la carte : il dit
    ce que l'affaire a été, la demande ne disait que ce qu'elle annonçait.
    Sans récit, l'extrait reste la demande (24/10/2026)."""
    from app.utils.synthese_affaire.lecture import synthese_lue, syntheses_validees

    validees = syntheses_validees(session, [e.ticket_id for e in entrees if e.ticket_id])
    for entree in entrees:
        synthese = validees.get(entree.ticket_id)
        if synthese is not None:
            entree.synthese = synthese_lue(session, synthese).model_dump(mode="json")
            entree.extrait = synthese.synthese or entree.extrait
