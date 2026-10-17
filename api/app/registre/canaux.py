"""Les CANAUX, les VAGUES et la VERSION CIBLE portée par le bail (R5 #1881, spec §4.11).

D21 : un canal est un **pointeur vers une version de `main`**, jamais une branche de
travail — `main` (la référence seule), `replica` (le défaut), `special-<nom>`
(épinglage d'un groupe d'installations). Ce qu'un client a de spécifique passe par
le registre des services (§4.8), jamais par un canal.

## Les règles

1. **La référence décide, l'installation suit** (règle 5) : la version que le bail
   porte (`version_cible`) est la seule que la mise à jour nocturne d'une réplique
   installe (`deploiement/standard/mise-a-jour.sh`). Sans bail valide, aucune (D18).
2. **`version_cible` est PURE** : l'installation, son canal et l'instant entrent ;
   une version — ou rien — sort. 🔒 `tests/test_registre_canaux.py`.
3. **En attente ou résiliée → aucune version** : pas de mise à jour automatique
   sans inscription valide (D18). **Suspendue → sa version reste calculée** : la
   lecture seule ne prive pas les syndicats de leurs correctifs de sécurité.
4. **Épinglée → cette version-là**, plus ancienne comprise : c'est l'**ordre de
   revenir à une version**, signé avec le bail. C'est le SEUL chemin d'un retour.
5. **Par vagues** (`VAGUES`) : quand le canal avance, la vague pilote reçoit la
   version aussitôt, les autres après leur délai ; avant leur tour, elles gardent
   la version précédente du canal.
6. **Une cible tirée du canal ne fait jamais reculer** une installation : un canal
   qui recule, ou une installation déplacée vers un canal en retard, la laisse sur
   sa version. Reculer s'ordonne par l'épinglage (règle 4).
7. **`replica` avance seul** : chaque nuit, la référence lit la version de la branche
   `replica` du dépôt public (`relire_replica`) — la lecture que faisait jusqu'ici
   chaque réplique. Elle n'avance qu'en avant, comme la branche (#1754). Un canal
   spécial avance par l'opérateur, et chaque installation qui le suit le note à
   son journal.
8. **`main` n'est le canal que de la référence** : aucune installation ne s'y met.

⚠️ La version cible doit avoir sa release (l'archive de déploiement que la mise à
jour télécharge), donc être PROMUE : une version non promue échoue à l'installation,
et le rapport nocturne le dit.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Callable, Optional

import httpx
from sqlalchemy.exc import SQLAlchemyError
from sqlmodel import Session, select

from app.registre import base, decisions
from app.registre.modeles import CanalDistribution, EtatInscription, Installation
from app.utils import demo, horloge
from app.utils.installation import DEPOT

logger = logging.getLogger("hostachy.registre")

#: Le canal de la référence seule (règle 8), et celui de toute réplique par défaut.
CANAL_REFERENCE = "main"
CANAL_DEFAUT = "replica"
#: Un canal spécial : `special-` puis un nom en minuscules, chiffres et tirets.
MOTIF_SPECIAL = re.compile(r"^special-[a-z0-9][a-z0-9-]{0,39}$")
#: Une version cible : `X.Y.Z`, celle d'un tag de `main` — jamais un commit.
MOTIF_VERSION = re.compile(r"^\d+\.\d+\.\d+$")

#: Ce que lit la référence pour faire avancer `replica` (règle 7).
URL_VERSION_REPLICA = f"https://raw.githubusercontent.com/{DEPOT}/{CANAL_DEFAUT}/front/package.json"

#: Le geste du journal qui règle la distribution d'une installation.
GESTE_DISTRIBUTION = "distribution"
GESTE_CANAL_AVANCE = "canal_avance"


@dataclass(frozen=True)
class Vague:
    nom: str
    libelle: str
    #: jours entre l'avancée du canal et le tour de cette vague
    delai: timedelta


#: Les vagues, dans leur ordre de passage — la seule liste ; l'écran lit ce que le
#: serveur rend. La générale (J+1) est celle de toute inscription, comme l'était le
#: délai par défaut de la mise à jour nocturne (`COPROFIRST_DELAI_JOURS=1`).
VAGUES: dict[int, Vague] = {
    0: Vague("pilote", "Pilote — dès que le canal avance", timedelta(0)),
    1: Vague("générale", "Générale — le lendemain", timedelta(days=1)),
    2: Vague("tardive", "Tardive — trois jours après", timedelta(days=3)),
}
VAGUE_DEFAUT = 1


def _semver(texte: Optional[str]) -> Optional[tuple[int, int, int]]:
    m = MOTIF_VERSION.match((texte or "").strip())
    if not m:
        return None
    majeure, mineure, correctif = m[0].split(".")
    return int(majeure), int(mineure), int(correctif)


def version_valide(texte: Optional[str]) -> bool:
    return _semver(texte) is not None


def version_cible(
    inst: Installation, canal: Optional[CanalDistribution], maintenant: datetime
) -> Optional[str]:
    """PURE — la version que le prochain bail de `inst` porte, ou None (aucune)."""
    if inst.etat not in (EtatInscription.active, EtatInscription.suspendue):
        return None  # règle 3
    if inst.version_epinglee:
        return inst.version_epinglee  # règle 4
    if canal is None or not version_valide(canal.version):
        return None
    vague = VAGUES.get(inst.vague, VAGUES[VAGUE_DEFAUT])
    a_son_tour = canal.avance_le is None or maintenant - canal.avance_le >= vague.delai
    choisie = canal.version if a_son_tour else canal.version_precedente
    if not version_valide(choisie):
        return None
    courante = _semver(inst.version_logicielle)
    if courante and _semver(choisie) < courante:
        return inst.version_logicielle  # règle 6 : jamais reculer par le canal
    return choisie


def canal_de(session: Session, inst: Installation) -> Optional[CanalDistribution]:
    return session.exec(
        select(CanalDistribution).where(CanalDistribution.nom == inst.canal)
    ).first()


def canal_existant(session: Session, nom: str) -> Optional[CanalDistribution]:
    return session.exec(select(CanalDistribution).where(CanalDistribution.nom == nom)).first()


# ── Les gestes de l'opérateur ────────────────────────────────────────────────


def regler_distribution(
    session: Session,
    inst: Installation,
    *,
    canal: str,
    vague: int,
    version_epinglee: Optional[str],
    motif: str,
    auteur: str,
):
    """Fixe le canal, la vague et l'épinglage de `inst` — motivé, inscrit au journal."""
    decisions.exiger_decidable(inst)
    motif = decisions.exiger_motif(motif)
    if canal == CANAL_REFERENCE:
        raise decisions.DecisionRefusee("Le canal main est celui de la référence seule.")
    if canal != CANAL_DEFAUT and canal_existant(session, canal) is None:
        raise decisions.DecisionRefusee(f"Canal inconnu : {canal}")
    if vague not in VAGUES:
        raise decisions.DecisionRefusee(f"Vague inconnue : {vague}")
    epinglee = (version_epinglee or "").strip() or None
    if epinglee and not version_valide(epinglee):
        raise decisions.DecisionRefusee(
            "Une version épinglée s'écrit X.Y.Z, celle d'un tag de main."
        )
    inst.canal, inst.vague, inst.version_epinglee = canal, vague, epinglee
    inst.mis_a_jour_le = horloge.maintenant()
    session.add(inst)
    resume = f"canal {canal}, vague {VAGUES[vague].nom}"
    resume += f", épinglée en {epinglee}" if epinglee else ", non épinglée"
    return decisions.consigner(session, inst, GESTE_DISTRIBUTION, f"{motif} — {resume}", auteur)


