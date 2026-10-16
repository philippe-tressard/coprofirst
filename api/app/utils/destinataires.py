"""Résolution des destinataires — source unique.

Factorise la logique « membres du CS concernés par un périmètre » utilisée par
la démarche nouvel arrivant (`admin.py`) et par les annonces de hall
(`annonces_hall.py`). Ne pas dupliquer ces règles dans les routers.

Règles :
  - Seuls les membres du CS **liés à un compte utilisateur actif avec e-mail**
    sont notifiables (`MembreCS.user_id` renseigné).
  - Le **gestionnaire du site** est toujours ajouté, quel que soit le périmètre.
  - Périmètre à portée globale (ou dont un ancêtre l'est) → tout le CS.
"""

from __future__ import annotations

from typing import Optional

from sqlalchemy import func
from sqlmodel import Session, or_, select

from app.auth.adresse_compte import normaliser_adresse
from app.models.core import (
    ConfigSite,
    GenreCivilite,
    MembreCS,
    MembreSyndic,
    RoleUtilisateur,
    Utilisateur,
)
from app.utils.noms import nom_affiche
from app.utils.perimetres import a_portee_globale, batiments_cibles
from app.utils.preferences_mail import Designe, Ecarte


def site_manager_user_id(session: Session) -> Optional[int]:
    """Id du gestionnaire du site (ConfigSite), ou None — un ADMINISTRATEUR, ou personne.

    Ce qu'il reçoit renvoie à `/admin` : valider un compte, relire un import,
    une alerte système. Le front réserve `/admin` aux administrateurs, et un
    gestionnaire sans ce rôle y était renvoyé au tableau de bord (#1505,
    01/10/2026). Un gestionnaire qui perd le rôle n'est donc plus lu : l'envoi
    retombe sur l'« E-mail administrateur » (`site_email`).
    """
    cfg = session.get(ConfigSite, "site_manager_user_id")
    valeur = ((cfg.valeur if cfg else "") or "").strip()
    if not valeur.isdigit():
        return None
    return int(valeur) if peut_gerer_le_site(session.get(Utilisateur, int(valeur))) else None


def peut_gerer_le_site(user: Optional[Utilisateur]) -> bool:
    """Le gestionnaire du site est un administrateur — la règle, lue ici et à l'écriture."""
    return user is not None and user.has_role(RoleUtilisateur.admin)


def batiments_du_perimetre(perimetres: list[str]) -> Optional[set[int]]:
    """`['bat:1','bat:3']` → `{1, 3}` ; None si le périmètre concerne tout le monde.

    Un nœud à portée globale — ou dont un ancêtre l'est — concerne l'ensemble des
    résidents, et l'on renvoie alors None (« tout le conseil syndical »). Sinon on
    remonte l'arbre pour chaque code afin de trouver le bâtiment visé : c'est ce qui
    permet de cibler « Bât. 2 › Hall d'entrée » sans redire que le hall est dans le
    bâtiment 2.

    La liste des périmètres transverses n'est plus écrite ici. Elle vivait en trois
    exemplaires et c'est maintenant `perimetre.portee_globale`.
    """
    if not perimetres:
        return None
    if a_portee_globale(perimetres):
        return None
    return batiments_cibles(perimetres) or None


def membres_cs_notifiables(
    session: Session, batiment_ids: Optional[set[int]] = None
) -> list[tuple[int, str]]:
    """Destinataires CS `[(user_id, email)]`, dédoublonnés.

    `batiment_ids` à None → tous les membres du CS. Sinon, membres rattachés à
    l'un des bâtiments, plus le gestionnaire du site.
    """
    return _cs_du_perimetre(session, batiment_ids)[0]


def cs_du_perimetre_ecartes(
    session: Session, batiment_ids: Optional[set[int]] = None
) -> list[Ecarte]:
    """Les membres du CS de ce périmètre que le courriel n'atteindra pas — l'aperçu les nomme."""
    return _cs_du_perimetre(session, batiment_ids)[1]


def _cs_du_perimetre(
    session: Session, batiment_ids: Optional[set[int]]
) -> tuple[list[tuple[int, str]], list[Ecarte]]:
    """(joignables, écartés) — UNE sélection, que l'envoi et l'aperçu se partagent (#2006)."""
    manager_id = site_manager_user_id(session)

    stmt = select(MembreCS).order_by(MembreCS.ordre, MembreCS.id)
    if batiment_ids:
        filtres = MembreCS.batiment_id.in_(batiment_ids)  # type: ignore[union-attr]
        if manager_id is not None:
            filtres = filtres | (MembreCS.user_id == manager_id)
        stmt = stmt.where(filtres)
    membres = session.exec(stmt).all()

    destinataires: list[tuple[int, str]] = []
    ecartes: list[Ecarte] = []
    vus: set[str] = set()
    for membre in membres:
        user = session.get(Utilisateur, membre.user_id) if membre.user_id else None
        motif = motif_injoignable(user)
        if motif:
            ecartes.append(Ecarte(nom_affiche(membre.prenom, membre.nom), motif))
            continue
        email = user.email.strip()
        if email.lower() in vus:
            continue
        vus.add(email.lower())
        destinataires.append((user.id, email))
    return destinataires, ecartes


