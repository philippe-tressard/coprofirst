"""Router tickets — création, suivi, messagerie, évolutions, relance syndic.

`tickets.py` faisait **1238 lignes**, dont deux fonctions de 224 et 231 lignes.
Découpé le 08/08/2026, au fil de l'eau : l'ajout du partage WhatsApp à la
création l'avait fait passer de 1213 à 1238 lignes, et c'est le garde-fou de
modularité écrit la veille (`scripts-ci-modularite.sh`) qui a refusé le lot.
Le contrôle a donc fonctionné exactement comme prévu — on découpe le fichier
quand on y touche.

## La règle de découpage : un domaine, un module

Reprise de `app/routers/admin/` et `app/routers/flux/` — par domaine, chacun
ayant sa propre raison de changer.

| Module | Ce qui y change |
|---|---|
| `crud` | cycle de vie : lister, créer, lire, modifier, supprimer |
| `messages` | messagerie publique et notes internes du CS |
| `evolutions` | fil de suivi : changements d'état et commentaires |
| `relance` | relance groupée du syndic, avec civilité et ancienneté |
| `entretien_periodique` | les visites périodiques de l'exercice, et si elles ont eu lieu |
| `courriels` | composition et envoi des e-mails d'un ticket |
| `commun` | destinataires, configuration, libellés, sérialisation |
| `recherche` | recherche libre : ce que le lecteur peut lire, et rien d'autre |

## Ce qui a été factorisé au passage

La longueur *fabrique* la duplication — trois exemples pris dans ce seul fichier :

- **la liste des destinataires syndic / CS**, écrite trois fois (création,
  relance, évolution), avec trois déduplications d'adresses indépendantes
  → `commun.destinataires_syndic_cs` ;
- **la lecture de `site_nom` / `site_url`**, refaite quatre fois
  → `commun.config_site` et `commun.contexte_site` ;
- **le libellé d'une évolution**, écrit deux fois avec deux résultats différents
  (« Commentaire CS » ici, « Commentaire : … » là) → `commun.libelle_evolution`,
  dont le paramètre `avec_extrait` conserve la nuance qui, elle, était voulue ;
- **la table des périmètres**, qui redoublait celle du fil d'activité en moins
  complet (ni AFUL, ni bâtiment hors table) → `app/utils/perimetres.py`, désormais
  partagé avec `routers/flux`.

L'e-mail `ticket_syndic` était par ailleurs composé à deux endroits : c'est ce
qui avait laissé la clé `fichiers` absente d'un des deux, si bien que les photos
partaient en pièce jointe sans être annoncées. Une seule écriture désormais.

## Ordre de montage — il n'est pas cosmétique

`relance` est monté **avant** `crud` : ses chemins sont littéraux
(`/tickets/relance-syndic`) et FastAPI résout dans l'ordre d'enregistrement. Monté
après, `/{ticket_id}` capterait « relance-syndic » et la route deviendrait
inatteignable — sans erreur, juste une relance qui répond 422.

`crud` est le seul sous-router à déclarer son propre préfixe : ses deux routes de
collection ont un chemin **vide** (`GET /tickets`, `POST /tickets`), et FastAPI
refuse un chemin vide sur un router sans préfixe. Les trois autres déclarent des
chemins nus et reçoivent le préfixe au montage. Les 12 chemins sont identiques au
caractère près à ceux d'avant le découpage, vérifié par comparaison d'inventaire.
"""

from fastapi import APIRouter

from . import (
    apercu,
    crud,
    depuis_annonce,
    entretien_periodique,
    evolutions,
    fusion,
    liees,
    lot,
    messages,
    mise_a_jour,
    recherche,
    relance,
    synthese,
    transferts,
)

#  Les sous-modules à chemins nus reçoivent le préfixe ici. Ce littéral est aussi
#  ce que lit `test_endpoints_orphelins` pour reconstruire les chemins d'un
#  paquet découpé : le garder en clair n'est pas cosmétique non plus.
_a_prefixer = APIRouter(prefix="/tickets", tags=["tickets"])
#  `apercu` est monté avec les littéraux, AVANT `crud` : `/apercu-diffusion` est
#  un chemin fixe, et `/{ticket_id}` le capterait — la route répondrait 422 sans
#  qu'aucune erreur ne le dise. Même raison que `/relance-syndic`.
for _sous_router in (
    apercu.router,
    liees.router,  # `/choix` : littéral, avant `crud` (#1342)
    recherche.router,  # `/recherche` : littéral, avant `crud` — sinon 422
    depuis_annonce.router,
    relance.router,
    entretien_periodique.router,  # `/entretiens-periodiques` : littéral, avant `crud`
    messages.router,
    evolutions.router,
    transferts.router,  # défaire un transfert de courriel (#1482)
    synthese.router,  # la synthèse d'une affaire close (#1643)
    fusion.router,  # les affaires liées à absorber en clôturant (#1704)
    lot.router,
):
    _a_prefixer.include_router(_sous_router)

#  ⚠️ Les chemins littéraux d'abord — voir la docstring : `/relance-syndic` doit
#  être testé avant le motif `/{ticket_id}` que porte `crud`.
router = APIRouter(tags=["tickets"])
router.include_router(_a_prefixer)
router.include_router(crud.router)
#  La CORRECTION (`PATCH /{id}`) vit à part depuis #833 : elle pesait 238 lignes
#  dans `crud`, et sa moitié basse était déjà dans `correction.py`.
router.include_router(mise_a_jour.router)

#  Surface publique conservée pour les importateurs externes.
from .commun import STATUT_LABELS  # noqa: E402  (après le montage, pour la lisibilité)
from .relance import RelanceSyndicRequest  # noqa: E402

__all__ = [
    "router",
    "STATUT_LABELS",
    "RelanceSyndicRequest",
]
