"""Les appels de CETTE installation à la référence — inscription et bail (R2 #1878, §4.11).

**L'installation tire, la référence ne pousse jamais** (règle 5) : rien n'entre ici
depuis la référence ; l'installation l'appelle, sous son nom dédié
(`REGISTRE_URL`), en signant chaque envoi de sa clé (`depot.cle_privee`).

- `inscrire` : l'opérateur a saisi ses coordonnées et accepté les conditions EN
  VIGUEUR (Administration › Maintenance) ; la demande part, l'identifiant revient,
  puis le premier bail est demandé.
- `renouveler` : le bail, chaque nuit (`run_renouvellement_bail`, tâche de la
  plateforme). Un bail reçu n'est RANGÉ que s'il se croit (`constat.bail_valide`).
- Sans renouvellement depuis 3 jours, l'opérateur est alerté (D19).
- `envoyer_rapport` : le rapport nocturne (R3, `inscription/rapport.py`), dans la
  même tâche, après le bail — que le bail ait été renouvelé ou non.

Ni la référence, ni une installation d'ESSAI n'appellent le registre (règles 7 et
9) ; le mode essai n'est cru que pour un hôte local ou une base en mémoire.
"""

from __future__ import annotations

import json
import logging
from urllib.parse import urlsplit

import httpx

from app.config import get_settings
from app import contexte
from app.contexte import nom_d_hote
from app.inscription import cles, constat, depot
from app.inscription.depot import Contact, EtatLocal
from app.registre import conditions, signature
from app.registre.contrat import (
    EN_TETE_SIGNATURE,
    VERSION_CONTRAT,
    AdministrateurInstallation,
    BailSigne,
    DemandeBail,
    DemandeInscription,
    ReponseInscription,
)
from app.utils import horloge, installation

logger = logging.getLogger("hostachy.inscription")

#: Un registre qui ne répond pas en dix secondes ne répondra pas mieux en trente.
DELAI = 10

#: Les hôtes où le mode essai est admis (règle 9).
HOTES_LOCAUX = frozenset({"localhost", "127.0.0.1", "::1"})


class RegistreInjoignable(Exception):
    """La référence n'a pas répondu, ou a refusé : le message dit pourquoi, en clair."""


def essai_declare() -> bool:
    return get_settings().installation_essai


def essai_admis() -> bool:
    """`INSTALLATION_ESSAI` n'est cru que pour un hôte local ou une base en mémoire."""
    s = get_settings()
    if not s.installation_essai:
        return False
    hote = nom_d_hote(urlsplit(s.origin).netloc or s.origin)
    local = hote in HOTES_LOCAUX or hote.endswith((".localhost", ".test"))
    return local or all(":memory:" in c.url_base for c in contexte.coproprietes())


def cle_publique() -> str | None:
    """La clé publique de l'installation — None tant qu'elle n'en a pas créé."""
    return signature.publique_de(depot.cle_privee()) if depot.cle_existe() else None


def constat_courant() -> constat.Constat:
    """Le verdict d'aujourd'hui, sur l'état rangé — sans aucun appel."""
    return constat.constater(
        depot.lire(),
        maintenant=horloge.maintenant(),
        cle_installation=cle_publique(),
        reference=installation.est_reference(),
        essai=essai_admis(),
        cles=cles.CLES_REFERENCE,
        revoquees=cles.REVOQUEES,
    )


def _appeler_permis() -> None:
    if installation.est_reference():
        raise RegistreInjoignable("la référence ne s'inscrit pas à son propre registre")
    if essai_admis():
        raise RegistreInjoignable("installation d'essai : la référence n'est pas appelée")


#: Le préfixe sous lequel le `Caddyfile` d'une installation CoproFirst confie une
#: requête à l'API (`handle /api/*` + `uri strip_prefix /api`). Le registre est une
#: route de l'API : sans lui, l'envoi partait au front et rendait 404 (#1878,
#: constaté le 13/10/2026). 🔒 `tests/aides_registre.py` le lit dans le `Caddyfile`.
PREFIXE_API = "/api"


def _poster(chemin: str, corps: dict) -> dict:
    """Envoie `corps`, signé ; rend la réponse JSON — ou lève avec le motif en clair."""
    octets = json.dumps(corps, ensure_ascii=False).encode()
    entetes = {
        "Content-Type": "application/json",
        EN_TETE_SIGNATURE: signature.signer(depot.cle_privee(), octets),
    }
    url = get_settings().registre_url.rstrip("/") + PREFIXE_API + chemin
    try:
        reponse = httpx.post(url, content=octets, headers=entetes, timeout=DELAI)
    except httpx.HTTPError as exc:
        raise RegistreInjoignable(f"registre injoignable ({type(exc).__name__})") from None
    if reponse.status_code not in (200, 201, 202):
        try:
            detail = str(reponse.json().get("detail", ""))[:200]
        except ValueError:
            detail = ""
        raise RegistreInjoignable(f"le registre a répondu {reponse.status_code} {detail}".strip())
    try:
        return reponse.json()
    except ValueError:
        raise RegistreInjoignable("réponse du registre illisible") from None


