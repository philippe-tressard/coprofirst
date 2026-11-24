"""Agrégation et purge de la télémétrie.

Rétention, par table :
  - Événements bruts (telemetry_event) : 30 jours — les seuls à porter le compte,
    la page et l'heure
  - Agrégation journalière (telemetry_daily) : 12 mois, en DEUX séries
    (`gestionnaire` : le gestionnaire du site, les autres)
  - Agrégation mensuelle (telemetry_monthly) : 10 ans, mêmes deux séries
  - Vues par canal d'accès (audience_canal_jour, audience_canal_mois) : 12 mois et
    10 ans, comme les deux agrégats (0335, `utils/telemetrie_canaux`)
  - Présence mensuelle (presence_mensuelle) : 12 mois — par compte et par mois,
    le seul fait « venu » ; c'est ce qui donne « Qui vient » à la vue Année (#1628)
  - Dernière visite (derniere_visite) : un jour par compte, effacé après 12 mois
    d'absence — c'est ce qui dit qui ne vient plus (#1629)
  - Erreurs vues dans le navigateur (erreur_navigateur) : 30 jours (#1631)
  - Durées d'affichage des écrans (mesure_affichage) : 30 jours (#1632)
  - Ouvertures et envois des formulaires (geste_formulaire) : 30 jours (#1633)

Appelé quotidiennement par le scheduler ou manuellement depuis l'admin.

## Les deux séries (03/10/2026)

L'écran filtre « avec / sans gestionnaire du site ». Au-delà des 30 jours
d'évènements, seul l'agrégat reste : il doit donc déjà savoir ce qui vient du
gestionnaire. Chaque jour s'agrège en deux séries disjointes — celle du compte
`site_manager_user_id` AU MOMENT de l'agrégation, celle de tout le monde d'autre.
Disjointes, leurs uniques s'additionnent, ce qu'une somme de distincts n'autorise
jamais autrement. Une ligne agrégée avant ce lot porte `None` : non distinguée.
Celles des 28 derniers jours sont RÉAGRÉGÉES depuis les évènements, qui existent
encore ; un mois dont tous les jours sont distingués l'est aussi.

Agréger un jour, c'est donc d'abord EFFACER ses lignes : l'opération est
idempotente, et la présence mensuelle ne compte jamais deux fois le même compte.

NOTE : Les événements (cree_le) sont stockés en UTC.
Les bornes jour/mois utilisent le fuseau Europe/Paris pour que le
découpage corresponde aux journées réelles des utilisateurs.
"""

from datetime import datetime, timedelta
import logging
import time
from typing import Optional

import sqlalchemy as sa
from sqlalchemy import func, text
from sqlmodel import Session, delete, select

from app import contexte
from app.models.core import (
    HistoriqueTelemetrie,
    PresenceMensuelle,
    TelemetryDaily,
    TelemetryEvent,
    TelemetryMonthly,
)
from app.models.telemetrie import ErreurNavigateur, GesteFormulaire, MesureAffichage
from app.utils import horloge, telemetrie_canaux
from app.utils.declenchement import AUTOMATIQUE
from app.utils.destinataires import site_manager_user_id
from app.utils.erreurs_navigateur import purger_releves_du_navigateur
from app.utils.noeud import noeud_courant
from app.utils.requete_liee import requete_liee
from app.utils.retour_comptes import noter_visites

logger = logging.getLogger(__name__)

_PARIS = horloge.TZ_PARIS

#: La page « total du jour » des agrégats : une ligne par série et par jour.
PAGE_TOTAL = "__total__"
#: Ce que vivent les évènements bruts, et la présence au-delà (en jours).
RETENTION_EVENEMENTS_JOURS = 30
RETENTION_DAILY_JOURS = 365
RETENTION_MONTHLY_JOURS = 3650
#: Un jour non distingué ne se réagrège que si ses évènements sont TOUS encore
#: là : la purge est glissante (maintenant − 30 jours), on garde deux jours de marge.
REAGREGATION_JOURS = RETENTION_EVENEMENTS_JOURS - 2
#: Les relevés du navigateur purgés chaque nuit : (clé du rapport, modèle, libellé d'erreur).
RELEVES_DU_NAVIGATEUR = (
    ("erreurs_navigateur_purgees", ErreurNavigateur, "erreurs navigateur"),
    ("mesures_affichage_purgees", MesureAffichage, "mesures affichage"),
    ("gestes_purges", GesteFormulaire, "gestes"),
)


