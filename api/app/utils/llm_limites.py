"""Les LIMITES d'un usage de l'assistant IA — combien d'appels par mois, combien
par heure et par personne, et ce qu'a coûté le premier essai.

## Pourquoi (04/10/2026)

Le plafond mensuel se saisissait en jetons (#1383) : un chiffre que personne ne
sait estimer — « 100000 » ne dit pas combien de synthèses il permet. Philippe
a demandé de se baser plutôt sur le coût du premier essai, avec un nombre
d'appels maximum par mois et un quota par heure et par utilisateur. Des trois
propositions faites, il a retenu celle-ci : **la limite compte des APPELS**, et
le premier essai sert d'étalon pour chiffrer ce que la limite laisse dépenser.

## Les trois règles

1. **Appels par mois** (`appels_mois`, vide = aucune limite) : les appels
   RÉUSSIS depuis le 1er du mois. Atteint, l'appel est refusé avant l'envoi
   (`STATUT_PLAFOND`) : l'usage automatique s'arrête, l'usage manuel reçoit un
   refus qui le dit, et le contrôle de 6 h le signale (`problemes_ia`).
2. **Appels par heure et par personne** (`appels_heure`) : sur l'heure
   GLISSANTE, pour qui fait le geste. Un usage automatique n'a personne derrière
   lui et n'y est pas soumis — le mois le borne.
3. **Le premier essai** (`reference`) : le premier appel réussi avec le modèle
   et l'effort ENREGISTRÉS. Changer l'un ou l'autre le périme — on ne l'efface
   pas, on cesse de le reconnaître —, et l'appel suivant devient le nouvel
   étalon. Le test de connexion n'en est jamais un : il pose une question d'un
   mot, pas celle de l'usage.

## 🔴 Le quota horaire se compte EN MÉMOIRE, jamais en base (arbitré)

Le journal (`AppelIA`) ne dit pas QUI a demandé — c'est voulu (`models/ia.py`,
`standards/14`). Y écrire l'identifiant pour compter une heure en ferait un
registre de qui interroge quoi. Le compteur vit donc dans ce processus : un
redémarrage ou une bascule le remet à zéro, ce qui ne coûte au pire qu'une
heure de quota en trop. L'API ne tourne que sur le nœud actif, dans un seul
processus : le compte est juste.

⚠️ Une place horaire se PREND avant l'envoi : un appel parti compte, même si le
fournisseur échoue ensuite — c'est la tentative qui coûte, et c'est la
répétition de tentatives qu'on borne.
"""

from __future__ import annotations

import json
import logging
import threading
import time
from collections import deque
from datetime import datetime
from typing import TYPE_CHECKING, Optional

from sqlalchemy import func
from sqlmodel import Session, select

from app import contexte
from app.models.core import ConfigSite
from app.models.ia import AppelIA
from app.utils import horloge
from app.utils.llm_journal import (
    STATUT_PLAFOND,
    STATUT_QUOTA,
    STATUT_SUCCES,
    cout_appel,
    debut_du_mois,
)
from app.utils.llm_usages import EFFORTS, USAGES
from app.utils.montants import montant_fr

if TYPE_CHECKING:  # pragma: no cover
    from app.utils.llm import ConfigLLM, Reponse

logger = logging.getLogger("hostachy.llm")

#: L'heure glissante du quota par personne, en secondes.
FENETRE_HEURE_S = 3600


def _lire(session: Session, cle: str) -> str:
    ligne = session.exec(select(ConfigSite).where(ConfigSite.cle == cle)).first()
    return (ligne.valeur if ligne else "") or ""


def _entier(session: Session, cle: str) -> int:
    """Un réglage entier de l'administration ; 0 s'il est absent ou illisible —
    une limite qu'on ne sait pas lire ne bloque rien."""
    try:
        return max(0, int(_lire(session, cle)))
    except (TypeError, ValueError):
        return 0


def appels_par_mois(session: Session, usage: str) -> int:
    return _entier(session, USAGES[usage].cle("appels_mois"))


def appels_par_heure(session: Session, usage: str) -> int:
    return _entier(session, USAGES[usage].cle("appels_heure"))


def appels_du_mois(session: Session, usage: str, maintenant: datetime) -> int:
    """Les appels RÉUSSIS de cet usage depuis le 1er du mois."""
    total = session.exec(
        select(func.count()).where(
            AppelIA.usage == usage,
            AppelIA.statut == STATUT_SUCCES,
            AppelIA.cree_le >= debut_du_mois(maintenant),
        )
    ).one()
    return int(total or 0)


def _nombre(n: int) -> str:
    return montant_fr(n, devise="")


def _refus_du_mois(session: Session, usage: str) -> Optional[str]:
    limite = appels_par_mois(session, usage)
    if not limite:
        return None
    faits = appels_du_mois(session, usage, horloge.maintenant())
    if faits < limite:
        return None
    return (
        f"Limite du mois atteinte pour « {USAGES[usage].libelle} » "
        f"({_nombre(faits)} appels sur {_nombre(limite)}). "
        "À relever dans Administration › Assistant IA, ou attendre le mois prochain."
    )


#  ── Le quota par heure et par personne — en mémoire ─────────────────────────


def _traces() -> dict[tuple[str, int], deque[float]]:
    """Les places prises dans LA copropriété servie, par (usage, personne) (#1744, §4.5)."""
    return contexte.etat("llm_limites.traces")


_verrou = threading.Lock()


