"""
Service d'auto-match déclenché à l'activation d'un utilisateur.

Appelé depuis :
  - admin.py  : traiter_compte (action="valider")
  - auth.py   : register (si inscription directement active — futur)

Pour chaque nouveau user, passe en revue les 3 files d'import staging
(lots, TC, vigik) et tente de lier automatiquement les lignes en attente
dont le nom correspond à ce user.
"""

from __future__ import annotations

import json

from sqlmodel import Session, select
from app.auth.adresse_compte import normaliser_adresse
from app.utils.liens import adresse_du_site
from app.utils.liens import nom_site
from app.utils.noms import contexte_personne
from app.models.core import StatutImport
from app.utils.types_acces import TELECOMMANDE, TypeAcces, VIGIK
from app.utils.valeurs import valeur
from app.utils.rapprochement_noms import (
    _cle_de_nom,
    _matches_user,
    _split_name_candidates,
    _user_keys,
)


def _statut_to_type_lien(statut) -> str:
    """Mappe le statut d'un utilisateur vers le type_lien dans LotImport."""
    _MAP = {
        "copropriétaire_résident": "propriétaire",
        "copropriétaire_bailleur": "bailleur",
        "mandataire": "mandataire",
        "locataire": "locataire",
    }
    val = str(valeur(statut))
    return _MAP.get(val, "propriétaire")


def rattacher_lot_unique(imp, session: Session) -> bool:
    """UN seul lot actif chez le propriétaire → l'import lui est rattaché.

    🔴 Écrite quatre fois, avec deux comportements. Elle décide qui verra ce lot.
    Le pourquoi : `tests/test_rattachement_lot_unique.py`.
    """
    from app.models.core import UserLot

    if not imp.user_proprietaire_id or imp.lot_id:
        return False
    lots = session.exec(
        select(UserLot).where(
            UserLot.user_id == imp.user_proprietaire_id,
            UserLot.actif == True,  # noqa: E712
        )
    ).all()
    if len(lots) != 1:
        return False
    imp.lot_id = lots[0].lot_id
    return True


def count_lots_for_user(nom: str, prenom: str, session: Session) -> int:
    """Dry-run : compte les LotImport dont le nom_coproprietaire correspond à ce user.
    Inclut tous les statuts pour donner un aperçu global (même 'resolu')."""
    from app.models.core import LotImport, StatutLotImport

    keys = _user_keys(nom, prenom)
    imports = session.exec(
        select(LotImport).where(
            LotImport.statut.in_(
                [
                    StatutLotImport.en_attente,
                    StatutLotImport.utilisateur_lie,
                    StatutLotImport.lot_lie,
                    StatutLotImport.resolu,
                ]
            )
        )
    ).all()
    count = 0
    for imp in imports:
        if not imp.nom_coproprietaire:
            continue
        for nom_brut in _split_name_candidates(imp.nom_coproprietaire):
            if _matches_user(nom_brut.strip(), keys):
                count += 1
                break
    return count


# ── Auto-match TC ─────────────────────────────────────────────────────────────


def _auto_match_acces(user, session: Session, type_acces: TypeAcces) -> int:
    """Apparie les imports de CE type au nouvel arrivant, et résout ce qui peut l'être.

    ## 🔴 Une fonction pour les deux types (18/09/2026, #779)

    C'était `_auto_match_tc` et `_auto_match_vigik` : cent vingt lignes pour deux
    fois la même chose, à trois mots près. Et elles avaient DÉJÀ divergé — le
    vigik créé ici ne recevait pas `chez_locataire`, quand la télécommande
    l'avait. C'est le défaut exact que #847 avait corrigé côté écran, survivant
    côté automatique parce que le code était ailleurs.

    Conséquence de cette divergence, avant correction : un vigik résolu au
    bénéfice d'un locataire arrivait marqué « chez le propriétaire », et
    `routers/bailleur/acces.py` le proposait au transfert vers le locataire
    suivant alors qu'il était déjà dans la poche du locataire en place.

    Depuis #1194, le rattachement lui-même est `utils/resolution_acces.rattacher`
    — celui de l'écran : il exige le LOT, plus un compte. Aucune attribution
    n'est écrite, les porteurs se déduisent du lot.
    """
    from app.utils.lot_des_imports import trouveur_de_lot
    from app.utils.resolution_acces import peut_se_rattacher, rattacher

    etape_lot = trouveur_de_lot(type_acces, session)
    modele_import = type_acces.modele_import
    cles = _user_keys(user.nom, user.prenom)
    imports = session.exec(
        select(modele_import).where(
            modele_import.statut.in_([StatutImport.en_attente, StatutImport.proprietaire_lie])
        )
    ).all()

    apparies = 0
    for imp in imports:
        change = False
        for champ_nom, champ_lien in (
            ("nom_proprietaire", "user_proprietaire_id"),
            ("nom_locataire", "user_locataire_id"),
        ):
            if getattr(imp, champ_lien) or not getattr(imp, champ_nom):
                continue
            if _matches_user(getattr(imp, champ_nom), cles):
                setattr(imp, champ_lien, user.id)
                change = True

        if change:
            etape_lot(imp)

        if not change:
            continue

        #  Règle du lot unique : `rattacher_lot_unique` (écrite 4× avant #829).
        rattacher_lot_unique(imp, session)
        if imp.user_proprietaire_id:
            imp.statut = StatutImport.proprietaire_lie

        if peut_se_rattacher(type_acces, imp):
            rattacher(type_acces, imp, session)
        session.add(imp)
        apparies += 1
    return apparies


