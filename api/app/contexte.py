"""Le contexte de copropriété — le SEUL accès aux ressources d'une copropriété (#1744).

Chantier multi-copropriétés, spec `specs/architecture/multi-coproprietes.md` §4.1,
règle 3 : *aucune ressource ne se construit depuis la configuration globale*. La
base, la racine des fichiers, le secret de signature et l'expéditeur des courriels
appartiennent à UNE copropriété ; ils se demandent ici, et nulle part ailleurs.

Tant qu'il n'y a qu'une copropriété (phase 2, §8 bis), le contexte les lit dans
`settings` : le comportement est inchangé. Le jour où une requête se résoudra par
son nom d'hôte (P2-9, #1751), seul ce module changera — et les appelants, qui ne
nomment plus `settings.database_url` ni `engine`, suivront sans un mot.

🔒 `tests/test_contexte_source_unique.py` refuse, dans `app/`, toute lecture
directe de ces ressources hors de ce module (et de `database.py`, qui construit
le moteur).

Il relit la configuration à chaque appel (`get_settings` est mis en cache une
fois pour le processus). Son seul état est le registre des états de processus
(`etat`), indexé par l'identifiant de la copropriété ; un registre des moteurs,
quand il viendra, le sera de même — `test_etat_module_par_copropriete.py` y veille.
"""

from __future__ import annotations

import functools
import logging
import threading
import time
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any

from sqlmodel import Session

from app.config import get_settings

if TYPE_CHECKING:
    from sqlalchemy.engine import Engine

logger = logging.getLogger("hostachy.taches")

#: L'identifiant de l'unique copropriété d'une installation de phase 2. Il indexe
#: déjà les états de processus (`etat`) : la seconde copropriété n'aura qu'à en
#: apporter un autre.
IDENTIFIANT_UNIQUE = "principale"


@dataclass(frozen=True)
class Copropriete:
    """Ce qu'il faut pour servir UNE copropriété — rien de commun à la plateforme."""

    identifiant: str
    url_base: str
    racine_fichiers: Path
    secret: str
    expediteur: str
    nom_expediteur: str


#: La copropriété que sert l'exécution en cours — posée par `dans()`. Une variable
#: de CONTEXTE, propre à chaque fil et à chaque tâche asynchrone : deux tâches
#: planifiées qui tournent en même temps ne se volent pas leur copropriété.
_servie: ContextVar[Copropriete | None] = ContextVar("copropriete_servie", default=None)


def courante() -> Copropriete:
    """La copropriété servie : celle que `dans()` a posée, sinon l'unique de l'installation.

    Le repli sur l'unique copropriété ne vaut qu'en phase 2 : la résolution par nom
    d'hôte (P2-9, #1751) le remplacera, et un hôte inconnu ne résoudra rien (§4.1,
    règle 2).
    """
    return _servie.get() or _unique()


def resoudre(scope: dict) -> Copropriete:
    """La copropriété qu'une requête sert, lue à son ENTRÉE (§4.1).

    Phase 2 : l'unique copropriété de l'installation. La résolution par nom d'hôte
    (P2-9, #1751) remplacera ce corps ; un hôte inconnu ne résoudra rien (règle 2).
    """
    return _unique()


class ResolutionCopropriete:
    """Intergiciel ASGI : chaque requête s'exécute dans le contexte de SA copropriété.

    Posé le plus à l'extérieur (`main.py`) : les dépendances (`get_session`), les
    routes, les tâches de fond d'une requête et les autres intergiciels voient la
    même copropriété. ASGI pur, et non `BaseHTTPMiddleware` : la variable de
    contexte se transmet alors sans détour à la route et à son fil d'exécution.
    """

    def __init__(self, app) -> None:
        self.app = app

    async def __call__(self, scope, receive, send) -> None:
        if scope["type"] not in ("http", "websocket"):
            await self.app(scope, receive, send)
            return
        with dans(resoudre(scope)):
            await self.app(scope, receive, send)


def coproprietes() -> tuple[Copropriete, ...]:
    """Toutes les copropriétés de l'installation. Une seule en phase 2."""
    return (_unique(),)


@contextmanager
def dans(copro: Copropriete) -> Iterator[Copropriete]:
    """Exécute le bloc dans le contexte de `copro` : base, fichiers, états, expéditeur."""
    jeton = _servie.set(copro)
    try:
        yield copro
    finally:
        _servie.reset(jeton)