def prendre_place(
    usage: str, demandeur: int, limite: int, instant: Optional[float] = None
) -> Optional[int]:
    """Prend une place dans l'heure glissante de `demandeur` pour cet usage.

    Rend `None` si la place est prise, sinon le nombre de secondes avant que la
    plus ancienne se libère. Le verrou couvre la relève des courriels, qui
    appelle depuis un autre fil que les requêtes.
    """
    instant = time.monotonic() if instant is None else instant
    with _verrou:
        trace = _traces().setdefault((usage, demandeur), deque())
        while trace and instant - trace[0] >= FENETRE_HEURE_S:
            trace.popleft()
        if len(trace) >= limite:
            return max(1, int(FENETRE_HEURE_S - (instant - trace[0])))
        trace.append(instant)
        return None


def oublier_les_places() -> None:
    """Vide le compteur horaire de la copropriété servie — pour les tests, qui partagent le processus."""
    with _verrou:
        _traces().clear()


def _refus_de_l_heure(session: Session, usage: str, demandeur: Optional[int]) -> Optional[str]:
    if demandeur is None:
        return None
    limite = appels_par_heure(session, usage)
    if not limite:
        return None
    attente = prendre_place(usage, demandeur, limite)
    if attente is None:
        return None
    minutes = max(1, -(-attente // 60))
    return (
        f"Vous avez fait {_nombre(limite)} appels « {USAGES[usage].libelle} » dans "
        f"l'heure, la limite par personne : réessayez dans {minutes} min."
    )


def refus_avant_envoi(
    session: Session, usage: str, demandeur: Optional[int]
) -> Optional[tuple[str, str]]:
    """(statut du journal, message) si l'appel doit être refusé, sinon `None`.

    Le mois d'abord : un appel refusé au mois ne doit pas prendre de place
    dans l'heure.
    """
    refus = _refus_du_mois(session, usage)
    if refus:
        return STATUT_PLAFOND, refus
    refus = _refus_de_l_heure(session, usage, demandeur)
    if refus:
        return STATUT_QUOTA, refus
    return None


#  ── Le premier essai — l'étalon du coût ─────────────────────────────────────


def _reference_lue(session: Session, usage: str) -> Optional[dict]:
    try:
        ref = json.loads(_lire(session, USAGES[usage].cle("reference")) or "null")
    except ValueError:
        return None
    return ref if isinstance(ref, dict) else None


def _reconnue(ref: Optional[dict], cfg: "ConfigLLM") -> bool:
    """L'essai a-t-il été fait avec le modèle ET l'effort enregistrés ?"""
    return bool(ref) and ref.get("modele") == cfg.modele and ref.get("effort") == cfg.effort


def noter_premier_essai(session: Session, cfg: "ConfigLLM", rep: "Reponse") -> None:
    """Enregistre cet appel comme premier essai s'il n'y en a pas pour le modèle
    et l'effort courants. Dans SA transaction, comme le journal — et une
    écriture qui échoue ne fait jamais échouer l'appel."""
    if cfg.usage is None or _reconnue(_reference_lue(session, cfg.usage.code), cfg):
        return
    valeur = json.dumps(
        {
            "modele": cfg.modele,
            "effort": cfg.effort,
            "entree": rep.jetons_entree,
            "sortie": rep.jetons_sortie,
            "cache": rep.jetons_cache,
            "le": horloge.maintenant().isoformat(timespec="seconds"),
        }
    )
    cle = cfg.usage.cle("reference")
    try:
        with Session(session.get_bind()) as s:
            ligne = s.get(ConfigSite, cle)
            if ligne:
                ligne.valeur = valeur
            else:
                ligne = ConfigSite(cle=cle, valeur=valeur)
            s.add(ligne)
            s.commit()
    except Exception as exc:  # noqa: BLE001 — l'étalon ne casse jamais l'appel  # pragma: no cover
        logger.warning("Premier essai IA non noté (%s) : %s", cfg.usage.code, exc)


def _libelle_effort(valeur_api: str) -> str:
    return next((lib for _, lib, api in EFFORTS if api == valeur_api), "Par défaut du modèle")


def premier_essai(session: Session, usage: str, cfg: "ConfigLLM") -> Optional[dict]:
    """Le premier essai RECONNU pour la configuration courante, chiffré au tarif
    saisi — `None` s'il n'y en a pas encore."""
    ref = _reference_lue(session, usage)
    if not _reconnue(ref, cfg):
        return None
    entree, sortie, cache = (ref.get(k) for k in ("entree", "sortie", "cache"))
    return {
        "modele": ref["modele"],
        "effort": _libelle_effort(ref.get("effort") or ""),
        "le": ref.get("le"),
        "jetons_entree": entree,
        "jetons_sortie": sortie,
        "jetons_cache": cache,
        "cout_usd": cout_appel(session, usage, entree, sortie, cache),
    }


def suivi(session: Session, maintenant: Optional[datetime] = None) -> list[dict]:
    """Ce que les écrans montrent de chaque usage : ses deux limites, ses appels
    du mois et son premier essai."""
    from app.utils.llm import config_llm

    maintenant = maintenant or horloge.maintenant()
    return [
        {
            "usage": code,
            "libelle": u.libelle,
            "appels_mois": appels_par_mois(session, code),
            "appels_heure": appels_par_heure(session, code),
            "appels": appels_du_mois(session, code, maintenant),
            "premier_essai": premier_essai(session, code, config_llm(session, code)),
        }
        for code, u in USAGES.items()
    ]


__all__ = [
    "FENETRE_HEURE_S",
    "appels_du_mois",
    "noter_premier_essai",
    "oublier_les_places",
    "premier_essai",
    "prendre_place",
    "refus_avant_envoi",
    "suivi",
]
