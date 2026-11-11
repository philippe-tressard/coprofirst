"""La pastille de lecture d'un objet ENREGISTRÉ — affaire, annonce, idée, sondage.

La règle (`regle.lecture_de`) est pure : ici, on lui fournit ses entrées, dont
« le périmètre vise-t-il MOINS que la copropriété ? », qui lit l'arbre des
périmètres (`a_portee_globale`).
"""

from __future__ import annotations

from typing import Any, Optional

from app.models.tickets import StatutTicket
from app.utils.lecture_pastille.modele import Lecture
from app.utils.lecture_pastille.regle import lecture_ciblee, lecture_de
from app.utils.nature_affaire import ACTUALITE
from app.utils.perimetres.arbre import a_portee_globale, parse_json_perimetres
from app.utils.valeurs import valeur
from app.utils.visibility.defauts_affaire import defauts_de_nature


def perimetre_restreint_de(perimetre: Any) -> bool:
    """Le périmètre vise-t-il moins que la copropriété ? Vide : aucune restriction."""
    codes = perimetre if isinstance(perimetre, list) else parse_json_perimetres(perimetre)
    return bool(codes) and not a_portee_globale(codes)


def lecture_de_saisie(
    *,
    categorie: Optional[str],
    statut: Optional[str],
    confidentiel: bool,
    public_cible: Any,
    perimetre_cible: Any,
    reserve_perimetre: bool,
) -> Lecture:
    """Une affaire — enregistrée ou en cours de saisie : la même règle (#2633)."""
    return lecture_de(
        actualite=valeur(categorie) == ACTUALITE,
        confidentiel=confidentiel,
        public_cible=public_cible,
        perimetre_restreint=perimetre_restreint_de(perimetre_cible),
        reserve_perimetre=reserve_perimetre,
        categorie=valeur(categorie),
        statut=valeur(statut),
    )


def lecture_du_ticket(ticket: Any) -> Lecture:
    """Qui lit cette affaire (ou cette actualité) — servi avec elle."""
    return lecture_de_saisie(
        categorie=ticket.categorie,
        statut=ticket.statut,
        confidentiel=ticket.confidentiel is True,
        public_cible=ticket.public_cible,
        perimetre_cible=ticket.perimetre_cible,
        reserve_perimetre=ticket.reserve_perimetre is True,
    )


def destinataires_par_etat(ticket: Any) -> Optional[dict[str, list[str]]]:
    """Les Destinataires qu'une Suite présélectionne, selon l'état qu'elle donne —
    une Étude & travaux mise en AG s'ouvre aux copropriétaires. `None` pour une
    actualité, qui a les siens (#1343, servi depuis #2633)."""
    if valeur(ticket.categorie) == ACTUALITE:
        return None
    return {s.value: defauts_de_nature(False, ticket.categorie, s.value) for s in StatutTicket}


def lecture_du_ciblage(objet: Any, *, masculin: bool = False) -> Lecture:
    """Qui lit une annonce, une idée (féminin) ou un sondage (masculin) — `cible_visible`."""
    return lecture_ciblee(
        public_cible=getattr(objet, "public_cible", None),
        perimetre_restreint=perimetre_restreint_de(getattr(objet, "perimetre_cible", None)),
        masculin=masculin,
    )
