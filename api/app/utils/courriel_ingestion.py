"""Ce qu'on fait d'un message arrivé dans la boîte des réponses (#703).

## La décision est ICI, et elle est PURE

Ce module ne se connecte à rien. Il reçoit les en-têtes et le corps d'un message
déjà lu, et rend un **verdict**. La relève IMAP vit dans `courriel_boite.py`, et
l'écriture dans le ticket dans le routeur.

C'est la leçon la plus chère de ce dépôt : *« je testais la décision, pas le
tuyau qui la nourrit »*. Ici on peut faire l'inverse — éprouver chaque verdict
sur un message écrit à la main, y compris les messages hostiles, sans boîte et
sans réseau.

## 🔴 SMTP N'AUTHENTIFIE PAS L'EXPÉDITEUR

C'est le seul point qui compte vraiment. N'importe qui peut écrire à cette boîte
en mettant l'adresse du syndic dans le `From:`. Sans vérification, son message
deviendrait un **commentaire officiel sur un ticket, visible des résidents, signé
du syndic**.

Notre DMARC en `p=reject` protège *notre* domaine contre l'usurpation — **pas
celui du syndic**. La preuve est une signature DKIM alignée sur le `From:`,
vérifiée par nous-mêmes à la relève (`courriel_authenticite`) et passée à
`examiner` en paramètre. Un message qu'on n'a pas pu vérifier n'est pas
« probablement bon » : il est **invérifiable**, et invérifiable n'est jamais OK
(`standards/04`).

🔴 Jusqu'au 28/09/2026, la preuve était lue dans l'en-tête `Authentication-Results`
du message. OVH ne le pose pas : aucune réponse authentique n'est jamais passée,
et un expéditeur qui l'écrivait lui-même était cru. Le verdict d'authenticité
n'est donc plus un en-tête — rien de ce que l'expéditeur écrit ne peut le fournir.

## Que fait-on d'un message qui ne passe pas ?

Trois options existaient. La retenue est la deuxième :

| Option | Conséquence |
|---|---|
| rejeter en silence | sûr, mais une réponse légitime disparaît sans que personne ne le sache — « un contrôle sans destinataire » |
| **rejeter ET prévenir le conseil syndical** | sûr *et* visible : rien n'est écrit dans le ticket, mais quelqu'un sait qu'un message attend |
| accepter en marquant « non vérifié » | ❌ écartée : un badge ne protège personne, on le lit une fois et plus jamais |

**Le silence est ce qui rend un filtre dangereux.** Un filtre qu'on n'entend
jamais finit par être cru parfait, et il l'est d'autant moins que personne ne le
regarde.

## La date plancher

*« À automatiser à partir des mails reçus au 2 septembre 2026 »* (arbitrage du
02/09/2026). Sans elle, la première relève rejouerait des mois d'archives et
déverserait dans les tickets des réponses déjà traitées à la main. Elle est
**configurable**, mais elle a une valeur : `PLANCHER_PAR_DEFAUT`.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime

from app.utils.courriel_entrant import jeton_dans, numero_dans_sujet

#: Les messages antérieurs sont ignorés — arbitrage du 02/09/2026.
PLANCHER_PAR_DEFAUT = datetime(2026, 9, 2)

#: Verdicts possibles. Ils sont trois et pas deux : « je ne sais pas rattacher »
#: n'est pas « je refuse », et les confondre ferait notifier le conseil syndical
#: pour chaque prospectus arrivé dans la boîte.
ACCEPTE = "accepte"  # à écrire dans le ticket
REFUSE = "refuse"  # rattaché, mais non authentifié → prévenir le CS
IGNORE = "ignore"  # sans rapport avec un ticket → ne rien faire

#: 🔴 Un QUATRIÈME verdict, ajouté le 04/09/2026. Une réponse à une relance
#: GROUPÉE est reçue, conservée et notifiée — mais elle n'entre dans aucun fil.
#: Elle était comptée `REFUSE`, ce qui est faux : rien n'a été refusé, on a fait
#: exactement ce qu'il fallait. Le journal disait « refusées=1 » sur un
#: traitement réussi, et c'est le journal qu'on lit pour savoir si la relève va
#: bien.
#: Le motif d'un message qui ne désigne rien — seul cas d'IGNORE qu'un correspondant
#: connu fait passer « à classer » (`courriel_boite`, #2555).
SANS_RATTACHEMENT = "ne répond à aucun ticket"
#: Ni affaire ni relance, d'un correspondant connu et authentifié : en attente (#2555).
A_CLASSER = "a_classer"
RELANCE = "relance"  # rattachée à une relance groupée → conservée, non ventilée


@dataclass(frozen=True)
class Verdict:
    """Ce qu'on fait du message, et pourquoi — le motif est destiné à un humain."""

    decision: str
    jeton: str | None = None
    reference: str | None = None
    #:  Le numéro lu dans le SUJET — un repli, quand le sous-adressage n'achemine
    #:  pas le jeton (05/09/2026). Il DÉSIGNE un ticket, il ne prouve rien : c'est
    #:  `courriel_boite` qui exige alors que l'expéditeur ait affaire à ce ticket.
    numero: str | None = None
    expediteur: str = ""
    motif: str = ""


