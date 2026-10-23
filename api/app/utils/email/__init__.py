"""Envoi d'e-mails via fastapi-mail + modèles Jinja2 stockés en base.

`email.py` faisait **686 lignes**. Découpé le 11/08/2026, au fil de l'eau.

| Module | Ce qui y change |
|---|---|
| `__init__` | à qui l'on écrit, quand, et avec quel contexte |
| `gabarit` | ce que le destinataire voit : gabarit HTML, bandeaux, logo |
| `pieces_jointes` | noms d'origine, en-têtes de disposition |

La surface publique ne bouge pas : `send_email`, `send_email_group`,
`INTENTIONS`, `get_site_manager_notification_email`, `_get_smtp_config` et
`connexion_smtp` s'importent depuis `app.utils.email` comme avant — vingt
modules en dépendent, plus les tests.
"""

import logging
from typing import Any

from sqlmodel import Session, select

from app.utils.config_site import config_site
from app.utils.demo import est_demo
from app.utils.preferences_mail import mail_autorise, trier_destinataires
from app.models.core import HistoriqueEmail, ModeleEmail, Utilisateur

#  La configuration du canal SMTP est un sujet distinct de la composition
#  d'un message : elle vit dans `app/utils/smtp.py` depuis le 08/08/2026.
from app.seed.emails import est_desactivable, expediteur_du_modele
from app.utils.smtp import (  # noqa: F401  (ré-export : config.py l'importe d'ici)
    _get_smtp_config,
    adresse_expedition,
    connexion_smtp,
    entete_reponse,
)

from .gabarit import INTENTIONS, _wrap_email  # noqa: F401  (ré-export : admin/communications l'importe d'ici)
from .pieces_jointes import _preparer_pieces_jointes


logger = logging.getLogger("email")


def _masquer(adresse: str | None) -> str:
    """`p***@domaine.fr` — assez pour diagnostiquer, pas assez pour ficher.

    🔴 Les journaux portaient l'adresse ENTIÈRE (#777). Ces lignes partent dans
    les alertes du monitoring et dans les rapports qu'on recopie ailleurs : c'est
    par là qu'une adresse de résident sort. Le premier caractère et le domaine
    suffisent à reconnaître un destinataire quand on cherche pourquoi un envoi a
    échoué.

    ⚠️ L'historique en base garde l'adresse entière : il répond à « qui n'a pas
    reçu quoi ? », derrière une session admin.
    """
    #  La forme est celle de `auth/adresse_compte.adresse_masquee`, sa seule
    #  écriture (#2153) ; le journal dit seulement « (vide) » plutôt que rien.
    from app.auth.adresse_compte import adresse_masquee

    return adresse_masquee(adresse) or "(vide)"


# Mapping code email → clé préférence utilisateur (catégorie_mail)
# Les codes absents (system, account) sont toujours envoyés.
#  Les rubriques ont disparu le 14/08/2026 (#339) : le réglage ne se fait plus par
#  type de contenu mais par BÂTIMENT — le mien, les autres. La décision est dans
#  `utils/preferences_mail.py`, seul endroit qui lit les préférences.


def get_site_manager_notification_email(session: Session) -> tuple[str, dict[str, str]]:
    """Retourne l'email de notification du gestionnaire du site et la config lue.

    Le gestionnaire se lit par `destinataires.site_manager_user_id` — un
    administrateur, ou personne (#1505) ; à défaut, l'« E-mail administrateur ».
    """
    from app.utils.destinataires import site_manager_user_id

    config = config_site(session, "site_email", "site_manager_user_id")
    site_email = (config.get("site_email") or "").strip()
    gestionnaire_id = site_manager_user_id(session)
    gestionnaire = session.get(Utilisateur, gestionnaire_id) if gestionnaire_id else None
    site_manager_email = (gestionnaire.email or "").strip() if gestionnaire else ""
    return site_manager_email or site_email, config


def _log_email(
    session: Session, code: str, to: str, statut: str, *, sujet: str = "", erreur: str | None = None
) -> None:
    """Enregistre une entrée dans historique_email (fail-safe)."""
    try:
        entry = HistoriqueEmail(
            code=code, destinataire=to, sujet=sujet[:200], statut=statut, erreur=erreur
        )
        session.add(entry)
        session.commit()
    except Exception:
        try:
            session.rollback()
        except Exception:
            pass


from .rendu import (  # noqa: E402,F401  (ré-export : le rendu vit dans `rendu.py`)
    _contexte_rendu,
    _render,
    _sujet_sur_une_ligne,
    composer_email,
)


