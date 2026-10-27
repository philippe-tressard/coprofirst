"""La CONCILIATION d'une fusion refusée pour fuite de lecture — la règle, écrite une fois.

## La demande (27/10/2026)

> « Quand on veut fusionner 2 affaires liées, la fusion est parfois refusée car
>   une section diffère, notamment le périmètre : proposer un plan de
>   conciliation pour autoriser la fusion. »

## Ce que ça ne remet pas en cause (#1704, arbitré le 05/10/2026)

Une fusion verse les Suites de l'absorbée dans la principale : tout lecteur de la
principale les lit alors. Le refus (`fusion_affaires._sans_fuite`) empêche qu'une
personne lise ce qu'elle ne lisait pas. **Cet invariant demeure** : la
conciliation ne le lève jamais en silence, elle le transforme en DÉCISION du
conseil, avec les noms de ceux qu'elle touche.

## Les trois options — et ce que chacune change

| Option | Ce qu'elle fait | Ce qu'elle exige |
|---|---|---|
| `inverser` | l'absorbée devient la principale (la plus étroite absorbe) | rien : plus aucun lecteur n'en gagne. Hors clôture seulement — à la clôture, celle qu'on clôt absorbe (#1704) |
| `restreindre` | la principale prend ce que les deux affaires avaient en commun (périmètre, Destinataires, confidentialité) | une confirmation nominative si quelqu'un lirait encore ce qu'il ne lisait pas (l'auteur de la principale la lit toujours) |
| `elargir` | la principale prend l'union des deux : ceux de l'absorbée ne perdent rien | **la confirmation nominative** de chaque personne qui lira désormais ce qu'elle ne lisait pas. Impossible si l'une des deux est confidentielle |

## 🔒 Les chiffres viennent de la règle, jamais d'un calcul parallèle

Les champs d'une option sont des CANDIDATS (périmètres, Destinataires, accès) ;
ce qu'ils font lire se MESURE en posant le candidat sur la principale et en
interrogeant `ticket_visible`, compte par compte — la règle de la fiche. Un
candidat maladroit ne peut donc pas mentir : il montre simplement plus de monde.

La confirmation est NOMINATIVE : le client renvoie les identifiants qu'il a
montrés, le serveur recalcule et exige la MÊME liste (409 sinon — la liste a
changé entre la lecture et le clic, on la relit).
"""

from __future__ import annotations

import html
import json
from contextlib import contextmanager
from typing import Iterator, Optional

from fastapi import HTTPException
from sqlmodel import Session, select

from app.models.core import Ticket, TicketEvolution, Utilisateur
from app.utils import horloge
from app.utils.journal_securite import journaliser_securite
from app.utils.noms import nom_affiche
from app.utils.perimetres import (
    couvre,
    parse_json_perimetres,
    perimetre_cible_json,
    perimetre_label_liste,
)
from app.utils.visibility import destinataires_par_defaut, ticket_visible
from app.utils.visibility.socle import CODES_PUBLIC_CIBLE, LIBELLES_PUBLIC_CIBLE, _parse_json_list

INVERSER, RESTREINDRE, ELARGIR = "inverser", "restreindre", "elargir"
OPTIONS = (INVERSER, RESTREINDRE, ELARGIR)

_LIBELLES = {
    INVERSER: "Inverser : l'autre affaire absorbe",
    RESTREINDRE: "Restreindre à ce que les deux affaires avaient en commun",
    ELARGIR: "Élargir à l'union des deux",
}

#: Le public « Tous » et celui qui ne lit rien par profil (résident concerné, inconnu).
_COPROPRIETAIRES = {"copropriétaires_occupants", "bailleurs"}

#: Les champs d'accès d'une affaire — ce que `ticket_visible` lit, et que l'option pose.
_CHAMPS = ("perimetre_cible", "public_cible", "confidentiel", "reserve_perimetre")


# ── Qui lit ─────────────────────────────────────────────────────────────────


def _lecteurs(session: Session, ticket: Ticket, utilisateurs: list[Utilisateur]) -> set[int]:
    """Les comptes pour qui `ticket_visible` est vrai — compte par compte."""
    return {u.id for u in utilisateurs if ticket_visible(ticket, u)}