def _paris_now() -> datetime:
    """Heure actuelle à Paris (consciente)."""
    return horloge.a_paris(horloge.maintenant())


def _serie(gestionnaire_id: Optional[int]):
    """L'expression SQL « cet évènement est du gestionnaire » — `True`/`False`, jamais `None`.

    Sans gestionnaire désigné, aucun compte ne porte l'identifiant −1 : tout est `False`.
    """
    cible = gestionnaire_id if gestionnaire_id is not None else -1
    return sa.case((TelemetryEvent.user_id == cible, True), else_=False)


def _agreger_jour(session: Session, jour_paris: datetime, gestionnaire_id: Optional[int]) -> bool:
    """(Ré)écrit les lignes de `telemetry_daily` et la présence d'UN jour ; True s'il a eu des vues."""
    debut_utc = horloge.debut_du_jour_utc(jour_paris)
    fin_utc = horloge.debut_du_jour_utc(jour_paris + timedelta(days=1))
    jour_str = jour_paris.strftime("%Y-%m-%d")
    fenetre = (TelemetryEvent.cree_le >= debut_utc, TelemetryEvent.cree_le < fin_utc)
    serie = _serie(gestionnaire_id)

    session.exec(delete(TelemetryDaily).where(TelemetryDaily.jour == jour_str))
    rows = session.exec(
        select(
            TelemetryEvent.page,
            TelemetryEvent.action,
            serie.label("gestionnaire"),
            func.count().label("total"),
            func.count(func.distinct(TelemetryEvent.user_id)).label("uniques"),
        )
        .where(*fenetre)
        .group_by(TelemetryEvent.page, TelemetryEvent.action, serie)
    ).all()
    #  La répartition par canal d'accès (0335), mêmes bornes et même série.
    telemetrie_canaux.agreger_jour(session, jour_str, fenetre, serie)
    for page, action, gestionnaire, total, uniques in rows:
        session.add(
            TelemetryDaily(
                jour=jour_str,
                page=page,
                action=action,
                total=total,
                utilisateurs_uniques=uniques,
                gestionnaire=bool(gestionnaire),
            )
        )
    if not rows:
        return False

    #  Ligne `__total__` par série : vrais uniques site-wide (COUNT DISTINCT user_id,
    #  qui ignore les vues anonymes ; `count()` les compte).
    totaux = session.exec(
        select(serie, func.count(), func.count(func.distinct(TelemetryEvent.user_id)))
        .where(*fenetre)
        .group_by(serie)
    ).all()
    for gestionnaire, total, uniques in totaux:
        session.add(
            TelemetryDaily(
                jour=jour_str,
                page=PAGE_TOTAL,
                action="view",
                total=total,
                utilisateurs_uniques=uniques,
                gestionnaire=bool(gestionnaire),
            )
        )

    #  La présence : un couple (mois, compte) écrit une fois.
    mois = jour_str[:7]
    venus = set(
        session.exec(
            select(TelemetryEvent.user_id).where(*fenetre, TelemetryEvent.user_id.isnot(None))
        ).all()
    )
    deja = set(
        session.exec(select(PresenceMensuelle.user_id).where(PresenceMensuelle.mois == mois)).all()
    )
    for user_id in sorted(venus - deja):
        session.add(PresenceMensuelle(mois=mois, user_id=user_id))
    #  Et le jour de la dernière visite (#1629), sauf pour qui a refusé la mesure.
    noter_visites(session, venus, jour_str)
    return True


