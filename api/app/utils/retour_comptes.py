"""Les comptes qui ne viennent plus, et les arrivants qui reviennent (#1629).

## Pourquoi (04/10/2026)

Rien ne signalait qu'un résident avait cessé de venir, ni qu'un nouvel arrivant
n'était jamais revenu après sa validation — les deux signaux qui disent si le
site s'installe dans les habitudes.

## Où se lit « la dernière visite »

- les **évènements bruts** (30 jours) pour le récent, au jour près ;
- au-delà, `DerniereVisite` : UN jour par compte, noté par l'agrégation
  quotidienne (`noter_visites`), gardé 12 mois.

⚠️ Pas `Utilisateur.derniere_connexion` : elle ne bouge qu'à la saisie du mot de
passe, et une session se renouvelle seule tant qu'on revient dans les 7 jours —
le résident le plus assidu ne se reconnecte jamais. Le pourquoi complet est sur
le modèle (`models/telemetrie.DerniereVisite`).

## Les deux règles

- **Dormant** à N jours : un compte ouvert et mesuré dont ni la dernière visite
  ni la validation (`comptes.valide_le`) n'ont moins de N jours. Un compte
  jamais vu se compte depuis sa validation — aucune visite n'est inventée, et
  un arrivant de la semaine n'est pas un dormant.
- **Revenu** : un compte validé sur les `PERIODE_ARRIVANTS_JOURS` derniers jours
  qui a ouvert au moins une page dans les `FENETRE_RETOUR_JOURS` qui suivent sa
  validation. Tant que la fenêtre est ouverte et qu'il n'est pas venu, il est
  « en attente » : le taux ne porte que sur les issues connues.

Les comptes qui ont refusé la mesure d'audience sortent des deux calculs —
leurs visites ne sont pas enregistrées — et leur nombre est rendu à côté, comme
dans « Qui vient » (`utils/adoption`). La liste nominative est servie par le
tableau de bord, réservé à l'administrateur (`require_admin`).
"""

from __future__ import annotations

from datetime import date, datetime, timedelta

from sqlalchemy import func
from sqlmodel import Session, select

from app.models.core import Utilisateur
from app.models.telemetrie import DerniereVisite, TelemetryEvent
from app.utils import horloge
from app.utils.comptes import valide_le
from app.utils.noms import nom_affiche
from app.utils.pourcentages import part_en_pourcent
from app.utils.roles_libelles import libelle_statut

#: Les seuils de dormance, en jours, du plus court au plus long.
SEUILS_DORMANCE = (60, 90)
#: Le délai, après la validation, dans lequel un arrivant « revient ».
FENETRE_RETOUR_JOURS = 7
#: Les arrivants regardés : ceux validés sur cette période. Les évènements, seuls
#: à dire QUAND un compte est venu, vivent 30 jours — la fenêtre d'un compte
#: validé il y a 30 jours y tient entière.
PERIODE_ARRIVANTS_JOURS = 30


def noter_visites(session: Session, user_ids: set[int], jour: str) -> None:
    """Note `jour` (« YYYY-MM-DD ») comme dernière visite de ces comptes — sans `commit`.

    Ne recule jamais : réagréger un jour ancien ne remplace pas un jour plus
    récent. Un compte qui a refusé la mesure n'est pas noté.
    """
    if not user_ids:
        return
    mesures = session.exec(
        select(Utilisateur.id).where(
            Utilisateur.id.in_(user_ids),
            Utilisateur.opt_out_telemetrie == False,  # noqa: E712  (colonne SQL)
        )
    ).all()
    connues = {
        d.user_id: d
        for d in session.exec(
            select(DerniereVisite).where(DerniereVisite.user_id.in_(mesures))
        ).all()
    }
    for user_id in mesures:
        ligne = connues.get(user_id)
        if ligne is None:
            session.add(DerniereVisite(user_id=user_id, jour=jour))
        elif ligne.jour < jour:
            ligne.jour = jour
            session.add(ligne)


