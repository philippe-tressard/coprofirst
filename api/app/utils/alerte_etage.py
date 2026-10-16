"""Prévenir l'administrateur du site quand un résident et son lot se contredisent.

Demandé par Philippe le 09/09/2026 : *« notifier s'il y a une différence entre le
lot et la saisie du résident ; préférer celle du Lot et envoyer un mail à
l'administrateur du site qu'il vérifie et corrige l'info si nécessaire »*.

## Pourquoi un module, et pas dix lignes dans `auth.py`

`routers/auth.py` passe déjà le plafond de modularité, et cette alerte n'est pas
une règle d'authentification : elle lit le patrimoine, compose un courriel et
connaît le gestionnaire du site. La décision — *y a-t-il divergence ?* — reste
dans `utils/etages.py`, pure et testable sans base ni SMTP.

## Ce qui n'est PAS ici, volontairement

La déduplication. Elle vit dans l'appelant, sous la forme d'une condition sur le
**changement** (`body.etage != user.etage`) : c'est la seule qui n'exige aucun
stockage, et elle dit exactement ce qu'on veut dire — une alerte par valeur neuve.
"""

from __future__ import annotations

from fastapi import BackgroundTasks
from sqlmodel import Session

from app.models.core import Utilisateur
from app.utils.etages import divergence_etage, etage_label
from app.utils.liens import base_site, nom_site
from app.utils.lots_rattaches import lots_de
from app.utils.noms import contexte_personne


def alerter_divergence_etage(
    session: Session,
    background_tasks: BackgroundTasks,
    user: Utilisateur,
    etage_saisi: int | None,
) -> None:
    """Envoie l'alerte si la saisie contredit le lot — silencieux sinon.

    Silencieux aussi quand le site n'a pas d'adresse de gestionnaire : un envoi
    sans destinataire n'est pas une alerte, c'est une ligne d'erreur dans un
    journal que personne ne lit (`standards/04` §7).
    """
    ecart = divergence_etage(etage_saisi, lots_de(session, user))
    if ecart is None:
        return

    from app.utils.email import get_site_manager_notification_email, send_email

    destinataire, cfg = get_site_manager_notification_email(session)
    if not destinataire:
        return

    saisi, lot = ecart
    background_tasks.add_task(
        send_email,
        code="etage_divergent",
        to=destinataire,
        context={
            "utilisateur": contexte_personne(user, email=user.email),
            "etage": {
                #  Les libellés sont calculés ICI : un modèle Jinja n'a pas à
                #  porter « RDC » ni « SS 1 », et le faire en gabarit rouvrirait
                #  la septième écriture de `etage_label`.
                "saisi": etage_label(saisi),
                "lot": etage_label(lot),
            },
            "residence": {"nom": nom_site(cfg.get("site_nom"))},
            "app": {"url": base_site(cfg.get("site_url"))},
        },
    )
