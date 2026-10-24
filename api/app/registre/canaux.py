"""Le CANAL, la VAGUE et la VERSION CIBLE portée par le bail (R5 #1881, spec §4.11).

Une installation suit soit le canal **Urgence** — la dernière version publiée de
`main` —, soit **une version** choisie dans la liste des versions publiées. La vague
dit QUAND elle la reçoit :

| Canal     | Vague      | Version cible                                              |
|-----------|------------|------------------------------------------------------------|
| Urgence   | Urgence    | la dernière version publiée, aussitôt                      |
| Urgence   | Pilote     | la dernière version publiée depuis au moins 7 jours        |
| Urgence   | Standard   | le dernier correctif de 7 jours de la mineure qui PRÉCÈDE la dernière (y-1) ; à défaut, d'une mineure antérieure |
| X.Y.Z     | Fixe       | X.Y.Z, une fois publiée depuis 7 jours ; d'ici là, rien ne bouge |

Une version est PUBLIÉE quand elle a sa release — l'archive de déploiement que la
mise à jour télécharge, jointe par le workflow « Images » après ses images
(`scripts/ci/publier-version.sh`). La référence relit ces releases chaque nuit
(`relire_versions`) ; sa date est celle du tag, d'où se comptent les 7 jours.

## Les règles

1. **La référence décide, l'installation suit** (règle 5) : la version que le bail
   porte (`version_cible`) est la seule que la mise à jour nocturne d'une réplique
   installe (`deploiement/standard/mise-a-jour.sh`). Sans bail valide, aucune (D18).
2. **`version_cible` est PURE** : l'installation, les versions publiées et l'instant
   entrent ; une version — ou rien — sort. 🔒 `tests/test_registre_canaux.py`.
3. **En attente ou résiliée → aucune version** : pas de mise à jour automatique
   sans inscription valide (D18). **Suspendue → sa version reste calculée** : la
   lecture seule ne prive pas les syndicats de leurs correctifs de sécurité.
4. **Une version choisie s'installe, plus ancienne comprise** : c'est l'**ordre de
   revenir à une version**, signé avec le bail — le SEUL chemin d'un retour.
5. **Urgence, Pilote et Standard ne font jamais reculer** une installation : la
   version retenue, ou celle qui tourne si elle est en avance.
6. **`main` n'est le canal que de la référence** : aucune installation ne s'y met.

Quelle version chaque vague retient, la liste proposée à l'opérateur (les 5 dernières
mineures, chacune à son dernier correctif) et ce que la purge des images et des
releases garde se lisent dans `registre/versions`, PUR : une seule règle pour l'API
et pour `scripts/ci/purge-paquets.sh`.

⚠️ Avant #2210, une installation suivait un canal-branche (`replica`, `special-…`)
et une version épinglée à part : `suivi_de` relit encore ces valeurs, qu'une image
précédente écrirait pendant un retour arrière (Urgence en Standard, ou la version
épinglée en Fixe). La table `canal_distribution` n'est plus lue.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime
from typing import Callable, Iterable, Optional

import httpx
from sqlalchemy.exc import SQLAlchemyError
from sqlmodel import Session, select

from app.registre import base, decisions
from app.registre.modeles import EtatInscription, Installation, VersionDisponible
from app.registre.versions import (
    ATTENTE_STANDARD,
    derniere,
    derniere_rodee,
    derniere_standard,
    plus_recente,
    version_valide,
)
from app.utils import demo, horloge
from app.utils.installation import DEPOT

logger = logging.getLogger("hostachy.registre")

#: Le canal de la référence seule (règle 6), et celui qui suit la dernière version.
CANAL_REFERENCE = "main"
CANAL_URGENCE = "urgence"
#: Ce que lit la référence : les releases du dépôt public, par pages de 100.
URL_RELEASES = f"https://api.github.com/repos/{DEPOT}/releases"
PAGES_MAX = 10

#: Le geste du journal qui règle la distribution d'une installation.
GESTE_DISTRIBUTION = "distribution"

VAGUE_URGENCE, VAGUE_PILOTE, VAGUE_STANDARD, VAGUE_FIXE = 0, 1, 2, 3


@dataclass(frozen=True)
class Vague:
    nom: str
    libelle: str
    #: ce qu'elle installe, en une phrase
    detail: str
    #: offerte quand le canal est Urgence ; sinon, quand c'est une version choisie
    avec_urgence: bool


#: Les vagues — la seule liste ; l'écran lit ce que le serveur rend.
VAGUES: dict[int, Vague] = {
    VAGUE_URGENCE: Vague(
        "urgence", "Urgence", "la dernière version, aussitôt publiée", avec_urgence=True
    ),
    VAGUE_PILOTE: Vague(
        "pilote", "Pilote", "la dernière version publiée depuis 7 jours", avec_urgence=True
    ),
    VAGUE_STANDARD: Vague(
        "standard",
        "Standard",
        "le dernier correctif de 7 jours de la mineure précédente (y-1)",
        avec_urgence=True,
    ),
    VAGUE_FIXE: Vague(
        "fixe", "Fixe", "la version choisie, 7 jours après sa publication", avec_urgence=False
    ),
}
#: Celle de toute inscription : une mineure de recul, rodée 7 jours.
VAGUE_DEFAUT = VAGUE_STANDARD


def suivi_de(inst: Installation) -> tuple[str, int]:
    """Le canal et la vague de `inst`, ramenés aux quatre combinaisons permises.

    Relit aussi les valeurs d'avant #2210 (voir l'en-tête) : un canal-branche
    devient Urgence, une version épinglée la version choisie."""
    if inst.canal == CANAL_REFERENCE:
        return CANAL_REFERENCE, VAGUE_DEFAUT
    for choisie in (inst.version_epinglee, inst.canal):
        if version_valide(choisie):
            return choisie.strip(), VAGUE_FIXE
    vague = inst.vague if inst.vague in VAGUES and VAGUES[inst.vague].avec_urgence else VAGUE_DEFAUT
    return CANAL_URGENCE, vague


def version_cible(
    inst: Installation, versions: Iterable[VersionDisponible], maintenant: datetime
) -> Optional[str]:
    """PURE — la version que le prochain bail de `inst` porte, ou None (aucune)."""
    if inst.etat not in (EtatInscription.active, EtatInscription.suspendue):
        return None  # règle 3
    canal, vague = suivi_de(inst)
    if canal == CANAL_REFERENCE:
        return None  # règle 6
    versions = list(versions)
    courante = inst.version_logicielle if version_valide(inst.version_logicielle) else None
    if vague == VAGUE_FIXE:
        publiee = next((v for v in versions if v.version == canal), None)
        if publiee is not None and maintenant - publiee.publiee_le >= ATTENTE_STANDARD:
            return canal  # règle 4 : plus ancienne, c'est l'ordre de revenir
        return courante  # pas encore son tour, ou plus publiée : rien ne bouge
    retenue = CIBLES[vague](versions, maintenant)
    if retenue is None:
        return None
    return plus_recente(v for v in (retenue.version, courante) if v)  # règle 5


#: Ce que retient chaque vague du canal Urgence.
CIBLES: dict[int, Callable[[list[VersionDisponible], datetime], Optional[VersionDisponible]]] = {
    VAGUE_URGENCE: lambda versions, _maintenant: derniere(versions),
    VAGUE_PILOTE: derniere_rodee,
    VAGUE_STANDARD: derniere_standard,
}


def versions_disponibles(session: Session) -> list[VersionDisponible]:
    return list(session.exec(select(VersionDisponible)).all())


# ── Le geste de l'opérateur ──────────────────────────────────────────────────


def regler_distribution(
    session: Session,
    inst: Installation,
    *,
    canal: str,
    vague: int,
    motif: str,
    auteur: str,
):
    """Fixe le canal et la vague de `inst` — motivé, inscrit au journal."""
    decisions.exiger_decidable(inst)
    motif = decisions.exiger_motif(motif)
    canal = canal.strip()
    if canal == CANAL_REFERENCE:
        raise decisions.DecisionRefusee("Le canal main est celui de la référence seule.")
    if vague not in VAGUES:
        raise decisions.DecisionRefusee(f"Vague inconnue : {vague}")
    if canal == CANAL_URGENCE:
        if not VAGUES[vague].avec_urgence:
            raise decisions.DecisionRefusee(
                "Le canal Urgence se suit en vague Urgence, Pilote ou Standard."
            )
    elif version_valide(canal):
        if vague != VAGUE_FIXE:
            raise decisions.DecisionRefusee("Une version choisie se suit en vague Fixe.")
        if canal not in {v.version for v in versions_disponibles(session)}:
            raise decisions.DecisionRefusee(
                f"Version non publiée : {canal} — elle n'a pas son archive de déploiement."
            )
    else:
        raise decisions.DecisionRefusee("Le canal est Urgence, ou une version X.Y.Z publiée.")
    inst.canal, inst.vague, inst.version_epinglee = canal, vague, None
    inst.mis_a_jour_le = horloge.maintenant()
    session.add(inst)
    suivi = "canal Urgence" if canal == CANAL_URGENCE else f"version {canal}"
    resume = f"{suivi}, vague {VAGUES[vague].libelle}"
    return decisions.consigner(session, inst, GESTE_DISTRIBUTION, f"{motif} — {resume}", auteur)


# ── Les versions publiées, relues chaque nuit ────────────────────────────────


@dataclass(frozen=True)
class Publication:
    version: str
    #: la date du tag : celle d'où se comptent les 7 jours
    publiee_le: datetime


def _date(texte: Optional[str]) -> Optional[datetime]:
    try:
        return datetime.fromisoformat((texte or "").replace("Z", "+00:00")).replace(tzinfo=None)
    except ValueError:
        return None


def publication_de(release: dict) -> Optional[Publication]:
    """PURE — la version qu'une release publie, ou None : brouillon, tag illisible, ou
    sans l'archive de déploiement que la mise à jour télécharge."""
    if not isinstance(release, dict) or release.get("draft"):
        return None
    version = str(release.get("tag_name") or "").removeprefix("v")
    archive = f"coprofirst-deploiement-{version}.tar.gz"
    noms = {a.get("name") for a in release.get("assets") or [] if isinstance(a, dict)}
    #  `created_at` : la date du commit tagué — juste aussi pour une release posée après.
    date = _date(release.get("created_at"))
    if not version_valide(version) or archive not in noms or date is None:
        return None
    return Publication(version, date)


