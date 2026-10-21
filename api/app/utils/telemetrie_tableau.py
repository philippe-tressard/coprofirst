"""Le tableau de bord de télémétrie — ses QUATRE portées et son filtre (03/10/2026).

Jusqu'ici, `routers/telemetry.dashboard` tenait trois portées en 300 lignes. Il
en reçoit une quatrième, et un filtre : ce module porte les lectures, le
routeur ne garde que la route.

| Portée | Ce qu'elle lit | Le graphe |
|---|---|---|
| `jour` | les évènements d'aujourd'hui | vues par heure |
| `mois` | l'agrégat journalier sur 30 jours | vues par jour |
| `annee` | l'agrégat mensuel des 11 mois terminés + le journalier du mois en cours | vues par mois, 12 derniers mois |
| `total` | l'agrégat mensuel sur 10 ans + le journalier du mois en cours | vues par année |

## Le filtre « avec / sans gestionnaire du site » (règle : `telemetrie_lecture`)

Il n'est PROPOSÉ que s'il changerait quelque chose : un gestionnaire
désigné, qui a des vues sur la portée, et d'autres que lui aussi. Sinon la
réponse applique « avec », quoi qu'on ait demandé — un « sans » qui viderait
l'écran se lirait « personne ne vient ».
"""

from __future__ import annotations

import calendar
from dataclasses import replace
from datetime import date, datetime, time, timedelta
from typing import Optional

import sqlalchemy as sa
from sqlalchemy import func
from sqlmodel import Session, select

from app import dialecte
from app.models.core import TelemetryDaily, TelemetryEvent, TelemetryMonthly
from app.utils import horloge
from app.utils.destinataires import site_manager_user_id
from app.utils.telemetrie_calculs import (
    _cumul_par_page,
    _palmares,
    uniques_par_page,
    vues_non_attribuees,
)
from app.utils.telemetrie_lecture import (
    PAGE_TOTAL,
    Lecture,
    communs,
    fiches_utilisateurs,
    heure_de_pointe,
    mois_il_y_a,
    record,
    top_utilisateurs,
    uniques_par_jour,
)

PORTEES = ("jour", "mois", "annee", "total")
FILTRES = ("avec", "sans")


# ── Les portées ──────────────────────────────────────────────────────────────


def _portee_jour(session: Session, lecture: Lecture) -> dict:
    depuis = lecture.today_start_utc
    filtre = lecture.evenements()
    today_stats = session.exec(
        select(
            TelemetryEvent.page,
            func.count().label("total"),
            func.count(func.distinct(TelemetryEvent.user_id)).label("uniques"),
        )
        .where(TelemetryEvent.cree_le >= depuis, *filtre)
        .group_by(TelemetryEvent.page)
        .order_by(func.count().desc())
    ).all()
    active_today = session.exec(
        select(func.count(func.distinct(TelemetryEvent.user_id))).where(
            TelemetryEvent.cree_le >= depuis, TelemetryEvent.user_id.isnot(None), *filtre
        )
    ).one()
    total_today = sum(r[1] for r in today_stats)

    hour_stats = session.exec(
        select(
            sa.extract("hour", TelemetryEvent.cree_le).label("heure"),
            func.count().label("total"),
            func.count(func.distinct(TelemetryEvent.user_id)).label("uniques"),
        )
        .where(TelemetryEvent.cree_le >= depuis, *filtre)
        .group_by("heure")
    ).all()
    chart_raw = sorted(
        (
            {"paris_h": (h[0] + lecture.paris_offset) % 24, "total": h[1], "uniques": h[2]}
            for h in hour_stats
        ),
        key=lambda x: x["paris_h"],
    )
    chart = [
        {"label": f"{c['paris_h']}h", "total": c["total"], "uniques": c["uniques"]}
        for c in chart_raw
    ]
    user_rows = top_utilisateurs(session, depuis, lecture)
    return {
        "kpi": {
            "utilisateurs": active_today or 0,
            "vues": total_today,
            "pages": len(today_stats),
            "heure_pointe": heure_de_pointe(session, lecture, depuis),
            "moy_vues_utilisateur": round(total_today / active_today, 1) if active_today else None,
        },
        "chart": chart,
        "chart_label": "Vues par heure",
        "top_pages": [{"page": r[0], "total": r[1], "uniques": r[2]} for r in today_stats],
        "top_users": _palmares(user_rows, fiches_utilisateurs(session, user_rows)),
    }