# ── Qui le courriel n'atteindra pas — et pourquoi (#2006) ─────────────────────
#
# Les sélections du conseil écartaient en silence un membre sans compte, au compte
# désactivé ou sans adresse. L'aperçu de la Diffusion le dit désormais, avec le
# motif : la même lecture que la sélection, jamais une seconde.

MOTIF_SANS_COMPTE = "n'a pas de compte sur le site"
MOTIF_DESACTIVE = "compte désactivé"
MOTIF_SANS_ADRESSE = "pas d'adresse renseignée"


def motif_injoignable(user: Optional[Utilisateur]) -> Optional[str]:
    """Pourquoi ce compte ne peut pas recevoir de courriel — ou None s'il le peut."""
    if user is None:
        return MOTIF_SANS_COMPTE
    if not user.actif:
        return MOTIF_DESACTIVE
    if not (user.email or "").strip():
        return MOTIF_SANS_ADRESSE
    return None


# ── Interlocuteurs chez le syndic ────────────────────────────────────────────

#: Fonctions auxquelles un e-mail de la copropriété s'adresse, en minuscules et
#: sans accents. Le cabinet fonctionne en binôme — l'assistante de gestion supplée
#: la gestionnaire en son absence — donc **les deux** figurent dans la formule
#: d'appel, et l'ordre de l'annuaire les classe.
#:
#: La comptable en est volontairement exclue : elle traite les appels de fonds,
#: pas les signalements techniques. Écrire les noms en dur serait le vrai défaut :
#: le cabinet change de personnel, l'annuaire est la seule source qui suit.
FONCTIONS_INTERLOCUTRICES = ("gestionnaire", "assistant")


def _sans_accent_minuscule(texte: str) -> str:
    """Comparaison tolérante d'un intitulé saisi à la main.

    Les intitulés sont saisis au clavier : « Gestionnaire de Copropriétés »,
    « Assistante de gestion », « Comptable de copropriété » — majuscules, accents
    et genre y varient d'une ligne à l'autre. Comparer sur la forme
    brute reviendrait à ne reconnaître que l'orthographe du jour de la saisie.
    """
    from app.utils.import_xlsx import normaliser

    #  `normaliser` est la fonction de comparaison de noms déjà partagée par les
    #  trois imports et l'appariement des accès. En réécrire une seconde ici,
    #  c'est exactement la duplication que le socle interdit — son emplacement
    #  dans `import_xlsx` est discutable, sa réutilisation ne l'est pas.
    return normaliser(texte).lower()


def interlocuteurs_syndic(session: Session) -> list[MembreSyndic]:
    """Les personnes du syndic à qui l'on s'adresse, dans l'ordre de l'annuaire.

    Sélection par **fonction**, jamais par nom. Repli sur le membre marqué
    `est_principal` si aucune fonction ne correspond — sans quoi un intitulé
    inattendu produirait une formule d'appel vide, et un e-mail qui commence par
    une virgule ne se remarque qu'une fois parti.
    """
    membres = session.exec(select(MembreSyndic).order_by(MembreSyndic.ordre, MembreSyndic.id)).all()
    retenus = [
        m
        for m in membres
        if any(f in _sans_accent_minuscule(m.fonction or "") for f in FONCTIONS_INTERLOCUTRICES)
    ]
    if retenus:
        return retenus
    return [m for m in membres if m.est_principal]


def _nom_presentable(nom: str) -> str:
    """« DUPONT » → « Dupont », « durand » → « Durand », « de La Tour » inchangé.

    Une casse uniforme trahit une saisie machinale, pas une orthographe voulue :
    on la corrige. Une casse mixte, elle, porte peut-être une particule ou un nom
    composé — on n'y touche pas.
    """
    nom = (nom or "").strip()
    return nom.title() if (nom.isupper() or nom.islower()) else nom


def formule_appel(membres: list[MembreSyndic]) -> str:
    """« Madame Dupont, Madame Durand » — civilité et NOM, sans prénom.

    Le prénom est volontairement absent : c'est une correspondance entre un
    conseil syndical et un cabinet de gestion, pas un échange personnel.
    """
    civilites = {GenreCivilite.mr: "Monsieur"}
    return ", ".join(
        f"{civilites.get(m.genre, 'Madame')} {_nom_presentable(m.nom)}"
        for m in membres
        if (m.nom or "").strip()
    )