async def _envoyer_modele(
    code: str,
    context: dict[str, Any],
    session: Session,
    *,
    to: list[str],
    cc: list[str] | None = None,
    bcc: list[str] | None = None,
    attachments: list[str] | None = None,
    jeton_reponse: str | None = None,
) -> bool:
    """Le tronc commun des deux envois : modèle, rendu, SMTP, journal, nettoyage.

    Rend vrai si le message est PARTI, faux sinon (modèle inactif, erreur SMTP) —
    sans jamais lever. La purge des comptes inactifs en dépend (#1580) : un
    avertissement qui n'est pas parti ne doit pas ouvrir le délai de suppression.

    🔴 `send_email` (103 l.) et `send_email_group` (112 l.) étaient identiques à
    **68 %** — mesuré. Deux écritures d'une même séquence, donc deux occasions de
    diverger, et elles avaient déjà divergé : le chemin groupé ne journalisait
    pas le cas « modèle inactif », abandonnant l'envoi sans laisser de trace.

    Ne reste chez les appelants que ce qui les distingue vraiment : la
    vérification des **préférences** et la résolution des destinataires.

    ⚠️ La session n'est ni ouverte ni fermée ici — elle appartient à l'appelant,
    seul à savoir s'il l'a créée.
    """
    trace = ", ".join(to + (cc or []))

    template: ModeleEmail | None = session.exec(
        select(ModeleEmail).where(ModeleEmail.code == code)
    ).first()
    #  Un modèle non désactivable part même décoché (#2054) : sa case ne coupe rien.
    if not template or (not template.actif and est_desactivable(code)):
        #  JOURNALISE DANS LES DEUX CAS depuis la factorisation : le chemin
        #  groupe abandonnait en silence, et un envoi qui n'a pas eu lieu sans
        #  trace est indistinguable d'un envoi qui n'a jamais ete demande.
        _log_email(session, code, trace, "ignore", erreur="template inactive ou inexistante")
        return False

    ctx, site_nom, site_url, email_footer = _contexte_rendu(session, context)
    smtp_cfg = _get_smtp_config(session)
    try:
        from fastapi_mail import FastMail, MessageSchema

        cfg = connexion_smtp(
            smtp_cfg,
            #  🔴 `intention_servie` : celle de la LIGNE, pas du code — les deux
            #  sources et leur histoire sont dans `expediteur_du_modele`.
            expediteur=adresse_expedition(
                smtp_cfg,
                expediteur_du_modele(
                    code,
                    jeton_reponse=jeton_reponse,
                    intention_servie=template.intention,
                ),
            ),
        )
        fm = FastMail(cfg)
        rendered_subject, full_html = composer_email(
            template,
            ctx,
            site_nom=site_nom,
            site_url=site_url,
            email_footer=email_footer,
            attachments=attachments,
        )
        msg_kwargs: dict[str, Any] = dict(
            subject=rendered_subject,
            #  Sans destinataire principal, les copies le deviennent : un
            #  message sans `recipients` ne part pas.
            recipients=to if to else (cc or []),
            body=full_html,
            subtype="html",
            headers=entete_reponse(smtp_cfg, jeton_reponse) or None,
        )
        if to and cc:
            msg_kwargs["cc"] = cc
        if bcc:
            msg_kwargs["bcc"] = bcc
        if attachments:
            msg_kwargs["attachments"] = _preparer_pieces_jointes(attachments)
        await fm.send_message(MessageSchema(**msg_kwargs))
        _log_email(session, code, trace, "succes", sujet=rendered_subject)
        return True
    except Exception as exc:
        #  L'ADRESSE EST MASQUEE (#777) : ces lignes partent dans les alertes du
        #  monitoring et dans les rapports qu'on recopie ailleurs. L'historique
        #  en base, lui, garde l'adresse entiere — il est derriere une session
        #  admin, et sert a repondre a « qui n'a pas recu quoi ? ».
        if len(to) + len(cc or []) > 1:
            logger.error(
                "Erreur envoi email groupe [%s] -> %d destinataire(s) : %s",
                code,
                len(to) + len(cc or []),
                exc,
            )
        else:
            logger.error("Erreur envoi email [%s] -> %s : %s", code, _masquer(trace), exc)
        _log_email(session, code, trace, "erreur", erreur=str(exc)[:500])
        return False


