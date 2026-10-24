"""« Cet objet est-il le mien ? » — les règles, au même endroit.

## Pourquoi ce module (#1028, point 2)

L'audit du 19/09/2026 relevait que les règles d'appartenance vivaient **chez les
routeurs**, hors du module central, et que `test_autorisation.py` ne pouvait pas
les voir : ce ne sont pas des `Depends`, mais des fonctions ordinaires appelées
au début d'un geste.

Le ticket demandait « un module d'appartenance complet ». La première question
était donc : **peut-on les fondre ?** La réponse est non, et c'est mesuré :

| | bail d'un bailleur | accès d'un porteur |
|---|---|---|
| champ de propriété | `bailleur_id` | `user_id` |
| le conseil syndical y a-t-il accès ? | **oui** | **non** |
| refus | **403** | **404** |

Trois axes de divergence pour deux fonctions. Les réunir demanderait quatre
paramètres de variation, c'est-à-dire une abstraction si pauvre qu'elle serait
contournée au troisième appelant (`standards/02` §4 quater). Et les deux
décisions sont **justes** : un bail refusé peut dire « interdit », parce que son
existence n'apprend rien ; un badge qui n'est pas le vôtre doit dire
« introuvable », parce que « interdit » confirmerait qu'il existe.

## Ce que ce module apporte, puisque ce n'est pas une fonction commune

**Un lieu.** Les deux règles sont côte à côte, avec leur décision écrite, et on
les compare d'un coup d'œil — ce qui était impossible quand l'une vivait dans
`routers/bailleur/commun.py` et l'autre dans `routers/acces/resident.py`.

C'est ce que `standards/03` §1 demande : une règle d'autorisation ne vit pas chez
un routeur. Le lieu ne supprime pas la divergence — il la rend **visible**, et
c'est la seule chose qui empêche la troisième règle d'être écrite au hasard.

🔒 `api/tests/test_appartenance_source_unique.py` refuse qu'une comparaison entre
un champ d'objet et `user.id` gouverne une levée HTTP hors de `auth/`.

## Deux questions, deux fonctions — ne pas les remélanger

« Existe-t-il ? » est répondu par `utils/recuperer.ou_404`, et **uniquement** par
lui. Les fonctions ci-dessous l'appellent, puis ajoutent leur question propre :
« est-ce le vôtre ? ». Les helpers qu'elles remplacent mêlaient les deux, et
`recuperer.py` explique déjà pourquoi c'est un défaut : un 404 posé « pour ne pas
révéler l'existence » est une décision de sécurité, pas une réponse à
« existe-t-il ? ».
"""

from __future__ import annotations

from typing import Any, Callable

from fastapi import HTTPException
from sqlmodel import Session

from app.auth.deps import est_auteur, est_moderateur, est_rattache_au_lot
from app.models.core import LocationBail, Lot, RoleUtilisateur, Utilisateur
from app.utils.recuperer import ou_404


def exiger_bail_du_bailleur(session: Session, bail_id: int, user: Utilisateur) -> LocationBail:
    """Le bail, s'il est celui de ce bailleur — **403** sinon.

    Le conseil syndical et l'administration y ont accès : ils arbitrent les
    litiges de gestion locative, et c'est pour cela que ce cas existe.

    ⚠️ **403 et non 404**, contrairement à l'accès d'un porteur : l'existence d'un
    bail sur un lot n'apprend rien à qui n'y a pas droit — le lot, lui, est
    public dans la copropriété. Dire « interdit » est donc honnête, et plus
    utile qu'un « introuvable » qui enverrait chercher une erreur de saisie.
    """
    bail = ou_404(session, LocationBail, bail_id, "Bail")
    if bail.bailleur_id != user.id and not est_moderateur(user):
        raise HTTPException(status_code=403, detail="Accès interdit")
    return bail


