"""L'expéditeur d'un courriel reçu est-il bien celui qu'il dit ? — vérifié ICI.

## 🔴 Pourquoi on ne lit plus `Authentication-Results` (28/09/2026)

#703 avait posé : *« `Authentication-Results` posé par le MTA fait foi — on ne
réimplémente ni SPF ni DKIM »*. Le raisonnement tenait **sur une hypothèse
fausse : que le serveur de réception écrive cet en-tête**. OVH ne l'écrit pas.

Ce que ça a coûté, constaté le 28/09/2026 dans les notifications du conseil :

- **aucune réponse par courriel n'est jamais entrée dans un fil** depuis la mise
  en service (05/09) — chaque message authentique était refusé pour « aucune
  trace de vérification d'authenticité » ;
- et, pire, **le contrôle croyait l'expéditeur** : un en-tête que personne ne
  pose à la réception, c'est l'expéditeur qui l'écrit. Un message forgé portant
  `Authentication-Results: x; spf=pass dkim=pass dmarc=pass` aurait été accepté.

## Ce qui fait foi désormais : une signature DKIM ALIGNÉE

On vérifie nous-mêmes la signature DKIM du message (`dkimpy`), et on exige que
le domaine signataire (`d=`) soit celui de l'adresse `From:` ou un domaine
parent — l'**alignement** qui fait passer DMARC. Sans lui, n'importe qui
signerait pour son propre domaine un message « de » quelqu'un d'autre.

Pourquoi DKIM et pas SPF : la boîte relevée reçoit par une **redirection**
(`affaire@` → `noreply@`). Le message y repart des serveurs d'OVH, et SPF — qui
juge l'adresse IP de l'émetteur — échoue alors par construction. La signature
DKIM, elle, voyage dans le message et survit à la redirection.

⚠️ **Ce que ça laisse dehors, et c'est voulu** : un domaine qui ne signe pas en
son nom. Son message est refusé, et le conseil est prévenu avec le motif — le
refus n'est jamais silencieux (`courriel_boite._prevenir_le_cs`).

Sauf **délégation déclarée** (#2554) : l'administrateur admet un signataire pour
UN domaine, à l'identique (`courriel_delegation`) — le cabinet sous Microsoft 365
qui signe du nom de son abonnement. Jamais un suffixe, jamais un signataire partagé.

## 🔴 La redirection ABÎME la signature — le constat scellé d'OVH (28/09/2026)

Premier passage réel, le soir même : les réponses signées par iCloud et Orange
étaient refusées pour « signature invalide ». OVH le dit lui-même dans l'en-tête
qu'il pose à la livraison : `dkim=fail (body has been altered)`. La redirection
`affaire@` → `noreply@` double le point des lignes qui en commencent une
(`..fr`), et le corps reçu n'est plus celui qui a été signé. Microsoft, qui
encode autrement, y survivait — c'est ce qui a fait croire au début que la
vérification marchait.

La redirection, elle, **scelle** ce qu'elle a constaté à l'arrivée : un jeu ARC
(RFC 8617) signé par `mail.ovh.net`, dont l'`ARC-Authentication-Results` dit
`dkim=pass header.d=orange.fr`. On en fait un **repli**, jamais la voie
principale, et à trois conditions — sans quoi le sceau ne prouverait rien :

- la chaîne ARC se vérifie **chez nous**, sur les octets reçus (`dkimpy`) ;
- l'instance la plus récente est scellée par un domaine de
  `SCELLEURS_DE_CONFIANCE` — le serveur de réception de la boîte, et lui seul :
  n'importe qui peut sceller pour son propre domaine un constat « pass » ;
- le domaine qu'elle déclare signataire est **aligné** sur le `From:`, comme
  pour une signature lue directement.

## INCONNU n'est pas REFUSÉ

Un DNS injoignable ne dit rien de l'expéditeur. `VerificationReportee` laisse
le message **non lu** : la relève suivante le reprend. Le refuser ferait
notifier le conseil d'une usurpation qui n'en est pas une, et perdrait la
réponse pour de bon (`standards/04` — un contrôle qui ne peut pas s'exécuter
rend INCONNU, jamais un verdict).
"""

from __future__ import annotations