# ── Syndic + conseil syndical : QUI reçoit un e-mail interne ──────────────────
#
# 🔴 Cette règle existait en QUATRE exemplaires, tous identiques à la variable
# près : tickets, calendrier, publications, sondages. Et celui des tickets
# portait, en toutes lettres, *« elle est le seul endroit où cette règle
# s'écrit »* — une affirmation d'unicité au milieu de quatre copies.
#
# ⚠️ C'est la forme la plus coûteuse de la duplication : les trois autres
# n'avaient AUCUN commentaire, donc rien ne signalait qu'elles existaient, et le
# seul fichier qui parlait du sujet disait que le problème n'existait pas.
# Corriger la règle chez l'un — ajouter un destinataire, changer la
# déduplication — laissait les trois autres en arrière sans qu'un contrôle,
# ni une relecture, ne puisse le voir.
#
# 🔒 `api/tests/test_destinataires_source_unique.py` refuse une cinquième.


def syndic_principal(session: Session) -> Optional[MembreSyndic]:
    """Le gestionnaire syndic principal, ou None s'il n'est pas configuré."""
    return session.exec(
        select(MembreSyndic).where(MembreSyndic.est_principal == True)  # noqa: E712
    ).first()


def est_adresse_syndic(session: Session, adresse: str) -> bool:
    """Cette adresse est-elle celle d'un membre du cabinet syndic ?

    Le syndic se reconnaît à son ADRESSE dans la fiche du cabinet, pas à un rôle :
    `RoleUtilisateur` n'en a pas, et le gestionnaire n'a souvent pas de compte.
    """
    adresse = normaliser_adresse(adresse)
    if not adresse:
        return False
    return bool(
        session.exec(select(MembreSyndic).where(func.lower(MembreSyndic.email) == adresse)).first()
    )


def membres_cs_avec_email(session: Session) -> list[tuple[int, str]]:
    """(id, e-mail) des membres du CS joignables par courriel.

    ⚠️ Le critère est le **rôle** `conseil_syndical`, sans notion de périmètre —
    à distinguer de `membres_cs_notifiables()` ci-dessus, qui part de la table
    `MembreCS` et filtre par bâtiment. Les deux coexistent volontairement, et
    `CLAUDE.md` dit laquelle sert à quoi : celle-ci vise le rôle (publications,
    sondages, calendrier, tickets), l'autre vise le périmètre (nouvel arrivant,
    annonces de hall).
    """
    return [(u.id, u.email) for u in _cs_par_role(session) if motif_injoignable(u) is None]


def ecartes_syndic_cs(session: Session, *, syndic: bool, cs: bool) -> list[Ecarte]:
    """Ceux que `destinataires_syndic_cs` n'atteindra pas, avec le motif — pour l'aperçu."""
    ecartes = ecartes_du_syndic(session) if syndic else []
    if cs:
        ecartes += [
            Ecarte(nom_affiche(u.prenom, u.nom), motif)
            for u in _cs_par_role(session)
            if (motif := motif_injoignable(u))
        ]
    return ecartes


def ecartes_du_syndic(session: Session) -> list[Ecarte]:
    """Le syndic coché, mais sans gestionnaire principal ou sans adresse."""
    principal = syndic_principal(session)
    if principal is None:
        return [Ecarte("Syndic", "aucun gestionnaire principal désigné")]
    if not (principal.email or "").strip():
        return [
            Ecarte(f"{nom_affiche(principal.prenom, principal.nom)} (syndic)", MOTIF_SANS_ADRESSE)
        ]
    return []


def _cs_par_role(session: Session) -> list[Utilisateur]:
    """Les comptes au rôle `conseil_syndical`, joignables ou non."""
    return list(
        session.exec(
            select(Utilisateur)
            .where(Utilisateur.roles_json.contains("conseil_syndical"))
            .order_by(Utilisateur.id)
        ).all()
    )