def exiger_lot_du_bailleur(session: Session, lot_id: int, user: Utilisateur) -> Lot:
    """Le lot, si ce compte peut le donner à bail — **403** sinon (#1535).

    La question d'AVANT le bail, jumelle de `exiger_bail_du_bailleur` et de même
    décision : 403, le conseil syndical et l'administration admis. Le lien exigé
    est ACTIF et de nature copropriétaire (`TYPES_COPROPRIETAIRES`) — le
    locataire d'un lot n'en est pas le bailleur.

    🔴 Elle manquait : `creer-multi` relisait le lot (« existe-t-il ? ») sans
    demander s'il était le vôtre. Tout propriétaire posait un bail sur le lot
    d'un voisin en s'en désignant locataire, et devenait ainsi porteur des
    badges remis à ce lot (`utils/porteurs_acces`) et bailleur du bail — que
    `exiger_bail_du_bailleur` lui laissait ensuite gérer. L'écran ne proposait
    que « mes lots » : un écran masqué n'est pas un accès refusé.

    Le refus est journalisé : il n'arrive pas par l'écran, c'est une requête
    forgée ou un compte détaché depuis la page ouverte, deux choses à relire.
    """
    from app.utils.journal_securite import journaliser_securite
    from app.utils.resolution_lots import TYPES_COPROPRIETAIRES

    lot = ou_404(session, Lot, lot_id, "Lot")
    if not est_moderateur(user) and not est_rattache_au_lot(
        user, lot_id, comme=TYPES_COPROPRIETAIRES
    ):
        journaliser_securite("bail_hors_de_ses_lots", acteur_id=user.id, detail=f"lot={lot_id}")
        raise HTTPException(status_code=403, detail=f"Le lot {lot.numero} n'est pas le vôtre")
    return lot


def exiger_lots_proposes_au_locataire(
    session: Session, lot_ids: list[int], user: Utilisateur
) -> list[Lot]:
    """Les lots, si CHACUN est proposé à ce locataire — **403** sinon, et rien n'est rattaché.

    « Ce lot est-il celui que je loue ? » n'a qu'une réponse : il figure parmi
    les lots du propriétaire nommé à l'inscription
    (`utils/rattachement_locataire.lots_proposes`). Ni le conseil syndical ni
    l'administration n'y passent : ils rattachent par leurs propres écrans.

    Le refus est journalisé, comme `exiger_lot_du_bailleur` : l'écran ne
    propose que ces lots, une autre désignation est une requête forgée.
    """
    from app.utils.journal_securite import journaliser_securite
    from app.utils.rattachement_locataire import lots_proposes

    proposes = {lot.id: lot for lots in lots_proposes(user, session).values() for lot in lots}
    if not lot_ids or any(i not in proposes for i in lot_ids):
        journaliser_securite(
            "rattachement_hors_proposition", acteur_id=user.id, detail=f"lots={lot_ids}"
        )
        raise HTTPException(status_code=403, detail="Ces lots ne vous sont pas proposés")
    return [proposes[i] for i in dict.fromkeys(lot_ids)]


def exiger_aidant_de_la_delegation(delegation, user: Utilisateur) -> None:
    """Seul l'aidant désigné accepte une délégation — **403** sinon.

    Troisième décision, troisième combinaison, et c'est tout l'intérêt de les
    avoir côte à côte : ici le conseil syndical n'est **pas** admis — accepter
    une délégation engage l'aidant personnellement, personne ne peut le faire à
    sa place — mais le refus dit « interdit », parce que la délégation existe
    bel et bien et que le demandeur le sait : il en est le mandant.

    ⚠️ La **révocation**, elle, admet le mandant, l'aidant ET le conseil : on
    peut avoir besoin de défaire ce qu'on n'a pas le droit de faire. Elle reste
    chez son routeur — elle ne compare pas une propriété, elle vérifie une
    appartenance à un ensemble de trois, ce qui est une autre question.
    """
    if delegation.aidant_id != user.id:
        raise HTTPException(403, "Seul l'aidant désigné peut accepter")