def _jours_a_agreger(session: Session, now_paris: datetime) -> list[datetime]:
    """Les jours à (ré)agréger, minuit Paris : les nouveaux, et les non distingués récents."""
    last_daily = session.exec(
        select(TelemetryDaily.jour).order_by(TelemetryDaily.jour.desc()).limit(1)
    ).first()
    aujourd_hui = now_paris.replace(hour=0, minute=0, second=0, microsecond=0)
    if last_daily:
        debut = datetime.strptime(last_daily, "%Y-%m-%d").replace(tzinfo=_PARIS) + timedelta(days=1)
    else:
        debut = aujourd_hui - timedelta(days=RETENTION_EVENEMENTS_JOURS)
    jours = set()
    courant = debut
    while courant < aujourd_hui:  # jamais le jour en cours : données incomplètes
        jours.add(courant)
        courant += timedelta(days=1)

    plancher = (aujourd_hui - timedelta(days=REAGREGATION_JOURS)).strftime("%Y-%m-%d")
    non_distingues = session.exec(
        select(TelemetryDaily.jour)
        .where(TelemetryDaily.gestionnaire.is_(None), TelemetryDaily.jour >= plancher)
        .distinct()
    ).all()
    for jour in non_distingues:
        jours.add(datetime.strptime(jour, "%Y-%m-%d").replace(tzinfo=_PARIS))
    return sorted(jours)


def _mois_suivant(mois: str) -> str:
    y, m = map(int, mois.split("-"))
    return f"{y + 1}-01" if m == 12 else f"{y}-{m + 1:02d}"


def _agreger_mois(session: Session, mois_str: str) -> bool:
    """(Ré)écrit les lignes de `telemetry_monthly` d'UN mois depuis le journalier ; True si des vues."""
    session.exec(delete(TelemetryMonthly).where(TelemetryMonthly.mois == mois_str))
    telemetrie_canaux.agreger_mois(session, mois_str)
    rows = session.exec(
        select(
            TelemetryDaily.page,
            TelemetryDaily.action,
            TelemetryDaily.gestionnaire,
            func.sum(TelemetryDaily.total),
            #  Approximation assumée : la somme des uniques quotidiens compte deux
            #  fois qui revient deux jours. Acceptable pour une tendance mensuelle.
            func.sum(TelemetryDaily.utilisateurs_uniques),
        )
        .where(TelemetryDaily.jour.startswith(mois_str))
        .group_by(TelemetryDaily.page, TelemetryDaily.action, TelemetryDaily.gestionnaire)
    ).all()
    ecrit = False
    for page, action, gestionnaire, total, uniques in rows:
        if not total:
            continue
        ecrit = ecrit or page != PAGE_TOTAL
        session.add(
            TelemetryMonthly(
                mois=mois_str,
                page=page,
                action=action,
                total=total,
                utilisateurs_uniques=uniques or 0,
                gestionnaire=gestionnaire,
            )
        )
    return ecrit


def _mois_a_agreger(session: Session, now_paris: datetime) -> list[str]:
    """Les mois terminés à agréger, et ceux non distingués dont tous les jours le sont."""
    mois_courant = now_paris.strftime("%Y-%m")
    last_monthly = session.exec(
        select(TelemetryMonthly.mois).order_by(TelemetryMonthly.mois.desc()).limit(1)
    ).first()
    if last_monthly:
        debut = _mois_suivant(last_monthly)
    else:
        debut = (now_paris - timedelta(days=365)).strftime("%Y-%m")
    mois = set()
    courant = debut
    while courant < mois_courant:
        mois.add(courant)
        courant = _mois_suivant(courant)

    non_distingues = session.exec(
        select(TelemetryMonthly.mois).where(TelemetryMonthly.gestionnaire.is_(None)).distinct()
    ).all()
    for m in non_distingues:
        jours = session.exec(
            select(func.count(), func.count(TelemetryDaily.gestionnaire)).where(
                TelemetryDaily.jour.startswith(m)
            )
        ).one()
        #  `count(colonne)` ignore les NULL : égal au `count()`, tout est distingué.
        if jours[0] and jours[0] == jours[1]:
            mois.add(m)
    return sorted(mois)