def envoi_actif(session: Session) -> bool:
    """L'envoi est-il actif ? La case de la copropriété, en base, et elle seule (#2058).

    `smtp_enabled` absent laissait `MAIL_ENABLED` trancher : la base de chaque
    copropriété a reçu cette valeur par `smtp.amorcer`. Absente encore — une
    copropriété d'installation commune que son administrateur n'a pas réglée —,
    rien ne part.
    """
    if est_demo():
        #  La démo publique : rien ne part, quoi que dise la base (#1902).
        return False
    return _get_smtp_config(session).get("smtp_enabled") == "1"


def _tracer_demo(session: Session, code: str, destinataires: str) -> None:
    """En démo, ce qui serait parti s'inscrit à l'historique : l'administrateur le voit.

    Statut « ignore », jamais « succes » : `send_email` rend faux, et la purge des
    comptes inactifs n'ouvre son délai que sur un envoi PARTI (#1580).
    """
    if est_demo():
        _log_email(session, code, destinataires, "ignore", erreur="démonstration : non envoyé")


def _session_ou_neuve(session: Session | None) -> tuple[Session, bool]:
    """La session de l'appelant, ou une neuve — et qui devra la fermer.

    Les tâches d'arrière-plan n'en ont pas : elles s'exécutent après la réponse.
    """
    if session is not None:
        return session, False
    from app import contexte

    return contexte.nouvelle_session(), True


async def send_email(
    code: str,
    to: str,
    context: dict[str, Any],
    session: Session | None = None,
    *,
    cc: list[str] | None = None,
    bcc: list[str] | None = None,
    attachments: list[str] | None = None,
    destinataire_id: int | None = None,
    batiments_concernes: set[int] | None = None,
    jeton_reponse: str | None = None,
) -> bool:
    """Envoie le modèle `code` à UN destinataire, si ses préférences l'acceptent.

    Fail graceful : une erreur d'envoi est journalisée, jamais propagée — un
    ticket créé ne doit pas échouer parce que le SMTP est indisponible. Rend
    vrai si le message est parti : faux pour une préférence, un envoi éteint,
    un modèle inactif ou une erreur — l'appelant qui en dépend le sait (#1580).

    Rendu, envoi et journal vivent dans `_envoyer_modele`, partagé avec l'envoi
    groupé : ne reste ici que **la préférence du destinataire**.
    """
    session, close_session = _session_ou_neuve(session)
    try:
        if destinataire_id:
            user = session.get(Utilisateur, destinataire_id)
            if user and not mail_autorise(user, batiments_concernes):
                logger.debug(
                    "Email [%s] non envoye -> preference de batiment, user %s",
                    code,
                    destinataire_id,
                )
                _log_email(session, code, to, "ignore", erreur="preference de batiment")
                return False

        if not envoi_actif(session):
            _tracer_demo(session, code, to)
            return False

        return await _envoyer_modele(
            code,
            context,
            session,
            to=[to],
            cc=cc,
            bcc=bcc,
            attachments=attachments,
            jeton_reponse=jeton_reponse,
        )
    finally:
        if close_session:
            session.close()


async def send_email_group(
    code: str,
    to_recipients: list[tuple[int | None, str]],
    context: dict[str, Any],
    session: Session | None = None,
    *,
    cc_recipients: list[tuple[int | None, str]] | None = None,
    bcc: list[str] | None = None,
    attachments: list[str] | None = None,
    batiments_concernes: set[int] | None = None,
    jeton_reponse: str | None = None,
):
    """Envoie UN seul message à plusieurs destinataires (to + cc facultatif).

    Les préférences de chacun sont vérifiées **individuellement** — c'est la
    seule vraie différence avec l'envoi unitaire. Les destinataires se voient
    entre eux, et l'historique n'enregistre qu'une ligne pour tous.

    Le reste vient de `_envoyer_modele`, partagé avec `send_email`.
    """
    session, close_session = _session_ou_neuve(session)
    try:
        if not envoi_actif(session):
            _tracer_demo(session, code, ", ".join(e for _uid, e in to_recipients))
            return

        #  La préférence de chacun — sauf du destinataire DÉSIGNÉ par la
        #  Diffusion (#2006). Même fonction que l'aperçu : `trier_destinataires`.
        to_emails, _ = trier_destinataires(session, to_recipients, batiments_concernes)
        cc_emails, _ = trier_destinataires(session, cc_recipients or [], batiments_concernes)
        #  Personne ne veut de ce message : ce n'est pas un echec, c'est la
        #  preference de chacun qui a ete respectee.
        if not to_emails and not cc_emails:
            return

        await _envoyer_modele(
            code,
            context,
            session,
            to=to_emails,
            cc=cc_emails,
            bcc=bcc,
            attachments=attachments,
            jeton_reponse=jeton_reponse,
        )
    finally:
        if close_session:
            session.close()
