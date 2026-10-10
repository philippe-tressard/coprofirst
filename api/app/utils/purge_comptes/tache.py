"""La tâche quotidienne de la purge des comptes inactifs (#1580).

Un passage, dans cet ordre :

1. **Relever** — chaque compte inactif depuis deux ans est classé : exclu (et
   signalé s'il administre), à avertir, ou à supprimer. Un compte redevenu actif
   perd l'avertissement qu'il portait.
2. **Avertir** — au plus `PLAFOND_AVERTISSEMENTS_PAR_PASSAGE`, du plus
   anciennement inactif au plus récent. La date n'est enregistrée **que si le
   courriel est parti** : un SMTP en panne ne vaut pas avertissement, donc ne
   mène à aucune suppression.
3. **Supprimer** — par `utils/suppression_compte`, la fonction même de
   l'administration, et seulement si le volume du passage est normal
   (`regles.suppressions_anormales`). Sinon, aucune suppression, et un `WARNING`.

⚠️ La tâche ne lève jamais : sous le planificateur, une exception tuerait le job
pour de bon. Elle laisse une ligne à CHAQUE passage, même vide — un battement
qu'on n'entend pas ne se distingue pas d'une tâche morte (`standards/07`).

⚠️ Un passage manqué (redémarrage à l'heure du rendez-vous) n'est pas rattrapé :
il décale d'un jour, dans le sens de la conservation, jamais de l'effacement.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime
from typing import Callable, Optional

from sqlmodel import Session, select

from app.models.core import Utilisateur
from app.utils import horloge
from app.utils.dates_fr import date_longue
from app.utils.destinataires import site_manager_user_id
from app.utils.journal_securite import journaliser_securite
from app.utils.noms import contexte_personne
from app.utils.purge_comptes import regles
from app.utils.suppression_compte import supprimer_compte

logger = logging.getLogger("hostachy.purge_comptes")

#: L'identifiant de la tâche permanente (`main.py`, `TACHES_PERMANENTES`).
ID_TACHE = "purge_comptes_inactifs"

#: `envoyer(session, user, contexte) -> bool` — vrai si le courriel est parti.
Envoyer = Callable[[Session, Utilisateur, dict], bool]


def _envoyer_avertissement(session: Session, user: Utilisateur, contexte: dict) -> bool:
    """Le facteur réel : le moteur de courriel, qui dit s'il a envoyé.

    ⚠️ Sans `destinataire_id` : l'avertissement est TRANSACTIONNEL — un compte qui
    a coupé ses notifications serait sinon supprimé sans avoir été prévenu
    (`test_courriels_transactionnels.py`).
    """
    from app.utils.email import send_email

    #  Le code et les clés du contexte s'écrivent en LITTÉRAUX : c'est ainsi que
    #  les contrôles des courriels reconnaissent le point d'appel et confrontent
    #  ses clés au modèle (`test_email_contexte_appel`, envoi transactionnel).
    envoi = send_email(
        code="compte_inactif_avertissement",
        to=user.email,
        context={
            "destinataire": contexte["destinataire"],
            "date_suppression": contexte["date_suppression"],
            "derniere_activite": contexte["derniere_activite"],
        },
        session=session,
    )
    return bool(asyncio.run(envoi))


def _signaler(user: Utilisateur, motif: str) -> None:
    journaliser_securite("compte_purge_epargne", cible_id=user.id, detail=f"{motif} inactif")


def _avertir(session: Session, user: Utilisateur, maintenant: datetime, envoyer: Envoyer) -> bool:
    """Envoie l'avertissement ; n'enregistre sa date QUE s'il est parti."""
    contexte = {
        "destinataire": contexte_personne(user),
        "date_suppression": date_longue(
            horloge.jour_civil(maintenant + regles.DELAI_AVANT_SUPPRESSION)
        ),
        "derniere_activite": date_longue(horloge.jour_civil(regles.date_de_reference(user))),
    }
    try:
        parti = envoyer(session, user, contexte)
    except Exception as exc:  # un envoi qui lève n'est pas parti
        logger.warning("Avertissement de purge non envoyé au compte %s : %s", user.id, exc)
        parti = False
    if not parti:
        return False
    user.purge_avertie_le = maintenant
    session.add(user)
    session.commit()
    journaliser_securite("compte_purge_averti", cible_id=user.id)
    return True


def _supprimer(
    session: Session, user: Utilisateur, maintenant: datetime, gestionnaire_id: Optional[int]
) -> bool:
    """Supprime un compte averti et toujours inactif — relu juste avant le geste."""
    user_id = user.id
    try:
        session.refresh(user)
        #  Il a pu se reconnecter, ou recevoir le rôle d'administrateur, depuis le
        #  relevé : on repose TOUTES les questions, sur le compte relu.
        if (
            regles.exclusion(user, gestionnaire_id) is not None
            or not regles.est_inactif(user, maintenant)
            or not regles.avertissement_echu(user, maintenant)
        ):
            return False
        inactif_jours = (maintenant - regles.date_de_reference(user)).days
        averti_jours = (maintenant - user.purge_avertie_le).days
        supprimer_compte(session, user_id)
        session.commit()
    except Exception as exc:
        session.rollback()
        logger.warning("Compte %s non supprimé par la purge : %s", user_id, exc)
        return False
    #  Personne n'agit : le planificateur efface. Après lui, cette ligne est la
    #  SEULE trace du compte — identifiant et durées, jamais une adresse.
    journaliser_securite(
        "compte_purge_inactivite",
        cible_id=user_id,
        detail=f"inactif {inactif_jours} j, averti il y a {averti_jours} j",
    )
    return True


