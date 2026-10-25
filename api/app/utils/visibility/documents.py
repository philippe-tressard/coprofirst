"""Accès aux documents — l'algorithme en cinq étapes.

⚠️ Fragment de `app/utils/visibility/` : le découpage en trois modules et sa couture
sont expliqués UNE fois, dans l'en-tête de `__init__.py` (#1564).
"""

from __future__ import annotations

import json

from app.models.core import (
    DiagnosticRapport,
    Document,
    ProfilAccesDocument,
    RegleResidence,
    RoleUtilisateur,
    Ticket,
    Utilisateur,
)
from app.models.evenement import Evenement

from .objets import evenement_visible, ticket_visible
from app.auth.deps import est_moderateur, est_rattache_au_lot
from app.utils.designation_lot import est_annexe
from app.utils.valeurs import valeur

# ── Règles document ───────────────────────────────────────────────────────────


def profil_admet(user: Utilisateur, profil: ProfilAccesDocument | None) -> bool:
    """Ce profil d'accès admet-il ce lecteur ? — la règle par RÔLE, et elle seule.

    Comparée aux rôles **et** au statut du lecteur : le syndic n'a aucun rôle de
    copropriétaire, son statut vaut `syndic`, et c'est ainsi qu'il lit les PV
    d'AG (migration 0159). Pas de profil → non : « aucune règle » n'est jamais
    une autorisation (`standards/04`).

    🔴 Écrite deux fois avant #1551, mot pour mot : ici et dans
    `routers/documents.py::list_categories`, qui choisit les catégories qu'on
    vous propose. Le jour où le profil apprend quelque chose, l'écran aurait
    proposé des catégories dont aucun document ne s'ouvre, ou tu les autres.
    `tests/test_autorisation.py` refuse une lecture de `roles_autorises` hors
    d'ici. Les modérateurs ne passent pas par là : chaque appelant les admet en
    tête, avant toute autre règle.
    """
    if profil is None:
        return False
    roles_autorises = json.loads(profil.roles_autorises)
    return any(r in roles_autorises for r in set(user.roles) | {valeur(user.statut)})


#: Les catégories que l'ADMINISTRATION seule lit, dépose, corrige et retire
#: (11/10/2026) : les fichiers du règlement que l'assistant interroge
#: (Ma résidence › Règlement). Le texte de travail nomme notaires et parties ; le
#: conseil comme les copropriétaires n'en lisent que les réponses, et un lien
#: vers le règlement publié dans la Fiche.
CATEGORIES_ADMIN_SEUL = frozenset({"texte_reglement"})


def reserve_a_l_admin(categorie) -> bool:
    """PURE. Cette catégorie est-elle réservée à l'administration ?"""
    return getattr(categorie, "code", None) in CATEGORIES_ADMIN_SEUL


def peut_ecrire_dans(user: Utilisateur, categorie) -> bool:
    """Ce modérateur peut-il déposer, corriger ou retirer un document de cette
    catégorie ? — le conseil et l'admin partout, sauf `CATEGORIES_ADMIN_SEUL`.
    Les routes d'écriture des documents exigent déjà le conseil ou l'admin."""
    return not reserve_a_l_admin(categorie) or user.has_role(RoleUtilisateur.admin)


