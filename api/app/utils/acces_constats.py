"""Le constat des badges : ce qu'un badge ouvre, confronté à ce que ses lots justifient (#2217).

Deux écarts, jamais bloquants — un badge se règle à la main, par le conseil :

- **manque** : une circulation des lots du badge (son lot, ceux de son porteur)
  qu'il n'ouvre pas — un badge « mal doté », qui ne se voyait qu'à la porte fermée ;
- **excès** : un bâtiment qu'aucun de ses lots ne justifie — un badge « trop doté »,
  qui ne se voyait jamais.

Ce qui ne se juge pas le dit (`standards/04` §1) : un badge sans lot ni porteur
rattaché, ou dont les lots n'ont ni bâtiment ni circulation (l'état descriptif
n'est pas encore appliqué), rend INCONNU — jamais « rien à signaler ». Un badge
sans accès enregistré (« on ne sait pas », #953) n'est pas un écart : il est compté.

Seuls les BÂTIMENTS se comparent : la racine (« toute la copropriété ») est une
décision délibérée du conseil, et les portillons configurés ne dépendent d'aucun
lot (`acces_choix`). 🔴 Aucune donnée personnelle : des numéros de lots et des
codes de périmètre.
"""

from __future__ import annotations

import json

from sqlmodel import Session, select

from app.models.acces import StatutAcces, Vigik
from app.models.copropriete import Lot
from app.utils.acces_choix import codes_batiments
from app.utils.acces_portes import lots_du_badge, portes_de_badge
from app.utils.constats import AVERTISSEMENT, INCONNU, INFORMATION, Constat, constat
from app.utils.perimetres import code_par_defaut


def _repere(session: Session, badge: Vigik) -> str:
    """Le lot du badge, sinon son code — ce que le conseil retrouve dans le parc."""
    lot = session.get(Lot, badge.lot_id) if badge.lot_id else None
    return lot.numero if lot else f"badge {badge.code}"


def constater_badges(session: Session) -> list[Constat]:
    """Les écarts des badges Vigik actifs — avertissements et inconnus, jamais bloquants."""
    batiments = set(codes_batiments())
    racine = code_par_defaut()
    manque: list[str] = []
    exces: list[str] = []
    inconnus: list[str] = []
    sans_acces = 0
    badges = session.exec(select(Vigik).where(Vigik.statut == StatutAcces.actif)).all()
    for badge in badges:
        if badge.perimetre_cible is None:
            sans_acces += 1
            continue
        if not lots_du_badge(session, badge):
            inconnus.append(_repere(session, badge))
            continue
        justifiees = {p.code for p in portes_de_badge(session, badge)}
        if not justifiees:
            inconnus.append(_repere(session, badge))
            continue
        ouvertes = set(json.loads(badge.perimetre_cible) or [])
        #  La racine ouvre tout : rien n'y manque, et elle n'est pas un bâtiment.
        if justifiees - ouvertes and racine not in ouvertes:
            manque.append(_repere(session, badge))
        if (ouvertes & batiments) - justifiees:
            exces.append(_repere(session, badge))

    trouves: list[Constat] = []
    if manque:
        trouves.append(
            constat(
                "badge_manque",
                AVERTISSEMENT,
                "Badge qui n'ouvre pas une circulation de ses lots (la porte de son "
                "logement, ou celle qui dessert sa place ou sa cave).",
                manque,
            )
        )
    if exces:
        trouves.append(
            constat(
                "badge_exces",
                AVERTISSEMENT,
                "Badge qui ouvre un bâtiment qu'aucun de ses lots ne justifie.",
                exces,
            )
        )
    if inconnus:
        trouves.append(
            constat(
                "badge_non_juge",
                INCONNU,
                "Badge qu'on ne peut pas juger : aucun lot actif, ou des lots sans "
                "bâtiment ni circulation (état descriptif non appliqué).",
                inconnus,
            )
        )
    if sans_acces:
        trouves.append(
            constat(
                "badge_sans_acces",
                INFORMATION,
                f"{sans_acces} badge(s) actif(s) sans accès enregistré : le conseil le "
                "décide dans le parc.",
            )
        )
    return trouves