def _purger(rapport: dict, cle: str, sql: str, **params) -> None:
    try:
        with contexte.moteur().connect() as conn:
            #  Un `datetime` se lie tel quel, jamais son `isoformat()` (#1298).
            result = conn.execute(requete_liee(sql, **params) if params else text(sql))
            conn.commit()
            rapport[cle] = result.rowcount
    except Exception as exc:
        rapport["erreurs"].append(f"{cle}: {exc}")


def run_telemetry_aggregation(entry_id: int | None = None) -> dict:
    """Exécute l'agrégation complète et retourne un rapport.

    Si *entry_id* est fourni, met à jour l'entrée HistoriqueTelemetrie correspondante.
    """
    t0 = time.monotonic()

    rapport = {
        "jours_agreges": 0,
        "mois_agreges": 0,
        "events_purges": 0,
        "daily_purges": 0,
        "monthly_purges": 0,
        "canaux_jour_purges": 0,
        "canaux_mois_purges": 0,
        "presences_purgees": 0,
        "dernieres_visites_purgees": 0,
        "erreurs_navigateur_purgees": 0,
        "mesures_affichage_purgees": 0,
        "gestes_purges": 0,
        "erreurs": [],
    }

    with contexte.nouvelle_session() as session:
        now_utc = horloge.maintenant()
        now_paris = _paris_now()

        # ─── 1. Agrégation journalière : events → daily (+ présence) ──────
        try:
            gestionnaire_id = site_manager_user_id(session)
            for jour in _jours_a_agreger(session, now_paris):
                if _agreger_jour(session, jour, gestionnaire_id):
                    rapport["jours_agreges"] += 1
            session.commit()
        except Exception as exc:
            rapport["erreurs"].append(f"agrégation daily: {exc}")
            session.rollback()

        # ─── 2. Agrégation mensuelle : daily → monthly ──────────────────
        try:
            for mois in _mois_a_agreger(session, now_paris):
                if _agreger_mois(session, mois):
                    rapport["mois_agreges"] += 1
            session.commit()
        except Exception as exc:
            rapport["erreurs"].append(f"agrégation monthly: {exc}")
            session.rollback()

        # ─── 3 à 6. Purges : events 30 j, daily 12 mois, monthly 10 ans, présence et visite 12 mois
        cutoff_daily = (now_paris - timedelta(days=RETENTION_DAILY_JOURS)).strftime("%Y-%m-%d")
        _purger(
            rapport,
            "events_purges",
            "DELETE FROM telemetry_event WHERE cree_le < :cutoff",
            cutoff=now_utc - timedelta(days=RETENTION_EVENEMENTS_JOURS),
        )
        _purger(
            rapport,
            "daily_purges",
            "DELETE FROM telemetry_daily WHERE jour < :cutoff",
            cutoff=cutoff_daily,
        )
        _purger(
            rapport,
            "monthly_purges",
            "DELETE FROM telemetry_monthly WHERE mois < :cutoff",
            cutoff=(now_paris - timedelta(days=RETENTION_MONTHLY_JOURS)).strftime("%Y-%m"),
        )
        #  La répartition par canal (0335) vit ce que vivent les agrégats.
        _purger(
            rapport,
            "canaux_jour_purges",
            "DELETE FROM audience_canal_jour WHERE jour < :cutoff",
            cutoff=cutoff_daily,
        )
        _purger(
            rapport,
            "canaux_mois_purges",
            "DELETE FROM audience_canal_mois WHERE mois < :cutoff",
            cutoff=(now_paris - timedelta(days=RETENTION_MONTHLY_JOURS)).strftime("%Y-%m"),
        )
        _purger(
            rapport,
            "presences_purgees",
            "DELETE FROM presence_mensuelle WHERE mois < :cutoff",
            cutoff=cutoff_daily[:7],
        )
        _purger(
            rapport,
            "dernieres_visites_purgees",
            "DELETE FROM derniere_visite WHERE jour < :cutoff",
            cutoff=cutoff_daily,
        )

        # ─── 7-9. Purge : les relevés du navigateur — erreurs (#1631),
        #  durées d'affichage (#1632), ouvertures et envois des formulaires
        #  (#1633). Une purge par relevé : l'échec de l'un n'empêche pas l'autre.
        for cle, modele, libelle in RELEVES_DU_NAVIGATEUR:
            try:
                rapport[cle] = purger_releves_du_navigateur(
                    session, modele, horloge.jour_civil(now_utc)
                )
            except Exception as exc:
                rapport["erreurs"].append(f"purge {libelle}: {exc}")
                session.rollback()

    # ─── Mise à jour de l'historique ──────────────────────────────────
    duree = round(time.monotonic() - t0, 2)
    if entry_id is not None:
        with contexte.nouvelle_session() as session:
            entry = session.get(HistoriqueTelemetrie, entry_id)
            if entry:
                entry.jours_agreges = rapport["jours_agreges"]
                entry.mois_agreges = rapport["mois_agreges"]
                entry.events_purges = rapport["events_purges"]
                entry.daily_purges = rapport["daily_purges"]
                entry.monthly_purges = rapport["monthly_purges"]
                entry.duree_secondes = duree
                entry.terminee_le = horloge.maintenant()
                if rapport["erreurs"]:
                    entry.statut = "erreur"
                    entry.erreur = "; ".join(rapport["erreurs"])
                else:
                    entry.statut = "succes"
                session.add(entry)
                session.commit()

    rapport["duree_secondes"] = duree
    return rapport