#: Les `Message-ID` cités par une réponse, dans l'ordre où on les préfère.
_REFERENCE = re.compile(r"<([^<>@\s]+@[^<>\s]+)>")


def reference_citee(in_reply_to: str | None, references: str | None) -> str | None:
    """Le `Message-ID` auquel cette réponse répond, s'il est cité.

    Seconde voie de rattachement, employée quand le jeton n'est pas dans
    l'adresse — un serveur qui refuserait le sous-adressage, un client qui aurait
    réécrit le destinataire. `In-Reply-To` d'abord : `References` porte toute la
    chaîne, et le dernier n'est pas toujours le bon.
    """
    for valeur in (in_reply_to, references):
        if not valeur:
            continue
        trouves = _REFERENCE.findall(valeur)
        if trouves:
            return trouves[-1].lower()
    return None


def examiner(
    entetes: dict[str, str],
    *,
    recu_le: datetime | None = None,
    plancher: datetime | None = None,
    authentification: tuple[bool, str] | None = None,
) -> Verdict:
    """Le verdict, à partir des seuls en-têtes. Aucun accès réseau ni base.

    L'ordre des tests n'est pas indifférent :

    1. **la date** — avant tout, sinon la première relève traiterait l'archive ;
    2. **le rattachement** — sans ticket, il n'y a personne à prévenir, et un
       message sans rapport ne doit produire aucun bruit ;
    3. **l'authentification** — en dernier, parce que c'est le seul cas où l'on
       veut *parler*. L'inverser ferait notifier le conseil syndical pour chaque
       message non authentifié de la boîte, ticket ou pas : le filtre deviendrait
       lui-même la nuisance, et on finirait par ne plus le lire.

    `authentification` est le verdict de `courriel_authenticite.verifier_expediteur`
    — `(vrai, motif)`. Absent, le message est **invérifié**, donc refusé.
    """
    lire = {k.lower(): v for k, v in entetes.items()}
    plancher = plancher or PLANCHER_PAR_DEFAUT
    from_ = lire.get("from", "")

    if recu_le is not None and recu_le < plancher:
        return Verdict(IGNORE, expediteur=from_, motif="antérieur à la date de mise en service")

    jeton = jeton_dans(
        lire.get("to"), lire.get("delivered-to"), lire.get("envelope-to"), lire.get("cc")
    )
    reference = reference_citee(lire.get("in-reply-to"), lire.get("references"))
    #  Le repli : le numéro écrit dans le sujet. Il n'est lu que si le jeton
    #  manque — un sujet réécrit ne doit jamais l'emporter sur une adresse qui,
    #  elle, prouve quelque chose.
    numero = numero_dans_sujet(lire.get("subject")) if not jeton else None
    if not jeton and not reference and not numero:
        return Verdict(IGNORE, expediteur=from_, motif=SANS_RATTACHEMENT)

    ok, motif = authentification or (
        False,
        "aucune vérification d'authenticité : ce message n'a pas pu être attribué "
        "avec certitude à son expéditeur apparent",
    )
    decision = ACCEPTE if ok else REFUSE
    return Verdict(
        decision, jeton=jeton, reference=reference, numero=numero, expediteur=from_, motif=motif
    )
