"""Router flux — agrégation temps réel pour le tableau de bord « pouls ».

`flux.py` faisait **1044 lignes**, dont un unique endpoint de 780 lignes portant
douze rubriques numérotées à la file. C'est le fichier d'API le plus modifié du
dépôt — 19 commits en 60 jours — et c'est celui que j'ai fait grossir de 996 à
1044 lignes le 07/08/2026 alors que la règle des 500 lignes existait déjà.
Découpé le 08/08/2026 ; le garde-fou `scripts-ci-modularite.sh`, écrit le même
jour, existe précisément pour que cette dérogation ne se répète pas.

## La règle de découpage : une rubrique, un module

Reprise de `app/routers/admin/` (06/08/2026) — un module par **domaine**, chacun
ayant sa propre raison de changer — et non un découpage par nature technique.
Chaque rubrique expose la même signature :

    collecter(ctx: ContexteFlux) -> list[FluxItem]

C'est ce contrat qui rend le découpage utile plutôt que cosmétique : ajouter une
rubrique au fil, c'est un module et une ligne dans `_COLLECTEURS` — pas une
treizième section à intercaler au milieu de 780 lignes.

| Module | Ce qui y change |
|---|---|
| `tickets` | ouvertures, changements d'état, réponses du CS, commentaires |
| `publications` | actualités, et leur règle d'archivage partagée avec /actualités |
| `prestataires` | nouvelles fiches — page réservée au CS/admin |
| `communaute` | sondages, petites annonces, boîte à idées |
| `ressources` | questions fréquentes, documents partagés, diagnostics |
| `reglement` | questions au règlement — leur auteur, le conseil, l'administration |
| `annuaire` | nouveaux membres du conseil syndical et du syndic |
| `sante` | indicateurs et agenda « Prochaines échéances » (aucune ligne de fil) |
| `epingles` | endpoint `/flux/epingles`, décompte du bandeau « Épinglé » |
| `commun` | contexte de collecte, périmètres, résumés, marqueurs |
| `schemas` | `FluxItem`, `FluxSante`, `FluxResponse`, `EpinglesCompte` |

## Ce qui a été factorisé, et ce qui a été laissé en double exprès

**Factorisé** — trois duplications que le fichier long avait fabriquées :

- la cascade de périmètre (`perimetre_cible` → `batiment_id` → défaut), recopiée
  cinq fois → `commun.perimetres_de` ;
- les cartes « réponse du CS » et « commentaire », identiques au caractère près
  hors trois valeurs, commentaire de six lignes compris → une seule écriture dans
  `tickets._carte_mise_a_jour`. C'est cette duplication qui a produit le bug du
  07/08/2026 : la clé de pièce jointe ajoutée d'un côté, oubliée de l'autre ;
- `TYPE_EMOJI`, défini une fois et partagé entre le fil et l'agenda.

**Laissé en double, volontairement** : les événements continuent d'appeler
`parse_perimetres(x.perimetre)` en direct. Ils n'ont pas de `perimetre_cible` et
leur règle ignore `batiment_id` — les faire passer par `perimetres_de` changerait
leur périmètre affiché dès qu'un bâtiment est renseigné. Le devis partageait cette
exception ; il n'y a plus qu'un cas, et une exception unique reste une exception. Deux règles qui se ressemblent ne sont pas la même règle
(`standards/02-factorisation.md` §4). Que `Evenement` ignore `batiment_id` est
peut-être un défaut en soi ; ce n'est pas à un découpage de le trancher.

## Ce qui n'a PAS changé

Les deux chemins (`GET /flux`, `GET /flux/epingles`), le contrat de sortie et
`main.py`, qui continue d'écrire `app.include_router(flux.router)` sans savoir
que ce module est devenu un paquet. Le préfixe `/flux` reste porté **ici**.

⚠️ `_lien_document` et `_CATEGORIES_DOCUMENT_AVEC_LIEN` étaient RÉ-EXPORTÉS ici
pour que `test_liens_front` puisse les importer. Ils ont quitté le paquet le
09/09/2026 : la notification et le courriel de publication en avaient besoin
aussi, et ils écrivaient leur propre version — plus pauvre. Ils vivent dans
`app/utils/documents`, et le ré-export a disparu avec eux : un alias qui délègue
masque l'origine sans rien apporter (`standards/02` §1, règle 6).
"""

from datetime import timedelta
from app.utils import horloge

from fastapi import APIRouter, Depends
from sqlmodel import Session, select

from app.auth.deps import get_current_user, require_admin
from app.database import get_session
from app.models.core import FluxMasque, Utilisateur
from app.utils.archivage import seuil_archivage_jours
from app.utils.visibility import concerne

from . import (
    annuaire,
    communaute,
    epingles,
    points_conseil,
    prestataires,
    publications,
    reglement,
    ressources,
    sante,
    tickets,
)
from .commun import ContexteFlux
from .schemas import EpinglesCompte, FluxItem, FluxResponse, FluxSante

#: Fenêtre glissante du fil, en jours — valeur reprise telle quelle du fichier
#: d'origine, où elle était écrite en dur sans justification. Un élément épinglé
#: y échappe (cf. `publications` et `evenements`).
_FENETRE_JOURS = 377

#: Les rubriques du fil, dans l'ordre de collecte. L'ordre d'affichage, lui, est
#: purement chronologique (tri global plus bas) : cette liste n'en décide pas.
_COLLECTEURS = (
    tickets.collecter,
    publications.collecter,
    prestataires.collecter,
    communaute.collecter,
    ressources.collecter,
    reglement.collecter,
    annuaire.collecter,
    points_conseil.collecter,
)

