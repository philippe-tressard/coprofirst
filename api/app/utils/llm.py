"""Parler à un modèle de langage — un seul point d'appel, trois fournisseurs.

## Ce que ce module porte

Le produit doit pouvoir interroger une IA (première usage : la synthèse d'un
contrat d'entretien, #899). Le fournisseur, la clé et le modèle se règlent depuis
l'administration — pas dans un fichier d'environnement, parce que c'est un
réglage de PRODUIT que le gestionnaire du site change, comme le SMTP.

## Où sont les fournisseurs

Dans `llm_fournisseurs.py`, depuis le 11/09/2026 : **ici on lit une
configuration et on passe un appel**, là-bas on décrit des services. Ce module
reste la porte d'entrée — les appelants importent d'ici, `__all__` le déclare, et
le découpage ne change aucun contrat.

## 🔴 Un appel qui ÉCOUTE le service

Un modèle récent a refusé `max_tokens` en réclamant `max_completion_tokens`
(constaté le 11/09/2026 au premier essai de `gpt-5.6-terra`). Deux voies :
tenir la liste des modèles qui veulent l'un ou l'autre nom — un catalogue, qui se
périme, et qu'on venait justement de supprimer du champ « Modèle » — ou lire le
paramètre que le service NOMME dans son refus, et reprendre l'appel corrigé.
C'est la seconde : voir `Fournisseur.adapter`, et `MAX_ADAPTATIONS` qui la borne.

## Deux étages de configuration (17/09/2026, #984)

Le **commun** — activation globale, fournisseur, clé, adresse, version d'API,
délai — se lit une fois pour tous. Le **par usage** — activation, modèle,
prompt, plafond — se lit pour l'usage demandé (`config_llm(session, usage)`),
sous les clés `llm_<usage>_*`. Les usages eux-mêmes sont déclarés dans
`llm_usages.py` : ce module n'en tient aucune liste.

⚠️ Il n'y a **pas de modèle commun** : chaque usage nomme le sien, et un usage
sans modèle ne peut pas appeler. C'est l'arbitrage de Philippe — deux usages
n'ont pas le même modèle idéal — et c'est ce qui évite qu'un réglage fait pour
la synthèse s'applique en silence à la réécriture d'une description.

## Ce que ce module NE fait pas

Il ne sait rien des contrats, des synthèses ni d'aucun métier : il envoie une
consigne et un message, il rend du texte. Ce qu'on demande au modèle vit chez
l'appelant — sinon ce fichier deviendrait le catalogue de tous les usages.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from typing import Any, Optional

from sqlmodel import Session, select

from app.models.core import ConfigSite
from app.utils.llm_fournisseurs import (
    FOURNISSEUR_DEFAUT,
    FOURNISSEURS,
    ErreurLLM,
    RefusLimite,
    Fournisseur,
    FournisseurAnthropic,
    FournisseurAzure,
    PieceJointe,
)
from app.utils import llm_journal, llm_limites
from app.utils.llm_usages import CHAMP_COPROPRIETAIRES, USAGES, Usage, valeur_effort
from app.utils.demo import exiger_hors_demo
from app.utils.services import SERVICE_IA, service_actif

#: 🔴 Ce module reste **la porte d'entrée unique**, même depuis que les
#: fournisseurs vivent à côté (11/09/2026). Les appelants — routers, synthèse de
#: contrat, tests — importent d'ici et n'ont pas à savoir qu'il y a deux
#: fichiers : le découpage est une affaire de lisibilité, pas un changement de
#: contrat. C'est ce que déclare ce `__all__`, et c'est pourquoi les noms
#: réexportés y figurent.
__all__ = [
    "CLE_API",
    "CLE_BASE_URL",
    "CLE_DELAI",
    "CLE_ENVOI_DOCUMENT",
    "CLE_FOURNISSEUR",
    "CLE_VERSION_API",
    "FOURNISSEUR_DEFAUT",
    "FOURNISSEURS",
    "USAGES",
    "ConfigLLM",
    "ErreurLLM",
    "RefusLimite",
    "Fournisseur",
    "FournisseurAnthropic",
    "FournisseurAzure",
    "PieceJointe",
    "Reponse",
    "config_llm",
    "demander",
    "modeles_disponibles",
    "tester",
]

logger = logging.getLogger("hostachy.llm")

#: Délai au-delà duquel on renonce. Une requête d'écran ne peut pas attendre
#: indéfiniment : le geste doit rendre la main, fût-ce sur un échec.
DELAI_DEFAUT_S = 45


@dataclass(frozen=True)
class Reponse:
    """Ce que le modèle a rendu, ET ce qu'il a réellement reçu.

    🔴 Le second point n'est pas un détail de journal : quand le service refuse
    les pièces jointes, l'appel aboutit quand même — sur la seule fiche. Sans
    `documents_joints`, l'écran présenterait cette synthèse appauvrie comme si
    elle avait lu les contrats. Une réponse qui ne dit pas ce qu'elle a lu est
    invérifiable (11/09/2026).
    """

    texte: str
    documents_joints: int
    #: Ce que le fournisseur dit avoir compté — `None` s'il ne le dit pas.
    jetons_entree: Optional[int] = None
    jetons_sortie: Optional[int] = None
    #: La part de l'entrée lue en cache — facturée à son propre prix.
    jetons_cache: Optional[int] = None

    def __str__(self) -> str:  # pragma: no cover - confort d'écriture
        return self.texte


#: Combien de fois au plus on corrige la requête après un refus de paramètre.
#: Deux suffisent aux cas connus (le plafond de jetons, la température) ; le
#: plafond existe pour qu'un service qui refuserait tout ne soit pas appelé en
#: boucle — il est facturé à l'appel.
MAX_ADAPTATIONS = 2


def _charge(reponse: Any) -> dict[str, Any]:
    """Le JSON d'une réponse, ou un objet vide — un corps illisible n'est pas
    une panne de plus à distinguer ici."""
    try:
        charge = reponse.json()
    except ValueError:
        return {}
    return charge if isinstance(charge, dict) else {}


#: Les clés de `ConfigSite` qui décrivent l'accès au modèle.
#:
#: ⚠️ `llm_api_key` est déclarée dans `routers/config._SECRETS` : sa valeur ne
#: sort JAMAIS de l'API, même pour un administrateur. L'écran sait seulement
#: qu'une clé existe (03/09/2026 — `smtp_password` avait voyagé en clair dans la
#: réponse HTTP alors que l'écran ne l'affichait pas ; la protection était dans
#: le rendu, c'est-à-dire nulle part).
#  L'activation de l'assistant n'est plus une clé d'ici : c'est celle du SERVICE
#  (`utils/services`, #1718), lue par `service_actif` comme les autres.
CLE_FOURNISSEUR = "llm_fournisseur"
CLE_API = "llm_api_key"
CLE_BASE_URL = "llm_base_url"
CLE_VERSION_API = "llm_api_version"
CLE_DELAI = "llm_delai_s"
CLE_ENVOI_DOCUMENT = "llm_envoi_document"
#  ⚠️ `llm_modele` et `llm_max_jetons` n'existent PLUS : la migration 0194 les a
#  déplacées sous `llm_synthese_contrat_*`. Les lire ici redonnerait deux vérités.


@dataclass
class ConfigLLM:
    """La configuration lue, prête à servir — ou à dire pourquoi elle ne peut pas.

    Le commun est toujours renseigné ; les quatre champs d'usage — `usage`,
    `actif_usage`, `modele`, `prompt`, `max_jetons` — ne le sont que si
    `config_llm` a reçu un usage. Sans usage (le catalogue des modèles, qui n'en
    a pas besoin), `modele` est vide et `verifier()` doit être appelée avec
    `exiger_modele=False`.
    """

    actif: bool
    fournisseur: Fournisseur
    cle: str
    base_url: str
    version_api: str
    delai_s: int
    envoi_document: bool
    #: L'usage lu, ou `None` pour le seul commun.
    usage: Optional[Usage] = None
    actif_usage: bool = False
    modele: str = ""
    prompt: str = ""
    max_jetons: int = 0
    #: La valeur d'API de l'effort de raisonnement (« low »…), ou vide : rien
    #: n'est envoyé et le modèle garde son défaut (`llm_usages.EFFORTS`).
    effort: str = ""
    #: L'usage est-il ouvert aux copropriétaires ? Toujours faux pour un usage
    #: qui ne s'y ouvre pas (`Usage.ouvrable_aux_coproprietaires`).
    ouvert_coproprietaires: bool = False

    def verifier(self, *, exiger_actif: bool = True, exiger_modele: bool = True) -> None:
        """Lève `ErreurLLM` si l'appel ne peut pas aboutir — avant de le tenter.

        ⚠️ On échoue AVANT la requête réseau plutôt qu'après : un 401 met
        plusieurs secondes et rend un message du fournisseur, pas du produit.

        🔴 `exiger_actif=False` pour le TEST DE CONNEXION (11/09/2026, constaté à
        l'écran : « j'ai voulu tester » → *« l'assistant est désactivé »*).

        L'ordre naturel est : je saisis, je teste, **puis** j'active — on vérifie
        une configuration pour DÉCIDER de l'activer. Exiger l'activation avant de
        pouvoir tester obligeait à ouvrir le service au produit sans savoir s'il
        répond, c'est-à-dire à prendre le risque qu'on cherchait à écarter.

        L'activation se vérifie aux DEUX étages : le commun coupe tout d'un
        geste, l'usage se coupe seul. Le message nomme l'étage en cause.
        """
        if exiger_actif and not self.actif:
            raise ErreurLLM("L'assistant est désactivé dans l'administration.")
        if exiger_actif and self.usage is not None and not self.actif_usage:
            raise ErreurLLM(
                f"L'usage « {self.usage.libelle} » est désactivé dans l'administration."
            )
        if not self.cle:
            raise ErreurLLM("Aucune clé d'API n'est enregistrée.")
        if exiger_modele and not self.modele:
            libelle = f" pour « {self.usage.libelle} »" if self.usage else ""
            raise ErreurLLM(f"Aucun modèle n'est indiqué{libelle}.")
        if self.fournisseur.base_url_obligatoire and not self.base_url:
            raise ErreurLLM(f"{self.fournisseur.libelle} exige l'adresse de votre point d'accès.")

    @property
    def pret(self) -> bool:
        """L'usage peut-il être PROPOSÉ à l'écran ? — activé aux deux étages, une
        clé, un modèle. C'est ce que lisent les `*_disponible()` des appelants,
        pour ne pas réécrire la règle trois fois."""
        try:
            self.verifier()
        except ErreurLLM:
            return False
        return True


def _lire(session: Session) -> dict[str, str]:
    return {r.cle: r.valeur for r in session.exec(select(ConfigSite)).all()}


def _entier(cfg: dict[str, str], cle: str, defaut: int) -> int:
    #  Une valeur illisible retombe sur le défaut : ce réglage gouverne un
    #  confort et un coût, il ne doit jamais empêcher l'appel de partir.
    try:
        return int(cfg.get(cle) or defaut)
    except (TypeError, ValueError):
        return defaut


def config_llm(session: Session, usage: Optional[str] = None) -> ConfigLLM:
    """La configuration de l'assistant, telle que l'administration l'a posée.

    :param usage: le code d'un usage (`llm_usages.USAGES`) pour lire aussi son
        modèle, son prompt et son plafond. `None` pour le seul commun.
    """
    cfg = _lire(session)
    code = cfg.get(CLE_FOURNISSEUR) or FOURNISSEUR_DEFAUT
    fournisseur = FOURNISSEURS.get(code) or FOURNISSEURS[FOURNISSEUR_DEFAUT]

    commun = ConfigLLM(
        actif=service_actif(cfg, SERVICE_IA),
        fournisseur=fournisseur,
        cle=cfg.get(CLE_API) or "",
        base_url=cfg.get(CLE_BASE_URL) or fournisseur.base_url,
        version_api=cfg.get(CLE_VERSION_API) or "2024-06-01",
        delai_s=_entier(cfg, CLE_DELAI, DELAI_DEFAUT_S),
        envoi_document=cfg.get(CLE_ENVOI_DOCUMENT, "1") == "1",
    )
    if usage is None:
        return commun
    u = USAGES[usage]
    commun.usage = u
    commun.actif_usage = cfg.get(u.cle("actif")) == "1"
    #  🔴 Pas de repli sur `fournisseur.modele_defaut` : un usage sans modèle ne
    #  part pas. Le repli faisait appeler en silence un modèle que personne
    #  n'avait choisi pour cet usage.
    commun.modele = (cfg.get(u.cle("modele")) or "").strip()
    #  Le prompt, lui, se replie sur l'ORIGINE : une clé vidée par erreur ne doit
    #  pas envoyer un modèle sans consigne — et « Rétablir » vide justement la clé.
    commun.prompt = (cfg.get(u.cle("prompt")) or "").strip() or u.prompt_defaut
    commun.max_jetons = _entier(cfg, u.cle("max_jetons"), u.max_jetons_defaut)
    commun.effort = valeur_effort(cfg.get(u.cle("effort")))
    commun.ouvert_coproprietaires = (
        u.ouvrable_aux_coproprietaires and cfg.get(u.cle(CHAMP_COPROPRIETAIRES)) == "1"
    )
    commun.delai_s = max(commun.delai_s, u.delai_min_s)
    return commun


async def demander(
    session: Session,
    *,
    usage: str,
    message: str,
    consigne: Optional[str] = None,
    max_jetons: Optional[int] = None,
    fichiers: tuple[PieceJointe, ...] = (),
    exiger_actif: bool = True,
    demandeur: Optional[int],
    etalon: bool = True,
) -> Reponse:
    """Pose une question au modèle configuré pour cet USAGE et rend sa réponse.

    :param consigne: le texte système. `None` = le prompt de l'usage, tel que
        l'administration l'a réglé. Un appelant qui doit y AJOUTER quelque chose
        que l'administrateur ne peut pas retirer (un format de réponse) le
        compose à partir de `config_llm(session, usage).prompt` et le passe ici.
    :param demandeur: l'utilisateur qui fait le geste, ou `None` pour un usage
        automatique. OBLIGATOIRE, sans défaut : c'est lui que borne la limite
        par heure et par personne, et un appelant qui l'oublierait l'éteindrait
        sans un mot (`test_llm_limites.py` le vérifie sur le code).
    :param etalon: `False` pour le test de connexion — une question d'un mot
        n'est pas le premier essai d'un usage (`llm_limites`).

    Lève `ErreurLLM` — jamais autre chose : l'appelant est un écran, il doit
    pouvoir dire « ça n'a pas marché » sans distinguer un délai dépassé d'un
    502 du fournisseur.

    🔴 Chaque appel parti se JOURNALISE — jetons, durée, statut —, et un usage
    qui a atteint sa limite d'appels du mois, ou une personne sa limite de
    l'heure, est refusé AVANT l'envoi (`llm_limites`). C'est ici, point d'appel
    unique, que le compte ne peut pas être oublié : un appelant ne peut ni
    l'omettre, ni le faire deux fois.
    """
    cfg = config_llm(session, usage)
    cfg.verifier(exiger_actif=exiger_actif)
    trace = {"usage": usage, "fournisseur": cfg.fournisseur.code, "modele": cfg.modele}
    refus = llm_limites.refus_avant_envoi(session, usage, demandeur)
    if refus:
        statut, message = refus
        llm_journal.journaliser(session, **trace, statut=statut)
        raise RefusLimite(message)
    debut = time.monotonic()
    try:
        rep = await _appeler(
            cfg,
            cfg.prompt if consigne is None else consigne,
            message,
            max_jetons or cfg.max_jetons,
            fichiers,
        )
    except ErreurLLM:
        duree_ms = int((time.monotonic() - debut) * 1000)
        llm_journal.journaliser(
            session, **trace, statut=llm_journal.STATUT_ERREUR, duree_ms=duree_ms
        )
        raise
    llm_journal.journaliser(
        session,
        **trace,
        statut=llm_journal.STATUT_SUCCES,
        duree_ms=int((time.monotonic() - debut) * 1000),
        jetons_entree=rep.jetons_entree,
        jetons_sortie=rep.jetons_sortie,
        jetons_cache=rep.jetons_cache,
    )
    if etalon:
        llm_limites.noter_premier_essai(session, cfg, rep)
    return rep


async def _appeler(
    cfg: ConfigLLM,
    consigne: str,
    message: str,
    max_jetons: int,
    fichiers: tuple[PieceJointe, ...],
) -> Reponse:
    """L'échange avec le fournisseur, reprises comprises — sans journal ni plafond."""
    import httpx

    exiger_hors_demo("Assistant IA")  # aucun appel facturé depuis la démo publique (#1902)

    f = cfg.fournisseur
    debut = time.monotonic()
    try:
        #  C'est ici, et nulle part ailleurs, que le format de message du
        #  fournisseur rencontre les fichiers du métier.
        joints = tuple(f.bloc_document(j.nom, j.mime, j.donnees_b64) for j in fichiers)
        corps = f.avec_effort(
            f.corps(cfg.modele, consigne, message, max_jetons, joints), cfg.effort
        )
        #  Vrai tant qu'on n'a pas dû renoncer aux pièces jointes.
        avec_documents = bool(joints)
        async with httpx.AsyncClient(timeout=cfg.delai_s) as client:
            #  Le plafond de reprises est BORNÉ : chaque tour retire ou renomme
            #  un paramètre, il y en a peu, et une boucle sans fin sur un service
            #  facturé à l'appel serait pire que l'échec qu'elle évite.
            #  +2 : un tour pour l'appel initial, un pour le repli sans pièces
            #  jointes qui ne doit pas consommer le budget des adaptations.
            for _ in range(MAX_ADAPTATIONS + 2):
                reponse = await client.post(
                    f.url(cfg.modele, cfg.base_url, cfg.version_api),
                    headers=f.entetes(cfg.cle),
                    json=corps,
                )
                if reponse.status_code != 400:
                    break
                param, code = f.lire_erreur(_charge(reponse))
                suite = f.adapter(corps, param, code)
                if suite is not None:
                    logger.info(
                        "LLM %s : paramètre « %s » refusé (%s) — réessai", f.code, param, code
                    )
                    corps = suite
                    continue
                if avec_documents:
                    #  🔴 Dernier recours : le service n'a pas voulu des fichiers
                    #  joints. On repose la MÊME question sans eux plutôt que de
                    #  rendre un échec — une synthèse fondée sur la seule fiche
                    #  vaut mieux que pas de synthèse, et elle le DIT (l'appelant
                    #  lit `documents_refuses` pour l'écrire dans l'encart).
                    #
                    #  ⚠️ Ce repli est distinct de `adapter()` : celui-là corrige
                    #  un RÉGLAGE, celui-ci renonce à du CONTENU. Les confondre
                    #  ferait disparaître des documents sans que personne le sache.
                    logger.info("LLM %s : documents joints refusés — reprise sans eux", f.code)
                    avec_documents = False
                    #  ⚠️ On ne reconstruit QUE les messages : les adaptations de
                    #  paramètres déjà obtenues (un plafond renommé, une
                    #  température retirée) doivent survivre, sinon on les repaie
                    #  en tours de boucle et on épuise le budget avant d'aboutir.
                    sans = f.corps(cfg.modele, consigne, message, max_jetons, ())
                    corps = {**corps, "messages": sans["messages"]}
                    continue
                break
    except httpx.TimeoutException as exc:
        raise ErreurLLM(f"Pas de réponse après {cfg.delai_s} s.") from exc
    except httpx.HTTPError as exc:
        raise ErreurLLM("Le service n'a pas pu être joint.") from exc

    duree = time.monotonic() - debut
    if reponse.status_code == 401 or reponse.status_code == 403:
        raise ErreurLLM("Clé d'API refusée par le fournisseur.")
    if reponse.status_code == 404:
        raise ErreurLLM(f"Modèle « {cfg.modele} » introuvable chez {f.libelle}.")
    if reponse.status_code == 429:
        raise ErreurLLM("Quota atteint chez le fournisseur — réessayez plus tard.")
    if reponse.status_code >= 400:
        #  ⚠️ On journalise le corps, on ne le RECOPIE PAS à l'écran : il peut
        #  contenir la requête, donc le contrat qu'on vient d'envoyer.
        logger.warning("LLM %s → %s : %s", f.code, reponse.status_code, reponse.text[:400])
        #  Le paramètre refusé, lui, se DIT : c'est un champ structuré, il ne
        #  porte aucun contenu, et sans lui l'écran affiche « répondu 400 » —
        #  un message sur lequel personne ne peut agir (constaté le 11/09/2026).
        charge = _charge(reponse)
        explication = f.diagnostiquer(charge)
        if explication:
            raise ErreurLLM(explication)
        param, _code = f.lire_erreur(charge)
        precision = f" — réglage refusé : « {param} »" if param else ""
        raise ErreurLLM(f"Le fournisseur a répondu {reponse.status_code}{precision}.")

    charge = reponse.json()
    texte = f.lire(charge)
    if not texte:
        raise ErreurLLM("Le modèle a répondu sans contenu.")
    logger.info(
        "LLM %s/%s : %d caractères en %.1f s (%d document(s) joint(s))",
        f.code,
        cfg.modele,
        len(texte),
        duree,
        len(fichiers) if avec_documents else 0,
    )
    return Reponse(
        texte,
        len(fichiers) if avec_documents else 0,
        *llm_journal.jetons_de(charge),
    )


#  Le catalogue des modèles vit dans `llm_modeles.py` depuis le 27/09/2026 : ce
#  module franchissait 500 lignes en recevant le journal des appels (#1383). Il
#  reste exporté d'ici — la porte d'entrée ne change pas (voir `__all__`).
from app.utils.llm_modeles import modeles_disponibles  # noqa: E402

#  Le test de connexion vit dans `llm_connexion.py` depuis le 04/10/2026, pour
#  la même raison : les limites d'appels (`llm_limites`) faisaient passer ce
#  module au-dessus de 500 lignes. Même porte d'entrée.
from app.utils.llm_connexion import tester  # noqa: E402
