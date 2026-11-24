"""Ce que coûte l'assistant IA — le journal et la consommation.

## Pourquoi (#1383, 27/09/2026)

Trois usages appellent un modèle facturé au jeton, dont un **automatique** : la
mise en forme des réponses du syndic reçues par courriel (#1322), déclenchée par
la relève toutes les dix minutes. Rien n'était compté. Une boucle — un courriel
qui en déclenche un autre — aurait facturé en silence jusqu'à la facture.

## Ce que ce module porte, et ce qu'il ne porte pas

- **le journal** : une ligne par appel parti chez le fournisseur (ou refusé par
  le plafond), écrite par `llm.demander` et par lui seul ;
- les **statuts** d'un refus avant l'envoi — les LIMITES elles-mêmes (appels
  par mois, par heure et par personne, premier essai) vivent dans
  `llm_limites` depuis le 04/10/2026, où elles ont remplacé un plafond mensuel
  en jetons que personne ne savait estimer ;
- **la consommation** par mois, usage et modèle, et son coût estimé au tarif
  que l'administrateur a saisi.

🔴 **Aucun tarif n'est écrit ici.** Les prix changent, et le modèle de chaque
usage se choisit dans l'administration : une grille codée en dur se périmerait
comme la liste de modèles retirée le 11/09. Sans tarif saisi, le coût est
`None` — jamais 0, qui se lirait « gratuit ».

🔴 **Les prix sont en DOLLARS par million de jetons** (30/09/2026, arbitré :
« comme les grilles »). Les grilles des fournisseurs sont en dollars ; les
recopier sans conversion est ce qui les rend vérifiables d'un coup d'œil. Ils
se stockent en TEXTE décimal (« 0.075 ») et se lisent en `Decimal` — jamais en
flottant, et plus en centimes : un prix de cache à 0,075 $ ne tient pas dans un
entier de centimes.

⚠️ Des COMPTEURS, jamais du contenu (`app/models/ia.py`).
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta
from decimal import Decimal, InvalidOperation
from typing import Any, Optional

from sqlalchemy import case, func
from sqlmodel import Session, select

from app import dialecte
from app.models.core import ConfigSite
from app.models.ia import AppelIA
from app.utils import horloge
from app.utils.llm_usages import USAGES

logger = logging.getLogger("hostachy.llm")

STATUT_SUCCES = "succes"
STATUT_ERREUR = "erreur"
#: Refusé avant l'envoi : la limite d'appels du mois est atteinte. La valeur
#: garde son nom d'origine — des lignes du journal la portent déjà.
STATUT_PLAFOND = "plafond"
#: Refusé avant l'envoi : la personne a atteint sa limite d'appels de l'heure.
STATUT_QUOTA = "quota"
#: Les refus avant l'envoi, que l'écran compte ensemble.
STATUTS_REFUS = (STATUT_PLAFOND, STATUT_QUOTA)

#: Le détail se garde treize mois : un an complet, plus le mois en cours, pour
#: comparer un mois à celui de l'an dernier. Purgé par la maintenance.
CONSERVATION_MOIS = 13


def jetons_de(charge: Any) -> tuple[Optional[int], Optional[int], Optional[int]]:
    """PURE. Les jetons (entrée, sortie, dont cache) d'une réponse de fournisseur.

    Deux vocabulaires existent, et les trois fournisseurs les emploient tous
    deux selon l'API : `input_tokens`/`output_tokens` (Anthropic, OpenAI
    Responses) et `prompt_tokens`/`completion_tokens` (OpenAI et Azure Chat).
    Une réponse sans compteur rend `None` — l'écran dira « non communiqué ».

    🔴 **Le cache, troisième prix** (30/09/2026). OpenAI met en cache, sans
    qu'on le demande, tout début de prompt de plus de 1 024 jetons déjà vu —
    nos consignes les dépassent — et le facture environ dix fois moins cher.
    L'entrée rendue ici est TOUJOURS le total, cache compris, et le troisième
    nombre en dit la part lue en cache :

    | Fournisseur | total d'entrée | dont cache |
    |---|---|---|
    | OpenAI, Azure | `prompt_tokens` (le contient déjà) | `prompt_tokens_details.cached_tokens` |
    | OpenAI Responses | `input_tokens` (idem) | `input_tokens_details.cached_tokens` |
    | Anthropic | `input_tokens` + `cache_read_input_tokens` + `cache_creation_input_tokens` | `cache_read_input_tokens` |

    ⚠️ Anthropic compte le cache À CÔTÉ de l'entrée : l'additionner est ce qui
    garde l'entrée comparable d'un fournisseur à l'autre. L'écriture de cache (+25 %) n'a pas de prix
    à elle : on n'active pas le cache chez Anthropic, elle vaut 0 aujourd'hui.
    """
    usage = charge.get("usage") if isinstance(charge, dict) else None
    if not isinstance(usage, dict):
        return None, None, None

    def entier(source: Any, *cles: str) -> Optional[int]:
        if not isinstance(source, dict):
            return None
        for cle in cles:
            v = source.get(cle)
            if isinstance(v, int) and not isinstance(v, bool):
                return v
        return None

    entree = entier(usage, "input_tokens", "prompt_tokens")
    sortie = entier(usage, "output_tokens", "completion_tokens")
    lu = entier(usage, "cache_read_input_tokens")
    if lu is not None:
        if entree is not None:
            entree += lu + (entier(usage, "cache_creation_input_tokens") or 0)
        return entree, sortie, lu
    details = usage.get("prompt_tokens_details") or usage.get("input_tokens_details")
    return entree, sortie, entier(details, "cached_tokens")


def debut_du_mois(maintenant: datetime) -> datetime:
    return maintenant.replace(day=1, hour=0, minute=0, second=0, microsecond=0)


def prix_par_million(valeur: Optional[str]) -> Optional[Decimal]:
    """PURE. Un prix saisi — en dollars par million de jetons —, ou `None`.

    Tolère la virgule française. Illisible, négatif ou nul : `None` — un prix
    qu'on ne sait pas lire ne vaut pas « gratuit ».
    """
    try:
        prix = Decimal(str(valeur or "").strip().replace(",", "."))
    except InvalidOperation:
        return None
    return prix if prix.is_finite() and prix > 0 else None


def journaliser(
    session: Session,
    *,
    usage: str,
    fournisseur: str,
    modele: str,
    statut: str,
    duree_ms: int = 0,
    jetons_entree: Optional[int] = None,
    jetons_sortie: Optional[int] = None,
    jetons_cache: Optional[int] = None,
) -> None:
    """Écrit une ligne du journal, dans SA propre transaction.

    ⚠️ Jamais dans la session de l'appelant : la valider emporterait ce qu'il
    avait en cours, au moment qu'il n'a pas choisi. Et une écriture de journal
    qui échoue ne fait JAMAIS échouer l'appel — elle se journalise.
    """
    try:
        with Session(session.get_bind()) as s:
            s.add(
                AppelIA(
                    usage=usage,
                    fournisseur=fournisseur,
                    modele=modele,
                    statut=statut,
                    duree_ms=max(0, int(duree_ms)),
                    jetons_entree=jetons_entree,
                    jetons_sortie=jetons_sortie,
                    jetons_cache=jetons_cache,
                )
            )
            s.commit()
    except Exception as exc:  # noqa: BLE001 — le journal ne casse pas l'appel  # pragma: no cover
        logger.warning("Journal IA non écrit (%s) : %s", usage, exc)


def _cout_usd(
    entree: int,
    sortie: int,
    cache: int,
    prix_entree: Optional[Decimal],
    prix_sortie: Optional[Decimal],
    prix_cache: Optional[Decimal],
) -> Optional[str]:
    """PURE. Le coût en dollars, au tarif saisi (dollars par million de jetons),
    en texte décimal à quatre décimales — `None` sans aucun prix.

    Calculé sur le TOTAL du mois, arrondi une fois : arrondir chaque appel perdait
    tout, un appel de 3 000 jetons coûtant moins d'un centime.

    `entree` comprend le `cache` (`jetons_de`) : la part en cache se facture au
    prix du cache, le reste au prix d'entrée. Sans prix de cache saisi, elle
    reste au prix d'entrée — une estimation haute plutôt qu'un coût oublié.
    """
    if prix_entree is None and prix_sortie is None:
        return None
    zero = Decimal(0)
    cache = min(max(cache, 0), entree)
    pe, ps = prix_entree or zero, prix_sortie or zero
    total = (entree - cache) * pe + cache * (prix_cache or pe) + sortie * ps
    return str((total / 1_000_000).quantize(Decimal("0.0001")))


def _tarif(reglages: dict[str, str], usage: str) -> tuple[Optional[Decimal], ...]:
    """Les trois prix saisis pour l'usage — envoyés, produits, lus en cache."""
    u = USAGES[usage]
    return tuple(
        prix_par_million(reglages.get(u.cle(c)))
        for c in ("prix_entree", "prix_sortie", "prix_cache")
    )