def inscrire(contact: Contact) -> EtatLocal:
    """Déclare l'installation à la référence, sur les conditions EN VIGUEUR, puis
    demande son premier bail. L'identifiant vient de la référence (D18)."""
    _appeler_permis()
    version = conditions.version_en_vigueur()
    demande = DemandeInscription(
        version_contrat=VERSION_CONTRAT,
        conditions_acceptees=version,
        empreinte_conditions=conditions.empreinte(version),
        cle_publique=signature.publique_de(depot.cle_privee()),
        version_logicielle=installation.version_logicielle(),
        administrateur=AdministrateurInstallation(**contact.model_dump()),
    )
    try:
        reponse = ReponseInscription.model_validate(
            _poster("/plateforme/inscriptions", demande.model_dump(mode="json"))
        )
    except ValueError as exc:  # ValidationError en est une
        raise RegistreInjoignable("réponse d'inscription illisible") from exc
    etat = depot.lire()
    etat.identifiant = reponse.identifiant
    etat.etat_inscription = reponse.etat
    etat.contact = contact
    etat.conditions_acceptees = version
    etat.inscrite_le = horloge.maintenant().isoformat(timespec="seconds")
    etat.illisible = False
    depot.ecrire(etat)
    logger.info("inscription : installation inscrite (%s)", reponse.identifiant)
    try:
        return renouveler()
    except RegistreInjoignable:
        return depot.lire()  # inscrite ; le bail viendra la nuit — l'erreur est rangée


def renouveler() -> EtatLocal:
    """Demande le bail. Il n'est RANGÉ que s'il se croit ; l'échec se range aussi."""
    _appeler_permis()
    etat = depot.lire()
    if not etat.identifiant:
        raise RegistreInjoignable("installation non inscrite")
    demande = DemandeBail(
        version_contrat=VERSION_CONTRAT,
        identifiant=etat.identifiant,
        cle_publique=signature.publique_de(depot.cle_privee()),
        version_logicielle=installation.version_logicielle(),
    )
    try:
        recu = BailSigne.model_validate(
            _poster("/plateforme/baux", demande.model_dump(mode="json"))
        )
        candidat = etat.model_copy(update={"bail": recu.model_dump(mode="json")})
        _, raison = constat.bail_valide(
            candidat, cle_publique(), cles.CLES_REFERENCE, cles.REVOQUEES
        )
        if raison:
            raise RegistreInjoignable(f"bail reçu refusé : {raison}")
    except (RegistreInjoignable, ValueError) as exc:
        etat.derniere_erreur = (
            str(exc) if isinstance(exc, RegistreInjoignable) else "bail illisible"
        )
        depot.ecrire(etat)
        raise RegistreInjoignable(etat.derniere_erreur) from None
    etat.bail = recu.model_dump(mode="json")
    etat.etat_inscription = recu.bail.etat
    etat.plus_haute_epoque = max(etat.plus_haute_epoque, recu.bail.epoque)
    etat.dernier_renouvellement_le = horloge.maintenant().isoformat(timespec="seconds")
    etat.derniere_erreur = None
    depot.ecrire(etat)
    return etat


def envoyer_rapport() -> EtatLocal:
    """Le rapport nocturne (R3), signé ; sa date se range quand la référence l'accepte."""
    from app.inscription import rapport

    _appeler_permis()
    if not depot.lire().identifiant:
        raise RegistreInjoignable("installation non inscrite")
    _poster("/plateforme/rapports", rapport.construire().model_dump(mode="json"))
    etat = depot.lire()
    etat.dernier_rapport_le = horloge.maintenant().isoformat(timespec="seconds")
    depot.ecrire(etat)
    return etat


def constat_pour_la_mise_a_jour() -> constat.Constat:
    """Ce que la mise à jour nocturne suit (R5 #1881) : le bail RENOUVELÉ si possible,
    puis le constat — un renouvellement manqué laisse le bail rangé, s'il vaut encore.

    La signature se vérifie ICI (`constat.bail_valide`), jamais dans le script :
    `deploiement/standard/mise-a-jour.sh` ne lit que la version que ce constat rend.
    """
    if not installation.est_reference() and not essai_admis() and depot.lire().identifiant:
        try:
            renouveler()
        except RegistreInjoignable as exc:
            logger.warning("inscription : bail non renouvelé avant la mise à jour (%s)", exc)
    return constat_courant()


def run_renouvellement_bail() -> None:
    """Tâche de la plateforme : le bail puis le rapport ; alerter l'opérateur après 3 jours."""
    if installation.est_reference() or essai_admis() or not depot.lire().identifiant:
        return
    try:
        renouveler()
        logger.info("inscription : bail renouvelé")
    except RegistreInjoignable as exc:
        logger.warning("inscription : bail non renouvelé (%s)", exc)
    try:
        envoyer_rapport()
        logger.info("inscription : rapport nocturne envoyé")
    except RegistreInjoignable as exc:
        logger.warning("inscription : rapport nocturne non envoyé (%s)", exc)
    verdict = constat_courant()
    if verdict.renouvellement_en_retard:
        from app.utils.sante_plateforme import alerter

        alerter(
            [
                "Le bail de l'installation n'a pas été renouvelé depuis plus de 3 jours "
                f"({verdict.raison}). Vérifier que le registre de la référence est joignable."
            ]
        )


def enregistrer(scheduler) -> None:
    """Pose la tâche — chaque nuit vers 04:20, étalée sur une demi-heure : les
    installations n'appellent pas la référence toutes à la même seconde."""
    scheduler.add_job(
        run_renouvellement_bail, "cron", hour=4, minute=20, jitter=1800, id="bail_installation"
    )
