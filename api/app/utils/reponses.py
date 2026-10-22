"""Helpers partagés pour les réponses de la Communauté (idées, annonces, sondages).

Source unique de vérité pour :
  - l'enrichissement de l'auteur d'une réponse (nom + bâtiment + rôle) ;
  - la mise en avant des réponses CS/admin (est_cs → tri prioritaire côté front) ;
  - la notification du créateur du contenu (in-app + email, dans le respect des
    préférences utilisateur).

Utilisé par idees.py, annonces.py et sondages.py pour une UX cohérente et éviter
toute divergence de code entre les sous-rubriques.
"""

from __future__ import annotations

from typing import Optional

from fastapi import BackgroundTasks
from sqlmodel import Session

from app.utils.batiments import libelle_batiment_ou
from app.models.core import (
    Batiment,
    RoleUtilisateur,
    Utilisateur,
)
from app.utils.noms import ANCIEN_RESIDENT, nom_affiche
from app.utils.recuperer import ou_rien
from app.utils.html_sur import html_riche
from app.utils.roles_libelles import libelle_role, libelle_statut_court
from app.utils.liens import adresse_du_site
from app.auth.deps import est_moderateur
from app.utils.cloche import sonner
from app.utils.valeurs import valeur

# Code du template email (voir seed.EMAIL_TEMPLATES + _EMAIL_PREF_MAP).
REPONSE_EMAIL_CODE = "reponse_communaute"

#  🔴 Les libellés vivent dans `app/utils/roles_libelles.py` depuis le
#  06/09/2026 (#801) : cette table était la SEPTIÈME écriture de la même notion,
#  et la seule qui divergeait pour une bonne raison — sans la dire. Elle est
#  désormais nommée `LIBELLES_STATUT_COURT`, avec son motif : à côté d'une
#  réponse, « Copropriétaire » suffit ; préciser « résident » ou « bailleur »
#  révélerait si la personne habite son lot ou le loue.


#  La signature d'un ADMINISTRATEUR en toutes lettres — « Admin » est
#  l'étiquette d'un écran d'administration, pas une signature. Divergence
#  assumée, écrite ici plutôt que subie (elle vivait dans `utils/reponses`).
SIGNATURE_ADMIN = "Administrateur"


def role_signature(personne) -> str | None:
    """Ce qu'une personne EST, en un mot, à côté de son nom.

    Le conseil syndical d'abord (c'est ce qui pèse dans un échange), puis
    l'administration, puis le statut dans sa forme courte (« Copropriétaire »,
    « Locataire », « Syndic »). `None` quand rien n'est connu.

    Sortie d'`auteur_meta` (#2075) : la signature d'une réponse de la
    Communauté et celle d'un avis sur l'application posent la même question —
    une seule écriture. Elle vit ICI et non dans `roles_libelles`, qui porte la
    table des rôles, `externe` compris : une décision par `has_role` à côté d'elle
    y passerait pour une copie du refus des comptes externes
    (`test_refus_externe_source_unique`).
    """
    if personne.has_role(RoleUtilisateur.conseil_syndical):
        return libelle_role(RoleUtilisateur.conseil_syndical)
    if personne.has_role(RoleUtilisateur.admin):
        return SIGNATURE_ADMIN
    statut = valeur(personne.statut) or ""
    return libelle_statut_court(statut) if statut else None


def auteur_meta(auteur: Optional[Utilisateur], session: Session) -> dict:
    """Nom + bâtiment + rôle d'un auteur de réponse.

    est_cs=True pour CS/admin : leur réponse a plus de poids (tri prioritaire +
    mise en avant côté front).
    """
    if auteur is None:
        return {
            "auteur_nom": ANCIEN_RESIDENT,
            "auteur_batiment": None,
            "auteur_role": None,
            "est_cs": False,
        }
    est_cs = est_moderateur(auteur)
    role = role_signature(auteur)
    batiment = None
    if auteur.batiment_id is not None:
        bat = session.get(Batiment, auteur.batiment_id)
        batiment = libelle_batiment_ou(bat, None)
    return {
        "auteur_nom": nom_affiche(auteur.prenom, auteur.nom),
        "auteur_batiment": batiment,
        "auteur_role": role,
        "est_cs": est_cs,
    }