def exiger_acces_du_porteur(session: Session, type_acces, objet_id: int, user: Utilisateur):
    """Le badge ou la télécommande, s'il appartient à qui le demande — **404** sinon.

    🔴 **404 et non 403**, et le conseil syndical n'est **pas** admis ici. Les
    deux décisions se tiennent : répondre « interdit » confirmerait l'existence
    d'un badge qui n'est pas le vôtre, et permettrait de deviner le parc d'un
    voisin en essayant des identifiants.

    Cette règle était écrite **quatre fois** à l'identique avant d'être ramenée
    dans `routers/acces/resident.py` ; elle est ici depuis #1028, avec les autres.
    """
    from app.utils.porteurs_acces import porteurs

    #  Porteur = ce que dit le LOT (#1194) : le conjoint signale la perte du
    #  badge du ménage, lui aussi. `user_id` seul n'en laissait qu'un.
    objet = session.get(type_acces.modele, objet_id)
    if not objet or user.id not in porteurs(session, objet):
        raise HTTPException(404, f"{type_acces.libelle} introuvable")
    return objet


def exiger_cible_visible(
    session: Session,
    modele: type,
    cible_id: int,
    libelle: str,
    user: Utilisateur,
    visible_de: Callable[[Any, Utilisateur], bool],
) -> Any:
    """La cible existe ET l'utilisateur a le droit de la voir — **404** sinon.

    Quatrième décision, quatrième combinaison — et la seule qui prenne le
    prédicat de visibilité **en paramètre** : ce qui rend une annonce visible
    n'est pas ce qui rend une idée visible, et cette variation-là est légitime
    parce qu'elle ne porte que sur UNE question, pas sur trois.

    🔒 **404 et non 403**, délibérément : répondre « interdit » confirmerait
    l'existence de l'objet à qui n'a pas le droit de le voir. Sur une petite
    annonce ciblée, cela révélerait qu'un voisin vend quelque chose sans dire
    quoi — une fuite plus discrète, mais réelle.

    Les trois routes de réponses posaient la même question à moitié (« existe-t-il ? »)
    et chacune à sa façon. Une seule écriture, appelée trois fois.
    """
    cible = session.get(modele, cible_id)
    if not cible or not visible_de(cible, user):
        raise HTTPException(404, f"{libelle} introuvable")
    return cible


def exiger_objet_autorise(
    session: Session,
    modele: type,
    objet_id: int,
    libelle: str,
    user: Utilisateur,
    autorise_de: Callable[[Any, Utilisateur], bool],
    refus: str = "Accès refusé",
) -> Any:
    """L'objet existe (404 sinon) ET l'utilisateur y a droit — **403** sinon (#1564).

    Le pendant de `exiger_cible_visible`, avec la décision inverse : ici le refus
    dit « interdit », parce que l'existence de l'objet n'apprend rien (une affaire,
    un sondage, une annonce sont listés à tous ceux qui ont un compte). Le motif
    « `ou_404`, puis `if not autorise: raise HTTPException(403)` » était écrit à
    l'identique dans six routeurs, avec trois formulations du refus : `refus` la
    garde, pour que le message vu par l'utilisateur ne change pas.

    Le prédicat reste celui de l'entité (`ticket_visible`, `sondage_accessible`…) :
    ce qui rend un objet accessible n'est pas une règle commune, la façon de le
    refuser l'est.
    """
    objet = ou_404(session, modele, objet_id, libelle)
    if not autorise_de(objet, user):
        raise HTTPException(403, refus)
    return objet


def peut_defaire_le_versement(v, user: Utilisateur, *, deplacer: bool) -> bool:
    """Ce lecteur peut-il défaire ce transfert ? — le PRÉDICAT, que le refus appelle.

    Celui qui a transféré, et l'administrateur ; déplacer exige en plus de
    modérer (voir `exiger_auteur_du_versement`, qui en fait un 403).

    🔴 Il était recopié dans `routers/tickets/transferts.py::lister_transferts`,
    qui filtrait par `continue` sur `v.transfere_par_id != user.id` et calculait
    `peut_deplacer` à part (#1551). Identiques ce jour-là ; mais la liste et le
    geste doivent dire la même chose, sinon l'écran propose un bouton qui rend
    403, ou tait un geste permis. `tests/test_appartenance_source_unique.py`
    refuse une comparaison de `transfere_par_id` à un utilisateur hors d'`auth/`.
    """
    from app.models.core import RoleUtilisateur

    if user.has_role(RoleUtilisateur.admin):
        return True
    return v.transfere_par_id == user.id and (not deplacer or est_moderateur(user))