import logging
import re
from email.utils import parseaddr

import dkim
import dns.exception
import dns.resolver

logger = logging.getLogger(__name__)


class _JournalDkim(logging.LoggerAdapter):
    """Le journal passé à `dkimpy`, qui écrit en ERROR une clé absente ou mal
    formée chez l'EXPÉDITEUR. Ce n'est pas une panne de l'API : le point 6 du
    pré-check compte les ERROR, et un courriel mal signé bloquerait une MEP. Le
    verdict, lui, n'est pas tu — il part au conseil avec son motif.
    """

    def error(self, msg, *args, **kwargs):
        self.debug(msg, *args, **kwargs)

    warning = error


_journal_dkim = _JournalDkim(logger, {})

#: Les algorithmes admis. `rsa-sha1` est déprécié (RFC 8301) : une signature
#: qui n'offre que lui ne prouve plus grand-chose.
_ALGORITHMES = (b"rsa-sha256", b"ed25519-sha256")

#: Délai d'une requête DNS, en secondes.
_DELAI_DNS = 5

#: Les scelleurs ARC dont on croit le constat : le serveur qui reçoit
#: `affaire@` et le redirige vers la boîte relevée. Un scelleur de plus est un
#: tiers de plus à qui l'on confie l'authenticité des réponses — il s'ajoute ici,
#: avec sa raison, et nulle part ailleurs.
SCELLEURS_DE_CONFIANCE = frozenset({"mail.ovh.net"})

#: `dkim=pass … header.d=<domaine>` dans un segment d'`Authentication-Results`.
_DKIM_PASS = re.compile(r"^\s*dkim\s*=\s*pass\b.*?\bheader\.d\s*=\s*([a-z0-9.-]+)", re.I)
_INSTANCE = re.compile(rb"(?:^|;)\s*i\s*=\s*(\d+)\s*(?:;|$)")
_ENTETES_SIGNES = re.compile(rb"(?:^|;)\s*h\s*=\s*([^;]*)")


class VerificationReportee(Exception):
    """La vérification n'a pas pu avoir lieu (DNS) — ni vrai ni faux : à reprendre."""


def _txt(nom: bytes, timeout: int = _DELAI_DNS) -> bytes | None:
    """La clé publique publiée dans le DNS, ou None si elle n'existe pas.

    Remplace le résolveur de `dkimpy`, qui confond « pas de clé » et « serveur
    DNS en panne » (`NoNameservers` → None) : la seconde doit REPORTER, pas
    refuser.
    """
    try:
        reponse = dns.resolver.resolve(
            nom.decode("ascii", "replace"), "TXT", raise_on_no_answer=False, lifetime=timeout
        )
    except (dns.resolver.NXDOMAIN, dns.resolver.NoAnswer):
        return None
    except (dns.exception.Timeout, dns.resolver.NoNameservers) as exc:
        raise VerificationReportee(f"DNS injoignable ({type(exc).__name__})") from exc
    for enregistrement in reponse.response.answer:
        if enregistrement.rdtype == dns.rdatatype.TXT:
            return b"".join(list(enregistrement.items)[0].strings)
    return None


def domaine_de(adresse: str) -> str:
    """Le domaine d'une adresse d'en-tête (« Nom <a@b.fr> » → « b.fr »), minuscule."""
    return (parseaddr(adresse or "")[1] or "").rpartition("@")[2].strip().lower().rstrip(".")


def aligne(domaine_signataire: str, domaine_expediteur: str) -> bool:
    """Le signataire répond-il du domaine de l'expéditeur ?

    Le même domaine, ou un domaine PARENT (`d=exemple.fr` pour
    `From: …@mail.exemple.fr`) : qui publie les clés de `exemple.fr` en contrôle
    les sous-domaines. L'inverse n'est pas admis — un sous-domaine délégué ne
    répond pas de son parent —, et la comparaison se fait sur les LIBELLÉS : `d=
    exemple.fr` ne couvre pas `faux-exemple.fr`.
    """
    s, e = domaine_signataire.lower().rstrip("."), domaine_expediteur.lower().rstrip(".")
    if not s or not e or "." not in s:
        return False
    return e == s or e.endswith("." + s)