def enrich_reponse(rep, session: Session) -> dict:
    """Sérialise une réponse (ReponseCommunaute ou CommentaireSondage) + auteur."""
    auteur = ou_rien(session, Utilisateur, rep.auteur_id)
    return {
        "id": rep.id,
        "auteur_id": rep.auteur_id,
        "contenu": rep.contenu,
        "cree_le": rep.cree_le,
        **auteur_meta(auteur, session),
    }


def tri_reponses(reponses: list[dict]) -> list[dict]:
    """CS/admin d'abord (plus de poids), puis du plus ancien au plus récent."""
    return sorted(reponses, key=lambda x: (not x["est_cs"], x["cree_le"]))


#  `_pref` a disparu le 14/08/2026 (#339). Il lisait `communaute_app`, l'un des
#  quatre réglages de notification DANS L'APPLICATION — supprimés avec la matrice.
#  Ces notifications restent actives, ce qui était déjà leur valeur par défaut :
#  la condition est donc devenue toujours vraie, et on la retire plutôt que de la
#  laisser mentir. Seul l'e-mail se règle désormais, par bâtiment
#  (`utils/preferences_mail.py`).


def notifier_nouvelle_reponse(
    session: Session,
    background_tasks: BackgroundTasks,
    *,
    createur_id: Optional[int],
    auteur: Utilisateur,
    rubrique_label: str,
    sujet: str,
    extrait: str,
    lien_path: str,
) -> None:
    """Notifie le créateur d'un contenu (idée/annonce/sondage) d'une nouvelle réponse.

    - Cloche : `utils/cloche.sonner` — le profil décide (#1187).
    - Email  : send_email(code=reponse_communaute) — le profil décide aussi, via
      `destinataire_id` (`utils/preferences_mail`).
    On ne notifie jamais l'auteur de sa propre réponse.
    """
    if not createur_id or createur_id == auteur.id:
        return
    createur = session.get(Utilisateur, createur_id)
    if not createur:
        return

    extrait = (extrait or "").strip()
    sonner(
        session,
        destinataire_id=createur_id,
        type="communaute_reponse",
        titre=f"Nouvelle réponse sur {rubrique_label}",
        corps=extrait[:200],
        lien=lien_path,
    )

    if createur.email:
        # send_email importé paresseusement (comme tickets.py) — évite un import
        # lourd au chargement du module et les cycles.
        from app.utils.email import send_email

        ctx = {
            "reponse": {
                "auteur": nom_affiche(auteur.prenom, auteur.nom),
                "rubrique_label": rubrique_label,
                "sujet": sujet,
                "extrait": html_riche(extrait[:300]),
                "lien": f"{adresse_du_site()}{lien_path}",
            }
        }
        background_tasks.add_task(
            send_email,
            code=REPONSE_EMAIL_CODE,
            to=createur.email,
            context=ctx,
            destinataire_id=createur_id,
        )


# Code du template email pour un changement de statut d'idée.
IDEE_STATUT_EMAIL_CODE = "idee_statut"


def notifier_votants_idee(
    session: Session,
    background_tasks: BackgroundTasks,
    *,
    votant_ids: list[int],
    idee_titre: str,
    statut_label: str,
    lien_path: str = "/sondages",
    exclure_id: Optional[int] = None,
) -> None:
    """Notifie les votants d'une idée qu'elle a changé de statut (retenue/réalisée).

    Cloche et courriel, chacun selon le profil (`utils/preferences_mail`). On
    ne notifie qu'une fois chaque votant et jamais l'auteur de l'action.
    """
    site_url = adresse_du_site()
    for uid in {u for u in votant_ids if u and u != exclure_id}:
        dest = session.get(Utilisateur, uid)
        if not dest:
            continue
        sonner(
            session,
            destinataire_id=uid,
            type="communaute_idee",
            titre=f"Une idée que vous avez soutenue est {statut_label.lower()}",
            corps=idee_titre[:200],
            lien=lien_path,
        )
        if dest.email:
            from app.utils.email import send_email

            ctx = {
                "idee": {
                    "titre": idee_titre,
                    "statut_label": statut_label,
                    "lien": f"{site_url}{lien_path}",
                }
            }
            background_tasks.add_task(
                send_email,
                code=IDEE_STATUT_EMAIL_CODE,
                to=dest.email,
                context=ctx,
                destinataire_id=uid,
            )
