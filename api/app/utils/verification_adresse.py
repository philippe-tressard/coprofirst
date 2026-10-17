"""L'adresse d'un compte se PROUVE — à l'inscription comme quand elle change (#1549).

## Pourquoi ce module (audit du 02/10/2026)

L'inscription exige qu'une adresse soit vérifiée avant d'ouvrir la porte. Changer
d'adresse, non : `PATCH /auth/me` la remplaçait sur-le-champ, sans mot de passe
ni re-vérification — et l'administrateur faisait de même pour un autre compte.
Une session volée suffisait à détourner un compte : nouvelle adresse, puis « mot
de passe oublié » sur celle-ci, et la victime ne recevait rien.

Trois écritures de « cette adresse est bien la sienne », une seule vérifiait. Il
n'en reste qu'une, ici, avec deux natures de lien sur la même table :

=====================================  =====================================
Lien de l'INSCRIPTION                  Lien d'un CHANGEMENT d'adresse
=====================================  =====================================
``nouvelle_adresse`` vide              ``nouvelle_adresse`` = l'adresse visée
envoyé à l'adresse du compte           envoyé à la nouvelle adresse
servi : l'adresse est vérifiée         servi : elle REMPLACE l'ancienne
=====================================  =====================================

## La règle d'un changement

1. le mot de passe de **celui qui agit** — le titulaire, ou l'administrateur pour
   un autre compte. Vérifié AVANT de dire si l'adresse est prise : une session
   volée n'apprend pas quelles adresses ont un compte ;
2. un lien à usage unique, stocké par son empreinte, envoyé à la nouvelle
   adresse — et l'ancienne reste celle du compte (connexion comprise) tant qu'il
   n'est pas servi ;
3. un avis à l'**ancienne** adresse : c'est elle qu'on prévient, puisque c'est
   elle qu'un détournement ferait taire ;
4. la demande et la confirmation au journal de sécurité, sans aucune adresse.

## Le lien se rejoue (`standards/03` §5 bis)

Les messageries ouvrent les liens reçus avant leur destinataire. Servir le lien
ne fait que CONSTATER que la nouvelle boîte est bien tenue par qui a demandé le
changement — demande déjà prouvée par le mot de passe. Il est donc idempotent :
un jeton connu dont l'effet est acquis répond « déjà confirmée ».
"""

from __future__ import annotations

import re
import secrets
from datetime import timedelta
from typing import Optional

from fastapi import BackgroundTasks, HTTPException
from sqlmodel import Session, select

from app.auth.adresse_compte import compte_par_adresse, normaliser_adresse
from app.auth.empreinte_jeton import empreinte
from app.auth.jwt import verify_password
from app.models.core import EmailVerificationToken, Utilisateur
from app.utils import horloge
from app.utils.config_site import config_site
from app.utils.journal_securite import journaliser_securite
from app.utils.liens import adresse_du_site, nom_site

#: La validité d'un lien de vérification d'adresse — **écrite une seule fois**.
#:
#: 🔴 Elle l'était QUATRE fois avant le 16/09/2026 : deux `timedelta(hours=24)`
#: (la durée réelle du jeton) et deux `"expire_heures": 24` (celle annoncée dans
#: le courriel), aux deux endroits qui émettent ce lien — l'inscription et le
#: renvoi. Rien ne les liait : changer la durée réelle sans toucher aux deux
#: littéraux aurait fait **mentir le message** au résident.
VALIDITE_VERIFICATION_EMAIL = timedelta(hours=24)

LIEN_INVALIDE = "Lien de vérification invalide ou expiré."
MOT_DE_PASSE_INCORRECT = "Mot de passe actuel incorrect."
ADRESSE_PRISE = "Cette adresse e-mail est déjà utilisée."

#: Une adresse a UN « @ », une partie locale, un domaine avec un point — rien de
#: plus fin : le lien envoyé est la seule vraie preuve qu'elle existe.
_FORME_ADRESSE = re.compile(r"[^@\s]+@[^@\s]+\.[^@\s]+")