def derniere_agregation_reussie(session) -> Optional[datetime]:
    """L'horodatage de la dernière agrégation qui a abouti, ou `None`.

    Le fait qu'interroge le rattrapage — la RÈGLE, elle, vit dans
    `utils/rattrapage.py` et sert aussi la sauvegarde (#876). Elle était écrite
    ici, et le commentaire de `main.py` annonçait déjà qu'elle « ne concerne pas
    que la télémétrie » : elle n'a servi qu'à elle pendant une journée.
    """
    ligne = session.exec(
        select(HistoriqueTelemetrie)
        .where(HistoriqueTelemetrie.statut == "succes")
        .order_by(HistoriqueTelemetrie.cree_le.desc())
        .limit(1)
    ).first()
    return ligne.cree_le if ligne else None


def reagregation_en_attente(session: Session) -> bool:
    """Reste-t-il un jour récent dont l'agrégat ne distingue pas le gestionnaire ?

    Après la mise en production du filtre « sans le gestionnaire du site », les
    lignes déjà agrégées portent `None` jusqu'au PROCHAIN passage de 02:00 : la
    vue Mois lisait zéro vue du gestionnaire, donc ne proposait pas le filtre —
    toute la journée de la mise en production (03/10/2026, signalé à l'écran).
    Les évènements de ces jours existent encore : on les réagrège sans attendre.
    """
    plancher = (_paris_now() - timedelta(days=REAGREGATION_JOURS)).strftime("%Y-%m-%d")
    return (
        session.exec(
            select(TelemetryDaily.id)
            .where(TelemetryDaily.gestionnaire.is_(None), TelemetryDaily.jour >= plancher)
            .limit(1)
        ).first()
        is not None
    )


def derniere_agregation_ou_rejeu(session: Session) -> Optional[datetime]:
    """Le fait qu'interroge le rattrapage : `derniere_agregation_reussie`, ou `None`
    (« rien n'a abouti », donc on rejoue) tant qu'une réagrégation est en attente."""
    if reagregation_en_attente(session):
        return None
    return derniere_agregation_reussie(session)


def run_telemetry_aggregation_cron() -> dict:
    """Wrapper appelé par le scheduler cron — crée automatiquement une entrée historique."""
    with contexte.nouvelle_session() as session:
        entry = HistoriqueTelemetrie(declenchee_par=AUTOMATIQUE, noeud=noeud_courant())
        session.add(entry)
        session.commit()
        session.refresh(entry)
        entry_id = entry.id
    return run_telemetry_aggregation(entry_id)
