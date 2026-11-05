"""Le journal des messages relevés — ce que la relève a décidé, et pourquoi (#1447).

Une ligne par message traité (`courriel_boite.traiter`), écrite dans la même
transaction que le verdict. Elle se lit dans Espace CS › Courriels (depuis le
05/10/2026 — elle était réservée à l'admin, sous Paramétrage › SMTP, et un
transfert refusé pour un numéro mal tapé y est resté invisible au conseil), et se
purge chaque dimanche (`maintenance.purger`).

🔴 Ce qu'elle ne porte pas : le corps du message. Le journal dit ce qu'on a
DÉCIDÉ ; le texte vit dans le fil de l'affaire ou dans la boîte de réception.
"""

from __future__ import annotations

from datetime import datetime
from email.utils import parseaddr

from sqlmodel import Session, select

from app.models.core import ConfigSite
from app.models.courriel import CourrielReleve

#: Combien de jours une ligne est gardée. Assez pour qu'un « je vous ai
#: répondu il y a trois semaines » se vérifie, pas davantage : l'adresse de
#: l'expéditeur est une donnée personnelle. La politique de confidentialité
#: le dit (`seed/contenus_legaux.CONSERVATION_RELEVES`).
CONSERVATION_RELEVES_JOURS = 90

#: Un objet s'arrête là : un sujet sans fin n'apprend rien de plus.
_OBJET_MAX = 300


def journaliser_releve(
    session: Session,
    entetes: dict,
    envoye_le: datetime | None,
    decision: str,
    motif: str,
    ticket=None,
) -> CourrielReleve:
    """Ajoute la ligne à la session — c'est l'appelant qui valide, avec le verdict."""
    lire = {k.lower(): v for k, v in entetes.items()}
    ligne = CourrielReleve(
        envoye_le=envoye_le,
        expediteur=(lire.get("from") or "")[:_OBJET_MAX],
        objet=(lire.get("subject") or "")[:_OBJET_MAX],
        decision=decision,
        motif=motif or "motif non renseigné",
        ticket_id=ticket.id if ticket is not None else None,
        affaire=ticket.numero if ticket is not None else None,
    )
    session.add(ligne)
    return ligne


#: Combien de lignes l'onglet « Courriels » d'Espace CS en montre : un paramètre
#: du site, réglé dans Paramétrage › SMTP (05/10/2026). 20 par défaut — de quoi
#: relire la semaine, sans en faire un second historique de la boîte.
CLE_AFFICHES = "courriels_affiches"
AFFICHES_PAR_DEFAUT = 20
#: Plafond : une valeur absurde (ou une faute de frappe) ne doit pas vider
#: la table dans une seule réponse.
AFFICHES_MAX = 100


def nombre_affiche(session: Session) -> int:
    """Le paramètre, borné ; illisible ou absent → la valeur par défaut."""
    ligne = session.get(ConfigSite, CLE_AFFICHES)
    try:
        valeur = int((ligne.valeur if ligne else "").strip())
    except ValueError:
        return AFFICHES_PAR_DEFAUT
    return max(1, min(valeur, AFFICHES_MAX))


def nom_de_l_expediteur(brut: str) -> str:
    """Le NOM d'un `From:` — jamais l'adresse (une donnée personnelle).

    >>> nom_de_l_expediteur('Gestionnaire <gestion@syndic.fr>')
    'Gestionnaire'
    >>> nom_de_l_expediteur('gestion@syndic.fr')
    '(sans nom)'
    """
    nom = parseaddr(brut or "")[0].strip()
    return nom or "(sans nom)"


def derniers_releves(session: Session, limite: int | None = None) -> list[CourrielReleve]:
    """Les lignes les plus récentes d'abord — `limite`, sinon le paramètre du site."""
    return session.exec(
        select(CourrielReleve)
        .order_by(CourrielReleve.releve_le.desc(), CourrielReleve.id.desc())
        .limit(limite or nombre_affiche(session))
    ).all()
