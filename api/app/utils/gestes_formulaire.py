"""Les gestes aboutis — un formulaire ouvert, puis envoyé (#1633).

## Pourquoi (04/10/2026)

On savait qu'une page de formulaire avait été vue, pas si le geste avait
ABOUTI. Un formulaire ouvert souvent et rarement envoyé signale un écran qui
décourage : trop long, peu clair, bloqué par une erreur.

## Ce qui arrive, et par où

Le navigateur poste, par la file de la mesure d'audience (même route, même
plafond, même refus du profil — `routers/telemetry_collecte.py`), deux
événements par geste : `ACTION_OUVERTURE` quand le formulaire s'ouvre,
`ACTION_ENVOI` quand l'envoi a RÉUSSI. Leur `detail` est l'IDENTIFIANT du geste
(`affaire.creer`), tiré de la liste fermée du front (`#lib/gestes`) — jamais le
contenu saisi. Un `detail` qui n'a pas cette forme ne s'enregistre pas : le
client du site n'en envoie pas, ce qui arrive ainsi vient d'ailleurs.

## Ce qui est stocké

Un COMPTEUR par jour (de Paris) et par geste, sans identifiant de compte et
sans page, dans sa propre table : `telemetry_event` compterait chaque ligne
comme une page vue.

⚠️ Les envois se comptent aussi en base (une affaire créée existe) ; ce compteur
n'en est pas une seconde mesure, il est le seul à connaître les OUVERTURES. Il
ne compte que les comptes qui n'ont pas refusé la mesure, et les deux termes du
taux sont pris à la même source.

## Durée

`CONSERVATION_JOURS`, purgés par l'agrégation quotidienne
(`telemetry_aggregation`) — ce que dit la politique de confidentialité
(`seed/contenus_legaux.TELEMETRIE_GESTES`).
"""

import re
from datetime import date, datetime, timedelta

from sqlalchemy import func
from sqlmodel import Session, delete, select

from app.models.telemetrie import GesteFormulaire
from app.utils import horloge

#  `CONSERVATION_JOURS` : celle des erreurs, et pas une seconde valeur — la
#  politique et le tableau de bord (`_depuis_detail`) les disent ensemble.
from app.utils.erreurs_navigateur import CONSERVATION_JOURS

#: Les deux actions d'un geste — celles que `TelemetryEvent.action` prévoyait
#: (« view | click | submit ») sans qu'aucun écran les envoie. ⚠️ Tenues à la
#: main avec `#lib/gestes.ts` : le front et l'API ne partagent aucun fichier.
ACTION_OUVERTURE = "click"
ACTION_ENVOI = "submit"

#: La forme d'un identifiant de geste : « objet.verbe », minuscules, court.
MOTIF_GESTE = re.compile(r"[a-z_]{1,24}\.[a-z_]{1,24}")


def _compter(session: Session, geste: str | None, instant: datetime, champ: str) -> None:
    if not geste or not MOTIF_GESTE.fullmatch(geste):
        return
    jour = horloge.jour_civil(instant).isoformat()
    ligne = session.exec(
        select(GesteFormulaire).where(GesteFormulaire.jour == jour, GesteFormulaire.geste == geste)
    ).first()
    if ligne is None:
        ligne = GesteFormulaire(jour=jour, geste=geste)
    setattr(ligne, champ, getattr(ligne, champ) + 1)
    session.add(ligne)


def enregistrer_ouverture(session: Session, _page: str, geste: str | None, instant: datetime):
    """Compte une ouverture — sans `commit`, que fait l'appelant pour tout son lot."""
    _compter(session, geste, instant, "ouvertures")


def enregistrer_envoi(session: Session, _page: str, geste: str | None, instant: datetime):
    """Compte un envoi réussi — sans `commit`."""
    _compter(session, geste, instant, "envois")


def synthese_gestes(session: Session, depuis: date) -> list[dict]:
    """Ouvertures, envois et taux d'aboutissement par geste depuis `depuis` (inclus).

    Sommes par geste, jamais une ligne lue telle quelle : deux collectes
    simultanées peuvent créer deux lignes pour le même jour. Sans ouverture, pas
    de taux — un envoi dont l'ouverture n'a pas été mesurée ne fait pas 100 %.
    """
    lignes = session.exec(
        select(
            GesteFormulaire.geste,
            func.sum(GesteFormulaire.ouvertures),
            func.sum(GesteFormulaire.envois),
        )
        .where(GesteFormulaire.jour >= depuis.isoformat())
        .group_by(GesteFormulaire.geste)
        .order_by(GesteFormulaire.geste)
    ).all()
    return [
        {
            "geste": geste,
            "ouvertures": ouvertures,
            "envois": envois,
            "taux": round(100 * envois / ouvertures) if ouvertures else None,
        }
        for geste, ouvertures, envois in lignes
    ]


def purger_gestes(session: Session, aujourd_hui: date) -> int:
    """Retire les compteurs de plus de `CONSERVATION_JOURS` ; rend leur nombre."""
    limite = (aujourd_hui - timedelta(days=CONSERVATION_JOURS)).isoformat()
    resultat = session.exec(delete(GesteFormulaire).where(GesteFormulaire.jour < limite))
    session.commit()
    return resultat.rowcount