#: Les deux appels nommés, pour les appelants historiques. Ils ne portent aucune
#: logique : ils NOMMENT le type, et c'est tout ce qui les distingue.
def _auto_match_tc(user, session: Session) -> int:
    return _auto_match_acces(user, session, TELECOMMANDE)


def _auto_match_vigik(user, session: Session) -> int:
    return _auto_match_acces(user, session, VIGIK)


# ── Auto-match Lots ───────────────────────────────────────────────────────────


def _auto_match_lots(user, session: Session) -> int:
    from app.models.core import LotImport, StatutLotImport, UserLot, TypeLien

    def _tl(s: str) -> TypeLien:
        try:
            return TypeLien(s)
        except ValueError:
            return TypeLien.propriétaire

    keys = _user_keys(user.nom, user.prenom)

    # Passe 1 : imports en attente / utilisateur_lie / lot_lie → ajouter à utilisateurs_json
    imports = session.exec(
        select(LotImport).where(
            LotImport.statut.in_(
                [
                    StatutLotImport.en_attente,
                    StatutLotImport.utilisateur_lie,
                    StatutLotImport.lot_lie,  # lot connu mais user pas encore matché
                ]
            )
        )
    ).all()

    matched = 0
    for imp in imports:
        if not imp.nom_coproprietaire:
            continue
        # Décomposer les noms potentiellement multiples (couples, séparateurs divers).
        noms = _split_name_candidates(imp.nom_coproprietaire)
        current_users: list[dict] = json.loads(imp.utilisateurs_json or "[]")
        existing_ids = {e["user_id"] for e in current_users}
        added = False
        type_lien = _statut_to_type_lien(user.statut)
        for nom in noms:
            if user.id in existing_ids:
                continue
            if _matches_user(nom, keys):
                current_users.append({"user_id": user.id, "type_lien": type_lien})
                existing_ids.add(user.id)
                added = True
        if added:
            imp.utilisateurs_json = json.dumps(current_users, ensure_ascii=False)
            if imp.lot_id:
                imp.statut = StatutLotImport.lot_lie
            else:
                imp.statut = StatutLotImport.utilisateur_lie
            session.add(imp)
            matched += 1

    # Passe 2 : imports déjà résolu (lot_id connu) où ce user n'est pas encore lié.
    # Cas typique : import résolu sans occupant, user inscrit après coup.
    # → ajouter à utilisateurs_json ET créer UserLot directement.
    imports_resolu = session.exec(
        select(LotImport).where(
            LotImport.statut == StatutLotImport.resolu,
            LotImport.lot_id.is_not(None),  # type: ignore
        )
    ).all()

    from app.utils.resolution_lots import TYPES_COPROPRIETAIRES

    type_lien = _statut_to_type_lien(user.statut)

    for imp in imports_resolu:
        if not imp.nom_coproprietaire or type_lien not in TYPES_COPROPRIETAIRES:
            continue
        noms = _split_name_candidates(imp.nom_coproprietaire)
        if not any(_matches_user(nom, keys) for nom in noms):
            continue
        # Vérifier d'abord si le UserLot existe réellement en base
        # (utilisateurs_json peut contenir l'user_id sans UserLot correspondant
        #  si supprimer_user_lot a été appelé avant le fix du nettoyage json).
        existing_ul = session.exec(
            select(UserLot).where(UserLot.user_id == user.id, UserLot.lot_id == imp.lot_id)
        ).first()
        if existing_ul:
            continue  # déjà lié correctement
        # Créer le UserLot manquant
        session.add(
            UserLot(user_id=user.id, lot_id=imp.lot_id, type_lien=_tl(type_lien), actif=True)
        )
        # Synchroniser utilisateurs_json si l'entry est absente
        current_users = json.loads(imp.utilisateurs_json or "[]")
        existing_ids = {e["user_id"] for e in current_users}
        if user.id not in existing_ids:
            current_users.append({"user_id": user.id, "type_lien": type_lien})
            imp.utilisateurs_json = json.dumps(current_users, ensure_ascii=False)
            session.add(imp)
        matched += 1

    return matched


