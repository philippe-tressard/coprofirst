"""Les jetons de rafraîchissement : les échanger, les révoquer, les purger.

## Un jeton rejoué après avoir été échangé : un vol (27/09/2026)

`/auth/refresh` échange le jeton présenté contre un neuf et révoque l'ancien.
Jusqu'ici, un jeton déjà échangé qui revenait était simplement refusé (401).
C'est pourtant le seul signal qu'on ait d'un vol : le porteur légitime et un
voleur détiennent **le même** jeton, et le premier des deux qui l'échange rend
l'autre obsolète. Quand l'obsolète revient, l'un des deux est un voleur, et on
ne sait pas lequel.

On ferme donc **toutes** les sessions du compte, celle du voleur comprise. Le
porteur légitime se reconnecte ; le voleur ne le peut pas, faute du mot de passe.
C'est la « détection de réutilisation » des recommandations OAuth (RFC 9700 §4.14).

## Pourquoi seul un jeton ÉCHANGÉ déclenche la fermeture

Un jeton révoqué par une **déconnexion** ou par un **mot de passe posé**
(`poser_mot_de_passe`) revient légitimement : l'autre appareil de quelqu'un qui
vient de changer son mot de passe présente son ancien jeton à la minute
suivante. Le traiter en vol fermerait la session que la personne vient
d'ouvrir. C'est `remplace_le`, posé par `remplacer` et par lui seul, qui les
distingue.

## Le délai de grâce

Quand une page charge, plusieurs appels reçoivent 401 **en même temps** et
rafraîchissent chacun la session : c'est mesuré, pas supposé
(`test_refresh_token_unique`, 19/08/2026). Le premier échange le jeton, les
suivants arrivent avec l'ancien quelques millisecondes plus tard. Ce n'est pas
un vol, et ils reçoivent un 401 simple, comme avant ce lot.
`DELAI_GRACE_ROTATION` fixe la limite.

## Les jetons d'accès tombent aussi (#2481, 03/11/2026)

Le voleur tient la PAIRE : fermer les sessions refusait ses rafraîchissements,
pas ses requêtes, et son jeton d'accès valait encore jusqu'à 120 minutes.
`fermer_apres_rejeu` incrémente donc `Utilisateur.generation_sessions`, qui entre
dans l'empreinte du jeton d'accès (`jwt.empreinte_du_compte`) : la mécanique de
#1063, sans liste de révocation. La valeur vit en base, donc vaut pour tous les
processus et les deux nœuds.

⚠️ **Ce que cela ne couvre pas.** Si la réponse d'un échange se perd, le
navigateur garde l'ancien jeton : passé le délai de grâce, il est lu comme un vol
et toutes les sessions ferment. C'est un faux positif rare, et son coût est une
reconnexion.

## La purge garde les jetons échangés jusqu'à leur expiration

Sans eux, rien ne reconnaît le jeton rejoué : il devient « inconnu », donc un
401 simple. Les deux purges (démarrage de l'API et maintenance hebdomadaire)
passent donc par `purger`, qui ne supprime un jeton échangé qu'une fois expiré.
Le coût est d'environ un jeton toutes les deux heures par session active,
supprimé au plus sept jours après.
"""

from datetime import datetime, timedelta
from typing import Optional

from sqlmodel import Session, and_, delete, or_, select, update

from app.auth.empreinte_jeton import empreinte
from app.utils.push.appareils import retirer_appareils
from app.models.core import Utilisateur
from app.models.jetons import RefreshToken

#: Au-delà, un jeton échangé qui revient est un jeton rejoué, pas un appel
#: concurrent. Les appels concurrents d'une page qui charge arrivent en quelques
#: millisecondes ; deux minutes couvrent aussi un Raspberry Pi très lent.
DELAI_GRACE_ROTATION = timedelta(minutes=2)


def remplacer(session: Session, jeton: RefreshToken, maintenant: datetime) -> None:
    """Révoque `jeton` parce qu'il vient d'être échangé contre un neuf."""
    jeton.revoked = True
    jeton.remplace_le = maintenant
    session.add(jeton)


def est_rejoue(jeton: RefreshToken, maintenant: datetime) -> bool:
    """Ce jeton a été échangé, et il revient après le délai de grâce."""
    return (
        jeton.revoked
        and jeton.remplace_le is not None
        and maintenant - jeton.remplace_le > DELAI_GRACE_ROTATION
    )


def revoquer_sessions(session: Session, user_id: int, sauf: Optional[str] = None) -> int:
    """Révoque les jetons encore actifs du compte, sauf `sauf`. Rend le nombre révoqué.

    `sauf` est le jeton BRUT de la session appelante (son cookie) : la base ne
    garde que les empreintes (#1389), on compare donc la sienne.

    Retire aussi TOUS les appareils du compte (#2493, spec push §6.3) : une session
    fermée ne laisse pas un téléphone sonner, et rien ne relie un appareil à une
    session — celui de la session gardée se ré-enregistre à l'ouverture de l'application.

    Ne valide pas la transaction : c'est l'appelant qui décide quand elle se termine.
    """
    retirer_appareils(session, user_id)
    actifs = session.exec(
        select(RefreshToken).where(
            RefreshToken.user_id == user_id,
            RefreshToken.revoked == False,  # noqa: E712
        )
    ).all()
    revoques = 0
    garde = empreinte(sauf) if sauf is not None else None
    for jeton in actifs:
        if garde is not None and jeton.token == garde:
            continue
        jeton.revoked = True
        session.add(jeton)
        revoques += 1
    return revoques


def fermer_apres_rejeu(session: Session, user_id: int) -> int:
    """Un jeton échangé est revenu : ferme TOUTES les sessions du compte, jetons
    d'accès compris. Rend le nombre de jetons de rafraîchissement révoqués.

    L'incrément s'écrit en SQL (`generation_sessions + 1`) : deux rejeux
    simultanés en font deux, jamais un seul perdu. Ne valide pas la transaction.
    """
    session.exec(
        update(Utilisateur)
        .where(Utilisateur.id == user_id)
        .values(generation_sessions=Utilisateur.generation_sessions + 1)
    )
    return revoquer_sessions(session, user_id)


def purger(session: Session, maintenant: datetime) -> int:
    """Supprime les jetons expirés, et ceux révoqués autrement que par un échange.

    Ne valide pas la transaction, pour la même raison que `revoquer_sessions`.
    """
    resultat = session.exec(
        delete(RefreshToken).where(
            or_(
                RefreshToken.expires_at < maintenant,
                and_(
                    RefreshToken.revoked == True,  # noqa: E712
                    RefreshToken.remplace_le.is_(None),
                ),
            )
        )
    )
    return resultat.rowcount or 0