def _ams_signe_from(arc: dkim.ARC, instance: int) -> bool:
    """L'`ARC-Message-Signature` de cette instance couvre-t-elle `From:` ?

    Sans elle, le `From:` pourrait changer après le sceau : le constat dirait
    vrai d'un autre expéditeur. `dkimpy` l'exige d'une signature DKIM, pas d'un
    jeu ARC.
    """
    for nom, valeur in arc.headers:
        if nom.lower() != b"arc-message-signature":
            continue
        valeur = re.sub(rb"\s+", b"", valeur)
        i = _INSTANCE.search(valeur)
        if not i or int(i.group(1)) != instance:
            continue
        h = _ENTETES_SIGNES.search(valeur)
        return bool(h) and b"from" in h.group(1).lower().split(b":")
    return False


def constat_de_redirection(brut: bytes, *, dnsfunc=_txt) -> tuple[str, list[str]] | None:
    """Ce que le serveur de réception a constaté AVANT de rediriger le message :
    `(scelleur, domaines dont la signature DKIM était valide)`, ou None si aucun
    constat digne de foi n'accompagne le message.

    Lève `VerificationReportee` si le DNS ne répond pas.
    """
    arc = dkim.ARC(brut, logger=_journal_dkim)
    try:
        cv, resultats, _raison = arc.verify(dnsfunc=dnsfunc)
    except dkim.DKIMException:
        return None
    if cv != dkim.CV_Pass or not resultats:
        return None
    #  L'instance la plus récente, et elle seule : c'est celle du dernier saut,
    #  celui qui a livré dans la boîte. Une instance plus ancienne a pu être
    #  scellée par n'importe qui avant d'arriver chez nous.
    dernier = resultats[0]
    scelleur = dernier.get("as-domain", b"").decode("ascii", "replace").lower()
    if scelleur not in SCELLEURS_DE_CONFIANCE:
        return None
    if dernier.get("ams-domain", b"").decode("ascii", "replace").lower() != scelleur:
        return None
    if not _ams_signe_from(arc, dernier["instance"]):
        return None
    constat = dernier.get("aar-value", b"").decode("utf-8", "replace")
    domaines = []
    for segment in constat.split(";"):
        trouve = _DKIM_PASS.match(segment)
        if trouve:
            domaines.append(trouve.group(1).lower().rstrip("."))
    return scelleur, domaines


def repond_de(signataire: str, expediteur: str, delegues: frozenset = frozenset()) -> bool:
    """Le signataire répond-il de l'expéditeur — aligné, ou DÉLÉGUÉ pour lui à l'identique ?"""
    s, e = signataire.lower().rstrip("."), expediteur.lower().rstrip(".")
    return aligne(s, e) or (e, s) in delegues


def verifier_expediteur(
    brut: bytes, from_: str, *, dnsfunc=_txt, delegues: frozenset = frozenset()
) -> tuple[bool, str]:
    """Rend `(vrai, motif)` : le message porte-t-il une signature DKIM valide et
    alignée sur son `From:` — ou d'un signataire délégué pour lui (`delegues`,
    paires `(domaine, signataire)` de `courriel_delegation`) ?

    Le motif est écrit pour un membre du conseil syndical, qui le lira dans une
    notification — il dit ce qui manque, jamais « échec de la validation ».

    Lève `VerificationReportee` si le DNS ne répond pas : ce n'est pas un verdict.
    """
    expediteur = domaine_de(from_)
    if not expediteur:
        return False, "l'expéditeur du message est illisible"

    ok, motif = _signature_directe(brut, expediteur, dnsfunc, delegues)
    if ok:
        return ok, motif
    #  Le repli : la signature a pu être valide à l'arrivée et cassée par la
    #  redirection. Seul le constat scellé par le serveur de réception le dit.
    constat = constat_de_redirection(brut, dnsfunc=dnsfunc)
    if constat:
        scelleur, domaines = constat
        for signataire in domaines:
            if repond_de(signataire, expediteur, delegues):
                return True, f"signé par {signataire}, constaté par {scelleur} avant la redirection"
    return False, motif