def cout_appel(
    session: Session,
    usage: str,
    entree: Optional[int],
    sortie: Optional[int],
    cache: Optional[int],
) -> Optional[str]:
    """Le coût d'UN appel, au tarif saisi pour l'usage — `None` sans tarif.

    Pour un historique qui garde le coût de chaque production (la synthèse
    d'une affaire close, #1643) : le journal, lui, ne chiffre que des totaux.
    """
    reglages = {r.cle: r.valeur for r in session.exec(select(ConfigSite)).all()}
    return _cout_usd(entree or 0, sortie or 0, cache or 0, *_tarif(reglages, usage))


def consommation(session: Session, maintenant: Optional[datetime] = None) -> dict:
    """Ce que l'écran de maintenance montre : par mois, par usage et modèle."""
    maintenant = maintenant or horloge.maintenant()
    mois = dialecte.mois(AppelIA.cree_le)  # clé machine, pas un affichage
    lignes = session.exec(
        select(
            mois,
            AppelIA.usage,
            AppelIA.modele,
            func.count(),
            #  🔴 `case`, jamais `func.sum(condition)` : SQLAlchemy type la somme
            #  d'un booléen en BOOLÉEN, et deux échecs se lisaient « 1 » (04/10/2026).
            func.sum(case((AppelIA.statut == STATUT_ERREUR, 1), else_=0)),
            func.sum(case((AppelIA.statut.in_(STATUTS_REFUS), 1), else_=0)),
            func.coalesce(func.sum(AppelIA.jetons_entree), 0),
            func.coalesce(func.sum(AppelIA.jetons_sortie), 0),
            func.coalesce(func.sum(AppelIA.jetons_cache), 0),
        )
        .group_by(mois, AppelIA.usage, AppelIA.modele)
        .order_by(mois.desc(), AppelIA.usage)
    ).all()
    reglages = {r.cle: r.valeur for r in session.exec(select(ConfigSite)).all()}
    tarifs = {code: _tarif(reglages, code) for code in USAGES}
    resultat: dict[str, list[dict]] = {}
    for m, usage, modele, appels, erreurs, refus, entree, sortie, cache in lignes:
        prix = tarifs.get(usage, (None, None, None))
        resultat.setdefault(m, []).append(
            {
                "usage": usage,
                "libelle": USAGES[usage].libelle if usage in USAGES else usage,
                "modele": modele,
                "appels": int(appels),
                "erreurs": int(erreurs or 0),
                "refus": int(refus or 0),
                "jetons_entree": int(entree),
                "jetons_sortie": int(sortie),
                "jetons_cache": int(cache),
                "cout_usd": _cout_usd(int(entree), int(sortie), int(cache), *prix),
            }
        )
    return {
        "mois": [{"mois": m, "usages": u} for m, u in resultat.items()],
        "mois_courant": maintenant.strftime("%Y-%m"),
    }


