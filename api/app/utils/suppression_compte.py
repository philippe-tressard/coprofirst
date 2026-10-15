"""Supprimer un compte — **une seule façon**, pour l'administration comme pour la purge.

## Pourquoi ce module (#1580, 04/10/2026)

La suppression vivait dans le routeur (`routers/admin/utilisateurs.supprimer_utilisateur`).
La purge automatique des comptes inactifs doit faire **exactement** la même chose :
une seconde écriture divergerait le jour où la première apprend une table de plus
— c'est ce qui était arrivé à la liste tenue à la main que `purge_referentielle`
a remplacée (#546). Le corps est donc ici, et le routeur comme la purge l'appellent.

## Ce qu'elle fait des objets de la personne

Les onze premières étapes portent des règles MÉTIER (remettre un statut d'import,
retirer une entrée d'un `..._json`, délier plutôt que supprimer un badge) et
passent en premier. `purger` ramasse ensuite le reste en lisant les métadonnées :
une référence obligatoire part avec le compte, une facultative est déliée.

✅ **Les affaires restent, sans nom** (arbitrage du 10/10/2026, #1688, qui
inverse celui du 28/08) : une affaire, son fil et ses messages sont la mémoire
de la copropriété. Leur `auteur_id` est facultatif, donc délié, et l'écran dit
« Ancien résident » (`utils/noms.nom_auteur`). Ce qui n'appartient qu'à la
personne part toujours avec elle. 🔒 `test_suppression_compte_anonymise.py`.

## Ce qu'elle ne fait pas

Ni `commit`, ni journal : l'appelant décide de la transaction, et c'est lui qui
sait **qui** supprime — l'administrateur nommé, ou personne (la purge).
"""

from __future__ import annotations

import json

from sqlalchemy import or_
from sqlmodel import Session, select

from app.models.core import (
    CommandeAcces,
    DemandeModificationProfil,
    HistoriqueSauvegarde,
    LocationBail,
    LotImport,
    Mandat,
    Notification,
    PasswordResetToken,
    RefreshToken,
    RemiseObjet,
    StatutImport,
    StatutLotImport,
    UserLot,
)
from app.utils.purge_referentielle import purger
from app.utils.telemetrie_compte import effacer_telemetrie
from app.utils.types_acces import TYPES_ACCES

#: Ce qu'un compte supprimé LAISSE, sans nom (#1688, #1821 — arbitrages du
#: 10/10/2026) : la référence est facultative, la purge la délie, l'écran dit
#: « Ancien résident » (`utils/noms.nom_auteur`).
CONTENUS_GARDES: dict[tuple[str, str], str] = {
    ("ticket", "auteur_id"): "une affaire — la mémoire de la copropriété, le carnet d'entretien",
    ("ticket_evolution", "auteur_id"): "le fil d'une affaire",
    ("message_ticket", "auteur_id"): "un message dans une affaire",
    ("evenement", "auteur_id"): "un évènement (table ancienne, migrée en 0212)",
    ("evenement_evolution", "auteur_id"): "le fil d'un évènement",
    ("document", "publie_par_id"): "un document de la copropriété",
    ("diagnostic_rapport", "publie_par_id"): "un rapport de diagnostic",
    ("regle_residence", "cree_par_id"): "une règle de la résidence",
    ("annonce_hall", "auteur_id"): "une annonce affichée dans le hall",
    ("sondage", "auteur_id"): "une consultation de la copropriété",
    ("vote_sondage", "user_id"): "un vote — sans lui, le résultat d'un sondage clos changerait",
    ("commentaire_sondage", "auteur_id"): "une réplique dans un échange où d'autres ont répondu",
    ("idee", "auteur_id"): "une idée, que d'autres ont soutenue",
    ("question_reglement", "auteur_id"): (
        "une question au règlement — sa réponse relue a pu nourrir la FAQ, et la question "
        "évite au conseil de repayer la même"
    ),
    ("vote_idee", "user_id"): "un soutien — sans lui, le compte d'une idée changerait",
    ("reponse_communaute", "auteur_id"): "une réplique dans un échange où d'autres ont répondu",
    ("notation_prestataire", "auteur_id"): "l'évaluation collective d'un prestataire",
    (
        "delegation",
        "cree_par_id",
    ): "qui a créé une délégation — elle appartient aux deux personnes liées",
}

#: Ce qui PART avec le compte : la référence est obligatoire, la purge supprime
#: la ligne. Une table neuve qui référence un compte se range ICI ou ci-dessus —
#: 🔒 `test_references_au_compte_declarees.py` refuse une référence obligatoire
#: que personne n'a classée : c'est ainsi que les affaires partaient sans que
#: personne l'ait décidé.
CONTENUS_PERSONNELS: dict[tuple[str, str], str] = {
    ("user_lot", "user_id"): "le lien de la personne à ses lots",
    ("refresh_token", "user_id"): "une session",
    ("password_reset_token", "user_id"): "un lien de mot de passe oublié",
    ("email_verification_token", "user_id"): "un lien de vérification d'adresse",
    ("notification", "destinataire_id"): "une notification adressée à la personne",
    ("commande_acces", "user_id"): "une demande de badge de la personne",
    ("demande_modification_profil", "utilisateur_id"): "une demande sur son propre profil",
    ("delegation", "mandant_id"): "une délégation donnée par la personne",
    ("delegation", "aidant_id"): "une délégation reçue par la personne",
    ("mandat", "bailleur_id"): "un mandat de gestion de la personne",
    ("mandat", "mandataire_id"): "un mandat confié à la personne",
    ("location_bail", "bailleur_id"): "le bail d'un lot de la personne (étape 10)",
    ("petite_annonce", "auteur_id"): "une offre personnelle, avec ses moyens de contact",
    ("signalement", "signale_par_id"): "une démarche personnelle ; la modération garde sa décision",
}