def _is_coproprietaire(user) -> bool:
    """True si ce user est copropriétaire/bailleur/mandataire (doit être résolu automatiquement)."""
    TYPES = {"copropriétaire_résident", "copropriétaire_bailleur", "mandataire"}
    val = str(valeur(user.statut))
    return val in TYPES


# ── Auto-résolution lots pour un utilisateur ─────────────────────────────────

#  🔴 `_auto_resoudre_lots_pour_utilisateur` vit dans `utils/resolution_lots`
#  depuis #829 : le même geste était écrit ICI et dans `routers/lots.py`, avec
#  TROIS règles divergentes — dont le garde-fou anti-pollution, que seule cette
#  copie-ci portait. Rapprocher des NOMS et résoudre un IMPORT sont deux
#  responsabilités ; ce module ne garde que la première.


# ── Auto-liaison annuaire CS / Syndic ──────────────────────────────────────


def _auto_link_annuaire(user, session: Session) -> dict:
    """Lie ce user aux membres CS et Syndic dont le NOM correspond (NFD, insensible casse).
    Ne committe pas — l'appelant doit faire session.commit()."""
    from app.models.core import MembreCS, MembreSyndic

    user_nom_norm = _cle_de_nom(user.nom)
    if not user_nom_norm:
        return {"cs": 0, "syndic": 0}

    cs_linked = 0
    for membre in session.exec(select(MembreCS)).all():
        if membre.user_id:
            continue
        if membre.nom and _cle_de_nom(membre.nom) == user_nom_norm:
            membre.user_id = user.id
            session.add(membre)
            cs_linked += 1

    syndic_linked = 0
    for membre in session.exec(select(MembreSyndic)).all():
        if membre.user_id:
            continue
        if membre.nom and _cle_de_nom(membre.nom) == user_nom_norm:
            membre.user_id = user.id
            session.add(membre)
            syndic_linked += 1

    return {"cs": cs_linked, "syndic": syndic_linked}


# ── Point d'entrée principal ──────────────────────────────────────────────────


def auto_match_pour_utilisateur(user, session: Session) -> dict:
    """
    Lance l'auto-match sur les 3 systèmes d'import pour un utilisateur donné,
    puis résout automatiquement les LotImport copropriétaires reconnus.

    Ordre critique :
      1. lots      → lie le user aux LotImport (crée utilisateurs_json)
      2. resoudre  → crée les UserLot (lots résolus en DB)
      3. tc        → auto-link lot via UserLot (SEULEMENT si propriétaire a des lots)
      4. vigik     → auto-link lot via UserLot (SEULEMENT si propriétaire a des lots)
      5. baux      → lie le locataire aux baux créés par email (si locataire)
      6. bailleur, puis fichier des lots → rattache le locataire sans bail (#1136, #2267)

    RÈGLE CRITIQUE pour propriétaires/bailleures :
      - Si lots_resolus = 0 ET c'est un copropriétaire/bailleur/mandataire
      - ALORS tc et vigik ne seront pas traités (0 affectation)

    Ne committe pas — l'appelant doit faire session.commit().
    """
    from app.models.core import StatutUtilisateur

    lots = _auto_match_lots(user, session)
    session.flush()
    from app.utils.resolution_lots import resoudre_pour_utilisateur

    lots_resolus = resoudre_pour_utilisateur(user, session)
    session.flush()

    user_statut = str(valeur(user.statut))
    is_coproprietaire = user_statut in {
        StatutUtilisateur.copropriétaire_résident.value,
        StatutUtilisateur.copropriétaire_bailleur.value,
        StatutUtilisateur.mandataire.value,
    }

    # RÈGLE : Pour les propriétaires, TC/Vigik ne sont traités que si lots ont réussi
    if is_coproprietaire and lots_resolus == 0:
        tc = 0
        vigik = 0
    else:
        tc = _auto_match_tc(user, session)
        vigik = _auto_match_vigik(user, session)

    #  🔴 Le conjoint inscrit après la résolution n'a plus de chemin à lui
    #  (#1194) : `_propagate_acces_pour_utilisateur` recopiait les badges du
    #  ménage dans les tables d'attribution. Il les voit désormais par son lot,
    #  dès qu'il y est rattaché — par ce service ou par l'administration.

    baux = _auto_match_baux_locataire(user, session)
    #  Sans bail à son adresse, le nom de propriétaire déclaré rattache (#1136).
    from app.utils.rattachement_bailleur import rattacher_au_bailleur

    rattache = 0 if baux else rattacher_au_bailleur(user, session)
    #  Sans bailleur inscrit, le fichier des lots rattache d'office (#2267).
    from app.utils.rattachement_locataire import rattacher_d_office, remettre_badges_manquants

    lots_d_office = 0 if baux or rattache else rattacher_d_office(user, session)
    #  Un locataire déjà lié à la main reçoit les badges qui lui manquent.
    badges_remis = sum(remettre_badges_manquants(user, session).values())
    annuaire = _auto_link_annuaire(user, session)
    return {
        "lots": lots,
        "lots_resolus": lots_resolus,
        "tc": tc,
        "vigik": vigik,
        "baux": baux,
        "rattache": rattache,
        "lots_d_office": lots_d_office,
        "badges_remis": badges_remis,
        "annuaire_cs": annuaire["cs"],
        "annuaire_syndic": annuaire["syndic"],
        "total": lots
        + tc
        + vigik
        + baux
        + rattache
        + lots_d_office
        + annuaire["cs"]
        + annuaire["syndic"],
    }