def membres_cs_ou_admin(session: Session) -> list[Utilisateur]:
    """Les `Utilisateur` à NOTIFIER dans l'application — conseil syndical **ou** admin.

    🔴 C'est la CINQUIÈME règle de destinataires, et la première qui n'était nulle
    part. `CLAUDE.md` écrivait, à propos du contrôle de source unique : *« il
    laisse passer les notifications in-app, qui visent CS ou admin et rendent des
    `Utilisateur` — autre décision, autre destinataire »*. C'est vrai, et c'était
    la bonne raison de ne pas les confondre avec `membres_cs_avec_email`.

    Sauf que cette autre décision était écrite **trois fois** : `tickets/crud.py`,
    `tickets/messages.py`, `signalements.py`. Et elle avait déjà commencé à
    diverger — la copie des messages exigeait en plus `email IS NOT NULL`, ce qui
    privait de notification **in-app** un membre du CS sans adresse. Une
    notification qui s'affiche à l'écran n'a pas besoin d'une adresse : la
    condition venait d'un copier-coller depuis un envoi de courriel.

    ⚠️ La différence avec `membres_cs_avec_email` est intacte, et elle compte :
    celle-ci vise l'écran (CS **ou** admin, avec ou sans adresse), l'autre la
    boîte aux lettres (CS seul, adresse obligatoire). Deux publics, deux
    fonctions, un seul endroit chacune.
    """
    return list(
        session.exec(
            select(Utilisateur).where(
                Utilisateur.actif == True,  # noqa: E712
                or_(
                    Utilisateur.roles_json.contains("conseil_syndical"),
                    Utilisateur.roles_json.contains("admin"),
                ),
            )
        ).all()
    )


def gestionnaire_puis_cs(session: Session) -> list[tuple[int | None, str]]:
    """(user_id, e-mail) du gestionnaire du site puis des membres du CS, dédoublonnés.

    La synthèse d'une affaire close à valider (#1643) — arbitré « le temps que la
    fonction soit stabilisée » : le gestionnaire la suit, le conseil la valide.
    Le CS par le **rôle** (`membres_cs_avec_email`), jamais par le périmètre ; le
    gestionnaire passe en premier et gagne le doublon, comme le syndic dans
    `syndic_puis` — un administrateur qui siège au conseil ne reçoit qu'un message.
    """
    destinataires: list[tuple[int | None, str]] = []
    vus: set[str] = set()
    gestionnaire_id = site_manager_user_id(session)
    gestionnaire = session.get(Utilisateur, gestionnaire_id) if gestionnaire_id else None
    candidats = [(gestionnaire.id, gestionnaire.email)] if gestionnaire else []
    for uid, email in [*candidats, *membres_cs_avec_email(session)]:
        if email and normaliser_adresse(email) not in vus:
            destinataires.append((uid, email))
            vus.add(normaliser_adresse(email))
    return destinataires


def destinataires_syndic_cs(
    session: Session,
    *,
    syndic: bool,
    cs: bool,
    deja_vus: Optional[set[str]] = None,
) -> list[tuple[int | None, str]]:
    """(user_id, e-mail) du syndic principal puis des membres du CS, dédoublonnés.

    Le syndic passe en premier et **gagne le doublon** : c'est lui le destinataire
    principal, un membre du CS qui serait aussi le syndic ne doit pas recevoir le
    message deux fois.

    `deja_vus` permet à une relance d'exclure du CC les adresses déjà placées en
    destinataire principal, sans réécrire la déduplication.
    """
    return syndic_puis(
        session,
        syndic=syndic,
        membres=membres_cs_avec_email(session) if cs else [],
        deja_vus=deja_vus,
    )


def syndic_puis(
    session: Session,
    *,
    syndic: bool,
    membres: list[tuple[int | None, str]],
    deja_vus: Optional[set[str]] = None,
) -> list[tuple[int | None, str]]:
    """Le syndic principal, puis une liste de membres DÉJÀ choisie, dédoublonnés.

    🔴 Ce site choisit le conseil syndical de **deux** façons, et les confondre
    envoie le bon message aux mauvaises personnes :

    - par le **rôle** — `membres_cs_avec_email` : publications, sondages,
      calendrier, tickets ;
    - par le **périmètre** — `membres_cs_notifiables` : nouvel arrivant, annonces
      de hall, où seul le CS du bâtiment concerné est visé.

    La règle de **déduplication**, elle, est la même dans les deux cas — le
    syndic passe en premier et gagne le doublon. Elle vit donc ici, et le choix
    du CS reste à l'appelant : c'est ce qui a permis à l'annonce de hall de
    recevoir le canal « syndic » (#480) sans écrire une cinquième copie du bloc.

    🔴 Chacun est rendu **désigné** (`Designe`, #2006) : la case de la Diffusion
    l'a choisi, et sa préférence de courriel ne l'écarte pas.

    ⚠️ Le bloc a déjà existé en **quatre exemplaires identiques** jusqu'au
    31/08/2026 — et celui des tickets affirmait, en toutes lettres, être « le
    seul endroit où cette règle s'écrit ».
    """
    destinataires: list[tuple[int | None, str]] = []
    vus: set[str] = set(deja_vus or ())

    if syndic:
        principal = syndic_principal(session)
        if principal and principal.email:
            destinataires.append(Designe(principal.user_id, principal.email))
            vus.add(principal.email.lower())

    for uid, email in membres:
        if email and email.lower() not in vus:
            destinataires.append(Designe(uid, email))
            vus.add(email.lower())

    return destinataires