@contextmanager
def _provisoirement(ticket: Ticket, session: Session, champs: dict) -> Iterator[Ticket]:
    """Pose `champs` sur le ticket le temps d'une mesure, puis les REPREND.

    Rien n'est écrit : `no_autoflush` empêche l'ORM d'envoyer l'état provisoire,
    et les valeurs d'origine sont rétablies même si la mesure lève.
    """
    avant = {k: getattr(ticket, k) for k in champs}
    with session.no_autoflush:
        try:
            for k, v in champs.items():
                setattr(ticket, k, v)
            yield ticket
        finally:
            for k, v in avant.items():
                setattr(ticket, k, v)


def _nom(u: Utilisateur) -> str:
    return nom_affiche(u.prenom, u.nom)


# ── Les champs candidats ────────────────────────────────────────────────────


def _public_ensemble(t: Ticket) -> Optional[set[str]]:
    """Les profils qui lisent : `None` = tous, ensemble vide = personne par profil.

    Sans choix du conseil, c'est le défaut de la catégorie (`destinataires_par_defaut`).
    « Résident concerné » ne désigne aucun profil : il lit par le lien à l'affaire.
    """
    codes = _parse_json_list(t.public_cible, []) or destinataires_par_defaut(t)
    if "résidents" in codes:
        return None
    rendu: set[str] = set()
    for c in codes:
        if c == "copropriétaires":
            rendu |= _COPROPRIETAIRES
        elif c in CODES_PUBLIC_CIBLE:
            rendu.add(c)
    return rendu


def _public_json(ensemble: Optional[set[str]]) -> str:
    """Un ensemble sous sa forme stockée — vide : le conseil seul (la plus fermée)."""
    if ensemble is None:
        return json.dumps(["résidents"], ensure_ascii=False)
    return json.dumps(sorted(ensemble) or ["conseil_syndical"], ensure_ascii=False)


def _public_libelle(t: Ticket) -> str:
    ensemble = _public_ensemble(t)
    if ensemble is None:
        return "Tous"
    if not ensemble:
        return "Résident concerné"
    return ", ".join(LIBELLES_PUBLIC_CIBLE[c] for c in sorted(ensemble))


def _fusionner_codes(codes: list[str]) -> list[str]:
    """Les périmètres dédoublonnés : un code que l'un des autres englobe disparaît."""
    rendu: list[str] = []
    for c in codes:
        if any(couvre([r], c) for r in rendu):
            continue
        rendu = [r for r in rendu if not couvre([c], r)]
        rendu.append(c)
    return rendu


def _union_perimetres(a: list[str], b: list[str]) -> list[str]:
    return _fusionner_codes(a + b)


def _intersection_perimetres(a: list[str], b: list[str]) -> list[str]:
    """Ce que les deux sélections ont en commun : le plus étroit de chaque couple."""
    communs = [x for x in a if couvre(b, x)] + [y for y in b if couvre(a, y)]
    return _fusionner_codes(communs)


def champs_restreints(p: Ticket, a: Ticket) -> Optional[dict]:
    """Ce que les deux affaires partagent — `None` si leurs périmètres n'ont rien en commun."""
    perims = _intersection_perimetres(
        parse_json_perimetres(p.perimetre_cible), parse_json_perimetres(a.perimetre_cible)
    )
    if not perims:
        return None
    pp, pa = _public_ensemble(p), _public_ensemble(a)
    commun = pa if pp is None else pp if pa is None else pp & pa
    return {
        "perimetre_cible": perimetre_cible_json(perims),
        "public_cible": _public_json(commun),
        "confidentiel": bool(p.confidentiel or a.confidentiel),
        "reserve_perimetre": bool(p.reserve_perimetre or a.reserve_perimetre),
    }


def champs_elargis(p: Ticket, a: Ticket) -> Optional[dict]:
    """L'union des deux — `None` si l'une est confidentielle : ouvrir un contenu
    réservé au conseil n'est jamais une conciliation, c'est une autre décision."""
    if p.confidentiel or a.confidentiel:
        return None
    perims = _union_perimetres(
        parse_json_perimetres(p.perimetre_cible), parse_json_perimetres(a.perimetre_cible)
    )
    pp, pa = _public_ensemble(p), _public_ensemble(a)
    union = None if pp is None or pa is None else pp | pa
    return {
        "perimetre_cible": perimetre_cible_json(perims),
        "public_cible": _public_json(union),
        "confidentiel": False,
        "reserve_perimetre": bool(p.reserve_perimetre and a.reserve_perimetre),
    }