def _expire_heures() -> int:
    #  Annoncée au résident, DÉDUITE de la validité réelle : elles ne divergent pas.
    return int(VALIDITE_VERIFICATION_EMAIL.total_seconds() // 3600)


def _site(session: Session) -> tuple[str, str]:
    cfg = config_site(session)
    return adresse_du_site(), nom_site(cfg.get("site_nom"))


def emettre_verification_email(
    session: Session,
    user: Utilisateur,
    background_tasks: BackgroundTasks,
    *,
    nouvelle_adresse: Optional[str] = None,
) -> None:
    """Crée le jeton de vérification et envoie le courriel — les deux, toujours ensemble.

    `nouvelle_adresse` — le lien d'un CHANGEMENT : il part à cette adresse et la
    confirmera. Sans elle, le lien de l'inscription, envoyé à l'adresse du compte.

    Un jeton posé sans courriel n'atteint personne, un courriel sans jeton porte
    un lien mort. ⚠️ Ce qui reste à l'appelant : invalider les liens précédents
    (`invalider_liens_en_attente`) — le renvoi et le changement le font,
    l'inscription n'en a pas.
    """
    brut = secrets.token_urlsafe(32)
    session.add(
        EmailVerificationToken(
            user_id=user.id,
            token=empreinte(brut),
            expires_at=horloge.maintenant() + VALIDITE_VERIFICATION_EMAIL,
            nouvelle_adresse=nouvelle_adresse,
        )
    )
    session.commit()

    site_url, site_nom = _site(session)
    from app.utils.email import send_email as _send_email

    background_tasks.add_task(
        _send_email,
        code="verification_email",
        to=nouvelle_adresse or user.email,
        context={
            "prenom": user.prenom,
            "token": brut,
            "lien": f"{site_url}/auth/verifier-email?token={brut}",
            "expire_heures": _expire_heures(),
            "residence": {"nom": site_nom},
            "app": {"url": site_url},
        },
    )


def invalider_liens_en_attente(session: Session, user_id: int, *, changement: bool) -> None:
    """Rend caducs les liens non servis d'UNE nature — l'autre n'est pas touchée.

    Renvoyer le lien de l'inscription n'annule pas un changement en cours, et une
    nouvelle demande de changement n'annule que la précédente : seule la
    dernière adresse demandée peut être confirmée.
    """
    colonne = EmailVerificationToken.nouvelle_adresse
    nature = colonne.is_not(None) if changement else colonne.is_(None)
    for lien in session.exec(
        select(EmailVerificationToken).where(
            EmailVerificationToken.user_id == user_id,
            EmailVerificationToken.used == False,  # noqa: E712  (colonne SQL)
            nature,
        )
    ).all():
        lien.used = True
        session.add(lien)


def demander_changement_adresse(
    session: Session,
    *,
    cible: Utilisateur,
    acteur: Utilisateur,
    nouvelle_adresse: Optional[str],
    mot_de_passe: Optional[str],
    background_tasks: BackgroundTasks,
) -> Optional[str]:
    """Demande que l'adresse de `cible` devienne `nouvelle_adresse` — rend celle-ci, ou None.

    None : ce n'est pas un changement (la même adresse, à la casse près), rien
    n'est demandé ni envoyé — un formulaire réenregistré tel quel reste muet.

    `acteur` — qui agit, et dont le MOT DE PASSE est éprouvé : le titulaire sur
    son profil, l'administrateur sur le compte d'un autre. Lève 400 sinon.
    """
    nouvelle = normaliser_adresse(nouvelle_adresse)
    if nouvelle == normaliser_adresse(cible.email):
        return None
    if not _FORME_ADRESSE.fullmatch(nouvelle):
        raise HTTPException(400, "Adresse e-mail invalide.")
    if not verify_password(mot_de_passe or "", acteur.hashed_password or ""):
        journaliser_securite("connexion_refusee", cible_id=acteur.id, detail="mot de passe actuel")
        raise HTTPException(400, MOT_DE_PASSE_INCORRECT)
    if compte_par_adresse(session, nouvelle):
        raise HTTPException(400, ADRESSE_PRISE)

    invalider_liens_en_attente(session, cible.id, changement=True)
    emettre_verification_email(session, cible, background_tasks, nouvelle_adresse=nouvelle)

    site_url, site_nom = _site(session)
    from app.utils.email import send_email as _send_email

    #  L'avis part à l'ANCIENNE adresse — sans `destinataire_id` : comme le mot de
    #  passe oublié, il ne se laisse couper par aucune préférence de notification
    #  (`test_courriels_transactionnels.py`).
    background_tasks.add_task(
        _send_email,
        code="adresse_changement_avis",
        to=cible.email,
        context={
            "destinataire": {"prenom": cible.prenom},
            "nouvelle_adresse": nouvelle,
            "par_un_administrateur": acteur.id != cible.id,
            "residence": {"nom": site_nom},
            "app": {"url": site_url},
        },
    )
    journaliser_securite("adresse_changement_demande", acteur_id=acteur.id, cible_id=cible.id)
    return nouvelle


def servir_lien(session: Session, brut: str) -> dict:
    """Sert un lien de vérification, quelle que soit sa nature — 400 s'il ne vaut rien."""
    lien = session.exec(
        select(EmailVerificationToken).where(EmailVerificationToken.token == empreinte(brut))
    ).first()
    user = session.get(Utilisateur, lien.user_id) if lien else None
    if not user:
        raise HTTPException(400, LIEN_INVALIDE)
    if lien.nouvelle_adresse:
        return _confirmer_changement(session, lien, user)

    #  Un lien DÉJÀ SERVI, pour une adresse vérifiée, dit « déjà vérifiée » — et
    #  non « invalide » (29/09/2026) : le scanner de la messagerie l'avait ouvert
    #  une minute avant le destinataire.
    if user.email_verifie:
        return {"message": "Adresse e-mail déjà vérifiée."}
    if lien.used or lien.expires_at < horloge.maintenant():
        raise HTTPException(400, LIEN_INVALIDE)
    user.email_verifie = True
    lien.used = True
    session.add(user)
    session.add(lien)
    session.commit()
    return {"message": "Adresse e-mail vérifiée avec succès."}


def _confirmer_changement(
    session: Session, lien: EmailVerificationToken, user: Utilisateur
) -> dict:
    if lien.used and normaliser_adresse(user.email) == lien.nouvelle_adresse:
        return {"message": "Nouvelle adresse e-mail déjà confirmée.", "changement_adresse": True}
    if lien.used or lien.expires_at < horloge.maintenant():
        raise HTTPException(400, LIEN_INVALIDE)

    #  Prise entre la demande et le clic (une inscription, un autre changement) :
    #  le lien ne la vole pas, il devient caduc. L'adresse du compte n'est pas
    #  encore la nouvelle (sinon c'était « déjà confirmée »), donc qui la porte
    #  est quelqu'un d'autre.
    if compte_par_adresse(session, lien.nouvelle_adresse):
        lien.used = True
        session.add(lien)
        session.commit()
        raise HTTPException(400, "Cette adresse e-mail est désormais utilisée par un autre compte.")

    user.email = lien.nouvelle_adresse
    #  Le lien vient d'être servi depuis cette boîte : c'est la preuve même.
    user.email_verifie = True
    lien.used = True
    session.add(user)
    session.add(lien)
    session.commit()
    #  `acteur_id` reste None : la route n'est pas authentifiée — le porteur du
    #  lien a prouvé tenir la boîte, pas qui il est.
    journaliser_securite("adresse_changee", cible_id=user.id)
    return {
        "message": "Nouvelle adresse e-mail confirmée : elle sert désormais à vous connecter.",
        "changement_adresse": True,
    }