def problemes_ia(session: Session) -> list[str]:
    """Pour le contrôle de 06:00 : les usages REFUSÉS par leur limite du mois depuis 24 h.

    Le fait du jour, pas l'état du mois : une limite atteinte le 3 ne doit pas
    écrire tous les matins jusqu'au 30. Le quota d'une personne dans l'heure
    n'alerte pas : il borne un geste, il n'arrête aucun usage. Ce qui alerte, c'est qu'un appel a été
    refusé — l'usage automatique s'est arrêté, ou quelqu'un a buté dessus.
    """
    depuis = horloge.maintenant() - timedelta(hours=24)
    refus = session.exec(
        select(AppelIA.usage, func.count())
        .where(AppelIA.statut == STATUT_PLAFOND, AppelIA.cree_le >= depuis)
        .group_by(AppelIA.usage)
    ).all()
    return [
        f"Assistant IA : « {USAGES[u].libelle if u in USAGES else u} » refusé {n} fois "
        "depuis 24 h — limite d'appels du mois atteinte (Administration › Assistant IA)"
        for u, n in refus
    ]


def limite_conservation(maintenant: datetime) -> datetime:
    """Le 1er du mois le plus ancien conservé : le mois courant et les douze
    précédents. `utils/maintenance.purger` efface ce qui est avant."""
    limite = debut_du_mois(maintenant)
    for _ in range(CONSERVATION_MOIS - 1):
        limite = debut_du_mois(limite - timedelta(days=1))
    return limite