#: Pourquoi aucune signature n'a suffi — un motif par cas (#1448). Ils étaient
#: tous « la signature DKIM du message est invalide », et trois d'entre eux
#: désignent des signatures VALIDES écartées par choix : le 28/09/2026, ce motif
#: unique a fait soupçonner notre vérification quand c'était la redirection qui
#: abîmait le corps. Chacun est écrit pour un membre du conseil syndical.
MOTIFS_ECART = {
    "sans_from": (
        "la signature ne couvre pas l'adresse de l'expéditeur, qui a pu être changée après coup"
    ),
    "partielle": (
        "la signature ne couvre qu'une partie du message : la suite a pu être ajoutée après coup"
    ),
    "algorithme": (
        "la signature utilise un algorithme trop ancien (rsa-sha1) pour prouver l'expéditeur"
    ),
    "cle_introuvable": (
        "la clé publique du signataire est introuvable : la signature ne peut pas être vérifiée"
    ),
    "modifiee": (
        "la signature ne correspond plus au message : il a sans doute été modifié "
        "après avoir été signé"
    ),
}

#: Quand plusieurs signatures échouent pour des raisons différentes, on dit la
#: plus instructive : une signature valide écartée en dit plus qu'une cassée.
_ORDRE_ECARTS = tuple(MOTIFS_ECART)


def _ecart(champs: dict, entetes_signes, cle_absente: bool, valide: bool) -> str | None:
    """Pourquoi cette signature ne prouve rien, ou None si elle prouve."""
    if not valide:
        return "cle_introuvable" if cle_absente else "modifiee"
    #  RFC 6376 impose de signer `From` ; on ne s'en remet pas au signataire.
    if b"from" not in entetes_signes:
        return "sans_from"
    #  `l=` borne la longueur du corps signé : ce qui suit peut être AJOUTÉ
    #  sans casser la signature. Une réponse dont la fin est libre ne prouve
    #  rien de ce qu'elle dit.
    if b"l" in champs:
        return "partielle"
    if champs.get(b"a") not in _ALGORITHMES:
        return "algorithme"
    return None


def _signature_directe(brut: bytes, expediteur: str, dnsfunc, delegues) -> tuple[bool, str]:
    """La signature DKIM lue sur les octets reçus, sans intermédiaire."""
    message = dkim.DKIM(brut, logger=_journal_dkim)
    nombre = sum(1 for nom, _ in message.headers if nom.lower() == b"dkim-signature")
    if not nombre:
        return False, (
            "le message ne porte aucune signature DKIM : il n'a pas pu être attribué "
            "avec certitude à son expéditeur apparent"
        )

    #  `dkimpy` rend False pour une clé absente comme pour un corps modifié : on
    #  note ce que le DNS a répondu pour les distinguer.
    cles_absentes: list[bytes] = []

    def dns_note(nom, *args, **kwargs):
        cle = dnsfunc(nom, *args, **kwargs)
        if cle is None:
            cles_absentes.append(nom)
        return cle

    signataires: list[str] = []
    ecarts: set[str] = set()
    for idx in range(nombre):
        cles_absentes.clear()
        try:
            valide = message.verify(idx=idx, dnsfunc=dns_note)
        except VerificationReportee:
            raise
        except Exception:  # noqa: BLE001 — une signature mal formée ne vaut rien
            ecarts.add("modifiee")
            continue
        champs = getattr(message, "signature_fields", {}) or {}
        ecart = _ecart(
            champs, getattr(message, "include_headers", ()), bool(cles_absentes), bool(valide)
        )
        if ecart:
            ecarts.add(ecart)
            continue
        signataire = (champs.get(b"d") or b"").decode("ascii", "replace").lower()
        signataires.append(signataire)
        if aligne(signataire, expediteur):
            return True, f"signé par {signataire}"
        if repond_de(signataire, expediteur, delegues):
            return True, f"signé par {signataire}, signataire admis pour {expediteur}"

    if signataires:
        return False, (
            f"le message est signé par {', '.join(sorted(set(signataires)))}, "
            f"et non par le domaine de l'expéditeur ({expediteur}) — un administrateur "
            "peut admettre ce signataire pour ce domaine (Admin › Services › Courriel, "
            "signataires délégués)"
        )
    return False, MOTIFS_ECART[min(ecarts, key=_ORDRE_ECARTS.index)]
