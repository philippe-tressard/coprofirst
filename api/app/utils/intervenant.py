"""L'intervenant d'une affaire, son équipement et la récurrence d'un Entretien — une écriture, deux chemins.

## Pourquoi (#1092, lot 5, arbitré le 23/09/2026)

Les événements du calendrier deviennent des affaires. Seize portent un
prestataire, et une maintenance récurrente sa fréquence. La section 6 du cadre,
« Intervenant », était déclarée « pas encore construite » (#1097) : ce lot la
construit, et la récurrence la rejoint pour la seule catégorie Entretien.

## La règle, ici et nulle part ailleurs

- **Le conseil seul** désigne l'intervenant et règle la récurrence. Un résident
  qui envoie ces champs est **ignoré**, comme pour les autres options réservées
  (`appliquer_options`) : sa correction de texte doit passer.
- Le prestataire désigné doit **exister** (`ou_404`) : un identifiant inventé
  afficherait un intervenant fantôme sur la fiche et dans le carnet.
- L'intervenant n'a de sens que pour une catégorie du **bâti**
  (`carnet_entretien.est_du_bati`), la récurrence que pour un
  **Entretien** : hors de là, ils sont effacés — sinon une affaire
  recatégorisée garderait en base ce qu'aucun écran ne montre plus (« sans
  données », arbitré le 23/09/2026).

## L'équipement (#1097, 24/09/2026)

« Sur quoi » : le **code** d'un équipement (`utils/equipements`), posé par le conseil et jamais
demandée au résident — il voit une flaque, il ne sait pas si c'est la plomberie,
la toiture ou la VMC. Mêmes règles que l'intervenant (conseil seul, bâti seul,
effacé ailleurs), plus une liste blanche — les équipements actifs, depuis #2442
administrés : `assurance` et `syndic` classent des **contrats**, pas un
équipement sur lequel on intervient (`HORS_AFFAIRES`).

C'est lui qui RANGE une affaire résolue au carnet d'entretien
(`carnet_entretien._entrees_affaires`) ; sans lui, elle y figure sous « Sans
équipement rattaché » — et non plus exclue, arbitré à l'écran le 24/09/2026.

Création (`crud.py`) et correction (`mise_a_jour.py`) l'appellent : deux
écritures de ces trois règles divergeraient au premier cas limite.
"""

from __future__ import annotations

from typing import Any

from fastapi import HTTPException
from sqlmodel import Session

from app.models.prestataires import ContratEntretien, Prestataire
from app.models.tickets import CategorieTicket
from app.utils.carnet_entretien import est_du_bati
from app.utils.corrections_texte import modification
from app.utils.equipements import HORS_AFFAIRES, exiger_equipement, libelle_equipement
from app.utils.recuperer import ou_404
from app.utils.valeurs import valeur

#: Les unités de récurrence — celles de `ContratEntretien`, qui fixe le rythme
#: d'un prestataire. Même table côté écran : `FREQUENCES` de `#lib/prestataires`.
#: « mois » vaut « mensuelle » : sans nombre saisi, il vaut 1.
FREQUENCES: tuple[str, ...] = ("semaines", "mois", "fois_par_an", "ans")

CHAMPS: tuple[str, ...] = (
    "prestataire_id",
    "contrat_id",
    "frequence_type",
    "frequence_valeur",
    "equipement",
)


def contrat_valide(
    session: Session, contrat_id: int, prestataire_id: int | None
) -> ContratEntretien:
    """Le contrat dans le cadre duquel le prestataire intervient (#1445).

    Il doit exister (404), être EN COURS, appartenir au prestataire désigné, et
    porter sur un équipement — une assurance ou un mandat de syndic ne cadrent
    pas une intervention (`HORS_AFFAIRES`). Écrit une fois : la création en
    lot (`routers/tickets/lot.py`) ne passe pas par `appliquer_intervenant`.
    """
    contrat = ou_404(session, ContratEntretien, contrat_id, "Contrat")
    if not contrat.actif:
        raise HTTPException(422, "Ce contrat n'est plus en cours")
    if prestataire_id is None or contrat.prestataire_id != prestataire_id:
        raise HTTPException(422, "Ce contrat n'est pas celui de l'intervenant désigné")
    if valeur(contrat.type_equipement) in HORS_AFFAIRES:
        raise HTTPException(422, "Ce contrat ne cadre pas une intervention")
    return contrat


def _envoye(body: Any, champ: str) -> bool:
    """Le corps dit-il quelque chose de ce champ ? (présence, pas non-nullité)"""
    return champ in getattr(body, "model_fields_set", set())


def _nom_prestataire(session: Session, prestataire_id: int | None) -> str | None:
    """Le nom de l'intervenant — ce que la ligne d'historique doit dire, pas son numéro."""
    prestataire = session.get(Prestataire, prestataire_id) if prestataire_id else None
    return prestataire.nom if prestataire else None