def _portee_mois(session: Session, lecture: Lecture) -> dict:
    thirty_days_ago = _minuit_il_y_a(lecture, 30)
    filtre = lecture.evenements()
    daily_rows = session.exec(
        select(TelemetryDaily)
        .where(
            TelemetryDaily.jour >= thirty_days_ago,
            TelemetryDaily.page != PAGE_TOTAL,
            *lecture.agregats(TelemetryDaily),
        )
        .order_by(TelemetryDaily.jour)
    ).all()
    daily_uniques_map = uniques_par_jour(session, lecture, thirty_days_ago.date())
    daily_chart: dict[str, dict] = {}
    for r in daily_rows:
        if r.jour not in daily_chart:
            daily_chart[r.jour] = {
                "label": r.jour[5:],
                "total": 0,
                "uniques": daily_uniques_map.get(r.jour, 0),
            }
        daily_chart[r.jour]["total"] += r.total

    #  `uniques` ne s'ADDITIONNE pas : les couples (page, utilisateur) distincts
    #  sont relus sur la période (#354).
    paires_page_user = session.exec(
        select(TelemetryEvent.page, TelemetryEvent.user_id)
        .where(
            TelemetryEvent.cree_le >= thirty_days_ago, TelemetryEvent.user_id.isnot(None), *filtre
        )
        .distinct()
    ).all()
    vues_attribuees = session.exec(
        select(func.count())
        .select_from(TelemetryEvent)
        .where(
            TelemetryEvent.cree_le >= thirty_days_ago, TelemetryEvent.user_id.isnot(None), *filtre
        )
    ).one()
    top_pages = _cumul_par_page(daily_rows, uniques=uniques_par_page(paires_page_user))

    total_vues = sum(d["total"] for d in daily_chart.values())
    nb_jours = len(daily_chart) or 1
    user_rows = top_utilisateurs(session, thirty_days_ago, lecture)
    return {
        "kpi": {
            "vues": total_vues,
            "utilisateurs": max(daily_uniques_map.values()) if daily_uniques_map else 0,
            "pages": len(top_pages),
            "heure_pointe": heure_de_pointe(session, lecture, thirty_days_ago),
            "moy_vues_jour": round(total_vues / nb_jours, 1),
            "moy_utilisateurs_jour": (
                round(sum(daily_uniques_map.values()) / nb_jours, 1) if daily_uniques_map else 0
            ),
            "jour_pointe": record(daily_uniques_map, "jour"),
            "vues_non_attribuees": vues_non_attribuees(total_vues, vues_attribuees),
        },
        "chart": sorted(daily_chart.values(), key=lambda x: x["label"]),
        "chart_label": "Vues par jour (30 j)",
        "top_pages": sorted(top_pages.values(), key=lambda x: -x["total"]),
        "top_users": _palmares(user_rows, fiches_utilisateurs(session, user_rows)),
    }


def _minuit_il_y_a(lecture: Lecture, jours: int) -> datetime:
    """Minuit, il y a `jours` jours de Paris — une DATE, comparée à `cree_le` (#1747).

    Jamais le texte « AAAA-MM-JJ » : le serveur refuse de comparer un
    horodatage à du texte. Le minuit naïf donne exactement la borne voulue.
    """
    return datetime.combine((lecture.now_paris - timedelta(days=jours)).date(), time.min)


def _lignes_mensuelles(session: Session, lecture: Lecture, depuis_mois: str) -> list:
    """Les lignes par mois depuis `depuis_mois` : l'agrégat mensuel, puis le
    journalier du mois EN COURS, que l'agrégat mensuel n'a pas encore (il ne
    s'écrit qu'un mois terminé). Les deux ont `page` et `total` : le cumul par
    page les lit indifféremment."""
    mensuelles = session.exec(
        select(TelemetryMonthly)
        .where(
            TelemetryMonthly.mois >= depuis_mois,
            TelemetryMonthly.mois < lecture.mois_courant,
            TelemetryMonthly.page != PAGE_TOTAL,
            *lecture.agregats(TelemetryMonthly),
        )
        .order_by(TelemetryMonthly.mois)
    ).all()
    journalieres = session.exec(
        select(TelemetryDaily).where(
            TelemetryDaily.jour.startswith(lecture.mois_courant),
            TelemetryDaily.page != PAGE_TOTAL,
            *lecture.agregats(TelemetryDaily),
        )
    ).all()
    return [(r.mois, r) for r in mensuelles] + [(r.jour[:7], r) for r in journalieres]