def document_visible(user: Utilisateur, doc: Document, session) -> bool:
    """Retourne True si l'utilisateur a le droit de lire ce document.

    Algorithme d'accès en 5 étapes (specs modele-donnees.md). Un document tire sa
    protection soit de l'objet qui le porte (contrat, actualité), soit de son profil
    d'accès de catégorie — jamais des deux, jamais d'aucun.

    Cette règle vivait dans `routers/documents.py`, et `flux.py` l'importait depuis
    ce router. Une règle de sécurité hors du module central, c'est une règle qu'un
    durcissement ultérieur peut manquer : c'est exactement ce qui est arrivé aux
    pièces jointes d'actualité, autorisées sans consulter l'actualité porteuse
    (cf. `tests/test_documents_acces.py`). Elle est ici, avec les autres.

    `session` n'est typé que par usage (`.get`) pour ne pas faire dépendre ce module
    de SQLModel : seuls les porteurs et `ProfilAccesDocument` sont chargés.
    """
    #  Avant la règle des modérateurs : le conseil ne lit PAS les fichiers du
    #  règlement que l'assistant interroge (`CATEGORIES_ADMIN_SEUL`).
    if reserve_a_l_admin(doc.categorie):
        return user.has_role(RoleUtilisateur.admin)

    # Admin et CS voient tout
    if est_moderateur(user):
        return True

    # Documents liés à un contrat (sans catégorie) : CS/admin uniquement
    if doc.contrat_id and not doc.categorie_id:
        return False

    #  🔴 Une pièce jointe d'ACTUALITÉ porte `ticket_id` depuis le 23/09/2026 :
    #  l'actualité est une affaire (#1091), et la 0210 a rattaché les anciennes.
    #  Un `publication_id` résiduel n'a plus de porteur lu par personne : il
    #  tombe dans le refus final, faute de règle à appliquer.

    #  Pièce jointe de TICKET ou d'ÉVÉNEMENT (#390) : elle suit EXACTEMENT la
    #  visibilité de l'objet qui la porte — un document n'a pas de ciblage propre.
    #
    #  🔴 « Qui voit le porteur », et rien d'autre — décision prise le 27/08/2026.
    #  Le régime actuel de ces fichiers est celui de l'objet qui les porte ; leur
    #  donner au passage le contrôle à trois couches des documents casserait des
    #  accès qui marchent aujourd'hui, sans que personne soit prévenu. Le gain de
    #  #390 est de fermer l'URL BRUTE, pas de changer qui voit quoi.
    #
    #  ⚠️ Porteur introuvable → on REFUSE. Une pièce jointe dont le ticket a été
    #  supprimé n'a plus de règle à appliquer, et « aucune règle » n'est jamais une
    #  autorisation (`standards/04` — un contrôle qui ne peut pas s'exécuter ne
    #  rend pas OK).
    if doc.ticket_id and not doc.categorie_id:
        ticket = session.get(Ticket, doc.ticket_id)
        if not ticket:
            return False
        return ticket_visible(ticket, user)

    if doc.evenement_id and not doc.categorie_id:
        ev = session.get(Evenement, doc.evenement_id)
        if not ev:
            return False
        return evenement_visible(ev, user)

    #  Une ANNEXE de fiche de « Ma résidence » (migration 0276, `utils/annexes`) :
    #  elle se lit EXACTEMENT comme sa fiche, comme une pièce jointe d'affaire
    #  suit son affaire. Fiche introuvable → refus, pour la même raison.
    if doc.document_parent_id and not doc.categorie_id:
        parent = session.get(Document, doc.document_parent_id)
        #  ⚠️ Une annexe d'annexe n'existe pas (`utils/annexes.verifier_porteur`) :
        #  si elle apparaissait, elle serait refusée — la remontée s'arrête à un cran.
        if not parent or parent.document_parent_id:
            return False
        return document_visible(user, parent, session)

    #  Un rapport de diagnostic et une règle se lisent par tout compte connecté :
    #  leurs routes de lecture ne demandent que `get_current_user`
    #  (`routers/diagnostics.download_rapport`, `routers/regles_residence.list_regles`).
    #  Seule l'EXISTENCE du porteur reste à vérifier.
    if doc.diagnostic_rapport_id and not doc.categorie_id:
        return session.get(DiagnosticRapport, doc.diagnostic_rapport_id) is not None

    if doc.regle_residence_id and not doc.categorie_id:
        return session.get(RegleResidence, doc.regle_residence_id) is not None

    #  🔴 UN DOCUMENT SANS SOURCE DE PROTECTION NE SE LIT PAS.
    #
    #  Cette ligne s'écrivait `doc.profil_acces_override_id or doc.categorie.profil_acces_id`,
    #  et déréférençait `doc.categorie` sans le tester. Un document sans catégorie
    #  NI contrat NI publication y arrive — les trois branches précédentes l'ont
    #  laissé passer — et `None.profil_acces_id` lève un `AttributeError`, donc un
    #  **500 sur la liste des documents** pour tout utilisateur non CS/admin.
    #
    #  ⚠️ Le cas est INATTEIGNABLE aujourd'hui : `POST /documents` exige l'un des
    #  trois, `PATCH` ne peut pas les vider, et aucun endpoint ne supprime une
    #  catégorie. C'est un invariant tenu à UN endroit (la création) et SUPPOSÉ à
    #  un autre (ici), sans rien qui relie les deux — la forme d'invariant qui se
    #  brise au premier appelant nouveau.
    #
    #  Et cet appelant est déjà écrit : l'étape 1 de #390 crée justement une ligne
    #  `Document` « sans publication_id, rattachée ensuite ». Elle aurait donc
    #  produit exactement ce document-là, et le 500 avec.
    #
    #  Le repli est le REFUS, jamais l'autorisation : une pièce jointe dont on ne
    #  sait pas de qui elle tire sa protection n'en a aucune (`standards/03` — en
    #  cas de doute sur un droit, on refuse).
    profil_id = doc.profil_acces_override_id or (
        doc.categorie.profil_acces_id if doc.categorie else None
    )
    if not profil_id:
        return False
    if not profil_admet(user, session.get(ProfilAccesDocument, profil_id)):
        return False

    # Vérifier le périmètre
    #
    #  🔴 `perimetre='bâtiment'` RESTREINT la lecture, et c'est son rôle : un
    #  diagnostic, un contrat ou une attestation ne concernent que les détenteurs
    #  d'un lot dans le bâtiment visé.
    #
    #  ⚠️ Ce n'est PAS le cas des comptes-rendus d'AG, dont le ciblage est
    #  descriptif — voir le bloc suivant. L'écran leur posait pourtant ce
    #  `perimetre='bâtiment'` dès qu'un seul bâtiment était coché, ce qui rendait
    #  une AG invisible aux copropriétaires des autres bâtiments (mesuré le
    #  29/08/2026). Corrigé à la source : l'écran n'en pose plus, et la migration
    #  0159 reverse les documents déjà en base.
    #
    #  🔒 « Détenteur d'un lot du bâtiment » : un lot de CE bâtiment auquel le
    #  lecteur est rattaché — et « rattaché » se demande à `est_rattache_au_lot`,
    #  qui exige le lien actif. Ce bloc jugeait `ul.actif` lui-même avant #1551.
    #  ⚠️ Plus étroit que `utils/mes_batiments`, et VOULU : le bâtiment de
    #  rattachement (`user.batiment_id`) n'y entre pas — un diagnostic ou une
    #  attestation de bâtiment concernent qui y détient un lot, pas qui y est
    #  domicilié sans lot. Ce n'est donc pas une copie de « mes bâtiments ».
    #  🔴 Une ANNEXE (cave, place) n'en est pas un détenteur : la spec
    #  `lots-et-perimetres.md` §6 refuse les PV d'un bâtiment à qui n'y range que sa
    #  voiture, et l'import de l'état descriptif situe désormais une cave dans SON
    #  bâtiment. Même règle que « mes bâtiments », lue au même endroit (#2212).
    if doc.perimetre == "bâtiment" and doc.batiment_id:
        lots_du_batiment = {
            ul.lot_id
            for ul in user.user_lots
            if ul.lot and ul.lot.batiment_id == doc.batiment_id and not est_annexe(ul.lot)
        }
        if not any(est_rattache_au_lot(user, lot_id) for lot_id in lots_du_batiment):
            return False

    #  ── `batiments_ids_json` NE RESTREINT PAS, et c'est une décision ─────────
    #
    #  Ce champ ne sert qu'aux comptes-rendus d'AG, et il y dit **de quoi parle**
    #  le document — pas qui a le droit de le lire. C'est l'arbitrage rendu par
    #  l'utilisateur le 29/08/2026 : *« une AG doit être visible par tous les
    #  copropriétaires, syndic et CS »*.
    #
    #  🔴 Un premier correctif (#617) avait fait l'inverse : il l'avait rendu
    #  restrictif, pour aligner les deux formes de ciblage que l'écran écrit
    #  (`perimetre='bâtiment'` pour un bâtiment, `batiments_ids_json` pour
    #  plusieurs). L'incohérence était réelle — mais elle a été refermée du
    #  mauvais côté : c'est `perimetre='bâtiment'` qui n'avait rien à faire sur
    #  un PV d'AG, pas l'inverse. La migration 0159 reverse les documents
    #  existants, et l'écran n'en pose plus.
    #
    #  ⚠️ Ne PAS ajouter ici de restriction sur ce champ sans revenir sur cet
    #  arbitrage : la cohérence des deux formes est désormais tenue en amont, par
    #  l'écran et la migration, et non par un second filtre ici.

    if doc.perimetre == "lot" and doc.lot_id:
        if not est_rattache_au_lot(user, doc.lot_id):
            return False

    return True
