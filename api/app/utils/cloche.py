"""La CLOCHE — une seule porte, qui obéit au profil (#1187, 23/09/2026).

## La règle posée par l'utilisateur

> « Aucun mail (ou autre notification) n'est envoyé autre que ceux précisés
>   dans la section Diffusion ou dans sa configuration profil. »

Les courriels passaient déjà par une porte (`utils/email.send_email`) qui lit
le profil (`utils/preferences_mail.mail_autorise`). La cloche, non : vingt-deux
`Notification(...)` étaient écrits à la main, dans treize fichiers, et partaient
sans condition. Le profil porte désormais les mêmes réglages pour la cloche —
**mon bâtiment / autres bâtiments** —, cochés par défaut : rien ne disparaît
sans un geste du résident.

## Deux portes, et seulement deux

| Porte | Quand | Le profil décide ? |
|---|---|---|
| `sonner` | un contenu : une affaire, un document, un sondage, une réponse… | **oui** |
| `sonner_systeme` | ce qui concerne le COMPTE ou une tâche du conseil | non — avec son **motif**, pris dans `MOTIFS_SYSTEME` |

🔒 `tests/test_cloche_porte_unique.py` refuse un `Notification(` construit
ailleurs qu'ici, et un motif système qui ne serait pas déclaré.
"""

from __future__ import annotations

from typing import Iterable, Optional

from sqlmodel import Session

from app.models.core import Notification, Utilisateur
from app.utils.preferences_mail import cloche_autorisee

#: Les envois qui ne se règlent PAS dans le profil — chacun avec sa raison.
#: Un motif ajouté ici est une décision : le contrôle refuse un motif inconnu.
MOTIFS_SYSTEME: dict[str, str] = {
    "compte": "la vie du compte — validation, rôle, profil, bannissement : "
    "c'est à la personne elle-même, et elle doit le savoir",
    "sa_demande": "la réponse à une demande que la personne a faite elle-même "
    "(commande d'accès, accès enregistré à son nom)",
    "moderation": "un signalement à modérer : l'obligation du conseil, pas un contenu",
    "tache_du_conseil": "un geste attendu du conseil (interphone d'un arrivant, "
    "courriel entrant à reporter) : une tâche, pas une information",
    "bug": "un bogue signalé : il revient au gestionnaire du site, et à lui seul (#1191)",
    "rattachement": "un locataire rattaché à son bailleur par le seul nom : le gestionnaire vérifie (#1136)",
    "relecture_transcription": "la transcription d'un PV d'AG par l'assistant, que "
    "l'administration relit avant qu'elle serve aux questions au règlement",
}


def _poser(session: Session, destinataire_id: int, champs: dict) -> None:
    session.add(Notification(destinataire_id=destinataire_id, **champs))


def sonner(
    session: Session,
    *,
    destinataire_id: Optional[int],
    batiments: Optional[Iterable[int]] = None,
    **champs,
) -> bool:
    """Un contenu : la cloche sonne si le profil du destinataire l'accepte.

    `batiments` : ceux que le contenu concerne, quand on les connaît — `None`
    vaut « chez moi » (`preferences_mail`). Rend `True` si la cloche a sonné.
    """
    #  Personne à prévenir : l'auteur d'une affaire dont le compte a été
    #  supprimé (#1688). Les cinq gestes qui « préviennent l'auteur » passent ici.
    if destinataire_id is None:
        return False
    destinataire = session.get(Utilisateur, destinataire_id)
    if destinataire is None or not cloche_autorisee(destinataire, batiments):
        return False
    _poser(session, destinataire_id, champs)
    return True


def sonner_systeme(session: Session, motif: str, *, destinataire_id: int, **champs) -> None:
    """Ce qui concerne le compte ou une tâche du conseil — hors profil, motif déclaré."""
    if motif not in MOTIFS_SYSTEME:
        raise ValueError(f"motif système non déclaré : {motif!r} (utils/cloche.MOTIFS_SYSTEME)")
    _poser(session, destinataire_id, champs)


__all__ = ["MOTIFS_SYSTEME", "sonner", "sonner_systeme"]