def _candidats(option: str, p: Ticket, a: Ticket) -> Optional[dict]:
    return {RESTREINDRE: champs_restreints, ELARGIR: champs_elargis}[option](p, a)


# ── L'écart, lisible ────────────────────────────────────────────────────────


def _acces_libelle(t: Ticket) -> str:
    if t.confidentiel:
        return "Confidentielle : le conseil syndical seulement"
    if t.reserve_perimetre:
        return "Réservée au périmètre sélectionné"
    return "Ouverte"


def ecarts(p: Ticket, a: Ticket) -> list[dict]:
    """Les sections d'accès qui DIFFÈRENT, chacune avec sa valeur des deux côtés."""
    lignes = [
        (
            "perimetre",
            "Périmètre",
            perimetre_label_liste(parse_json_perimetres(p.perimetre_cible)),
            perimetre_label_liste(parse_json_perimetres(a.perimetre_cible)),
        ),
        ("destinataires", "Destinataires", _public_libelle(p), _public_libelle(a)),
        ("acces", "Accès", _acces_libelle(p), _acces_libelle(a)),
    ]
    return [
        {"champ": c, "libelle": lib, "principale": vp, "absorbee": va}
        for c, lib, vp, va in lignes
        if vp != va
    ]


# ── Les options ─────────────────────────────────────────────────────────────


def _mesure(session, p: Ticket, a: Ticket, champs: dict, utilisateurs, lp: set[int], la: set[int]):
    """Ce qu'un candidat fait lire : (qui gagne l'accès à un contenu, qui le perd)."""
    with _provisoirement(p, session, champs):
        apres = _lecteurs(session, p, utilisateurs)
    return apres - (lp & la), (lp | la) - apres


def _entree(code: str, disponible: bool, pourquoi: Optional[str] = None, **suite) -> dict:
    return {
        "code": code,
        "libelle": _LIBELLES[code],
        "disponible": disponible,
        "pourquoi": pourquoi,
        "exposes": [],
        "perdants": 0,
        "resultat": None,
        "consentement": False,
        **suite,
    }


def _lu(t: Ticket) -> dict:
    """Les trois sections d'accès d'une affaire, en toutes lettres."""
    return {
        "perimetre": perimetre_label_liste(parse_json_perimetres(t.perimetre_cible)),
        "destinataires": _public_libelle(t),
        "acces": _acces_libelle(t),
    }


def _resultat(session: Session, p: Ticket, champs: dict) -> dict:
    """Ce que dirait la principale une fois `champs` posés — mesuré, rien n'est écrit."""
    with _provisoirement(p, session, champs):
        return _lu(p)


def options(
    session: Session, principale: Ticket, absorbee: Ticket, *, inversion: bool
) -> list[dict]:
    """Les trois options pour cette paire, chacune avec ce qu'elle fait lire.

    `inversion` : l'appelant laisse-t-il choisir qui absorbe ? (Pas à la clôture.)
    """
    utilisateurs = list(session.exec(select(Utilisateur)).all())
    lp = _lecteurs(session, principale, utilisateurs)
    la = _lecteurs(session, absorbee, utilisateurs)
    par_id = {u.id: u for u in utilisateurs}
    rendu = []

    # inverser : l'absorbée absorbe, si plus aucun lecteur n'y gagne.
    if not inversion:
        rendu.append(
            _entree(INVERSER, False, "À la clôture, l'affaire qu'on clôt absorbe les autres.")
        )
    elif la <= lp:
        rendu.append(_entree(INVERSER, True, perdants=len(lp - la)))
    else:
        rendu.append(
            _entree(
                INVERSER,
                False,
                "L'autre affaire serait lue par des personnes qui ne lisent pas celle-ci.",
            )
        )

    for code in (RESTREINDRE, ELARGIR):
        champs = _candidats(code, principale, absorbee)
        if champs is None:
            motif = (
                "Les deux périmètres n'ont rien en commun."
                if code == RESTREINDRE
                else "L'une des affaires est confidentielle : la rendre lisible est une autre décision."
            )
            rendu.append(_entree(code, False, motif))
            continue
        exposes, perdants = _mesure(session, principale, absorbee, champs, utilisateurs, lp, la)
        rendu.append(
            _entree(
                code,
                True,
                exposes=[{"id": i, "nom": _nom(par_id[i])} for i in sorted(exposes)],
                perdants=len(perdants),
                resultat=_resultat(session, principale, champs),
                consentement=bool(exposes),
            )
        )
    return rendu