#  Le préfixe et le tag vivent ICI : les sous-routers déclarent des chemins nus,
#  donc identiques à ceux d'avant le découpage.
router = APIRouter(prefix="/flux", tags=["flux"])
router.include_router(epingles.router)


@router.get("", response_model=FluxResponse)
def get_flux(
    session: Session = Depends(get_session),
    user: Utilisateur = Depends(get_current_user),
):
    now = horloge.maintenant()
    ctx = ContexteFlux(
        session=session,
        user=user,
        now=now,
        since=now - timedelta(days=_FENETRE_JOURS),
    )

    items: list[FluxItem] = []
    for collecter in _COLLECTEURS:
        items.extend(collecter(ctx))

    #  🔴 LE MASQUAGE S'APPLIQUE ICI, ET NULLE PART AILLEURS.
    #
    #  Le fil a SEPT collecteurs. Filtrer chez chacun d'eux, c'est écrire sept
    #  fois la même règle et en oublier une au huitième — celui qu'on ajoutera.
    #  Au point d'assemblage, la règle est écrite une fois et couvre ce qui
    #  existe comme ce qui viendra.
    #
    #  ⚠️ Aucun objet n'est supprimé : ce sont des identifiants d'AFFICHAGE
    #  (`pub_7`, `mcs_12`) qui sont retirés de la vue. L'actualité, le membre du
    #  conseil ou le ticket restent consultables depuis leur écran — c'est très
    #  exactement ce que la demande du 31/08/2026 dit.
    masques = set(session.exec(select(FluxMasque.item_id)).all())
    items = [i for i in items if i.id not in masques]
    #  « Ce qui me concerne » (#2215), au même point d'assemblage et pour la même
    #  raison : la règle de l'accès (`visibility.concerne`), une fois, sur chaque
    #  élément qui porte un lieu. Ceux qui n'en portent pas restent `None` : ils
    #  s'adressent à toute la copropriété, et la pastille les garde.
    for item in items:
        if codes := item.meta.get("perimetre_codes"):
            item.me_concerne = concerne(user, codes)

    items.sort(key=lambda x: x.date, reverse=True)

    return FluxResponse(
        items=items,
        sante=sante.calculer(ctx),
        delai_recent_jours=seuil_archivage_jours(session),
    )


@router.delete("/{item_id}", status_code=204)
def masquer_item(
    item_id: str,
    session: Session = Depends(get_session),
    admin: Utilisateur = Depends(require_admin),
):
    """Retirer une carte du fil — **sans toucher à l'objet qu'elle décrit**.

    > *« supprimer, uniquement pour l'admin sur le fil d'actualité (pour
    > supprimer certaines publications dans le fil, celle-ci reste tracée à
    > l'origine : actualité, annuaire, ticket, …) »* — 31/08/2026

    ## 🔴 Où ce geste est OFFERT, et pourquoi pas partout

    Arbitré le 31/08/2026, après avoir posé le bouton sur toutes les cartes :

    > *« si on archive le document d'origine, il disparaît donc c'est bon […]
    > juste le pb de l'annuaire »*

    Ce qui s'archive se retire du fil **en s'archivant**, et c'est le geste du
    site : *archiver, pas supprimer*. Poser un 🗑️ à côté offrirait un second
    chemin pour la même intention — la « troisième forme pour une même
    intention » que #367 a supprimée, et qu'il a fallu signaler trois fois.

    L'annuaire, lui, n'a pas d'archivage : un membre du conseil syndical y est
    ou n'y est pas. Sa carte est donc la seule qu'on ne puisse retirer autrement.
    L'écran ne propose le bouton que sur elle (`FluxCard`, `retirable`).

    ⚠️ **Cet endpoint reste générique**, et c'est délibéré : lui faire connaître
    la liste des types archivables serait une seconde liste à tenir d'accord avec
    la première, et c'est toujours la seconde qui dérive. C'est l'OFFRE qui est
    restreinte, pas la capacité — un administrateur qui appellerait l'API sur une
    autre carte obtiendrait ce qu'il demande, et il l'aura demandé.

    ## Pourquoi `require_admin` et pas `require_cs_or_admin`

    Le geste demandé est explicitement réservé à l'administrateur. Il n'a rien
    d'une modération de contenu — le contenu ne bouge pas : c'est un réglage de
    ce que le fil montre, et le fil est vu par tous les résidents.

    ## Pourquoi c'est idempotent, et pourquoi ça compte

    Masquer une carte déjà masquée est le même fait, pas une erreur. L'écran
    retire la carte de sa liste avant même la réponse ; un second clic sur un
    autre onglet ne doit pas produire un message d'erreur pour un état déjà
    atteint. La contrainte d'unicité de `item_id` porte la même idée en base.

    ⚠️ **Aucune validation du format de `item_id`.** Un identifiant qui ne
    correspond à aucune carte crée une ligne inerte : le fil ne la rencontrera
    jamais. Refuser demanderait de connaître les sept formats — donc de les
    recopier ici, et de les tenir à jour à chaque collecteur ajouté. Le coût du
    refus dépasse le coût de la ligne morte.
    """
    deja = session.exec(select(FluxMasque).where(FluxMasque.item_id == item_id)).first()
    if deja is None:
        session.add(FluxMasque(item_id=item_id, masque_par_id=admin.id))
        session.commit()
    return None


__all__ = [
    "router",
    "ContexteFlux",
    "EpinglesCompte",
    "FluxItem",
    "FluxResponse",
    "FluxSante",
]