def _uniques_par_mois(session: Session, lecture: Lecture, depuis_mois: str) -> dict[str, int]:
    """Les uniques de chaque mois : les évènements bruts d'abord (30 jours), puis l'agrégat."""
    mois = dialecte.mois(TelemetryEvent.cree_le, lecture.paris_offset_str)
    recents = session.exec(
        select(mois, func.count(func.distinct(TelemetryEvent.user_id)))
        .where(
            TelemetryEvent.cree_le >= _minuit_il_y_a(lecture, 30),
            TelemetryEvent.user_id.isnot(None),
            *lecture.evenements(),
        )
        .group_by(mois)
    ).all()
    uniques = {r[0]: r[1] for r in recents}
    totaux = session.exec(
        select(TelemetryMonthly.mois, func.sum(TelemetryMonthly.utilisateurs_uniques))
        .where(
            TelemetryMonthly.mois >= depuis_mois,
            TelemetryMonthly.page == PAGE_TOTAL,
            *lecture.agregats(TelemetryMonthly),
        )
        .group_by(TelemetryMonthly.mois)
    ).all()
    for r in totaux:
        uniques.setdefault(r[0], r[1] or 0)
    return uniques


def _portee_longue(session: Session, lecture: Lecture, depuis_mois: str, par_annee: bool) -> dict:
    """Année (12 derniers mois, un bâton par mois) et Total (10 ans, un bâton par année)."""
    lignes = _lignes_mensuelles(session, lecture, depuis_mois)
    uniques_mois = _uniques_par_mois(session, lecture, depuis_mois)
    chart: dict[str, dict] = {}
    for mois, r in lignes:
        cle = mois[:4] if par_annee else mois
        if cle not in chart:
            chart[cle] = {"label": cle, "total": 0, "uniques": None if par_annee else 0}
        chart[cle]["total"] += r.total
        if not par_annee:
            chart[cle]["uniques"] = uniques_mois.get(mois, 0)
    #  Sans `uniques` : le cumul mois par mois — voir `_cumul_par_page`.
    top_pages = _cumul_par_page([r for _, r in lignes])
    total_vues = sum(d["total"] for d in chart.values())
    daily_uniques = uniques_par_jour(
        session, lecture, None if par_annee else date.fromisoformat(depuis_mois + "-01")
    )
    kpi = {
        "vues": total_vues,
        "pages": len(top_pages),
        "record_jour": record(daily_uniques, "jour"),
        "record_mois": record(uniques_mois, "mois"),
    }
    if par_annee:
        kpi["annees_actives"] = len(chart)
        kpi["moy_vues_an"] = round(total_vues / (len(chart) or 1), 1)
    else:
        kpi["mois_actifs"] = len(chart)
        kpi["moy_vues_mois"] = round(total_vues / (len(chart) or 1), 1)
    return {
        "kpi": kpi,
        "chart": sorted(chart.values(), key=lambda x: x["label"]),
        "chart_label": "Vues par année (10 ans)" if par_annee else "Vues par mois (12 mois)",
        "top_pages": sorted(top_pages.values(), key=lambda x: -x["total"]),
        "top_users": [],
    }


# ── Le filtre : proposé ? jusqu'où distingué ? ───────────────────────────────


