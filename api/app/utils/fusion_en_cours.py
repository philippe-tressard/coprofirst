"""Les affaires LIÉES du Suivi des affaires : les rassembler, les fusionner, ou
écarter leur fusion (#2083) — la règle, écrite une fois.

## La demande (19/10/2026, reformulation validée le 20/10/2026)

> « Si dans la liste des affaires il y a deux ou plusieurs affaires liées :
> les rassembler dans le tri ; offrir la possibilité de les fusionner — l'IA
> propose un nouveau titre et un nouveau résumé comprenant les affaires
> fusionnées (descriptifs, suites et PJ). L'historique de fusion est conservé
> pour citer les affaires fusionnées lors du point. Si la fusion est annulée,
> il y aura un CR pour chaque affaire et le tri par ancienneté reprendra —
> historique pour indiquer que les affaires n'ont pas été fusionnées (et ne
> sera pas repris à la clôture de l'une d'elles). La fusion peut se faire en
> dehors d'un point. »

## Arbitré

- **La plus ancienne absorbe** (20/10/2026) — elle garde son numéro ; les autres
  lui sont rattachées par le mécanisme de la clôture (#1704,
  `fusion_affaires.fusionner`), y compris son refus quand un lecteur de la
  principale ne lisait pas l'absorbée. Différence : l'affaire **reste ouverte**,
  et prend le titre et la description relus par le conseil.
- **Rassembler** : les affaires liées par un lien NON écarté, toutes deux au
  relevé, forment un groupe ; il prend la place de la plus ancienne, les autres
  la suivent dans l'ordre d'ancienneté (`ordonner`).
- **Écarter** : le lien reste ; la paire ne se rassemble plus, n'est plus
  proposée à la fusion — ici comme à la clôture (`fusion_affaires.candidates`) —,
  et une Suite le dit dans chaque affaire.
- **Citer au point** : une affaire qui en a absorbé d'autres les nomme
  (`absorbees_par`) — au tableau, au compte rendu et au PDF.
"""

from __future__ import annotations

import html
from typing import Iterable, Optional

from fastapi import HTTPException
from sqlmodel import Session, col, or_, select

from app.auth.deps import est_moderateur
from app.models.affaires_liees import AffaireLiee
from app.models.core import Utilisateur
from app.models.tickets import Ticket, TicketEvolution
from app.utils import horloge
from app.utils.affaires_liees import ids_lies
from app.utils.dates_fr import date_longue


def composantes(paires: Iterable[tuple[int, int]], ids: list[int]) -> dict[int, int]:
    """PURE. Le GROUPE de chaque affaire liée : l'identifiant du premier membre
    dans l'ordre de `ids` (la plus ancienne). Une affaire seule n'a pas de groupe."""
    rang = {i: n for n, i in enumerate(ids)}
    parent = {i: i for i in ids}

    def racine(i: int) -> int:
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    for a, b in paires:
        if a in parent and b in parent:
            ra, rb = racine(a), racine(b)
            if ra != rb:
                parent[max(ra, rb, key=rang.get)] = min(ra, rb, key=rang.get)
    membres: dict[int, list[int]] = {}
    for i in ids:
        membres.setdefault(racine(i), []).append(i)
    return {i: r for r, m in membres.items() if len(m) > 1 for i in m}


def ordonner(affaires: list, groupe_de: dict[int, int]) -> list:
    """PURE. Les affaires dans leur ordre, chaque groupe rassemblé à la place de
    son premier membre — les autres membres le suivent, dans leur ordre."""
    rendu, vus = [], set()
    for a in affaires:
        if a.id in vus:
            continue
        g = groupe_de.get(a.id)
        bloc = [a] if g is None else [b for b in affaires if groupe_de.get(b.id) == g]
        rendu.extend(bloc)
        vus.update(b.id for b in bloc)
    return rendu


def _liens_entre(session: Session, ids: list[int]) -> list[AffaireLiee]:
    if len(ids) < 2:
        return []
    return list(
        session.exec(
            select(AffaireLiee).where(
                col(AffaireLiee.affaire_id).in_(ids), col(AffaireLiee.liee_id).in_(ids)
            )
        ).all()
    )


def groupes(session: Session, ids: list[int]) -> dict[int, int]:
    """Le groupe de chaque affaire du relevé — les liens écartés ne rassemblent pas."""
    paires = [
        (lg.affaire_id, lg.liee_id)
        for lg in _liens_entre(session, ids)
        if lg.fusion_ecartee_le is None
    ]
    return composantes(paires, ids)


def absorbees_par(session: Session, ids: list[int]) -> dict[int, list[Ticket]]:
    """Les affaires que chacune a absorbées — l'historique de fusion, cité au point."""
    if not ids:
        return {}
    rendu: dict[int, list[Ticket]] = {}
    for t in session.exec(
        select(Ticket)
        .where(col(Ticket.fusionnee_dans_id).in_(ids))
        .order_by(Ticket.cree_le, Ticket.id)
    ).all():
        rendu.setdefault(t.fusionnee_dans_id, []).append(t)
    return rendu


# ── Les gestes ────────────────────────────────────────────────────────────


def _exiger_conseil(lecteur: Utilisateur) -> None:
    if not est_moderateur(lecteur):
        raise HTTPException(403, "Seul le conseil syndical fusionne des affaires")