def _supprimer_ferme(
    session: Session, user: Utilisateur, maintenant: datetime, gestionnaire_id: Optional[int]
) -> bool:
    """Supprime un compte fermé dont la durée est échue (#1822) — relu juste avant."""
    user_id = user.id
    try:
        session.refresh(user)
        motif = regles.fermeture_echue(user, maintenant)
        if motif is None or regles.compte_d_administration(user, gestionnaire_id) is not None:
            return False
        depuis = user.compte_ferme_le or user.cree_le
        supprimer_compte(session, user_id)
        session.commit()
    except Exception as exc:
        session.rollback()
        logger.warning("Compte %s non supprimé par la purge : %s", user_id, exc)
        return False
    journaliser_securite(
        "compte_purge_fermeture",
        cible_id=user_id,
        detail=f"{motif} depuis {(maintenant - depuis).days} j",
    )
    return True


def purger_comptes_inactifs(
    session: Optional[Session] = None,
    *,
    maintenant: Optional[datetime] = None,
    envoyer: Optional[Envoyer] = None,
) -> dict:
    """La tâche permanente. Rend le compte rendu du passage ; ne lève jamais."""
    from app import contexte

    propre = session is None
    session = session or contexte.nouvelle_session()
    maintenant = maintenant or horloge.maintenant()
    envoyer = envoyer or _envoyer_avertissement
    rendu = {
        "avertis": 0,
        "supprimes": 0,
        "supprimes_fermes": 0,
        "epargnes": 0,
        "echecs_envoi": 0,
        "echecs_suppression": 0,
        "suspendue": False,
    }
    try:
        gestionnaire_id = site_manager_user_id(session)
        comptes = session.exec(select(Utilisateur).order_by(Utilisateur.id)).all()
        a_avertir: list[Utilisateur] = []
        a_supprimer: list[Utilisateur] = []
        fermes: list[Utilisateur] = []
        for user in comptes:
            #  Fermé (refusé, désactivé) ou jamais décidé : sa propre durée (#1822).
            if not user.actif:
                if regles.fermeture_echue(user, maintenant) is not None:
                    motif = regles.compte_d_administration(user, gestionnaire_id)
                    if motif is None:
                        fermes.append(user)
                    else:
                        rendu["epargnes"] += 1
                        _signaler(user, motif)
                continue
            if not regles.est_inactif(user, maintenant):
                if user.purge_avertie_le is not None:
                    user.purge_avertie_le = None  # redevenu actif : l'avertissement tombe
                    session.add(user)
                continue
            motif = regles.exclusion(user, gestionnaire_id)
            if motif is not None:
                if motif in regles.MOTIFS_SIGNALES:
                    rendu["epargnes"] += 1
                    _signaler(user, motif)
                continue
            if regles.avertissement_echu(user, maintenant):
                a_supprimer.append(user)
            elif user.purge_avertie_le is None or regles.avertissement_perime(user, maintenant):
                a_avertir.append(user)
        session.commit()

        a_avertir.sort(key=regles.date_de_reference)
        for user in a_avertir[: regles.PLAFOND_AVERTISSEMENTS_PAR_PASSAGE]:
            rendu[
                "avertis" if _avertir(session, user, maintenant, envoyer) else "echecs_envoi"
            ] += 1

        if regles.suppressions_anormales(len(a_supprimer) + len(fermes), len(comptes)):
            rendu["suspendue"] = True
            logger.warning(
                "Purge des comptes inactifs SUSPENDUE : %d suppression(s) sur %d compte(s), "
                "au-delà du seuil de sûreté (%d, ou %d %%). Aucun compte supprimé — "
                "horloge, base restaurée ? À examiner avant toute suppression manuelle.",
                len(a_supprimer) + len(fermes),
                len(comptes),
                regles.SURETE_NOMBRE_MAX,
                round(regles.SURETE_PROPORTION_MAX * 100),
            )
        else:
            for user in a_supprimer:
                ok = _supprimer(session, user, maintenant, gestionnaire_id)
                rendu["supprimes" if ok else "echecs_suppression"] += 1
            for user in fermes:
                ok = _supprimer_ferme(session, user, maintenant, gestionnaire_id)
                rendu["supprimes_fermes" if ok else "echecs_suppression"] += 1
        logger.info(
            "Purge des comptes inactifs : %d averti(s), %d supprimé(s), %d fermé(s) "
            "supprimé(s), %d épargné(s), %d envoi(s) en échec, %d suppression(s) en échec%s",
            rendu["avertis"],
            rendu["supprimes"],
            rendu["supprimes_fermes"],
            rendu["epargnes"],
            rendu["echecs_envoi"],
            rendu["echecs_suppression"],
            " — SUSPENDUE" if rendu["suspendue"] else "",
        )
    except Exception as exc:  # pragma: no cover - la tâche ne meurt pas
        session.rollback()
        logger.warning("Purge des comptes inactifs non traitée : %s", exc)
    finally:
        if propre:
            session.close()
    return rendu


__all__ = ["ID_TACHE", "purger_comptes_inactifs"]