def _avancer(canal: CanalDistribution, version: str, maintenant: datetime) -> bool:
    """Pose `version` sur le canal ; False si c'est déjà la sienne."""
    if canal.version == version:
        return False
    canal.version_precedente, canal.version = canal.version, version
    canal.avance_le = maintenant
    return True


def pointer_canal_special(session: Session, nom: str, version: str, motif: str, auteur: str):
    """Crée un canal spécial, ou le fait pointer vers `version` — chaque installation qui
    le suit l'inscrit à son journal (règle 7)."""
    motif = decisions.exiger_motif(motif)
    if not MOTIF_SPECIAL.match(nom):
        raise decisions.DecisionRefusee(
            "Un canal spécial s'écrit special-<nom> : minuscules, chiffres et tirets."
        )
    if not version_valide(version):
        raise decisions.DecisionRefusee(
            "La version d'un canal s'écrit X.Y.Z, celle d'un tag de main."
        )
    canal = canal_existant(session, nom) or CanalDistribution(nom=nom)
    neuf = canal.id is None
    if not _avancer(canal, version, horloge.maintenant()) and not neuf:
        return canal
    if neuf:
        canal.avance_le = None  # un canal neuf n'ouvre pas de vagues : rien n'avait la précédente
    session.add(canal)
    suiveuses = session.exec(select(Installation).where(Installation.canal == nom)).all()
    for inst in suiveuses:
        decisions.consigner(
            session, inst, GESTE_CANAL_AVANCE, f"{motif} — {nom} en {version}", auteur
        )
    return canal


# ── `replica`, relu chaque nuit (règle 7) ────────────────────────────────────


def lire_version_replica(get: Callable[..., httpx.Response] = httpx.get) -> Optional[str]:
    """La version que porte la branche `replica`, ou None : injoignable ou illisible."""
    try:
        reponse = get(URL_VERSION_REPLICA, timeout=10)
        version = reponse.json().get("version") if reponse.status_code == 200 else None
    except Exception:  # noqa: BLE001 — réseau, délai, JSON : jamais une version
        return None
    return version if version_valide(version) else None


def relire_replica(session: Session, version: Optional[str], maintenant: datetime) -> str:
    """Fait avancer le canal `replica` vers `version` — jamais en arrière. Rend le constat."""
    if not version_valide(version):
        return "version de replica illisible : le canal ne bouge pas"
    canal = canal_existant(session, CANAL_DEFAUT)
    if canal is None:
        #  Première lecture : cette version est promue depuis longtemps, toutes les
        #  vagues l'ont — aucune n'attend son tour (`avance_le` vide).
        session.add(CanalDistribution(nom=CANAL_DEFAUT, version=version))
        return f"replica lu pour la première fois : {version}"
    if canal.version and _semver(version) < _semver(canal.version):
        return f"replica porte {version}, plus ancienne que {canal.version} : ignorée"
    if not _avancer(canal, version, maintenant):
        return f"replica inchangé : {version}"
    session.add(canal)
    return f"replica avancé : {canal.version_precedente} → {version}"


def run_canaux_registre() -> None:
    """Tâche de la plateforme : relire `replica` — chez la référence seulement."""
    if not base.registre_actif() or demo.est_demo():
        return
    version = lire_version_replica()
    try:
        with Session(base.moteur()) as session:
            constat = relire_replica(session, version, horloge.maintenant())
            session.commit()
    except SQLAlchemyError as exc:
        logger.warning("registre : canal replica non relu (%s)", type(exc).__name__)
        return
    logger.info("registre : %s", constat)


def enregistrer(scheduler) -> None:
    """Pose la lecture à 03:50 — avant les baux de la nuit (04:20, `bail_installation`)."""
    scheduler.add_job(run_canaux_registre, "cron", hour=3, minute=50, id="canaux_registre")