def diagnostic(session: Session, principale: Ticket, absorbee: Ticket, *, inversion: bool) -> dict:
    """Ce que montre la boîte pour une affaire refusée : l'écart, puis les options."""
    return {
        "ecarts": ecarts(principale, absorbee),
        "options": options(session, principale, absorbee, inversion=inversion),
    }


# ── Appliquer ───────────────────────────────────────────────────────────────


def _trace(
    principale: Ticket,
    absorbee: Ticket,
    option: str,
    avant: dict,
    apres: dict,
    exposes: list[dict],
    lecteur: Utilisateur,
) -> TicketEvolution:
    """La Suite qui DIT, dans le fil de la principale, ce qui a changé de lecture."""
    e = html.escape
    lignes = [
        f"<p><strong>🔒 Conciliation de la fusion avec {e(absorbee.numero)}</strong> — "
        f"{e(_LIBELLES[option].split(':')[0])}.</p>"
    ]
    for cle, lib in (
        ("perimetre", "Périmètre"),
        ("destinataires", "Destinataires"),
        ("acces", "Accès"),
    ):
        if avant[cle] != apres[cle]:
            lignes.append(f"<p>{lib} : {e(avant[cle])} → {e(apres[cle])}</p>")
    if exposes:
        lignes.append(
            "<p>Liront désormais ce qu'ils ne lisaient pas, confirmés par le conseil : "
            + e(", ".join(x["nom"] for x in exposes))
            + ".</p>"
        )
    return TicketEvolution(
        ticket_id=principale.id,
        type="commentaire",
        contenu="".join(lignes),
        auteur_id=lecteur.id,
        cree_le=horloge.maintenant(),
    )


def appliquer(
    session: Session,
    principale: Ticket,
    absorbee: Ticket,
    option: str,
    confirmes: list[int],
    lecteur: Utilisateur,
) -> None:
    """Pose l'option sur la principale — 422 si elle n'est pas disponible, 409 si
    la liste confirmée n'est plus celle du serveur. Sans `commit`.

    `inverser` n'écrit rien ici : c'est l'ordre des affaires (`principale_id`)
    qui change, chez l'appelant ; elle est vérifiée par `_absorbables`.
    """
    if option not in (RESTREINDRE, ELARGIR):
        raise HTTPException(422, f"Conciliation inconnue : {option}")
    entree = next(
        o for o in options(session, principale, absorbee, inversion=False) if o["code"] == option
    )
    if not entree["disponible"]:
        raise HTTPException(
            422, f"Conciliation impossible pour {absorbee.numero} : {entree['pourquoi']}"
        )
    attendus = sorted(x["id"] for x in entree["exposes"])
    if sorted(set(confirmes or [])) != attendus:
        raise HTTPException(
            409,
            "La liste des personnes concernées a changé : relisez-la avant de confirmer.",
        )
    champs = _candidats(option, principale, absorbee)
    avant = _lu(principale)
    for k in _CHAMPS:
        setattr(principale, k, champs[k])
    principale.mis_a_jour_le = horloge.maintenant()
    session.add(principale)
    session.add(
        _trace(principale, absorbee, option, avant, entree["resultat"], entree["exposes"], lecteur)
    )
    journaliser_securite(
        "fusion_conciliation",
        acteur_id=lecteur.id,
        cible_id=principale.id,
        detail=f"option={option} absorbee={absorbee.id} exposes={len(attendus)}",
    )


def lecteurs_en_trop(session: Session, principale: Ticket, absorbee: Ticket) -> set[int]:
    """Ceux qui liraient l'absorbée via la principale sans la lire aujourd'hui."""
    utilisateurs = list(session.exec(select(Utilisateur)).all())
    return _lecteurs(session, principale, utilisateurs) - _lecteurs(session, absorbee, utilisateurs)


__all__ = [
    "ELARGIR",
    "INVERSER",
    "OPTIONS",
    "RESTREINDRE",
    "appliquer",
    "champs_elargis",
    "champs_restreints",
    "diagnostic",
    "ecarts",
    "lecteurs_en_trop",
    "options",
]