def _vues(session: Session, lecture: Lecture, du_gestionnaire: bool) -> int:
    """Les vues de la portée en « avec » — toutes, ou celles de la série du gestionnaire."""
    if lecture.scope == "jour":
        conditions = [TelemetryEvent.cree_le >= lecture.today_start_utc]
        if du_gestionnaire:
            conditions.append(TelemetryEvent.user_id == lecture.gestionnaire_id)
        return session.exec(
            select(func.count()).select_from(TelemetryEvent).where(*conditions)
        ).one()
    if lecture.scope == "mois":
        depuis = (lecture.now_paris - timedelta(days=30)).strftime("%Y-%m-%d")
        requete = select(func.coalesce(func.sum(TelemetryDaily.total), 0)).where(
            TelemetryDaily.jour >= depuis, TelemetryDaily.page == PAGE_TOTAL
        )
        if du_gestionnaire:
            requete = requete.where(TelemetryDaily.gestionnaire.is_(True))
        return session.exec(requete).one()
    depuis = mois_il_y_a(lecture.now_paris, 11 if lecture.scope == "annee" else 120)
    mensuel = select(func.coalesce(func.sum(TelemetryMonthly.total), 0)).where(
        TelemetryMonthly.mois >= depuis, TelemetryMonthly.page == PAGE_TOTAL
    )
    courant = select(func.coalesce(func.sum(TelemetryDaily.total), 0)).where(
        TelemetryDaily.jour.startswith(lecture.mois_courant), TelemetryDaily.page == PAGE_TOTAL
    )
    if du_gestionnaire:
        mensuel = mensuel.where(TelemetryMonthly.gestionnaire.is_(True))
        courant = courant.where(TelemetryDaily.gestionnaire.is_(True))
    return session.exec(mensuel).one() + session.exec(courant).one()


def _filtre_propose(session: Session, lecture: Lecture) -> bool:
    if lecture.gestionnaire_id is None:
        return False
    du_gestionnaire = _vues(session, lecture, True)
    return du_gestionnaire > 0 and _vues(session, lecture, False) > du_gestionnaire


def non_distingue_jusqu_au(session: Session, scope: str) -> Optional[str]:
    """Le dernier jour dont l'agrégat ne sépare pas le gestionnaire, ou `None`.

    Lu sur le journalier (12 mois) et, pour les portées longues, sur le mensuel
    — dont un mois non distingué se lit à son dernier jour.
    """
    if scope == "jour":
        return None
    jour = session.exec(
        select(func.max(TelemetryDaily.jour)).where(TelemetryDaily.gestionnaire.is_(None))
    ).one()
    if scope == "mois":
        return jour
    mois = session.exec(
        select(func.max(TelemetryMonthly.mois)).where(TelemetryMonthly.gestionnaire.is_(None))
    ).one()
    if mois:
        y, m = map(int, mois.split("-"))
        fin_de_mois = f"{mois}-{calendar.monthrange(y, m)[1]:02d}"
        jour = max(jour or "", fin_de_mois)
    return jour or None


# ── La réponse ───────────────────────────────────────────────────────────────


def tableau(session: Session, scope: str, filtre: str) -> dict:
    """La réponse de `GET /telemetry/dashboard` pour une portée et un filtre."""
    now_paris = horloge.a_paris(horloge.maintenant())
    gestionnaire_id = site_manager_user_id(session)
    lecture = Lecture(
        scope=scope,
        sans_gestionnaire=False,
        gestionnaire_id=gestionnaire_id,
        now_paris=now_paris,
        paris_offset=int(now_paris.utcoffset().total_seconds() // 3600),
    )
    propose = _filtre_propose(session, lecture)
    applique = "sans" if propose and filtre == "sans" else "avec"
    lecture = replace(lecture, sans_gestionnaire=applique == "sans")

    if scope == "jour":
        corps = _portee_jour(session, lecture)
    elif scope == "mois":
        corps = _portee_mois(session, lecture)
    elif scope == "annee":
        corps = _portee_longue(session, lecture, mois_il_y_a(now_paris, 11), par_annee=False)
    else:
        corps = _portee_longue(session, lecture, mois_il_y_a(now_paris, 120), par_annee=True)
    return {
        "scope": scope,
        **corps,
        **communs(session, lecture),
        "filtre_gestionnaire": {
            "propose": propose,
            #  Faux : aucun administrateur n'est désigné gestionnaire (Copropriété › Fonctionnement) —
            #  c'est la cause de filtre absent que l'administrateur peut corriger.
            "gestionnaire_designe": gestionnaire_id is not None,
            "applique": applique,
            "non_distingue_jusqu_au": (
                non_distingue_jusqu_au(session, scope) if applique == "sans" else None
            ),
        },
    }