# ── Auto-liaison bail par email (locataires) ─────────────────────────────────


def _auto_match_baux_locataire(user, session: Session) -> int:
    """Lie ce user comme locataire sur les baux créés avec son email.
    Ne committe pas — l'appelant doit faire session.commit()."""
    from app.models.core import LocationBail, StatutBail, StatutUtilisateur

    # Uniquement pour les locataires
    val = str(valeur(user.statut))
    if val != StatutUtilisateur.locataire.value:
        return 0

    if not user.email:
        return 0

    baux = session.exec(
        select(LocationBail).where(
            LocationBail.locataire_email == normaliser_adresse(user.email),
            LocationBail.locataire_id.is_(None),  # type: ignore
            LocationBail.statut != StatutBail.termine,
        )
    ).all()

    matched = 0
    for bail in baux:
        bail.locataire_id = user.id
        session.add(bail)
        matched += 1
    return matched


# ── Notification du gestionnaire du site ─────────────────────────────────────


def notifier_gestionnaire_appariement(
    user, resultat: dict, background_tasks, session: Session
) -> None:
    """Prévient le gestionnaire du site quand des accès ont été créés tout seuls.

    Pourquoi ce message existe (demandé le 03/08/2026) : l'appariement se fait
    sur le **nom de famille**, volontairement — un foyer partage ses accès, et le
    fichier du syndic ne nomme souvent qu'un occupant. La contrepartie est que
    deux foyers homonymes sont indiscernables, et que `_auto_match_tc` ne propose
    pas : il **crée** le badge et marque l'import « résolu ».

    La revue du CS reste le filet ; ce message la déclenche au lieu de l'attendre.

    Silencieux si rien n'a été créé : une notification à chaque inscription
    finirait ignorée, et un canal qu'on ignore est un canal absent
    (`standards/07-observabilite-et-alertes.md`).
    """
    tc = resultat.get("tc", 0)
    vigik = resultat.get("vigik", 0)
    if tc + vigik <= 0:
        return

    from app.utils.email import get_site_manager_notification_email, send_email

    destinataire, cfg = get_site_manager_notification_email(session)
    if not destinataire:
        return

    statut = str(valeur(user.statut))
    total = tc + vigik
    background_tasks.add_task(
        send_email,
        code="acces_apparies_auto",
        to=destinataire,
        context={
            "utilisateur": contexte_personne(user, email=user.email, statut=statut),
            "resultat": {
                "telecommandes": tc,
                "vigiks": vigik,
                "lots": resultat.get("lots_resolus", 0),
                "total_acces": total,
                # Accords calculés ici : un modèle Jinja n'a pas à porter la
                # grammaire française, et le faire à trois endroits divergerait.
                "pluriel": "s" if total > 1 else "",
                "pluriel_tc": "s" if tc > 1 else "",
                "pluriel_vigik": "s" if vigik > 1 else "",
            },
            "residence": {"nom": nom_site(cfg.get("site_nom"))},
            "app": {"url": adresse_du_site()},
        },
    )