def exiger_auteur_du_versement(
    session: Session, ticket_id: int, versement_id: int, user: Utilisateur, *, deplacer: bool
):
    """Le transfert versé dans CETTE affaire, s'il est celui de qui le défait — **403** sinon.

    Cinquième combinaison (#1482, arbitré le 30/09/2026) : celui qui a transféré,
    et l'administrateur — pas le conseil syndical en tant que tel. Défaire un
    transfert retire des Suites que d'autres n'ont pas écrites ; c'est le geste
    de celui qui s'est trompé, ou de l'arbitre.

    ⚠️ DÉPLACER exige en plus de modérer : un correspondant de l'affaire (son
    auteur, le syndic) peut transférer dans l'affaire que le courriel désigne,
    mais il ne choisit pas l'affaire où verser — ce serait écrire dans une
    affaire qu'il ne lit peut-être pas. Il peut annuler.

    404 pour un transfert d'une AUTRE affaire : l'adresse dit laquelle, et la
    lecture de l'affaire a déjà été vérifiée par le routeur.
    """
    from app.models.courriel import VersementCourriel

    v = ou_404(session, VersementCourriel, versement_id, "Transfert", sous={"ticket_id": ticket_id})
    if not peut_defaire_le_versement(v, user, deplacer=deplacer):
        raise HTTPException(403, "Seul celui qui a transféré, ou l'administrateur, peut le défaire")
    return v


# ── Les avis sur l'application (#2075) ─────────────────────────────────────
#
#  Trois gestes, trois règles — elles ne se fondent pas : retirer admet l'auteur
#  et le gestionnaire du site ; ressortir, le gestionnaire, et l'auteur pour ce
#  qu'il a rangé lui-même ; supprimer, l'auteur et l'administration. Le
#  gestionnaire se demande à `utils/destinataires.est_gestionnaire_du_site` (il
#  faut la base) : l'appelant le passe.


def peut_retirer_l_avis(avis, user: Utilisateur, *, gestionnaire: bool) -> bool:
    """📦 Retirer un avis : son auteur, ou le gestionnaire du site."""
    return gestionnaire or est_auteur(avis, user)


def peut_ressortir_l_avis(avis, user: Utilisateur, *, gestionnaire: bool) -> bool:
    """↩️ Ressortir un avis retiré : le gestionnaire ; l'auteur, s'il l'a rangé lui-même.

    Ce que le gestionnaire a retiré (un avis inapproprié), son auteur ne le
    republie pas d'un clic.
    """
    return gestionnaire or (avis.archive_par_id is not None and avis.archive_par_id == user.id)


def peut_supprimer_l_avis(avis, user: Utilisateur) -> bool:
    """🗑️ Supprimer un avis, aux Archives : son auteur (droit à l'effacement), ou l'administration."""
    return est_auteur(avis, user) or user.has_role(RoleUtilisateur.admin)


#: Les liens à un lot qui en montrent les TANTIÈMES (#2212, spec `lots-et-perimetres.md`
#: §9). Arbitré le 24/10/2026 (coordination, sur délégation de Philippe du 17/10) :
#: le copropriétaire et qui le représente — le mandataire de gestion —, pas le
#: locataire, qui ne paie pas les charges de copropriété. Le conseil et
#: l'administration lisent le patrimoine entier par `/lots/admin/tous`.
LIENS_QUI_LISENT_LES_TANTIEMES = frozenset({"propriétaire", "bailleur", "mandataire"})


def lit_les_tantiemes(type_lien: Any) -> bool:
    """Ce lien à un lot en montre-t-il les tantièmes ?"""
    from app.utils.valeurs import valeur

    return str(valeur(type_lien) or "") in LIENS_QUI_LISENT_LES_TANTIEMES