def pour_chaque_copropriete(tache: Callable[[], Any], nom: str) -> Callable[[], None]:
    """L'enveloppe d'une tâche planifiée qui travaille pour UNE copropriété (§4.6, #1745).

    La tâche tourne une fois par copropriété, dans son contexte. L'échec de l'une
    est journalisé et ne bloque pas les suivantes ; chaque exécution laisse une
    ligne qui nomme la copropriété. Avec une seule copropriété, la boucle fait un
    tour.

    🔒 Toute tâche enregistrée passe par elle, sauf celles que
    `utils/taches.TACHES_DE_LA_PLATEFORME` déclare avec leur raison —
    `test_taches_planifiees_declarees.py` le vérifie sur le code, et
    `taches.verifier_taches_enregistrees` sur le planificateur au démarrage.
    """

    @functools.wraps(tache)
    def _par_copropriete() -> None:
        for copro in coproprietes():
            debut = time.monotonic()
            with dans(copro):
                try:
                    tache()
                except Exception:
                    #  ERROR, comme APScheduler l'aurait écrit sans l'enveloppe : une
                    #  tâche qui lève est une panne, et le pré-check doit la compter.
                    logger.exception("tache %s — copropriete %s : ECHEC", nom, copro.identifiant)
                    continue
            logger.info(
                "tache %s — copropriete %s : faite (%.1f s)",
                nom,
                copro.identifiant,
                time.monotonic() - debut,
            )

    _par_copropriete.par_copropriete = True  # type: ignore[attr-defined]
    return _par_copropriete


def _unique() -> Copropriete:
    """L'unique copropriété d'une installation de phase 2 : celle de la configuration."""
    s = get_settings()
    return Copropriete(
        identifiant=IDENTIFIANT_UNIQUE,
        url_base=s.database_url,
        racine_fichiers=Path(s.uploads_dir),
        secret=s.secret_key,
        expediteur=s.mail_from,
        nom_expediteur=s.mail_from_name,
    )


#: Les moteurs des copropriétés autres que l'unique, par (identifiant, URL de base).
#: L'URL fait partie de la clé : une copropriété dont la base change d'adresse
#: reçoit un moteur neuf, jamais celui de l'ancienne base.
_moteurs: dict[tuple[str, str], Engine] = {}
_verrou_moteurs = threading.Lock()


def moteur() -> Engine:
    """Le moteur de la base de la copropriété servie.

    L'unique copropriété de la phase 2 garde `app.database.engine`, lu à l'APPEL :
    un test qui le remplace obtient sa base partout. Toute autre copropriété reçoit
    le sien, construit une fois par la même recette (`database.creer_moteur`) —
    c'est ce qui permet au test d'étanchéité (#1746) de servir deux bases.
    """
    from app import database

    copro = courante()
    if copro.identifiant == IDENTIFIANT_UNIQUE:
        return database.engine
    cle_moteur = (copro.identifiant, copro.url_base)
    with _verrou_moteurs:
        if cle_moteur not in _moteurs:
            _moteurs[cle_moteur] = database.creer_moteur(copro.url_base)
        return _moteurs[cle_moteur]


def nouvelle_session() -> Session:
    """Une session hors requête HTTP (tâche planifiée, envoi différé, cache).

    Dans une route, la session vient de la dépendance `get_session`.
    """
    return Session(moteur())


#: Les états de processus (caches, quotas), un dictionnaire par (copropriété, nom).
#: Le SEUL état mutable qu'un module de l'application puisse tenir pour une
#: copropriété — `test_etat_module_par_copropriete.py` refuse tout autre (§4.5).
_etats: dict[tuple[str, str], dict] = {}


def etat(nom: str) -> dict:
    """Le dictionnaire d'état `nom` de la copropriété servie, créé vide au besoin.

    L'utilisateur n° 12 d'une copropriété n'est pas celui d'une autre : un cache
    indexé par le seul `user_id` les confondrait. Un module ne garde donc pas son
    cache dans une variable à lui ; il le demande ici à chaque usage, et reçoit
    celui de la copropriété servie. `setdefault` est atomique sous le GIL : deux
    fils qui demandent le même état reçoivent le même dictionnaire.
    """
    return _etats.setdefault((courante().identifiant, nom), {})