def lire_publications(
    get: Callable[..., httpx.Response] = httpx.get,
) -> Optional[list[Publication]]:
    """Les versions publiées sur le dépôt, ou None : injoignable ou illisible — alors
    rien ne bouge (une lecture partielle effacerait des versions encore servies)."""
    lues: list[Publication] = []
    try:
        for page in range(1, PAGES_MAX + 1):
            reponse = get(URL_RELEASES, params={"per_page": 100, "page": page}, timeout=10)
            if reponse.status_code != 200:
                return None
            releases = reponse.json()
            if not isinstance(releases, list):
                return None
            lues += [p for p in map(publication_de, releases) if p]
            if len(releases) < 100:
                return lues
    except Exception:  # noqa: BLE001 — réseau, délai, JSON : jamais une liste
        return None
    return lues


def relire_versions(
    session: Session, publications: Optional[list[Publication]], maintenant: datetime
) -> str:
    """Aligne `version_disponible` sur les releases lues — ajoute, retire. Rend le constat."""
    if publications is None:
        return "releases illisibles : les versions publiées ne bougent pas"
    if not publications:
        return "aucune release lisible : les versions publiées ne bougent pas"
    lues = {p.version: p for p in publications}
    tenues = {v.version: v for v in versions_disponibles(session)}
    for version, ligne in tenues.items():
        if version not in lues:
            session.delete(ligne)  # release retirée : elle ne s'installe plus
    for version, p in lues.items():
        ligne = tenues.get(version) or VersionDisponible(version=version, publiee_le=p.publiee_le)
        ligne.publiee_le, ligne.lue_le = p.publiee_le, maintenant
        session.add(ligne)
    retirees = len(set(tenues) - set(lues))
    ajoutees = len(set(lues) - set(tenues))
    tete = plus_recente(lues)
    return f"versions publiées : {len(lues)} (+{ajoutees}, -{retirees}), dernière {tete}"


def run_canaux_registre() -> None:
    """Tâche de la plateforme : relire les versions publiées — chez la référence seulement."""
    if not base.registre_actif() or demo.est_demo():
        return
    publications = lire_publications()
    try:
        with Session(base.moteur()) as session:
            constat = relire_versions(session, publications, horloge.maintenant())
            session.commit()
    except SQLAlchemyError as exc:
        logger.warning("registre : versions publiées non relues (%s)", type(exc).__name__)
        return
    logger.info("registre : %s", constat)


def enregistrer(scheduler) -> None:
    """Pose la lecture à 03:50 — avant les baux de la nuit (04:20, `bail_installation`) —,
    et une première au démarrage : la liste que l'opérateur choisit n'attend pas la nuit."""
    scheduler.add_job(
        run_canaux_registre,
        "cron",
        hour=3,
        minute=50,
        id="canaux_registre",
        next_run_time=horloge.a_paris(horloge.maintenant()),
    )