def dernieres_visites(session: Session) -> dict[int, date]:
    """Le jour de la dernière visite connue de chaque compte : les évènements, puis la table."""
    visites = {
        d.user_id: date.fromisoformat(d.jour) for d in session.exec(select(DerniereVisite)).all()
    }
    recents = session.exec(
        select(TelemetryEvent.user_id, func.max(TelemetryEvent.cree_le))
        .where(TelemetryEvent.user_id.isnot(None))
        .group_by(TelemetryEvent.user_id)
    ).all()
    for user_id, instant in recents:
        jour = horloge.jour_civil(instant)
        if user_id not in visites or visites[user_id] < jour:
            visites[user_id] = jour
    return visites


def _dormants(mesures: list[Utilisateur], visites: dict[int, date]) -> list[dict]:
    """Les comptes sans visite depuis le plus court des seuils, du plus ancien au plus récent."""
    aujourd_hui = horloge.aujourd_hui()
    lignes = []
    for c in mesures:
        valide = valide_le(c)
        reperes = [d for d in (visites.get(c.id), valide and horloge.jour_civil(valide)) if d]
        if not reperes:
            continue
        jours = (aujourd_hui - max(reperes)).days
        if jours < SEUILS_DORMANCE[0]:
            continue
        derniere = visites.get(c.id)
        lignes.append(
            {
                "user_id": c.id,
                "nom": nom_affiche(c.prenom, c.nom),
                "type": libelle_statut(c.statut),
                "derniere_visite": derniere.isoformat() if derniere else None,
                "jours": jours,
            }
        )
    return sorted(lignes, key=lambda d: (-d["jours"], d["nom"]))


def _arrivants(session: Session, mesures: list[Utilisateur], maintenant: datetime) -> dict:
    debut = maintenant - timedelta(days=PERIODE_ARRIVANTS_JOURS)
    fenetre = timedelta(days=FENETRE_RETOUR_JOURS)
    arrivants = {c.id: v for c in mesures if (v := valide_le(c)) and v >= debut}
    venues: dict[int, list[datetime]] = {}
    if arrivants:
        for user_id, instant in session.exec(
            select(TelemetryEvent.user_id, TelemetryEvent.cree_le).where(
                TelemetryEvent.user_id.in_(arrivants), TelemetryEvent.cree_le >= debut
            )
        ).all():
            venues.setdefault(user_id, []).append(instant)
    revenus = jamais = attente = 0
    for user_id, valide in arrivants.items():
        if any(valide <= t <= valide + fenetre for t in venues.get(user_id, [])):
            revenus += 1
        elif maintenant >= valide + fenetre:
            jamais += 1
        else:
            attente += 1
    connus = revenus + jamais
    return {
        "periode": f"{PERIODE_ARRIVANTS_JOURS} derniers jours",
        "fenetre_jours": FENETRE_RETOUR_JOURS,
        "valides": len(arrivants),
        "revenus": revenus,
        "jamais_revenus": jamais,
        "en_attente": attente,
        "taux": part_en_pourcent(revenus, connus, vide=None),
    }


def retour_comptes(session: Session) -> dict:
    """Dormants par seuil, leur liste nominative, et le retour des arrivants."""
    ouverts = session.exec(select(Utilisateur).where(Utilisateur.actif == True)).all()  # noqa: E712
    mesures = [c for c in ouverts if not c.opt_out_telemetrie]
    liste = _dormants(mesures, dernieres_visites(session))
    return {
        "comptes_mesures": len(mesures),
        "refus": len(ouverts) - len(mesures),
        "dormants": [
            {"seuil": s, "nombre": sum(1 for d in liste if d["jours"] >= s)}
            for s in SEUILS_DORMANCE
        ],
        "liste_dormants": liste,
        "arrivants": _arrivants(session, mesures, horloge.maintenant()),
    }