def supprimer_compte(session: Session, user_id: int) -> dict[str, int]:
    """Efface le compte `user_id` et ce qui en dépend. Rend le compte par table.

    ⚠️ Ne fait **pas** de `commit` et ne journalise rien (voir l'en-tête).
    """
    # 0. Télémétrie (RGPD art. 17) — évènements, présence et dernière visite (#1629)
    effacer_telemetrie(session, user_id)

    # 1. Tokens d'authentification
    for t in session.exec(select(RefreshToken).where(RefreshToken.user_id == user_id)).all():
        session.delete(t)
    for t in session.exec(
        select(PasswordResetToken).where(PasswordResetToken.user_id == user_id)
    ).all():
        session.delete(t)

    # 2. UserLot + nettoyage utilisateurs_json dans LotImport + reset statut
    user_lots = session.exec(select(UserLot).where(UserLot.user_id == user_id)).all()
    lot_ids = {ul.lot_id for ul in user_lots}
    for ul in user_lots:
        session.delete(ul)
    if lot_ids:
        for imp in session.exec(select(LotImport).where(LotImport.lot_id.in_(lot_ids))).all():  # type: ignore
            users = json.loads(imp.utilisateurs_json or "[]")
            nouveau = [e for e in users if e.get("user_id") != user_id]
            if len(nouveau) != len(users):
                imp.utilisateurs_json = json.dumps(nouveau, ensure_ascii=False)
                if not nouveau and imp.statut != StatutLotImport.ignore:
                    imp.statut = (
                        StatutLotImport.lot_lie if imp.lot_id else StatutLotImport.en_attente
                    )
                    imp.resolu_le = None
                session.add(imp)

    # 3. Commandes d'accès
    for c in session.exec(select(CommandeAcces).where(CommandeAcces.user_id == user_id)).all():
        session.delete(c)

    # 4. Notifications
    for n in session.exec(
        select(Notification).where(Notification.destinataire_id == user_id)
    ).all():
        session.delete(n)

    #  5. Les votes RESTENT, sans nom (#1821) : les supprimer changeait le
    #  résultat d'un sondage clos. La purge délie leur `user_id`, facultatif.

    # 6. Demandes modification profil
    for d in session.exec(
        select(DemandeModificationProfil).where(DemandeModificationProfil.utilisateur_id == user_id)
    ).all():
        session.delete(d)
    for d in session.exec(
        select(DemandeModificationProfil).where(DemandeModificationProfil.traite_par_id == user_id)
    ).all():
        d.traite_par_id = None
        session.add(d)

    # 7. Mandats (bailleur ou mandataire)
    for m in session.exec(
        select(Mandat).where(or_(Mandat.bailleur_id == user_id, Mandat.mandataire_id == user_id))
    ).all():
        session.delete(m)

    #  8. Les badges RESTENT sur leur lot (arbitrage du 23/09/2026, #1194) : la
    #  purge délie `user_id`, désormais facultatif. Ils étaient supprimés, et
    #  avec eux la trace d'objets physiques toujours en circulation.
    #  9. Les lignes d'import perdent ce compte ; une ligne résolue le reste —
    #  son badge existe toujours.
    for type_acces in TYPES_ACCES.values():
        modele = type_acces.modele_import
        for ligne in session.exec(
            select(modele).where(
                or_(
                    modele.user_proprietaire_id == user_id,
                    modele.user_locataire_id == user_id,
                )
            )
        ).all():
            if ligne.user_proprietaire_id == user_id:
                ligne.user_proprietaire_id = None
            if ligne.user_locataire_id == user_id:
                ligne.user_locataire_id = None
            if ligne.statut == StatutImport.proprietaire_lie and not ligne.user_proprietaire_id:
                ligne.statut = StatutImport.en_attente
            session.add(ligne)

    # 10. LocationBail : locataire → nullifier ; bailleur → supprimer bail + objets remis
    for bail in session.exec(
        select(LocationBail).where(LocationBail.locataire_id == user_id)
    ).all():
        bail.locataire_id = None
        session.add(bail)
    for bail in session.exec(select(LocationBail).where(LocationBail.bailleur_id == user_id)).all():
        for obj in session.exec(select(RemiseObjet).where(RemiseObjet.bail_id == bail.id)).all():
            session.delete(obj)
        session.delete(bail)

    # 11. HistoriqueSauvegarde — nullifier la référence optionnelle
    for h in session.exec(
        select(HistoriqueSauvegarde).where(HistoriqueSauvegarde.declenchee_par_user_id == user_id)
    ).all():
        h.declenchee_par_user_id = None
        session.add(h)

    #  🔴 Le reste — et « le reste » est la majorité (#546, 28/08/2026).
    #
    #  Le modèle compte plus de cinquante références à `utilisateur`, dont une
    #  majorité obligatoires. Vingt-six tables n'étaient nettoyées nulle part —
    #  publications, tickets, messages, idées, sondages, signalements… Faute de
    #  clés vérifiées, la suppression réussissait quand même, et laissait en base
    #  des lignes pointant vers un compte disparu.
    #
    #  ⚠️ Une liste tenue à la main ne peut pas suivre : c'est bien ce qui s'est
    #  passé. `purger` LIT les métadonnées au lieu de les réciter.
    session.flush()
    return purger(session, "utilisateur", user_id)


__all__ = ["supprimer_compte"]