def _libelle_recurrence(type_: str | None, nombre: int | None) -> str | None:
    """`("mois", 3)` → « 3 mois » ; `("fois_par_an", 2)` → « 2 fois par an »."""
    if not type_ or nombre is None:
        return None
    return f"{nombre} {type_.replace('_', ' ')}"


def appliquer_intervenant(ticket: Any, body: Any, session: Session, *, est_cs: bool) -> list[str]:
    """Pose l'intervenant et la récurrence ; rend les lignes du journal de correction."""
    changes: list[str] = []
    if not est_du_bati(ticket.categorie):
        if ticket.prestataire_id is not None:
            changes.append("Intervenant effacé")
        if ticket.equipement is not None:
            changes.append("Équipement effacé")
        if ticket.contrat_id is not None:
            changes.append("Contrat effacé")
        ticket.prestataire_id = None
        ticket.equipement = None
        ticket.contrat_id = None
    else:
        if (
            est_cs
            and _envoye(body, "prestataire_id")
            and body.prestataire_id != ticket.prestataire_id
        ):
            if body.prestataire_id is not None:
                ou_404(session, Prestataire, body.prestataire_id, "Prestataire")
            changes.append(
                modification(
                    "de l'intervenant",
                    _nom_prestataire(session, ticket.prestataire_id),
                    _nom_prestataire(session, body.prestataire_id),
                )
            )
            ticket.prestataire_id = body.prestataire_id
        #  Le CADRE de l'intervention (#1445) : sous contrat — lequel —, ou hors
        #  contrat (`None`). APRÈS l'intervenant, qu'il doit suivre.
        if est_cs and _envoye(body, "contrat_id") and body.contrat_id != ticket.contrat_id:
            if body.contrat_id is not None:
                contrat_valide(session, body.contrat_id, ticket.prestataire_id)
            ticket.contrat_id = body.contrat_id
            changes.append(
                "Intervention rattachée à un contrat d'entretien"
                if body.contrat_id is not None
                else "Intervention désormais hors contrat"
            )
        #  Un contrat qui n'est plus celui de l'intervenant — il a changé, ou le
        #  contrat a été réattribué — ne se garde pas : il dirait « sous contrat »
        #  d'une intervention qu'aucun contrat ne cadre.
        if ticket.contrat_id is not None:
            contrat = session.get(ContratEntretien, ticket.contrat_id)
            if contrat is None or contrat.prestataire_id != ticket.prestataire_id:
                ticket.contrat_id = None
                changes.append("Contrat effacé")
        if (
            est_cs
            and _envoye(body, "equipement")
            and (body.equipement or None) != ticket.equipement
        ):
            exiger_equipement(session, body.equipement, "affaire")
            changes.append(
                modification(
                    "de l'équipement",
                    libelle_equipement(session, ticket.equipement) or None,
                    libelle_equipement(session, body.equipement) or None,
                )
            )
            ticket.equipement = body.equipement or None

    if valeur(ticket.categorie) != CategorieTicket.entretien.value:
        #  Hors Entretien : rien ne se garde, quel que soit l'auteur du geste.
        if ticket.frequence_type or ticket.frequence_valeur:
            changes.append("Récurrence effacée")
        ticket.frequence_type = None
        ticket.frequence_valeur = None
        return changes

    #  🔴 SOUS CONTRAT, le rythme est celui du contrat (#1445) — il se lit, il
    #  ne se saisit pas : deux rythmes pour une même visite divergeraient.
    if ticket.contrat_id is not None:
        if ticket.frequence_type or ticket.frequence_valeur:
            changes.append("Récurrence : celle du contrat")
        ticket.frequence_type = None
        ticket.frequence_valeur = None
        return changes

    if est_cs and (_envoye(body, "frequence_type") or _envoye(body, "frequence_valeur")):
        type_ = body.frequence_type or None
        nombre = 1 if type_ == "mois" and body.frequence_valeur is None else body.frequence_valeur
        if type_ is None or nombre is None:
            type_, nombre = None, None
        elif type_ not in FREQUENCES or nombre < 1:
            raise HTTPException(422, "Récurrence invalide : une unité connue et un nombre positif")
        if (type_, nombre) != (ticket.frequence_type, ticket.frequence_valeur):
            changes.append(
                modification(
                    "de la récurrence",
                    _libelle_recurrence(ticket.frequence_type, ticket.frequence_valeur),
                    _libelle_recurrence(type_, nombre),
                )
            )
            ticket.frequence_type, ticket.frequence_valeur = type_, nombre
    return changes


__all__ = ["CHAMPS", "FREQUENCES", "appliquer_intervenant"]