def affaires_du_groupe(
    session: Session, ids: list[int], principale_id: Optional[int] = None
) -> list[Ticket]:
    """Les affaires demandées, la plus ancienne en tête — 422 s'il en manque une,
    s'il y en a moins de deux, ou si elles ne sont pas liées entre elles.

    `principale_id` : le conseil a CONCILIÉ une fusion refusée en faisant absorber
    l'autre (`fusion_conciliation`, option « inverser ») — elle passe en tête."""
    uniques = list(dict.fromkeys(int(i) for i in ids))
    tickets = [session.get(Ticket, i) for i in uniques]
    if len(uniques) < 2 or any(t is None for t in tickets):
        raise HTTPException(422, "Deux affaires liées au moins, toutes existantes")
    paires = [(lg.affaire_id, lg.liee_id) for lg in _liens_entre(session, uniques)]
    if set(composantes(paires, uniques)) != set(uniques):
        raise HTTPException(422, "Ces affaires ne sont pas liées entre elles")
    rendu = sorted(tickets, key=lambda t: (t.cree_le, t.id))
    if principale_id is not None:
        if principale_id not in uniques:
            raise HTTPException(422, "La principale choisie n'est pas dans ce groupe")
        rendu.sort(key=lambda t: t.id != principale_id)  # stable : le reste garde l'ancienneté
    return rendu


def _suite(ticket: Ticket, contenu: str, lecteur: Utilisateur) -> TicketEvolution:
    return TicketEvolution(
        ticket_id=ticket.id,
        type="commentaire",
        contenu=contenu,
        auteur_id=lecteur.id,
        cree_le=horloge.maintenant(),
    )


def fusionner(
    session: Session,
    ids: list[int],
    lecteur: Utilisateur,
    titre: str,
    description: str,
    principale_id: Optional[int] = None,
    conciliations: Optional[dict] = None,
) -> tuple[Ticket, list[tuple[Ticket, str]]]:
    """La plus ancienne absorbe les autres et prend le titre et la description
    relus par le conseil ; elle reste ouverte. Rend la principale et les
    absorbées (avec l'état qu'elles quittent). Sans `commit`.

    `principale_id` et `conciliations` : ce que le conseil a décidé pour une
    fusion refusée pour fuite de lecture (`utils/fusion_conciliation`)."""
    from app.utils.fusion_affaires import fusionner as absorber

    _exiger_conseil(lecteur)
    principale, *autres = affaires_du_groupe(session, ids, principale_id)
    restantes = {t.id for t in autres}
    absorbees: list[tuple[Ticket, str]] = []
    #  Une chaîne A–B–C : C ne devient candidate qu'une fois B absorbée (ses
    #  liens passent alors à A, `_deplacer_liens`).
    while restantes:
        directes = sorted(restantes & ids_lies(session, principale.id))
        if not directes:
            raise HTTPException(422, "Ces affaires ne sont pas liées entre elles")
        absorbees += absorber(session, principale, directes, lecteur, None, conciliations)
        restantes -= set(directes)
    e = html.escape
    ancien = principale.titre
    liste = ", ".join(f"{e(a.numero)} — « {e(a.titre)} »" for a, _ in absorbees)
    session.add(
        _suite(
            principale,
            f"<p><strong>🔀 Fusion</strong> de {liste}, décidée par le conseil le "
            f"{date_longue(horloge.aujourd_hui())}. Ancien titre : « {e(ancien)} ».</p>",
            lecteur,
        )
    )
    principale.titre = titre.strip() or ancien
    principale.description = description
    #  Le résumé de l'assistant décrivait l'affaire d'avant : il est à refaire.
    principale.resume_ia = None
    principale.resume_ia_le = None
    principale.mis_a_jour_le = horloge.maintenant()
    session.add(principale)
    return principale, absorbees


def ecarter(session: Session, ids: list[int], lecteur: Utilisateur) -> list[Ticket]:
    """« Ne pas fusionner » : chaque lien entre ces affaires est écarté, et une
    Suite le dit dans chacune. Sans `commit`."""
    _exiger_conseil(lecteur)
    tickets = affaires_du_groupe(session, ids)
    maintenant = horloge.maintenant()
    for lg in _liens_entre(session, [t.id for t in tickets]):
        lg.fusion_ecartee_le = maintenant
        lg.fusion_ecartee_par_id = lecteur.id
        session.add(lg)
    e = html.escape
    for t in tickets:
        autres = ", ".join(f"{e(a.numero)} — « {e(a.titre)} »" for a in tickets if a.id != t.id)
        session.add(
            _suite(
                t,
                f"<p><em>Fusion écartée par le conseil avec {autres} : chaque affaire "
                "garde son suivi.</em></p>",
                lecteur,
            )
        )
    return tickets


def liens_ecartes(session: Session, ticket_id: int) -> set[int]:
    """Les affaires dont la fusion avec celle-ci a été écartée — la clôture les tait."""
    return {
        (lg.liee_id if lg.affaire_id == ticket_id else lg.affaire_id)
        for lg in session.exec(
            select(AffaireLiee).where(
                or_(AffaireLiee.affaire_id == ticket_id, AffaireLiee.liee_id == ticket_id),
                col(AffaireLiee.fusion_ecartee_le).is_not(None),
            )
        ).all()
    }


__all__ = [
    "absorbees_par",
    "composantes",
    "ecarter",
    "fusionner",
    "groupes",
    "liens_ecartes",
    "ordonner",
]
